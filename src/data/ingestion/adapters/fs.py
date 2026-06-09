# resources/fs.py
import os
import re
from dataclasses import dataclass
from pathlib import Path

# Regex tên ZIP:
ZIP_RE = re.compile(
    r"(?P<base>[A-Za-z_][A-Za-z0-9_]*)_(?P<yymm>\d{4})\.zip$"
    r"|(?P<base_update>[A-Za-z_][A-Za-z0-9_]*)_update_(?P<update_ddmmyy>\d{6})\.zip$"
    r"|(?P<base_snapshot>[A-Za-z_][A-Za-z0-9_]*)_(?P<ddmmyy>\d{6})\.zip$",
    re.IGNORECASE,
)

@dataclass
class FSConfig:
    """Config cho filesystem."""
    incoming_dir: Path
    saved_dir: Path
    fail_dir: Path

    def ensure_dirs(self) -> None:
        """Đảm bảo các thư mục tồn tại."""
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.saved_dir.mkdir(parents=True, exist_ok=True)
        self.fail_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "FSConfig":
        """
        Factory method dùng trong sensor / job:
        - Đọc env (nếu có)
        - Tạo FSConfig
        - Gọi ensure_dirs()
        """
        inc = Path(os.getenv("CSKH_FILE_PATH", "data/ftp_churn"))
        sav = Path(os.getenv("SAVED_DIR", "data/saved"))
        fail = Path(os.getenv("FAIL_DIR", "data/fail"))
        cfg = cls(incoming_dir=inc, saved_dir=sav, fail_dir=fail)
        cfg.ensure_dirs()
        return cfg

def list_zip_files(src: Path | FSConfig) -> list[Path]:
    """Trả về list các file ZIP trong incoming_dir, lọc theo pattern."""
    if isinstance(src, FSConfig):
        incoming_dir = src.incoming_dir
    else:
        incoming_dir = src

    return [p for p in sorted(incoming_dir.glob("*.zip")) if ZIP_RE.fullmatch(p.name)]
