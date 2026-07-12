# ST CORE — Backup Guide

## Overview

The backup system uses SQLite's file-based nature for simple, reliable backups. Backups are stored in the `./backups/` directory.

## Automatic Backups

Access the admin dashboard at `/admin/backups` to:

- **Create** a backup with an optional label
- **List** all backups with size and date
- **Restore** from any backup (creates a safety backup first)
- **Delete** old backups

## CLI Scripts

### Create a backup

```bash
python scripts/backup.py
python scripts/backup.py --label before-update
```

### List backups

```bash
python scripts/backup.py --list
```

### Delete a backup

```bash
python scripts/backup.py --delete st_core_backup_20260711_120000
```

### Restore a backup

```bash
# Dry-run
python scripts/restore.py st_core_backup_20260711_120000

# Actually restore
python scripts/restore.py st_core_backup_20260711_120000 --apply
```

The restore command creates a safety backup before restoring.

## Retention Policy

Backups are retained up to the configured maximum (default: 10). When the limit is exceeded, the oldest backup is automatically removed.

## Scheduling (Cron)

### Linux

```cron
# Daily backup at 02:00
0 2 * * * /opt/st_core/venv/bin/python /opt/st_core/scripts/backup.py >> /var/log/st_core_backup.log 2>&1
```

### Windows Task Scheduler

```powershell
# Create a scheduled task to run daily at 2 AM
$action = New-ScheduledTaskAction -Execute "C:\path\to\venv\Scripts\python.exe" -Argument "C:\path\to\st_core\scripts\backup.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 02:00
Register-ScheduledTask -TaskName "STCORE_Backup" -Action $action -Trigger $trigger -RunLevel Highest
```

## Manual Backup (SQLite)

```bash
# Direct file copy (safe when app is not writing)
cp ./database/st_core.db ./backups/manual_backup_$(date +%Y%m%d).db

# Or use SQLite's backup API
sqlite3 ./database/st_core.db ".backup './backups/sqlite_backup.db'"
```

## Integrity Verification

```bash
# Check database integrity
python scripts/verify.py

# Verbose output with row counts
python scripts/verify.py --verbose
```
