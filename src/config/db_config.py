"""Database configuration.

Conventions applied:
  - 02-Config §3.1: One config object per subsystem (PostgresConfig).
  - 02-Config §5.1: Strong typing — all fields explicitly typed.
  - 02-Config §6.1: Self-validating config object.
  - 02-Config §7.2: Derived value (dsn, sqlalchemy_url) masks password in safe_dict.
  - 02-Config §9.2: Env vars uppercase with PG_ prefix.
  - 08-Security §3.2: No hardcoded credentials.
  - 08-Security §6.2: Safe defaults only for non-sensitive values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL connection configuration.

    Attributes:
        host: Database server hostname.
        port: Database server port.
        dbname: Target database name.
        user: Database username.
        password: Database password.
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

        Required env vars (prefix PG_):
            PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PW

        Safe defaults are provided only for host/port (non-sensitive).
        User and password MUST be set via environment for security.

        Raises:
            EnvironmentError: If required secrets (PG_USER, PG_PW) are missing.
        """
        user = os.getenv("PG_USER")
        password = os.getenv("PG_PW")

        if not user or not password:
            raise OSError(
                "Missing required environment variables: PG_USER and PG_PW. "
                "Set them in .env or export them before running."
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

        Raises:
            ValueError: If any field fails validation.
        """
        if not self.host:
            raise ValueError("PostgresConfig.host must not be empty.")
        if not (1 <= self.port <= 65535):
            raise ValueError(f"PostgresConfig.port must be 1–65535, got {self.port}.")
        if not self.dbname:
            raise ValueError("PostgresConfig.dbname must not be empty.")
        if not self.user:
            raise ValueError("PostgresConfig.user must not be empty.")
        if not self.password:
            raise ValueError("PostgresConfig.password must not be empty.")

    # ── Derived values ─────────────────────────────────────
    def dsn(self) -> str:
        """libpq-style DSN (for psycopg2.connect)."""
        return f"host={self.host} port={self.port} dbname={self.dbname} user={self.user} password={self.password}"

    def sqlalchemy_url(self) -> str:
        """SQLAlchemy connection URL."""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    # ── Safe representation ────────────────────────────────
    def to_safe_dict(self) -> dict[str, str | int]:
        """Return config dict with password masked (for logging/debug).

        Convention: 08-Security §7.2 — redact sensitive data before output.
        """
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": "***REDACTED***",
        }

    def __repr__(self) -> str:
        """Safe repr — never expose password."""
        return (
            f"PostgresConfig(host={self.host!r}, port={self.port}, "
            f"dbname={self.dbname!r}, user={self.user!r}, password='***')"
        )
