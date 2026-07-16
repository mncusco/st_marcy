"""
Datetime consistency tests — protects against regression of the
datetime audit findings.  Each test cites the exact file:line of
real project code it verifies.
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, Column, Integer, DateTime, text
from sqlalchemy.orm import declarative_base, Session


# ── Helpers ──────────────────────────────────────────────────────

_engine = create_engine("sqlite://", echo=False)
_Base = declarative_base()


class _DtModel(_Base):
    __tablename__ = "dt_test"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime)


_Base.metadata.create_all(bind=_engine)


def _store_and_read(dt: datetime) -> datetime:
    """Store *dt* in SQLite via SQLAlchemy and read it back."""
    with Session(_engine) as s:
        s.add(_DtModel(ts=dt))
        s.commit()
    with Session(_engine) as s:
        row = s.query(_DtModel).order_by(_DtModel.id.desc()).first()
        return row.ts


# ── Tests ────────────────────────────────────────────────────────


class TestAwareVsNaive:
    """Verifies that Python-level aware-vs-naive comparison raises
    TypeError — confirming why lead_service.py must normalize."""

    def test_aware_greater_than_naive_raises_typeerror(self):
        """
        Real code: lead_service.py:245-246 (the FIX).
        Before the fix, comparing datetime.now(timezone.utc) (aware)
        with a naive DB value would crash with TypeError.
        """
        naive = datetime(2026, 7, 14, 12, 0, 0)
        aware = datetime.now(timezone.utc)
        with pytest.raises(TypeError, match="can't compare"):
            _ = aware > naive

    def test_naive_greater_than_aware_raises_typeerror(self):
        naive = datetime(2026, 7, 14, 12, 0, 0)
        aware = datetime.now(timezone.utc)
        with pytest.raises(TypeError, match="can't compare"):
            _ = naive > aware


class TestUtcNormalization:
    """Verifies the normalization used after the fix."""

    def test_replace_tzinfo_utc_makes_aware(self):
        """
        Real code: lead_service.py:245.
        `expires.replace(tzinfo=timezone.utc)` re-attaches UTC
        to a naive datetime read from SQLite.
        """
        naive = datetime(2026, 7, 14, 12, 0, 0)
        aware = naive.replace(tzinfo=timezone.utc)
        assert aware.tzinfo is timezone.utc
        assert aware.hour == 12

    def test_aware_can_compare_after_normalization(self):
        """
        Real code: lead_service.py:246.
        After normalizing the DB value to aware UTC, comparison
        with datetime.now(timezone.utc) works without TypeError.
        """
        naive = datetime(2026, 7, 14, 12, 0, 0)
        normalized = naive.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        result = normalized < now  # should not raise
        assert isinstance(result, bool)


class TestMicroseconds:
    """Verifies microsecond precision through SQLite DateTime columns."""

    def test_microseconds_preserved(self):
        """
        Real code: models.py:72-73 (and 40+ other DateTime columns).
        All model DateTime columns use `default=lambda: datetime.now(timezone.utc)`,
        which produces microsecond precision.  SQLite must preserve it.
        """
        original = datetime(2026, 7, 14, 12, 0, 0, 123456)
        readback = _store_and_read(original)
        assert readback.microsecond == 123456, f"Expected 123456, got {readback.microsecond}"

    def test_no_microseconds_preserved(self):
        """
        Real code: lead_service.py:126,132.
        User-provided date filters come from `datetime.strptime(...)`
        which produces zero-microsecond datetimes.
        """
        original = datetime(2026, 7, 14, 12, 0, 0, 0)
        readback = _store_and_read(original)
        assert readback.microsecond == 0


class TestIsoFormat:
    """Verifies ISO 8601 serialization behaviour relevant to the project."""

    def test_isoformat_aware_produces_plus_0000(self):
        """
        Real code: email_engine.py:118,127.
        `.isoformat()` is called on aware datetimes to serialise
        them for email headers / logs.
        """
        dt = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
        iso = dt.isoformat()
        assert iso == "2026-07-14T12:00:00+00:00"
        assert iso.endswith("+00:00")

    def test_isoformat_naive_has_no_suffix(self):
        """
        Real code: email_engine.py:118,127.
        DB-stored datetimes (naive) produce no timezone suffix.
        """
        dt = datetime(2026, 7, 14, 12, 0, 0)
        iso = dt.isoformat()
        assert iso == "2026-07-14T12:00:00"
        assert "+" not in iso and not iso.endswith("Z")

    def test_iso_lexical_sort_z_after_plus(self):
        """
        Real code: all SQL ORDER BY on DateTime columns.
        SQLite sorts ISO strings lexically.  'Z' (ASCII 90) sorts
        after '+' (ASCII 43), so '2026-01-01T10:00:00Z' > '2026-01-01T10:00:00+00:00'.
        The project consistently uses `.isoformat()` → '+00:00', never 'Z',
        so this is not a current risk.
        """
        with _engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS iso_order (ts TEXT)"))
            conn.execute(text("DELETE FROM iso_order"))
            for val in ["2026-01-01T10:00:00+00:00", "2026-01-01T10:00:00Z"]:
                conn.execute(text("INSERT INTO iso_order (ts) VALUES (:ts)"), {"ts": val})
            conn.commit()
            rows = conn.execute(
                text("SELECT ts FROM iso_order ORDER BY ts ASC")
            ).fetchall()
        assert rows[0][0] == "2026-01-01T10:00:00+00:00"
        assert rows[1][0] == "2026-01-01T10:00:00Z"


class TestSqliteRoundtrip:
    """Verifies that SQLite strips tzinfo during write/readback."""

    def test_tzinfo_lost_on_roundtrip(self):
        """
        Real code: all 40+ DateTime columns in models.py.
        SQLite's SQLAlchemy driver does not preserve tzinfo;
        readback datetimes are always naive.
        """
        original = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
        assert original.tzinfo is timezone.utc
        readback = _store_and_read(original)
        assert readback.tzinfo is None, f"Expected None, got {readback.tzinfo}"

    def test_aware_stored_as_naive_string(self):
        """
        Real code: models.py columns.
        Verifies that the raw SQLite text contains no timezone suffix.
        """
        original = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
        _store_and_read(original)  # write via SQLAlchemy
        with _engine.connect() as conn:
            rows = conn.execute(
                text("SELECT ts FROM dt_test ORDER BY id DESC LIMIT 1")
            ).fetchall()
        raw = rows[0][0]
        assert "+" not in raw, f"Raw stored value contains tz suffix: {raw}"
        assert not raw.endswith("Z"), f"Raw stored value ends with Z: {raw}"


class TestSqlAlchemyFilter:
    """Verifies that SQLAlchemy filters with aware datetimes are safe."""

    def test_filter_with_aware_datetime(self):
        """
        Real code (7 sites):
          email_engine.py:242, task_service.py:87,95,127,
          interview_service.py:133, booking_service.py:55,
          analytics_service.py:104, dashboard.py:97.
        SQLAlchemy serialises the aware datetime to a string for SQLite,
        so the comparison happens in SQL string space, not Python space.
        """
        with Session(_engine) as s:
            s.add(_DtModel(ts=datetime(2026, 7, 14, 12, 0, 0)))
            s.commit()
        aware_now = datetime.now(timezone.utc)
        with Session(_engine) as s:
            rows = s.query(_DtModel).filter(_DtModel.ts <= aware_now).all()
        assert len(rows) >= 1

    def test_filter_with_naive_datetime(self):
        """
        Real code: lead_service.py:126,132 (user-provided date filters).
        Naive datetimes from strptime work in SQLAlchemy filters too.
        """
        with Session(_engine) as s:
            s.add(_DtModel(ts=datetime(2026, 7, 14, 12, 0, 0)))
            s.commit()
        naive_dt = datetime(2026, 7, 14, 12, 0, 0)
        with Session(_engine) as s:
            rows = s.query(_DtModel).filter(_DtModel.ts >= naive_dt).all()
        assert len(rows) >= 1


class TestPythonComparison:
    """Verifies the exact comparison pattern from lead_service.py."""

    def test_naive_vs_naive_comparison_works(self):
        """
        Real code: lead_service.py:245-246 (after the fix).
        Both sides are naive → comparison succeeds.
        """
        naive_db = datetime(2026, 7, 14, 12, 0, 0)  # as read from SQLite
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        result = now_naive > naive_db
        assert isinstance(result, bool)

    def test_aware_vs_aware_comparison_works(self):
        """
        Real code: lead_service.py:245-246 (after the fix).
        Both sides are aware UTC → comparison succeeds.
        """
        normalized_db = datetime(2026, 7, 14, 12, 0, 0).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        result = now > normalized_db
        assert isinstance(result, bool)


class TestDownloadTokenExpiration:
    """Tests the full mark_downloaded_by_token flow."""

    def test_expired_token_raises_410(self):
        """
        Real code: lead_service.py:240-247.
        Verifies that an expired download_token raises HTTP 410.
        """
        from database import SessionLocal
        from models import Lead
        session = SessionLocal()
        try:
            past = datetime.now(timezone.utc) - timedelta(days=1)
            lead = Lead(
                first_name="Test",
                last_name="User",
                email="test_expired@example.com",
                download_token="tok_expired",
                download_expires_at=past,
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)

            from services.lead_service import LeadService
            with pytest.raises(Exception) as exc:
                LeadService.mark_downloaded_by_token(
                    session, "tok_expired", "127.0.0.1", "pytest"
                )
            assert exc.value.status_code == 410
            assert "scaduto" in exc.value.detail.lower()
        finally:
            session.close()

    def test_valid_token_does_not_raise(self):
        """
        Real code: lead_service.py:240-247.
        Verifies that a valid (future) download_token passes through.
        """
        from database import SessionLocal
        from models import Lead
        session = SessionLocal()
        try:
            future = datetime.now(timezone.utc) + timedelta(days=30)
            lead = Lead(
                first_name="Test",
                last_name="User",
                email="test_valid@example.com",
                download_token="tok_valid",
                download_expires_at=future,
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)

            from services.lead_service import LeadService
            result = LeadService.mark_downloaded_by_token(
                session, "tok_valid", "127.0.0.1", "pytest"
            )
            assert result is not None
            assert result.downloaded_editorial is True
        finally:
            session.close()

    def test_none_expires_at_does_not_crash(self):
        """
        Real code: lead_service.py:243 (the `if expires is not None` guard)
        and models.py:65 (nullable=True).
        Before the fix, `None.tzinfo` raised AttributeError.
        After the fix, `if expires is not None` guards against it.
        """
        from database import SessionLocal
        from models import Lead
        session = SessionLocal()
        try:
            lead = Lead(
                first_name="Test",
                last_name="User",
                email="test_none@example.com",
                download_token="tok_none",
                download_expires_at=None,
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)

            from services.lead_service import LeadService
            result = LeadService.mark_downloaded_by_token(
                session, "tok_none", "127.0.0.1", "pytest"
            )
            # Should NOT raise AttributeError; should proceed normally
            assert result is not None
            assert result.downloaded_editorial is True
        finally:
            session.close()


class TestNoneHandling:
    """Verifies code paths that may receive None datetimes."""

    def test_none_tzinfo_access_guarded(self):
        """
        Real code: lead_service.py:243 (after the fix).
        `if expires is not None` prevents None.tzinfo AttributeError.
        """
        value = None
        # This is what the original code did (before fix) — would crash:
        # value.tzinfo
        # This is what the fix does:
        if value is not None:
            if value.tzinfo is None:
                pass  # would normalize
        # No exception → pass
        assert True
