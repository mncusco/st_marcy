# RELEASE NOTES — ST CORE v1.0.0

**Release date:** 2026-07-14  
**Python version:** 3.14.5  
**Database:** SQLite (SQLAlchemy 2.0.51)

---

## What's New

- **CRM Lead Funnel** — Full lead lifecycle: creation, status tracking, editorial download, interview pipeline, booking
- **Email Automation** — Follow-up sequences (3-day, editorial, interview, journey), queue with retry logic
- **Admin Dashboard** — Real-time stats, task management, reminders, CRM notes, audit log
- **Backup & Restore** — Web interface and CLI for SQLite backups with restore safety
- **Multi-language Editorial** — PDF delivery in EN, IT, ES, RU, SR
- **Health & Diagnostics** — `/health`, `/admin/system`, `/admin/email-diagnostics`
- **AI Analysis** — Auto-generated candidate analysis from interview notes

---

## Bug Fixes (this release)

- Fixed 8 test path-resolution failures in `test_operations.py` (TestDocumentation, TestScriptsDir, TestVerifyScript)
- Fixed `TypeError: can't compare offset-naive and offset-aware datetimes` in `lead_service.py:242` (SQLite stores datetimes naively)
- Fixed duplicate-email collision in test database cleanup (retry loop + drop_all before create_all)

---

## Hardening (this release)

- Replaced all `datetime.utcnow()` → `datetime.now(timezone.utc)` across 65 occurrences in 12 files
- Upgraded `config.py` from Pydantic V1 `class Config` to V2 `model_config = SettingsConfigDict(...)`
- Pinned `requirements.txt` to exact installed versions (FastAPI 0.139.0, SQLAlchemy 2.0.51, Pydantic 2.13.4)
- Created `st_core/.gitignore` for __pycache__, .db, .env, logs, backups
- Created `PRODUCTION_REPORT.md` with production readiness assessment
- Repository audit: removed test artifacts, debug scripts, dev utilities, coverage files, backup archives

---

## Test Suite

| Metric | Value |
|---|---|
| Total tests | 194 |
| Passed | 194 |
| Failed | 0 |
| Runtime | ~218s (3m38s) |
| Framework | pytest 9.1.1 |

---

## Dependencies

| Package | Version |
|---|---|
| fastapi | 0.139.0 |
| uvicorn | 0.51.0 |
| sqlalchemy | 2.0.51 |
| pydantic | 2.13.4 |
| pydantic-settings | 2.14.2 |
| python-dotenv | 1.2.2 |
| jinja2 | 3.1.6 |
| python-multipart | 0.0.32 |
| email-validator | 2.3.0 |

---

## Known Limitations

1. **SQLite concurrency** — Not suitable for high-traffic multi-server deployments. Migrate to PostgreSQL for scale.
2. **Sync route handlers** — All FastAPI routes are sync (def). FastAPI wraps via thread pool; acceptable but adds overhead vs native async.
3. **No migration tool** — Schema is created via `Base.metadata.create_all`. Alembic recommended for production schema changes.
4. **No structured logging** — Uses stdlib `logging`. Consider `structlog` for production log aggregation.
5. **Coverage blind spots** — Coverage report not yet generated. Run `pytest --cov=st_core` to measure.
6. **Default credentials in `.env`** — The `.env.example` has placeholder credentials; must be changed before deployment.
7. **CSRF middleware** — `csrf_middleware` blocks non-GET/HEAD/OPTIONS requests; public API endpoints must be verified as `csrf_exempt`.

---

## Upgrading

```bash
git pull origin main
cd st_core
pip install -r requirements.txt
# Re-create database tables:
python -c "from database import engine, Base; Base.metadata.create_all(bind=engine)"
# Run tests to verify:
python -m pytest tests/ -q
```
