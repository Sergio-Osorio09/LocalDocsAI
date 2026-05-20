"""Tests for Settings (pydantic + YAML) — no ML deps required."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from localdocsai.config.settings import (
    AppSettings,
    ModelSettings,
    ReportsSettings,
    RetrievalSettings,
    Settings,
    UISettings,
    _deep_merge,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: object) -> Path:
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AppSettings
# ---------------------------------------------------------------------------


class TestAppSettings:
    def test_defaults(self) -> None:
        s = AppSettings()
        assert s.name == "LocalDocsAI"
        assert s.language == "es"
        assert s.theme == "dark"

    def test_valid_language(self) -> None:
        s = AppSettings(language="en")
        assert s.language == "en"

    def test_invalid_language(self) -> None:
        with pytest.raises(ValidationError):
            AppSettings(language="fr")  # type: ignore[arg-type]

    def test_valid_theme(self) -> None:
        for theme in ("dark", "light", "custom"):
            assert AppSettings(theme=theme).theme == theme  # type: ignore[arg-type]

    def test_invalid_theme(self) -> None:
        with pytest.raises(ValidationError):
            AppSettings(theme="blue")  # type: ignore[arg-type]

    def test_extra_keys_ignored(self) -> None:
        s = AppSettings.model_validate({"name": "MyApp", "unknown_key": "ignored"})
        assert s.name == "MyApp"


# ---------------------------------------------------------------------------
# ModelSettings
# ---------------------------------------------------------------------------


class TestModelSettings:
    def test_defaults(self) -> None:
        s = ModelSettings()
        assert s.llm == "qwen2.5-14b-instruct-q4_k_m"
        assert s.context_window == 16384
        assert s.max_tokens == 512
        assert s.n_gpu_layers == 0

    def test_context_window_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ModelSettings(context_window=0)

    def test_max_tokens_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ModelSettings(max_tokens=-1)

    def test_n_gpu_layers_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            ModelSettings(n_gpu_layers=-1)

    def test_n_gpu_layers_zero_allowed(self) -> None:
        assert ModelSettings(n_gpu_layers=0).n_gpu_layers == 0


# ---------------------------------------------------------------------------
# RetrievalSettings
# ---------------------------------------------------------------------------


class TestRetrievalSettings:
    def test_defaults(self) -> None:
        s = RetrievalSettings()
        assert s.top_k == 6
        assert s.rerank is False
        assert s.min_similarity == 0.5

    def test_top_k_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalSettings(top_k=0)

    def test_min_similarity_bounds(self) -> None:
        assert RetrievalSettings(min_similarity=0.0).min_similarity == 0.0
        assert RetrievalSettings(min_similarity=1.0).min_similarity == 1.0

    def test_min_similarity_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalSettings(min_similarity=1.1)
        with pytest.raises(ValidationError):
            RetrievalSettings(min_similarity=-0.1)


# ---------------------------------------------------------------------------
# UISettings
# ---------------------------------------------------------------------------


class TestUISettings:
    def test_defaults(self) -> None:
        s = UISettings()
        assert s.primary_color == "#1a73e8"
        assert s.accent_color == "#fbbc04"

    def test_valid_hex_color(self) -> None:
        s = UISettings(primary_color="#ff0000")
        assert s.primary_color == "#ff0000"

    def test_invalid_hex_color_no_hash(self) -> None:
        with pytest.raises(ValidationError):
            UISettings(primary_color="ff0000")

    def test_invalid_hex_color_wrong_length(self) -> None:
        with pytest.raises(ValidationError):
            UISettings(primary_color="#fff")

    def test_invalid_hex_color_non_hex_chars(self) -> None:
        with pytest.raises(ValidationError):
            UISettings(primary_color="#gggggg")


# ---------------------------------------------------------------------------
# ReportsSettings
# ---------------------------------------------------------------------------


class TestReportsSettings:
    def test_defaults(self) -> None:
        s = ReportsSettings()
        assert s.default_format == "docx"
        assert s.font == "Arial"

    def test_valid_format_pdf(self) -> None:
        assert ReportsSettings(default_format="pdf").default_format == "pdf"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValidationError):
            ReportsSettings(default_format="txt")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Settings (root)
# ---------------------------------------------------------------------------


class TestSettings:
    def test_defaults_creates_sub_models(self) -> None:
        s = Settings()
        assert isinstance(s.app, AppSettings)
        assert isinstance(s.model, ModelSettings)
        assert isinstance(s.retrieval, RetrievalSettings)
        assert isinstance(s.ui, UISettings)
        assert isinstance(s.reports, ReportsSettings)

    def test_defaults_loads_yaml(self) -> None:
        s = Settings.defaults()
        assert s.app.name == "LocalDocsAI"
        assert s.model.context_window == 16384

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg = _write_yaml(
            tmp_path / "cfg.yaml",
            {"app": {"name": "MiApp"}, "retrieval": {"top_k": 3}},
        )
        s = Settings.load(cfg)
        assert s.app.name == "MiApp"
        assert s.retrieval.top_k == 3
        assert s.model.max_tokens == 512  # default preserved

    def test_load_empty_file_uses_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("", encoding="utf-8")
        s = Settings.load(cfg)
        assert s.app.name == "LocalDocsAI"

    def test_load_invalid_value_raises(self, tmp_path: Path) -> None:
        cfg = _write_yaml(tmp_path / "bad.yaml", {"retrieval": {"top_k": -1}})
        with pytest.raises(ValidationError):
            Settings.load(cfg)

    def test_load_profile(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import localdocsai.config.settings as settings_mod

        monkeypatch.setattr(settings_mod, "get_app_root", lambda: tmp_path)
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _write_yaml(profiles_dir / "osinergmin.yaml", {"app": {"name": "Osinergmin RAG"}})

        s = Settings.load_profile("osinergmin")
        assert s.app.name == "Osinergmin RAG"
        assert s.model.max_tokens == 512  # default still present

    def test_load_profile_not_found_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import localdocsai.config.settings as settings_mod

        monkeypatch.setattr(settings_mod, "get_app_root", lambda: tmp_path)
        with pytest.raises(FileNotFoundError):
            Settings.load_profile("nonexistent")


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_merges_flat(self) -> None:
        result = _deep_merge({"a": 1, "b": 2}, {"b": 99, "c": 3})
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_merges_nested(self) -> None:
        base = {"app": {"name": "Base", "theme": "dark"}}
        override = {"app": {"name": "Override"}}
        result = _deep_merge(base, override)
        assert result["app"]["name"] == "Override"
        assert result["app"]["theme"] == "dark"

    def test_does_not_mutate_base(self) -> None:
        base = {"a": {"x": 1}}
        _deep_merge(base, {"a": {"x": 2}})
        assert base["a"]["x"] == 1

    def test_override_replaces_non_dict_with_dict(self) -> None:
        result = _deep_merge({"a": 1}, {"a": {"nested": True}})
        assert result["a"] == {"nested": True}
