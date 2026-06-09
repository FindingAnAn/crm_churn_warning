"""Database configuration.

Provides strongly-typed PostgreSQL connection configuration.
Environment variables are read only at load time through from_env().
No direct os.getenv() calls should appear in feature code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL connection configuration.

    Attributes:
        host: Database server hostname or IP.
        port: Database server port.
        dbname: Target database name.
        user: Database username for authentication.
        password: Database password (SECRET).
    """

    host: str
    port: int
    dbname: str
    user: str
    password: str

    # ── Factory ────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> PostgresConfig:
        """Load config from environment variables.

        Required environment variables (prefix PG_):
            PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD

        Safe defaults are provided only for host/port (non-sensitive).
        User and password MUST be set via environment for security.

        Returns:
            PostgresConfig instance with values from environment.

        Raises:
            OSError: If required secrets (PG_USER, PG_PASSWORD) are missing.
        """
        user = os.getenv("PG_USER")
        password = os.getenv("PG_PASSWORD")

        if not user or not password:
            raise OSError(
                "Missing required environment variables: PG_USER and PG_PASSWORD. "
                "Set them in .env or export them before running. "
                "See .env.example for reference."
            )

        return cls(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            dbname=os.getenv("PG_DB", "churn"),
            user=user,
            password=password,
        )

    # ── Validation ─────────────────────────────────────────
    def validate(self) -> None:
        """Validate config correctness without side-effects.

        Checks:
        - All fields are non-empty
        - Port is in valid range (1–65535)

        Does NOT:
        - Connect to database
        - Check if database/user exists
        - Modify any system state

        Raises:
            ValueError: If any field fails validation.
        """
        if not self.host:
            raise ValueError("PostgresConfig.host must not be empty.")
        if not (1 <= self.port <= 65535):
            raise ValueError(
                f"PostgresConfig.port must be 1–65535, got {self.port}."
            )
        if not self.dbname:
            raise ValueError("PostgresConfig.dbname must not be empty.")
        if not self.user:
            raise ValueError("PostgresConfig.user must not be empty.")
        if not self.password:
            raise ValueError("PostgresConfig.password must not be empty.")

    # ── Derived values ─────────────────────────────────────
    def dsn(self) -> str:
        """libpq-style connection string for psycopg2.connect().

        Format: host=... port=... dbname=... user=... password=...

        Returns:
            DSN string suitable for psycopg2.
        """
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )

    def sqlalchemy_url(self) -> str:
        """SQLAlchemy connection URL.

        Format: postgresql+psycopg2://user:password@host:port/dbname

        Returns:
            Connection URL suitable for sqlalchemy.create_engine().
        """
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )

    # ── Safe representation ────────────────────────────────
    def to_safe_dict(self) -> dict[str, str | int]:
        """Return config dict with password masked for logging.

        All fields are included, but password is replaced with ***REDACTED***.
        Safe to use in logs, debug output, and error messages.

        Returns:
            Dictionary with non-sensitive config values.
        """
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": "***REDACTED***",
        }

    def __repr__(self) -> str:
        """Safe string representation for logging (password masked)."""
        return (
            f"PostgresConfig("
            f"host={self.host!r}, port={self.port}, dbname={self.dbname!r}, "
            f"user={self.user!r}, password=***REDACTED***)"
        )
