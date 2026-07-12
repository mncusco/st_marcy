#!/usr/bin/env python
"""
ST CORE — Database integrity checker and diagnostics.

Usage:
    python scripts/verify.py
    python scripts/verify.py --verbose
    python scripts/verify.py --fix
"""

import sys
import os
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "st_core"))


def check_integrity(db_path: str, verbose: bool = False, fix: bool = False) -> dict:
    results = {
        "database": db_path,
        "exists": False,
        "integrity_check": "SKIPPED",
        "table_count": 0,
        "row_counts": {},
        "issues": [],
        "status": "UNKNOWN",
    }

    if not os.path.exists(db_path):
        results["issues"].append(f"Database file not found: {db_path}")
        results["status"] = "MISSING"
        return results

    results["exists"] = True

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        results["integrity_check"] = integrity
        if integrity != "ok":
            results["issues"].append(f"Integrity check failed: {integrity}")
            if fix:
                cur.execute("PRAGMA quick_check")
                quick = cur.fetchone()[0]
                results["quick_check"] = quick
                if quick != "ok":
                    results["issues"].append("Database may be corrupt; consider restoring from backup")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        results["table_count"] = len(tables)

        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM \"{table}\"")
                count = cur.fetchone()[0]
                results["row_counts"][table] = count
            except Exception:
                results["row_counts"][table] = -1

        conn.close()
        results["status"] = "OK" if not results["issues"] else "ISSUES_FOUND"

    except Exception as e:
        results["issues"].append(f"Error checking database: {e}")
        results["status"] = "ERROR"

    if verbose:
        cur_path = Path(db_path)
        if cur_path.exists():
            results["size_bytes"] = cur_path.stat().st_size
            results["size_mb"] = round(cur_path.stat().st_size / (1024 * 1024), 2)

    return results


def check_directory_structure() -> dict:
    required = {
        "st_core": "st_core/",
        "config.py": "st_core/config.py",
        "app.py": "st_core/app.py",
        "templates": "st_core/templates/",
        "services": "st_core/services/",
        ".env": ".env",
    }
    found = {}
    for name, path in required.items():
        found[name] = os.path.exists(path)
    return found


def check_environment() -> list:
    issues = []
    required_vars = ["PROJECT_NAME", "DATABASE_URL", "ADMIN_USERNAME", "ADMIN_PASSWORD", "SECRET_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"Environment variable {var} is not set")
    return issues


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args
    fix = "--fix" in args

    report = []

    project_root = os.path.join(os.path.dirname(__file__), "..")
    os.chdir(project_root)

    db_paths = ["./test_shamanic.db", "./database"]
    for db_path in db_paths:
        if os.path.exists(db_path) or os.path.isdir(db_path):
            result = check_integrity(db_path, verbose=verbose, fix=fix)
            report.append(result)

    structures = check_directory_structure()
    missing_dirs = [k for k, v in structures.items() if not v]
    env_issues = check_environment()

    print("=" * 60)
    print("  ST CORE — Database Integrity & Diagnostics")
    print("=" * 60)

    for result in report:
        print(f"\n--- Database: {result['database']} ---")
        print(f"  Exists:       {result['exists']}")
        print(f"  Integrity:    {result['integrity_check']}")
        print(f"  Tables:       {result['table_count']}")
        print(f"  Status:       {result['status']}")
        if verbose and "size_mb" in result:
            print(f"  Size:         {result['size_mb']} MB")
        if result["row_counts"]:
            for table, count in result["row_counts"].items():
                print(f"  - {table}: {count} rows")
        for issue in result["issues"]:
            print(f"  ! {issue}")

    print(f"\n--- Directory Structure ---")
    for name, present in structures.items():
        print(f"  {'OK' if present else 'MISSING'} {name}")

    if env_issues:
        print(f"\n--- Environment Issues ---")
        for issue in env_issues:
            print(f"  ! {issue}")
    else:
        print(f"\n  Environment: OK")

    has_error = any(r["status"] in ("ERROR", "MISSING") for r in report)
    if has_error or missing_dirs or env_issues:
        print(f"\n  Overall: ISSUES FOUND")
        sys.exit(1)
    else:
        print(f"\n  Overall: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
