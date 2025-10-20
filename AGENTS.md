# Repository Guidelines
Always review in Japanese.

## Project Structure & Module Organization
- `downloader.py`: Main CLI to download models from Civitai.
- `config_manager.py`: Loads and validates `config.json` (API key, paths, history).
- `url_parser.py`, `model_type_classifier.py`: URL parsing and type inference.
- `download_history.py`: CSV history I/O and duplicate handling.
- `model_metadata_scanner.py`, `regenerate_metadata.py`: Scan existing files and extract metadata.
- `docs/`: Additional technical notes and references. Assets download to `downloads/` and logs in `logs/`.

## Build, Test, and Development Commands
- Install deps: `pip install -r requirements.txt`
- Run downloader: `python downloader.py -u "<civitai_url>" [-t lora|checkpoint|embedding]`
- Scan metadata (single/batch): `python model_metadata_scanner.py`, `python regenerate_metadata.py`
- Integration run (updates history): `python integration_test.py`
- Quick checks: `python test_metadata_extraction.py`, `python test_url_fix.py`, `python test_lora_detection.py`
Notes: Python 3.10+ recommended. Some tests call the Civitai API and require a valid `config.json`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4‑space indentation; keep functions focused and small.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Use type hints and concise docstrings (triple quotes) for public methods.
- Async: prefer non‑blocking I/O (`aiohttp`, streams); avoid long blocking work inside `async` functions.
- CLI entry points should live under `if __name__ == "__main__":`.

## Testing Guidelines
- Tests are executable scripts under the repo root named `test_*.py` plus `integration_test.py`.
- Run with: `python test_metadata_extraction.py` (requires a real model file path and API key).
- Add new tests as `test_<feature>.py` and keep them self‑contained. Print key assertions and sample outputs.
- If a test writes files, target the existing `downloads/` and CSV under the configured paths.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (<=72 chars). Example: `downloader: improve resume progress output`.
- PRs: include a clear description, linked issues, reproduction steps, and before/after logs or screenshots when applicable.
- Update `README.md` and `docs/` for user‑visible changes (CLI flags, config keys, CSV schema).
- Do not include secrets or personal `config.json` changes.

## Security & Configuration Tips
- Never commit real API keys. Create `config.json` from `config.json.example` locally and keep it untracked.
- Rotate keys if leaked; redact URLs/headers in logs before sharing.
- Respect Civitai API rate limits; handle 401/403/429 gracefully and keep retry logic conservative.
