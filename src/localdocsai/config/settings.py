from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from localdocsai.utils.paths import get_app_root

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "LocalDocsAI"
    language: Literal["es", "en"] = "es"
    theme: Literal["dark", "light", "custom"] = "dark"


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    llm: str = "qwen2.5-14b-instruct-q4_k_m"
    embeddings: str = "BAAI/bge-m3"
    context_window: int = 8192
    max_tokens: int = 1024
    n_gpu_layers: int = 0

    @field_validator("context_window", "max_tokens")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v

    @field_validator("n_gpu_layers")
    @classmethod
    def must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class RetrievalSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    top_k: int = 10
    rerank: bool = False
    min_similarity: float = 0.5

    @field_validator("top_k")
    @classmethod
    def top_k_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("top_k must be a positive integer")
        return v

    @field_validator("min_similarity")
    @classmethod
    def similarity_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("min_similarity must be between 0.0 and 1.0")
        return v


class UISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_color: str = "#1a73e8"
    accent_color: str = "#fbbc04"
    logo_path: str = "resources/logo.png"

    @field_validator("primary_color", "accent_color")
    @classmethod
    def valid_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"invalid hex color: {v!r} (expected #RRGGBB)")
        return v


class ReportsSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_format: Literal["docx", "pdf"] = "docx"
    template: str = "resources/report_templates/default.docx"
    font: str = "Arial"


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = Path(__file__).parent / "default_config.yaml"


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    ui: UISettings = Field(default_factory=UISettings)
    reports: ReportsSettings = Field(default_factory=ReportsSettings)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def defaults(cls) -> Settings:
        """Return settings loaded from the bundled default_config.yaml."""
        return cls.load(_DEFAULT_CONFIG)

    @classmethod
    def load(cls, path: Path) -> Settings:
        """Load settings from *path* (YAML). Missing keys use model defaults."""
        with open(path, encoding="utf-8") as fh:
            data: Any = yaml.safe_load(fh) or {}
        return cls.model_validate(data)

    @classmethod
    def load_profile(cls, name: str) -> Settings:
        """Load a named profile from *<app_root>/profiles/<name>.yaml*.

        The profile is merged on top of the bundled defaults: keys present in
        the profile override the defaults, absent keys keep their default value.
        """
        profile_path = get_app_root() / "profiles" / f"{name}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        # Start from bundled defaults, then apply profile overrides
        base: dict[str, Any] = {}
        if _DEFAULT_CONFIG.exists():
            with open(_DEFAULT_CONFIG, encoding="utf-8") as fh:
                base = yaml.safe_load(fh) or {}

        with open(profile_path, encoding="utf-8") as fh:
            overrides: dict[str, Any] = yaml.safe_load(fh) or {}

        merged = _deep_merge(base, overrides)
        return cls.model_validate(merged)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
