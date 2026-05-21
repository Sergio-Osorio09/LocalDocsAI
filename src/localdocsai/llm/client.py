from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from localdocsai.utils.paths import get_models_dir

_log = logging.getLogger(__name__)


def _safe_gpu_layers(requested: int) -> int:
    """Return *requested* if a CUDA-capable GPU is available, else 0.

    llama-cpp-python will silently crash or log cryptic errors when
    n_gpu_layers > 0 but the CUDA runtime is missing or incompatible.
    """
    if requested <= 0:
        return 0
    try:
        import ctypes

        ctypes.cdll.LoadLibrary(
            "nvcuda.dll" if __import__("sys").platform == "win32" else "libcuda.so.1"
        )
        return requested
    except OSError:
        _log.warning(
            "CUDA runtime not found — disabling GPU layers (requested %d). "
            "Install the CUDA toolkit or use n_gpu_layers=0.",
            requested,
        )
        return 0


_DEFAULT_MODEL = "qwen2.5-3b-instruct-q4_k_m.gguf"


class LLMClient:
    """Lazy-loaded llama-cpp-python wrapper for local GGUF models.

    The model is only loaded on the first call to generate(), so startup is
    fast when the LLM is not needed (e.g., running `index` or `search`).
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_ctx: int = 16384,
        n_gpu_layers: int = 0,
    ) -> None:
        self._model_path = model_path or (get_models_dir() / _DEFAULT_MODEL)
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._llm: Any = None

    def _load(self) -> Any:
        from llama_cpp import Llama

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {self._model_path}\n"
                "Run 'python scripts/download_models.py' to download it."
            )
        return Llama(
            model_path=str(self._model_path),
            n_ctx=self._n_ctx,
            n_gpu_layers=_safe_gpu_layers(self._n_gpu_layers),
            verbose=False,
        )

    @property
    def _model(self) -> Any:
        if self._llm is None:
            self._llm = self._load()
        return self._llm

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """Generate a response for *user_message* given *system_prompt*."""
        response: Any = self._model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content: str = response["choices"][0]["message"]["content"]
        return content

    def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        on_token: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        """Generate a response token by token; calls *on_token* with the
        accumulated text after each chunk so the caller can stream it live.

        When *should_cancel* is provided, it is consulted between batches
        of prompt processing AND between every sampled token, so the user
        can interrupt the request even before the first token has been
        emitted. The high-level create_chat_completion path cannot do
        this because it makes one C++ call that blocks until prompt
        processing is complete (up to ~60s on CPU for a 5k-token prompt).

        On cancellation the partial text accumulated so far is returned
        and *on_token* is not called again; the caller is responsible
        for treating the result as cancelled (typically the caller raises
        its own sentinel exception in *on_token* or checks afterwards).
        """
        # Fast path when the caller does not need interruption — keep the
        # original high-level API which handles chat templates uniformly
        # across model families.
        if should_cancel is None:
            buffer: list[str] = []
            for chunk in self._model.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            ):
                delta: str = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    buffer.append(delta)
                    if on_token:
                        on_token("".join(buffer))
            return "".join(buffer)

        # Cancellable path — drive llama-cpp at the eval/sample level so
        # we can interrupt during prompt processing. The Qwen 2.5 family
        # uses the ChatML template; if a different model is ever wired
        # in this template will need to follow it.
        return self._generate_stream_cancellable(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
            on_token=on_token,
            should_cancel=should_cancel,
        )

    def _generate_stream_cancellable(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
        on_token: Callable[[str], None] | None,
        should_cancel: Callable[[], bool],
    ) -> str:
        llm = self._model

        # Qwen 2.5 ChatML template — must match the model exactly or
        # output quality drops noticeably. The system + user messages go
        # in their own roles, and the assistant turn is opened so the
        # model continues from there.
        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{user_message}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        try:
            llm.reset()
        except Exception:
            # Some older versions of llama-cpp-python don't expose reset;
            # the eval calls below still work but the KV cache may carry
            # over from a previous request, which is harmless.
            _log.debug("Llama.reset() unavailable — continuing without KV reset")

        tokens = llm.tokenize(prompt.encode("utf-8"), add_bos=True, special=True)

        # Eval the prompt in small batches so cancellation has a fast
        # checkpoint. 64 tokens is a good balance: small enough that
        # cancel is noticeable, large enough that batching still helps.
        n_batch = 64
        i = 0
        while i < len(tokens):
            if should_cancel():
                _log.info("Cancelled during prompt processing (%d/%d tokens)", i, len(tokens))
                return ""
            chunk = tokens[i : i + n_batch]
            llm.eval(chunk)
            i += len(chunk)

        # Sample loop. Match the sampling parameters that
        # create_chat_completion would use by default so output quality
        # is comparable.
        generated: list[int] = []
        text_buffer = ""
        eos = llm.token_eos()
        stop_marker = "<|im_end|>"

        for _ in range(max_tokens):
            if should_cancel():
                _log.info("Cancelled after %d generated tokens", len(generated))
                break
            try:
                tok = llm.sample(
                    temp=temperature,
                    top_p=0.95,
                    top_k=40,
                    repeat_penalty=1.1,
                )
            except TypeError:
                # Older signatures only accept temp
                tok = llm.sample(temp=temperature)
            if tok == eos:
                break
            generated.append(tok)
            try:
                text_buffer = llm.detokenize(generated).decode("utf-8", errors="replace")
            except Exception:
                pass
            # ChatML stop sequence — strip if the model emits the marker.
            if stop_marker in text_buffer:
                text_buffer = text_buffer.split(stop_marker)[0]
                if on_token:
                    on_token(text_buffer)
                break
            if on_token:
                on_token(text_buffer)
            llm.eval([tok])

        return text_buffer
