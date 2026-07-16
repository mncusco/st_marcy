import shutil
from datetime import datetime, timezone
from pathlib import Path


class BackupService:
    def __init__(self, db_path: str = "./database", backup_dir: str = "./backups", max_backups: int = 10):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, label: str = "") -> dict:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_label = f"_{label}" if label else ""
        backup_name = f"st_core_backup_{timestamp}{safe_label}"
        backup_path = self.backup_dir / backup_name

        if self.db_path.exists():
            if self.db_path.is_dir():
                shutil.copytree(self.db_path, backup_path)
            else:
                backup_path = self.backup_dir / f"{backup_name}.db"
                shutil.copy2(self.db_path, backup_path)
        else:
            # fallback: copy any .db files in current directory
            for f in Path(".").glob("*.db"):
                dest = self.backup_dir / f"{backup_name}_{f.name}"
                shutil.copy2(f, dest)

        self._enforce_retention()

        return {
            "success": True,
            "path": str(backup_path),
            "created_at": timestamp,
            "label": label,
        }

    def list_backups(self) -> list[dict]:
        backups = []
        if not self.backup_dir.exists():
            return backups
        for entry in sorted(self.backup_dir.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
            stat = entry.stat()
            backups.append({
                "name": entry.name,
                "path": str(entry),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        return backups

    def _resolve_backup(self, backup_name: str) -> Path:
        resolved = (self.backup_dir / backup_name).resolve()
        if not str(resolved).startswith(str(self.backup_dir.resolve())):
            raise ValueError("Invalid backup name")
        return resolved

    def restore_backup(self, backup_name: str) -> dict:
        backup_path = self._resolve_backup(backup_name)
        if not backup_path.exists():
            return {"success": False, "error": "Backup not found"}

        # create safety backup of current db first
        safety = self.create_backup(label="pre_restore")

        if backup_path.is_dir():
            if self.db_path.exists():
                shutil.rmtree(self.db_path)
            shutil.copytree(backup_path, self.db_path)
        else:
            shutil.copy2(backup_path, self.db_path)

        return {"success": True, "restored_from": backup_name, "safety_backup": safety}

    def delete_backup(self, backup_name: str) -> dict:
        backup_path = self._resolve_backup(backup_name)
        if not backup_path.exists():
            return {"success": False, "error": "Backup not found"}
        if backup_path.is_dir():
            shutil.rmtree(backup_path)
        else:
            backup_path.unlink()
        return {"success": True, "deleted": backup_name}

    def _enforce_retention(self):
        entries = sorted(self.backup_dir.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True)
        while len(entries) > self.max_backups:
            old = entries.pop()
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
