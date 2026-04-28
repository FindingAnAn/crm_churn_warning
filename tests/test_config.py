"""Tests for src/config/ — configuration validation.

Convention: 13-Data_ML §3.3 — validate config at startup.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from config.db_config import PostgresConfig


class TestPostgresConfig:
    """Tests for PostgresConfig dataclass."""

    def test_from_env_with_all_vars(self):
        """from_env() should read all PG_* environment variables."""
        env = {
            "PG_HOST": "testhost",
            "PG_PORT": "5433",
            "PG_DB": "testdb",
            "PG_USER": "testuser",
            "PG_PW": "testpass",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = PostgresConfig.from_env()

        assert cfg.host == "testhost"
        assert cfg.port == 5433
        assert cfg.dbname == "testdb"
        assert cfg.user == "testuser"
        assert cfg.password == "testpass"

    def test_from_env_missing_user_raises(self):
        """from_env() should raise if PG_USER is not set."""
        env = {"PG_HOST": "h", "PG_PORT": "5432", "PG_DB": "d"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises((ValueError, EnvironmentError)):
                PostgresConfig.from_env()

    def test_from_env_missing_password_raises(self):
        """from_env() should raise if PG_PW is not set."""
        env = {
            "PG_HOST": "h",
            "PG_PORT": "5432",
            "PG_DB": "d",
            "PG_USER": "u",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises((ValueError, EnvironmentError)):
                PostgresConfig.from_env()

    def test_validate_invalid_port(self):
        """validate() should reject port outside 1–65535."""
        cfg = PostgresConfig(
            host="h", port=99999, dbname="d", user="u", password="p"
        )
        with pytest.raises(ValueError, match="port"):
            cfg.validate()

    def test_dsn_format(self):
        """dsn() should return a valid PostgreSQL DSN string."""
        cfg = PostgresConfig(
            host="localhost", port=5432, dbname="mydb",
            user="me", password="pw",
        )
        dsn = cfg.dsn()
        assert "host=localhost" in dsn
        assert "port=5432" in dsn
        assert "dbname=mydb" in dsn
        assert "user=me" in dsn
        assert "password=pw" in dsn

    def test_safe_repr_hides_password(self):
        """__repr__ should NOT expose the password."""
        cfg = PostgresConfig(
            host="h", port=5432, dbname="d",
            user="u", password="supersecret",
        )
        r = repr(cfg)
        assert "supersecret" not in r
        assert "***" in r

    def test_to_safe_dict_excludes_password(self):
        """to_safe_dict() should mask the password."""
        cfg = PostgresConfig(
            host="h", port=5432, dbname="d",
            user="u", password="supersecret",
        )
        d = cfg.to_safe_dict()
        assert "supersecret" not in str(d["password"])
        assert d["host"] == "h"

    def test_sqlalchemy_url(self):
        """sqlalchemy_url() should produce the correct connection URL."""
        cfg = PostgresConfig(
            host="myhost", port=5432, dbname="mydb",
            user="myuser", password="mypass",
        )
        url = cfg.sqlalchemy_url()
        assert url == "postgresql+psycopg2://myuser:mypass@myhost:5432/mydb"

    def test_frozen_immutable(self):
        """PostgresConfig should be frozen (immutable)."""
        cfg = PostgresConfig(
            host="h", port=5432, dbname="d", user="u", password="p"
        )
        with pytest.raises(AttributeError):
            cfg.host = "changed"
