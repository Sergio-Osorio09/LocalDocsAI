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
    ) -> str:
        """Generate a response token by token; calls *on_token* with the
        accumulated text after each chunk so the caller can stream it live."""
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
