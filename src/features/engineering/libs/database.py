"""PostgreSQL configuration and connection helpers for engineering features."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg2

from src.features.engineering.config.env_loader import parse_int
from src.features.engineering.config.env_loader import require_env


@dataclass
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            host=require_env("PG_HOST"),
            port=parse_int("PG_PORT"),
            dbname=require_env("PG_DB"),
            user=require_env("PG_USER"),
            password=require_env("PG_PW"),
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


def get_pg_conn(cfg: PostgresConfig, *, autocommit: bool = False):
    """Open a psycopg2 connection from ``PostgresConfig``."""
    conn = psycopg2.connect(cfg.dsn())
    conn.autocommit = autocommit
    return conn
