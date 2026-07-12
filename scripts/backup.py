#!/usr/bin/env python
"""
ST CORE — Automatic SQLite backup script.

Usage:
    python scripts/backup.py                    # create backup
    python scripts/backup.py --label pre-deploy # backup with label
    python scripts/backup.py --list             # list backups
    python scripts/backup.py --delete <name>    # delete a backup
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
        print(f"{'Name':<50} {'Size':<12} {'Created'}")
        print("-" * 80)
        for b in backups:
            size_kb = b["size_bytes"] / 1024
            print(f"{b['name']:<50} {size_kb:>8.1f} KB  {b['created_at']}")
        return

    if "--delete" in args:
        idx = args.index("--delete")
        if idx + 1 >= len(args):
            print("Error: --delete requires a backup name")
            sys.exit(1)
        name = args[idx + 1]
        result = svc.delete_backup(name)
        if result["success"]:
            print(f"Deleted backup: {name}")
        else:
            print(f"Error: {result.get('error')}")
            sys.exit(1)
        return

    label = ""
    if "--label" in args:
        idx = args.index("--label")
        if idx + 1 < len(args):
            label = args[idx + 1]

    result = svc.create_backup(label=label)
    if result["success"]:
        print(f"Backup created: {result['path']}")
    else:
        print(f"Backup failed: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
