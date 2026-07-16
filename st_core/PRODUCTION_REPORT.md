# PRODUCTION_REPORT.md

**Project:** ST CORE  
**Generated:** 2026-07-14  
**Python:** 3.14.5  
**Test suite:** 194/194 passed (218s)

---

## 1. Hardening Changes Applied

| Task | Description | Status |
|------|-------------|--------|
| 1 | `requirements.txt` pinned to actual installed versions (FastAPI 0.139.0, SQLAlchemy 2.0.51, Pydantic 2.13.4, Uvicorn 0.51.0, email-validator 2.3.0) | Done |
| 2 | Fixed 8 test path-resolution failures (TestDocumentation, TestScriptsDir, TestVerifyScript) | Done |
| 3 | Replaced all `datetime.utcnow()` with `datetime.now(timezone.utc)` across 12 files; fixed naive-aware comparison in `lead_service.py:242` | Done |
| 4 | Upgraded `config.py` from `class Config` to `model_config = SettingsConfigDict(...)` (Pydantic V2) | Done |
| 5 | Improved test DB cleanup: drop tables both before and after each test; retry file deletion on PermissionError | Done |
| 6 | Created `st_core/.gitignore` (pycache, pytest cache, .db, logs, backups, uploads, .env) | Done |

---

## 2. Remaining Production Concerns (non-blocking)

### 2.1 Secrets in `.env`
`st_core/.env` contains default credentials (default username/password, weak `SECRET_KEY`). The file is git-ignored (not committed) but contains defaults that must be changed before production. **Action:** Generate a strong `SECRET_KEY`, rotate `ADMIN_PASSWORD`, ensure `.env` is never committed.

### 2.2 `DEBUG=true` in `.env`
Enables debug mode in production. **Action:** Set `DEBUG=false` before deployment.

### 2.3 SQLite in production
`DATABASE_URL` points to `sqlite:///./shamanic.db`. SQLite is adequate for low-traffic single-server deployments but has concurrency limits. **Action:** Migrate to PostgreSQL for multi-server or high-traffic scenarios.

### 2.4 Sync routes
All route handlers are sync (def, not async). FastAPI wraps them in thread pool, which is acceptable but adds overhead vs native async handlers.

### 2.5 No database migration tool
Tables are created/dropped via `Base.metadata.create_all` / `drop_all`. **Action:** Adopt Alembic for schema migrations in production.

### 2.6 No structured logging
Logging uses plain `logging` module. For production, consider `structlog` or `loguru` with JSON output and log aggregation.

### 2.7 Test coverage blind spots
Coverage report not generated. **Action:** Run `pytest --cov=st_core` to measure coverage; aim for >80%.

### 2.8 CSRF middleware on API
`csrf_middleware` in `app.py` blocks all non-GET/HEAD/OPTIONS requests. API routes (lead creation, downloads) must skip or override this. Currently works because the middleware is bypassed for routes with `csrf_exempt`. Verify all public API endpoints are exempt.

---

## 3. Test Infrastructure Notes

- Tests run against SQLite (`test_shamanic.db`), cleaned per-function via `_db` fixture.
- `conftest.py` uses a fresh test database per run (drop_all + create_all).
- Ebook PDF stubs are created in `./ebooks/` by `_ensure_all_ebooks` fixture.
- Test suite runtime: ~3.5 minutes on Windows/Python 3.14.

---

## 4. Quick Reference

```bash
# Install dependencies
pip install -r st_core/requirements.txt

# Run tests
cd st_core && python -m pytest tests/ -q

# Start development server
cd st_core && uvicorn app:app --reload
```
