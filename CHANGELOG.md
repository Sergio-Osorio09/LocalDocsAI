# Changelog

All notable changes to LocalDocsAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and repository setup (Phase 0)
- `pyproject.toml` with uv, ruff, black, mypy, pytest configuration
- `.gitignore` with strict exclusion of `samples/` (client documents)
- `.gitattributes` with `eol=lf` for Linux/Windows compatibility
- `CLAUDE.md` with project conventions for Claude Code
- Five custom skills in `.claude/skills/`: `rag-architecture`, `citation-format`,
  `chunking-strategy`, `cross-platform-paths`, `windows-packaging`
- GitHub Actions CI workflow (`tests.yml`)
- MIT License
- README in English and Spanish
