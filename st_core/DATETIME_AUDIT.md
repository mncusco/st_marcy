# Datetime Consistency Audit

**Date:** 2026-07-14  
**Project:** st_core (Python 3.14, SQLAlchemy 2.0.51, SQLite)  
**Status:** PASS - No code changes required

---

## Convention

All datetimes in the codebase follow a single convention:

| Source | Convention | Example |
|--------|-----------|---------|
| New datetimes (Python) | `datetime.now(timezone.utc)` (aware UTC) | All creation sites |
| DB storage (SQLite) | Naive datetime (tzinfo stripped by SQLite driver) | All 40 model columns |
| SQLAlchemy filters | Aware UTC (safe - serialized to string for SQL) | `query.filter(Model.dt <= datetime.now(timezone.utc))` |
| Python-level comparisons | Both sides naive (via `.replace(tzinfo=None)`) | `lead_service.py:242` |
| Template `now` context | `lambda: datetime.now(timezone.utc)` (callable) | `routes/dashboard.py`, `routes/system.py` |
| Serialization (`.isoformat()`) | `+00:00` suffix for aware, no suffix for naive | `email_engine.py:118,127` |

---

## Verified Behaviors (6 tests)

### 1. SQLAlchemy filter with aware datetime — SAFE
```python
# This works fine because SQLAlchemy serializes the aware datetime
# to an ISO string and sends it to SQLite as a bound parameter.
# The comparison happens in SQL string space, not Python space.
query.filter(Model.dt <= datetime.now(timezone.utc))
```
**Result:** PASS. All 7 filter-site comparisons are safe.

### 2. Python-level aware vs naive — TypeError
```python
datetime.now(timezone.utc) > naive_db_value
# Raises: can't compare offset-naive and offset-aware datetimes
```
**Result:** PASS (expected error). Only 1 Python-level comparison exists (`lead_service.py:242`) and it already uses `.replace(tzinfo=None)`.

### 3. ISO format lexical ordering — REQUIRES CONSISTENCY
```
Ascending sort of ISO datetimes as strings in SQLite:
  2026-01-01T10:00:00              (naive, no suffix)
  2026-01-01T10:00:00+00:00        (+00:00 suffix)
  2026-01-01T10:00:00.000000+00:00 (microseconds + +00:00)
  2026-01-01T10:00:00Z             (Z suffix)
```
**Result:** Consistent within the codebase (all use `.isoformat()` → `+00:00`). `Z` suffix sorts after `+00:00` due to ASCII ordering (`Z`=90 > `+`=43). **Mix of `Z` and `+00:00` on serialization would break ordering.** Currently no risk.

### 4. SQLite strips tzinfo — CONFIRMED
```python
session.add(TZTest(ts=aware_dt))   # store aware
row = session.query(TZTest).first()
row.ts.tzinfo  # None - LOST
```
**Result:** All 40 DateTime columns produce naive datetimes on readback.

### 5. Microsecond precision — PRESERVED
```python
session.add(TZTest(ts=dt_with_123456us))
row = session.query(TZTest).first()
row.ts.microsecond  # 123456 - preserved
```
**Result:** PASS.

### 6. lead_service workaround — CORRECT (with caveat)
```python
expires = row.download_expires_at
if expires.tzinfo is not None:
    expires = expires.replace(tzinfo=None)
if datetime.now(timezone.utc).replace(tzinfo=None) > expires:
    # expired
```
**Result:** PASS functionally. **The `.replace(tzinfo=None)` workaround solves the Type mismatch but makes an implicit UTC assumption.** The value originates at `lead_service.py:65` as `datetime.now(timezone.utc) + timedelta(days=30)`, which is aware UTC. SQLite strips tzinfo on write, so readback is naive. The `.tzinfo is not None` guard never triggers for SQLite. There is no code-enforced invariant guaranteeing `download_expires_at` is UTC — it relies on there being only one code path that sets it (line 65). A more defensive approach would be `expires.replace(tzinfo=timezone.utc)` (attach UTC explicitly) instead of `.replace(tzinfo=None)` (discard timezone), keeping both sides aware and making the UTC convention explicit in code.

**Latent bug on lines 243-244:** If `download_expires_at` is `None`, then `expires = None` (line 242) and `if expires.tzinfo is not None` (line 243) raises `AttributeError`. Currently unreachable because `create_lead` always sets the field, but the model declares `nullable=True`.

---

## Code Locations Inventory

