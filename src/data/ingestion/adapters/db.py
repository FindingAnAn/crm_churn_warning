"""PostgreSQL adapter exports used by ingestion."""

from core.database import get_pg_conn
from settings.database import PostgresConfig

__all__ = ["PostgresConfig", "get_pg_conn"]
