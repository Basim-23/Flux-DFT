# Contributing to FluxDFT

Thank you for your interest in contributing to FluxDFT! This document provides guidelines and best practices for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

---

## Code of Conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

---

## How Can I Contribute?

### 🐛 Reporting Bugs

If you find a bug, please [open an issue](https://github.com/Basim-23/Flux-DFT/issues/new) with:

- A clear, descriptive title.
- Steps to reproduce the behavior.
- Expected vs. actual behavior.
- Your environment details (OS, Python version, Qt version).
- Screenshots or error logs, if applicable.

### 💡 Feature Requests

We welcome ideas! Please [open a feature request](https://github.com/Basim-23/Flux-DFT/issues/new) with:

- A clear description of the proposed feature.
- The problem it solves or the use case it enables.
- Any relevant references (papers, related tools, mock-ups).

### 🔧 Code Contributions

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature-name`).
3. Commit your changes with clear, descriptive messages.
4. Push to your fork and submit a pull request.

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git

### Setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/Flux-DFT.git
cd Flux-DFT

# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# .\venv\Scripts\Activate.ps1   # Windows

# Install all dependencies (including dev tools)
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run the full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=fluxdft
```

### Code Formatting

```bash
# Format code with Black
black src/ tests/ --line-length 100

# Lint with Ruff
ruff check src/ tests/
```

---

## Code Style

- **Formatter:** [Black](https://github.com/psf/black) with a line length of 100.
- **Linter:** [Ruff](https://github.com/astral-sh/ruff) with a line length of 100.
- **Type Hints:** Use type annotations for all function signatures.
- **Docstrings:** Use triple-quoted docstrings for all public classes and functions.
- **Naming Conventions:**
  - `snake_case` for functions, methods, and variables.
  - `PascalCase` for class names.
  - `UPPER_SNAKE_CASE` for constants.

---

## Pull Request Process

1. Ensure your code passes all tests and linting checks.
2. Update documentation if your changes affect user-facing features.
3. Add or update tests for any new functionality.
4. Write a clear PR description explaining:
   - **What** the change does.
   - **Why** it is needed.
   - **How** it was implemented.
5. Link any related issues using `Closes #<issue-number>`.

### PR Checklist

- [ ] Code follows the project style guidelines.
- [ ] Tests pass locally (`pytest tests/ -v`).
- [ ] Linting passes (`ruff check src/`).
- [ ] Documentation has been updated (if applicable).
- [ ] Commit messages are clear and descriptive.

---

## 🏷️ Commit Message Convention

Use clear, imperative-mood commit messages:

```
feat: add phonon dispersion workflow
fix: resolve k-path generation for hexagonal cells
docs: update installation instructions for Linux
refactor: simplify output parser logic
test: add unit tests for input builder
```

**Prefixes:**
| Prefix | Purpose |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring (no behavior change) |
| `test` | Adding or updating tests |
| `style` | Formatting, whitespace (no logic change) |
| `chore` | Build, CI, or tooling changes |

---

## 📬 Questions?

If you have questions about contributing, feel free to [open a discussion](https://github.com/Basim-23/Flux-DFT/issues) or reach out via the repository.

Thank you for helping make FluxDFT better! 🚀
