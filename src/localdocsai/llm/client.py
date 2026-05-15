from __future__ import annotations

from pathlib import Path
from typing import Any

from localdocsai.utils.paths import get_models_dir

_DEFAULT_MODEL = "qwen2.5-3b-instruct-q4_k_m.gguf"


class LLMClient:
    """Lazy-loaded llama-cpp-python wrapper for local GGUF models.

    The model is only loaded on the first call to generate(), so startup is
    fast when the LLM is not needed (e.g., running `index` or `search`).
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_ctx: int = 8192,
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
            n_gpu_layers=self._n_gpu_layers,
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
