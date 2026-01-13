# Project Coding Guidelines

## General

- **README.md:** Always create and maintain a `README.md` file that includes:
  - A clear description of the project's purpose.
  - Detailed, step-by-step instructions for setting up the development environment and running the project.
  - Instructions for running tests.

## Python

- **Language Version:** All Python code must be compatible with Python 3.
- **Virtual Environment:**
  - Always use a virtual environment named `venv`.
  - The `README.md` must include instructions for creating, activating, and installing dependencies within the virtual environment.
- **Code Style:**
  - Format all Python code with the `black` code formatter.
  - Lint all Python code with the `ruff` linter.
- **Dependencies:**
  - Use `pip` for package management.
  - List all dependencies in a `requirements.txt` file.
  - Prioritize lightweight, well-maintained libraries.
- **Execution:**
  - When providing commands for running Python scripts, always use `python3`.

## Java

- **Language Version:** All Java code must be written in Java 21.
- **Code Style:** Use standard Java pretty printing.
- **Documentation:**
  - All public classes, methods, and complex code blocks must have Javadoc comments.
  - Javadoc should clearly explain the purpose, parameters, and return values of the documented code.
- **Testing:**
  - All new components and functions must have corresponding JUnit tests.
- **Dependencies:**
  - Prioritize lightweight, well-maintained libraries.
