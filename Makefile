.PHONY: help install install-dev install-poetry poetry-install format format-check lint mypy bandit test coverage all clean dev pre-commit-install pre-commit-run pre-commit-update

help:
	@echo "writ - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install           Install project dependencies"
	@echo "  make install-dev       Install development dependencies (pip)"
	@echo "  make install-poetry    Install poetry package manager"
	@echo "  make poetry-install    Install dependencies with poetry"
	@echo "  make dev               Setup complete development environment"
	@echo "  make pre-commit-install  Install pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format            Format code with black and isort"
	@echo "  make format-check      Check code formatting without changes"
	@echo "  make lint              Run linting checks (ruff, pylint)"
	@echo "  make mypy              Run type checking"
	@echo "  make bandit            Run security checks"
	@echo "  make all               Run all quality checks"
	@echo "  make pre-commit-run    Run all pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run tests with pytest"
	@echo "  make coverage          Run tests with coverage report"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             Remove temporary files and build artifacts"
	@echo ""
	@echo "Pre-commit:"
	@echo "  make pre-commit-update Update pre-commit hooks"
	@echo ""
	@echo "Tox (recommended):"
	@echo "  tox -e format          Format code"
	@echo "  tox -e lint            Run linting"
	@echo "  tox -e mypy            Type checking"
	@echo "  tox -e all             All checks"
	@echo "  tox                    Run all environments"
	@echo ""
	@echo "Poetry Commands:"
	@echo "  poetry install         Install dependencies"
	@echo "  poetry add pkg         Add a package"
	@echo "  poetry update          Update dependencies"
	@echo "  poetry shell           Activate virtual environment"

install:
	pip3 install -e .

install-dev:
	pip3 install -r requirements-dev.txt

install-poetry:
	@command -v poetry >/dev/null 2>&1 || { \
		echo "Installing poetry..."; \
		curl -sSL https://install.python-poetry.org | python3 -; \
	}
	@echo "Poetry is installed!"
	@poetry --version

poetry-install: install-poetry
	poetry install

dev: install-poetry poetry-install pre-commit-install
	@echo "Development environment ready!"
	@echo "Run 'make help' to see available commands"

pre-commit-install:
	@command -v pre-commit >/dev/null 2>&1 || poetry install
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "Pre-commit hooks installed!"

pre-commit-run:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

format:
	tox -e format

format-check:
	tox -e format-check

lint:
	tox -e lint

mypy:
	tox -e mypy

bandit:
	tox -e bandit

test:
	tox -e py3

coverage:
	tox -e coverage

all:
	tox -e all

clean:
	tox -e clean
	@echo "Cleanup complete!"
