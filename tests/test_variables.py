"""Tests for variable substitution and secret management."""

from pathlib import Path
from unittest.mock import patch

import pytest

from writ.exceptions import VariableError
from writ.variables import SecretStore, VariableResolver


class TestVariableResolver:
    def test_substitutes_config_variables(self) -> None:
        resolver = VariableResolver(config_vars={"project": "myapp"})
        result = resolver.resolve("echo ${project}")
        assert result == "echo myapp"

    def test_substitutes_multiple_variables(self) -> None:
        resolver = VariableResolver(config_vars={"name": "app", "env": "prod"})
        result = resolver.resolve("deploy ${name} to ${env}")
        assert result == "deploy app to prod"

    def test_pipeline_vars_override_config_vars(self) -> None:
        resolver = VariableResolver(
            config_vars={"env": "staging"},
            pipeline_vars={"env": "production"},
        )
        result = resolver.resolve("deploy to ${env}")
        assert result == "deploy to production"

    def test_falls_back_to_env_vars(self) -> None:
        resolver = VariableResolver(config_vars={})
        with patch.dict("os.environ", {"MY_VAR": "from_env"}):
            result = resolver.resolve("value is ${MY_VAR}")
        assert result == "value is from_env"

    def test_secrets_resolve_before_env(self) -> None:
        secrets = SecretStore()
        secrets.add("DB_PASS", "s3cret")
        resolver = VariableResolver(config_vars={}, secrets=secrets)
        result = resolver.resolve("pass=${DB_PASS}")
        assert result == "pass=s3cret"

    def test_raises_on_unresolved_variable(self) -> None:
        resolver = VariableResolver(config_vars={})
        with pytest.raises(VariableError, match="MISSING_VAR"):
            resolver.resolve("${MISSING_VAR}")

    def test_no_substitution_when_no_variables(self) -> None:
        resolver = VariableResolver(config_vars={})
        result = resolver.resolve("plain text")
        assert result == "plain text"

    def test_literal_dollar_brace_escaped(self) -> None:
        resolver = VariableResolver(config_vars={})
        result = resolver.resolve("cost is $100")
        assert result == "cost is $100"


class TestSecretStore:
    def test_add_and_retrieve_secret(self) -> None:
        store = SecretStore()
        store.add("API_KEY", "abc123")
        assert store.get("API_KEY") == "abc123"

    def test_get_returns_none_for_missing(self) -> None:
        store = SecretStore()
        assert store.get("NOPE") is None

    def test_mask_replaces_secret_values(self) -> None:
        store = SecretStore()
        store.add("TOKEN", "supersecret")
        result = store.mask("the token is supersecret here")
        assert result == "the token is *** here"

    def test_mask_handles_multiple_secrets(self) -> None:
        store = SecretStore()
        store.add("A", "alpha")
        store.add("B", "beta")
        result = store.mask("alpha and beta")
        assert result == "*** and ***"

    def test_load_from_dotenv(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("SECRET_KEY=mykey123\nDB_URL=postgres://localhost\n")
        store = SecretStore()
        store.load_dotenv(env_file)
        assert store.get("SECRET_KEY") == "mykey123"
        assert store.get("DB_URL") == "postgres://localhost"

    def test_load_dotenv_missing_file_is_noop(self, tmp_path: Path) -> None:
        store = SecretStore()
        store.load_dotenv(tmp_path / "nonexistent.env")
        assert store.all_values() == []

    def test_all_values_returns_secret_values(self) -> None:
        store = SecretStore()
        store.add("A", "val1")
        store.add("B", "val2")
        assert sorted(store.all_values()) == ["val1", "val2"]

    def test_as_env_dict(self) -> None:
        store = SecretStore()
        store.add("X", "1")
        store.add("Y", "2")
        assert store.as_env_dict() == {"X": "1", "Y": "2"}
