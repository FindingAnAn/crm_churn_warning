# sensors/incoming_zip_sensor.py
from __future__ import annotations

from data.ingestion.jobs.ingest_zip_job import ingest_zip_job
from data.ingestion.ops.naming import parse_zip_and_decide_names
from data.ingestion.resources import (
    FSConfig,
    PostgresConfig,
    get_pg_conn,
    list_zip_files,
)
from shared.logging_config import get_logger

logger = get_logger(__name__)


def has_success_log(
    zip_name: str,
    pg_cfg: PostgresConfig,
    *,
    ingest_schema: str = "ingest",
) -> tuple[bool, float]:
    """
    Check xem ZIP này đã có bản ghi success trong ingest_log hay chưa.

    Returns:
        (already_processed, logged_mtime)
        - already_processed: True nếu đã xử lý thành công
        - logged_mtime: modification time đã ghi log (Unix timestamp), 0.0 nếu chưa có log
    """
    conn = get_pg_conn(pg_cfg)
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT file_mtime
            FROM {ingest_schema}.ingest_log
            WHERE zip_name = %s
              AND status = 'success'
            ORDER BY finished_at DESC
            LIMIT 1;
            """,
            (zip_name,),
        )
        row = cur.fetchone()
        if row:
            return (True, float(row[0] or 0.0))
        return (False, 0.0)
    except Exception as e:
        logger.warning(f"Could not check ingest_log for {zip_name}: {e}")
        return (False, 0.0)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def filter_files_to_process(zip_paths: list, pg_cfg: PostgresConfig, ingest_schema: str) -> list:
    """
    Lọc files cần xử lý:
    - Snapshot mode (cas_customer, cas_info, cms_complaint): Chỉ lấy file mới nhất theo period_key
    - Monthly mode (bccp_orderitem): Chỉ lấy 2 tháng mới nhất theo YYMM
    """
    from collections import defaultdict

    snapshot_files = defaultdict(list)  # {base: [(period_key, path), ...]}
    monthly_files = defaultdict(list)  # {base: [(yymm, path), ...]}

    for zip_path in zip_paths:
        try:
            meta = parse_zip_and_decide_names(zip_path)
            mode = meta.get("mode")
            base = meta.get("base")

            if mode == "snapshot":
                period_key = meta.get("period_key")  # YYYYMMDD
                snapshot_files[base].append((period_key, zip_path))
            elif mode == "monthly":
                yymm = meta.get("yymm")  # 2501, 2502
                monthly_files[base].append((yymm, zip_path))
        except Exception as e:
            logger.warning(f"Skipping {zip_path.name}: {e}")
            continue

    # Filter snapshot: chỉ lấy file có period_key lớn nhất
    result = []
    for base, files in snapshot_files.items():
        files.sort(key=lambda x: x[0], reverse=True)  # Sort DESC by period_key
        latest = files[0]
        logger.info(f"Selected latest snapshot {base}: {latest[1].name} (period_key={latest[0]})")
        result.append(latest[1])

        if len(files) > 1:
            skipped = [f[1].name for f in files[1:]]
            logger.debug(f"Skipped {len(skipped)} older {base} files")

    # Filter monthly: logic thông minh cho bccp_orderitem
    # - Luôn process top 2 tháng mới nhất (refresh policy)
    # - Tự động fill gap (tháng chưa success)
    # - Giới hạn batch size để tránh overload (set None để process tất cả)
    MAX_BATCH_SIZE = None  # None = process ALL, hoặc số cụ thể (ví dụ: 6)

    for base, files in monthly_files.items():
        files.sort(key=lambda x: x[0], reverse=True)  # Sort DESC by yymm

        if len(files) == 0:
            continue

        # Luôn lấy top 2 mới nhất (hoặc ít hơn nếu không đủ)
        top_2 = files[: min(2, len(files))]
        to_process = set()

        logger.info(f"Selected top {len(top_2)} month(s) for {base} (monthly mode - always refresh)")
        for yymm, path in top_2:
            logger.info(f"  [TOP] {path.name} (yymm={yymm})")
            to_process.add((yymm, path))

        # Tìm gap trong các tháng cũ hơn (nếu có)
        if len(files) > 2:
            older_files = files[2:]
            gaps_found = []

            for yymm, old_path in older_files:
                old_zip_name = old_path.name
                already_done, _ = has_success_log(old_zip_name, pg_cfg, ingest_schema=ingest_schema)

                if not already_done:
                    gaps_found.append((yymm, old_path))
                    # Giới hạn số gap nếu MAX_BATCH_SIZE được set
                    if MAX_BATCH_SIZE is not None and len(to_process) + len(gaps_found) >= MAX_BATCH_SIZE:
                        logger.info(
                            f"  Reached batch size limit ({MAX_BATCH_SIZE}), will process remaining gaps in next run"
                        )
                        break

            if gaps_found:
                logger.info(f"Found {len(gaps_found)} gap(s) in older months (not yet processed):")
                for yymm, gap_path in gaps_found:
                    logger.info(f"  [GAP] {gap_path.name} (yymm={yymm})")
                    to_process.add((yymm, gap_path))
            else:
                logger.info("All older months already processed successfully")
                skipped_count = len(older_files)
                logger.debug(f"Skipped {skipped_count} older {base} months (already in DB)")

        # Add to result (sorted DESC by yymm)
        sorted_files = sorted(to_process, key=lambda x: x[0], reverse=True)
        for yymm, path in sorted_files:
            result.append(path)

    return result


def run_once_scan(
    fs_cfg: FSConfig | None = None,
    pg_cfg: PostgresConfig | None = None,
    *,
    prod_schema: str = "public",
    ingest_schema: str = "ingest",
) -> None:
    if fs_cfg is None:
        fs_cfg = FSConfig.from_env()
    if pg_cfg is None:
        pg_cfg = PostgresConfig.from_env()

    incoming = fs_cfg.incoming_dir
    logger.info(f"Scanning ZIP files in: {incoming}")

    zip_paths = list_zip_files(fs_cfg)
    if not zip_paths:
        logger.info(f"No ZIP files found in {incoming}")
        return

    # Filter files: chỉ xử lý file mới nhất (snapshot) hoặc 2 tháng mới nhất (monthly)
    filtered_paths = filter_files_to_process(zip_paths, pg_cfg, ingest_schema)
    logger.info(f"Filtered: {len(filtered_paths)}/{len(zip_paths)} files to process")

    for zip_path in filtered_paths:
        zip_name = zip_path.name

        # Parse ZIP để xác định mode (monthly/snapshot)
        try:
            meta = parse_zip_and_decide_names(zip_path)
            mode = meta.get("mode", "monthly")
        except Exception as e:
            logger.warning(f"Could not parse {zip_name}: {e}. Skipping.")
            continue

        # Kiểm tra xem file đã được xử lý thành công chưa
        already_processed, logged_mtime = has_success_log(zip_name, pg_cfg, ingest_schema=ingest_schema)

        if already_processed:
            # So sánh modification time - nếu KHÁC → file đã được cập nhật → re-ingest
            current_mtime = zip_path.stat().st_mtime

            if current_mtime != logged_mtime:
                from datetime import datetime

                logged_time_str = datetime.fromtimestamp(logged_mtime).strftime("%Y-%m-%d %H:%M:%S")
                current_time_str = datetime.fromtimestamp(current_mtime).strftime("%Y-%m-%d %H:%M:%S")

                logger.info(
                    f"Re-ingesting {zip_name} (mode={mode}): File was updated. "
                    f"Old mtime: {logged_time_str}, New mtime: {current_time_str}"
                )
                # Tiếp tục xử lý (không continue)
            else:
                # Timestamp GIỐNG NHAU → skip
                logger.info(f"Skipping {zip_name} (mode={mode}): already processed (same mtime)")
                continue

        try:
            logger.info(f"Running ingest_zip_job for {zip_name}")
            result = ingest_zip_job(
                zip_path=zip_path,
                fs_cfg=fs_cfg,
                pg_cfg=pg_cfg,
                prod_schema=prod_schema,
                ingest_schema=ingest_schema,
            )

            # Kiểm tra kết quả
            if result.get("success"):
                logger.info(
                    f"Successfully ingested {zip_name}: "
                    f"staging_rows={result['staging_rows']:,}, "
                    f"prod_rows={result['prod_rows']:,}"
                )

                # COPY file sang saved_data sau khi xử lý thành công (GIỮ NGUYÊN file gốc)
                import shutil

                saved_path = fs_cfg.saved_dir / zip_name

                # Nếu file đã tồn tại trong saved_data (re-ingest), ghi đè
                if saved_path.exists():
                    logger.info(f"File {zip_name} already exists in saved_data, overwriting...")
                    saved_path.unlink()

                saved_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(zip_path), str(saved_path))
                logger.info(f"Copied {zip_name} to saved_data (kept original in incoming_dir)")

            elif result.get("skipped"):
                logger.info(f"Skipped {zip_name}: {result.get('reason', 'unknown')}")
            else:
                logger.error(f"Failed {zip_name}: {result.get('error', 'unknown error')}")

        except Exception as e:
            logger.error(f"Error processing {zip_name}: {e}")


def main() -> None:
    import time

    logger.info("Starting incoming ZIP sensor...")
    while True:
        run_once_scan()
        time.sleep(30)  # Scan every 30 seconds


if __name__ == "__main__":
    main()
