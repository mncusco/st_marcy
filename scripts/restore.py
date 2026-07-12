#!/usr/bin/env python
"""
ST CORE — Database restore utility.

Usage:
    python scripts/restore.py <backup_name>          # dry-run (default)
    python scripts/restore.py <backup_name> --apply  # actually restore
    python scripts/restore.py --list                 # list available backups
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "st_core"))

from services.backup_service import BackupService


def main():
    args = sys.argv[1:]
    svc = BackupService(db_path="./database", backup_dir="./backups")

    if "--list" in args:
        backups = svc.list_backups()
        if not backups:
            print("No backups found.")
            return
        print("Available backups:")
        for b in backups:
            size_kb = b["size_bytes"] / 1024
            print(f"  {b['name']:<50} {size_kb:>8.1f} KB  {b['created_at']}")
        return

    if not args or args[0].startswith("--"):
        print("Usage: python scripts/restore.py <backup_name> [--apply]")
        sys.exit(1)

    backup_name = args[0]
    apply_flag = "--apply" in args

    if not apply_flag:
        print(f"[DRY-RUN] Would restore from: {backup_name}")
        print("Pass --apply to execute the restore.")
        return

    confirm = input(f"Restore from '{backup_name}'? A safety backup will be created first. [y/N]: ")
    if confirm.lower() not in ("y", "yes"):
        print("Restore cancelled.")
        return

    result = svc.restore_backup(backup_name)
    if result["success"]:
        print(f"Restore completed from: {result['restored_from']}")
        print(f"Safety backup: {result['safety_backup']['path']}")
    else:
        print(f"Restore failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
