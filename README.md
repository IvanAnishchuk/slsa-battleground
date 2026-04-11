# SLSA Battleground

Minimal package for testing SLSA provenance in GitHub Actions

## Installation

```bash
uv tool install slsa-battleground
# or
pip install slsa-battleground
```

## Usage

```bash
slsa-battleground --help
```

## Development

```bash
git clone https://github.com/IvanAnishchuk/slsa-battleground.git
cd slsa-battleground
uv sync

# Run tests
uv run pytest

# Run lints
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run ty check

# Run full pre-commit suite
uv run pre-commit run --all-files

# Run supply-chain audit
uv run python scripts/audit.py
```

## License

CC0-1.0
