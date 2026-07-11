"""
Database backup utility.

Usage:
    python scripts/backup_database.py

Copies the SQLite database to a timestamped backup file.
For production use with PostgreSQL, connect via pg_dump instead.
"""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def backup_sqlite(db_path: str = "./database/shamanic.db", backup_dir: str = "./backups"):
    src = Path(db_path)
    if not src.exists():
        print(f"[ERROR] Database not found: {src.resolve()}")
        return False

    dst_dir = Path(backup_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dst = dst_dir / f"shamanic_backup_{timestamp}.db"

    try:
        con = sqlite3.connect(str(src))
        bck = sqlite3.connect(str(dst))
        con.backup(bck)
        bck.close()
        con.close()
        print(f"[OK] Backup saved: {dst} ({dst.stat().st_size / 1024:.1f} KB)")
        return True
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")
        return False


if __name__ == "__main__":
    backup_sqlite()
