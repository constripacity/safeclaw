# Contributing to SafeClaw

Welcome! SafeClaw is a portfolio project, and contributions are welcome.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Ensure `ruff check .` and `pytest` pass
5. Open a Pull Request

## Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/safeclaw.git
cd safeclaw
pip install -e ".[dev]"

# Lint
ruff check .

# Test
pytest
```

## Writing Plugins

See [docs/plugin-guide.md](docs/plugin-guide.md) for the full guide. Key rules:

- Plugins must not invoke shell commands unless `allow_shell: true` in policy
- Plugins must not make network calls unless `allow_network: true` in policy
- Always respect `max_file_mb` and `max_files` limits
- Report all touched files

## Code Standards

- Type hints on all functions
- Google-style docstrings on all public functions
- Ruff-clean (line length 100)
- All tests passing (`pytest`)
- Use `pathlib.Path` for all file operations

## Security Issues

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## Commit Messages

Use conventional commits:

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation changes
- `test:` — adding or updating tests
- `chore:` — maintenance tasks
