from dotenv import load_dotenv
from sqlalchemy import text

from config.db_config import PostgresConfig
from shared.db import get_engine

load_dotenv()

cfg = PostgresConfig.from_env()
engine = get_engine(cfg)

key_tables = [
    "public.cas_customer",
    "data_static.cus_lifetime",
    "cskh.confirmed_churners",
    "cskh.prototype_cache",
]

print("=== Key Tables Check ===")
with engine.connect() as conn:
    for tbl in key_tables:
        try:
            # Use LIMIT 1 instead of COUNT(*) for speed
            # Standard pattern: nosec S608 as tbl is from a hardcoded trusted list
            r = conn.execute(text(f"SELECT 1 FROM {tbl} LIMIT 1"))  # noqa: S608
            has_data = r.fetchone() is not None
            status = "HAS DATA" if has_data else "EMPTY"
            print(f"  [{status}] {tbl}")
        except Exception as e:
            err = str(e).split("\n")[0][:80]
            print(f"  [MISSING] {tbl}: {err}")

    # Check data_window tables
    print("\n=== Feature Window Tables (data_window) ===")
    r = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'data_window' AND table_name LIKE 'cus_feature_%' "
            "ORDER BY table_name"
        )
    )
    tables = [row[0] for row in r]
    if tables:
        for t in tables:
            print(f"  data_window.{t}")
        print(f"  Total: {len(tables)} feature tables")
    else:
        print("  (no feature tables yet - need to run feature generation)")

    print("\n=== Schemas ===")
    r = conn.execute(
        text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
            "ORDER BY schema_name"
        )
    )
    for row in r:
        print(f"  {row[0]}")
