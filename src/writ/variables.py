"""Variable substitution and secret management."""

import os
import re
from pathlib import Path

from writ.exceptions import VariableError

VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class SecretStore:
    """Manages secrets with masking support."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def add(self, key: str, value: str) -> None:
        """Add a secret."""
        self._secrets[key] = value

    def get(self, key: str) -> str | None:
        """Get a secret value by key."""
        return self._secrets.get(key)

    def all_values(self) -> list[str]:
        """Return all secret values."""
        return list(self._secrets.values())

    def as_env_dict(self) -> dict[str, str]:
        """Return secrets as a dict suitable for env injection."""
        return dict(self._secrets)

    def mask(self, text: str) -> str:
        """Replace all secret values in text with '***'."""
        result = text
        for value in sorted(self._secrets.values(), key=len, reverse=True):
            if value:
                result = result.replace(value, "***")
        return result

    def load_dotenv(self, path: Path) -> None:
        """Load secrets from a .env file."""
        if not path.exists():
            return
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                self._secrets[key.strip()] = value.strip()


class VariableResolver:
    """Resolves ${var} references using layered variable sources."""

    def __init__(
        self,
        config_vars: dict[str, str],
        pipeline_vars: dict[str, str] | None = None,
        secrets: SecretStore | None = None,
    ) -> None:
        self._config_vars = config_vars
        self._pipeline_vars = pipeline_vars or {}
        self._secrets = secrets or SecretStore()

    def resolve(self, text: str) -> str:
        """Resolve all ${var} references in text."""

        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            # Resolution order: pipeline > config > secrets > env
            if var_name in self._pipeline_vars:
                return self._pipeline_vars[var_name]
            if var_name in self._config_vars:
                return self._config_vars[var_name]
            secret = self._secrets.get(var_name)
            if secret is not None:
                return secret
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            raise VariableError(f"Unresolved variable: {var_name}")

        return VAR_PATTERN.sub(_replace, text)