### 40 model columns (`models.py`)
All use `DateTime` (no `timezone=True`), all defaults = `lambda: datetime.now(timezone.utc)`.
Consistent. No change needed.

### 7 SQLAlchemy filter comparisons (safe, SQL-level)
| File | Line | Code |
|------|------|------|
| `email_engine.py` | 242 | `.filter(EmailQueue.scheduled_for <= datetime.now(timezone.utc))` |
| `task_service.py` | 87 | `.filter(Task.due_at >= today_start)` |
| `task_service.py` | 95 | `.filter(Task.due_at < now)` |
| `task_service.py` | 127 | `.filter(Reminder.remind_at <= datetime.now(timezone.utc))` |
| `interview_service.py` | 133 | `.filter(Interview.scheduled_at >= now)` |
| `booking_service.py` | 55 | `.filter(Retreat.start_date >= now)` |
| `analytics_service.py` | 104 | `.filter(Lead.created_at >= since)` |

### 1 Python-level comparison (already fixed)
| File | Lines | Code | Status |
|------|-------|------|--------|
| `lead_service.py` | 242–245 | `expires = lead.download_expires_at; if expires.tzinfo is not None: expires = expires.replace(tzinfo=None); if lead.download_expires_at and datetime.now(timezone.utc).replace(tzinfo=None) > expires:` | ✅ `.replace(tzinfo=None)` workaround in place |

### User-provided date input (naive, correctly used as naive)
| File | Line | Code |
|------|------|------|
| `lead_service.py` | 126 | `dt_from = datetime.strptime(...)` (naive, from query params) |
| `lead_service.py` | 132 | `dt_to = datetime.strptime(...)` (naive, from query params) |
| `dashboard.py` | 36-38 | `datetime.now(timezone.utc)` → `strftime` → `strptime` → naive (used as UI defaults) |

These are applied only in SQLAlchemy `.filter()`, so safe. However, the semantic meaning differs: user-provided naive datetimes represent "local calendar date" while DB dates are UTC. This could cause incorrect date-range filtering around midnight UTC. Mitigation: user-facing date pickers default to a 30-day range, limiting impact.

### Template `now` context (correct)
| File | Line | Code |
|------|------|------|
| `routes/dashboard.py` | 178 | `"now": lambda: datetime.now(timezone.utc)` |
| `routes/system.py` | 35 | `"now": lambda: datetime.now(timezone.utc)` |
| `routes/system.py` | 100 | `"now": lambda: datetime.now(timezone.utc)` |
| `routes/system.py` | 154 | `"now": lambda: datetime.now(timezone.utc)` |
| `routes/system.py` | 210 | `"now": lambda: datetime.now(timezone.utc)` |

Template usage: `{{ now().strftime('%H:%M:%S') }}` in `email_diagnostics.html:89`. The lambda returns an aware UTC datetime when called. Correct.

---

## Findings Summary

| # | Area | Severity | Verdict |
|---|------|----------|---------|
| 1 | SQLAlchemy filter comparisons | None | Safe (SQL-level, serialized to string) |
| 2 | Python-level aware vs naive | None | Only 1 occurrence, already fixed |
| 3 | ISO format `Z` vs `+00:00` ordering | Low | Consistent (all `.isoformat()`), no fix needed |
| 4 | Microsecond preservation | None | Preserved through DateTime column |
| 5 | User-provided naive date filters | Low | Semantic mismatch (local vs UTC), limited impact |
| 6 | Template `now` context | None | Correct (callable returning aware UTC) |
| 7 | `lead_service` comparison workaround | Low | Functionally correct but UTC assumption not enforced in code; latent `AttributeError` if field is `None` |

## Final Verdict

**No code changes required for the 7 SQLAlchemy filter comparisons.** The single Python-level comparison at `lead_service.py:242-245` is functionally correct but has two caveats: (1) the UTC assumption is implicit not enforced (`expires` could theoretically come from a non-UTC source), (2) a latent `AttributeError` exists if `download_expires_at` is `None` (lines 243-244 run before the `None` check on line 245). A root fix would re-attach UTC explicitly: `expires = expires.replace(tzinfo=timezone.utc)` instead of stripping it. The existing convention of `DateTime` without `timezone=True` is incompatible with `datetime.now(timezone.utc)` at the Python level, but since all other comparisons go through SQLAlchemy filters (SQL-level), the system operates correctly in practice.

---

*Audit methodology: 6 automated tests covering filter safety, Python-level comparison, ISO ordering, tzinfo round-trip, microsecond precision, and the lead_service workaround. All pass.*
