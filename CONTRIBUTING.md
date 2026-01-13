# Contributing

Thank you for your interest in contributing to the MongoDB Atlas Cluster Report Generator!

## Development Setup

1. Clone the repository and create a virtual environment:

    ```bash
    git clone https://github.com/orichaud/mongo_reporting.git
    cd mongo_reporting
    python3 -m venv venv
    source venv/bin/activate
    ```

2. Install development dependencies:

    ```bash
    pip install -r requirements-dev.txt
    ```

3. Set up your `.env` file with Atlas API credentials (see README.md).

## Code Style

This project uses:

- **black** for code formatting
- **ruff** for linting

Before committing, ensure your code passes both:

```bash
black get_cluster_report.py tests/
ruff check get_cluster_report.py tests/
```

## Testing

All changes must pass the existing test suite:

```bash
PYTHONPATH=. python3 -m pytest -v
```

When adding new features, include corresponding tests in `tests/test_get_cluster_report.py`.

## Pull Request Guidelines

1. Create a feature branch from `main`
2. Make your changes with clear, descriptive commits
3. Ensure all tests pass and code is formatted
4. Update documentation if needed (README.md, docstrings)
5. Submit a PR with a clear description of changes

## Reporting Issues

When reporting bugs, please include:

- Python version (`python3 --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant error messages
