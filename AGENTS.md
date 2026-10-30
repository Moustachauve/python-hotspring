# Coding Assistant Instructions: python-hotspring Library

This repository contains `python-hotspring`, a standalone asynchronous Python client library for controlling and monitoring Hot Spring spas equipped with the Connected Spa Kit 2 over its local HTTP API.

## Git Commit & Pull Request Guidelines

- **First line**: Short, specific imperative sentence (e.g. "Fix FreshWaterIQ installed detection and normalize sentinel readings"). No emojis in titles.
- **Commit & PR description**: Focus on the **WHY** (problem, context, and architectural rationale). Do not merely narrate the diff or use boilerplate section headings. Keep it concise, factual, and proportional.
- **Do NOT amend, squash, or rebase commits that have already been pushed to the PR branch after the PR is opened**: Reviewers need to follow the commit history and see what changed since their last review.
- **Pull Request Labels**: Every PR **must** have **exactly one** label from `.github/workflows/pr-labels.yaml` (`breaking-change`, `new-feature`, `bugfix`, `enhancement`, `refactor`, `performance`, `maintenance`, `ci`, `documentation`, `dependencies`, `chore`). Pass `--label <label>` when creating a PR via `gh pr create` (see [CONTRIBUTING.md](CONTRIBUTING.md#pull-request-labels)).

## Development Commands

- Install dependencies: `poetry install`
- Run test suite (with coverage): `poetry run pytest`
- Run a specific test file: `poetry run pytest tests/test_models.py`
- Update Syrupy snapshots: `poetry run pytest --snapshot-update`
- Check linting and formatting: `poetry run ruff check` and `poetry run ruff format --check`
- Run static type checking: `poetry run mypy src tests`
- Run Pylint: `poetry run pylint src`
- Run all pre-commit hooks: `poetry run prek run --all-files`

## Architecture & Boundaries

- **Strict Decoupling from Home Assistant**:
  - This library MUST NEVER import `homeassistant` or depend on Home Assistant Core modules, constants, or types.
  - The library must be 100% installable, testable, and runnable independently in any standard Python 3.12+ environment.
- **Adapter Roles (HNA vs SNA)**:
  - The Connected Spa Kit 2 consists of a Home Network Adapter (**HNA**, inside the home on WiFi/Ethernet) and a Spa Network Adapter (**SNA**, wired to the IQ2020/Eagle control board via RS485 and linked to the HNA over LoRA).
  - All client API calls target the **HNA**. Connecting directly to an SNA raises `HotSpringSNADetectedError` when `validate_device=True`.
- **Immutable State Merging**:
  - Model parsers in `src/hotspring/models.py` use `@dataclass` with `dataclasses.replace(base, **kwargs)` and accept `existing` instances so partial responses (e.g. `POST /spaManager` command echoes or incremental polls) update changed fields without clobbering cached state.
  - Normalize firmware sentinel values (such as `-1` / `-1.0` or pre-UART-sync all-zero registers) to `None` rather than exposing raw sentinel numbers to consumers.

## Testing Standards

- Verify HTTP client behavior, payload parsing, partial state merging, and error handling.
- We use **Syrupy** for snapshot testing (`tests/__snapshots__/*.ambr`). Leverage `assert result == snapshot` or dataclass equality (`assert result == ExpectedModel(...)`) instead of long chains of repetitive field-by-field assertions.
- When writing tests or implementation code, ensure all parameters have precise type annotations. **The use of `Any` is strictly forbidden in new code.**
- **Single purpose tests**: Each test function must verify only one specific behavior or outcome. Avoid chaining sequential behaviors in a single test; split them into focused tests or use parametrization.
- Prefer `@pytest.mark.usefixtures` over unused fixture arguments.
- Avoid branching (`if`/`else`) in tests; use `@pytest.mark.parametrize` with `pytest.param(..., id="...")` for table-driven testing.
- Tests must execute cleanly with `poetry run pytest` without requiring network access (mock HTTP responses with `aresponses`).

## Good practices

- Built with `asyncio`, `aiohttp`, `yarl`, and `backoff`.
- Non-blocking I/O: never perform synchronous disk or network operations on the event loop.
- Keep `try` clauses as small as possible; avoid catching exceptions from functions not expected to raise them.
- When a dict key is already checked or guaranteed, avoid redundant `.get(key, default)` fallbacks; use `if (val := data.get("key")) is not None:` or direct `data["key"]` access.
- Keep comments concise. Explain non-obvious constraints or firmware quirks (the WHY), never what the code does. Do not add section or divider comments (`# --- XYZ ---`).
- Semantic Versioning (`MAJOR.MINOR.PATCH`): Releases are drafted automatically by Release Drafter based on PR labels.

## AI policy

Autonomous contributions are not accepted. Every change must be reviewed and understood by a human contributor before submission. Never open pull requests, create release tags, or post comments autonomously without explicit contributor instruction.
