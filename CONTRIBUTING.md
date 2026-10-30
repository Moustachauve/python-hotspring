# Contributing to `python-hotspring`

Thank you for your interest in contributing to `python-hotspring`! Whether you are reporting a bug, adding support for new spa hardware features, or improving documentation, contributions are welcome.

## Setting Up the Development Environment

This project uses [Poetry](https://python-poetry.org/) for dependency management and requires **Python 3.12+**.

1. Clone the repository and install dependencies:
   ```bash
   poetry install
   ```
2. Install the git pre-commit hooks via [prek](https://github.com/j178/prek):
   ```bash
   poetry run prek install
   ```

## Code Quality, Linting & Testing

Before committing or opening a Pull Request, ensure all checks and tests pass locally:

```bash
# Run all pre-commit hooks (ruff, codespell, yamllint, etc.)
poetry run prek run --all-files

# Run ruff linter and formatter checks
poetry run ruff check
poetry run ruff format --check

# Run static type checking and Pylint
poetry run mypy src tests
poetry run pylint src

# Run unit tests with coverage (90% minimum required)
poetry run pytest
```

If your changes intentionally modify model structures covered by [Syrupy](https://github.com/syrupy-project/syrupy) snapshots, update the `.ambr` snapshot files and review the diff carefully:

```bash
poetry run pytest --snapshot-update
```

## Submitting a Pull Request

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-change main
   ```
2. Write focused commits with a concise imperative subject line and a body explaining **why** the change is needed.
3. Do not amend, squash, or force-push commits after a Pull Request has been opened and reviewed, so reviewers can easily track incremental changes.
4. Open a Pull Request targeting `main` and apply **one** required PR label.

## Pull Request Labels

Every Pull Request **must** have **exactly one** label from the table below. This is enforced in CI by [`.github/workflows/pr-labels.yaml`](.github/workflows/pr-labels.yaml) (`mheap/github-action-required-labels`) and used by [`.github/release-drafter.yml`](.github/release-drafter.yml) to categorize release notes and resolve the next [Semantic Version](https://semver.org/) (`MAJOR.MINOR.PATCH`):

| Label             | Version Bump | Release Category      | Description                                          |
| :---------------- | :----------- | :-------------------- | :--------------------------------------------------- |
| `breaking-change` | **Major**    | 🚨 Breaking changes   | Introduces an incompatible API or data model change  |
| `new-feature`     | **Minor**    | ✨ New features       | Introduces a backwards-compatible new feature        |
| `bugfix`          | **Patch**    | 🐛 Bug fixes          | Fixes a bug                                          |
| `enhancement`     | **Patch**    | 🚀 Enhancements       | Improvements or additions to existing features       |
| `refactor`        | **Patch**    | 🚀 Enhancements       | Code refactoring without changing external behavior  |
| `performance`     | **Patch**    | 🚀 Enhancements       | Performance improvements                             |
| `maintenance`     | **Patch**    | 🧰 Maintenance        | Housekeeping, e.g., test updates or internal cleanup |
| `ci`              | **Patch**    | 🧰 Maintenance        | Changes to CI/CD workflows                           |
| `documentation`   | **Patch**    | 📚 Documentation      | Changes to documentation                             |
| `dependencies`    | **Patch**    | ⬆️ Dependency updates | Updates to dependencies                              |
| `chore`           | **Patch**    | _(Uncategorized)_     | Routine tasks                                        |

When creating a Pull Request with the GitHub CLI, always specify `--label`:

```bash
gh pr create --draft --label bugfix
```

## AI Policy

AI tools are welcome as an assistant, but you must review, understand, and be able to explain every change you submit. Autonomous contributions (unreviewed PRs, issues, or comments generated without human oversight) are not accepted.
