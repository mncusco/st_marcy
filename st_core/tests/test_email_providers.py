import os
import logging
import io
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

from config import settings
from models import EmailQueue, EmailStatus, Lead


class TestSmtpTimeoutConfig:
    def test_smtp_timeout_default_is_30(self):
        assert settings.SMTP_TIMEOUT == 30

    def test_smtp_timeout_override_via_env(self):
        os.environ["SMTP_TIMEOUT"] = "15"
        from config import Settings
        s = Settings()
        assert s.SMTP_TIMEOUT == 15
        del os.environ["SMTP_TIMEOUT"]

    def test_smtp_timeout_is_int(self):
        assert isinstance(settings.SMTP_TIMEOUT, int)


class TestSmtpProvider:
    def test_smtp_timeout_passed_to_smtp(self):
        from providers.smtp_provider import SmtpProvider
        with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
            mock_instance = MagicMock()
            mock_smtp.return_value = mock_instance
            provider = SmtpProvider()
            result = provider.send("test@example.com", "Subject", "<p>Hi</p>", 1, "test")
            mock_smtp.assert_called_once_with(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT
            )
            assert result is True

    def test_smtp_ssl_timeout_passed_to_smtp_ssl(self):
        from providers.smtp_provider import SmtpProvider
        original_ssl = settings.SMTP_SSL
        original_tls = settings.SMTP_TLS
        settings.SMTP_SSL = True
        settings.SMTP_TLS = False
        try:
            with patch("providers.smtp_provider.smtplib.SMTP_SSL") as mock_ssl:
                mock_instance = MagicMock()
                mock_ssl.return_value = mock_instance
                provider = SmtpProvider()
                result = provider.send("test@example.com", "Subject", "<p>Hi</p>", 1, "test")
                mock_ssl.assert_called_once_with(
                    settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT
                )
                assert result is True
        finally:
            settings.SMTP_SSL = original_ssl
            settings.SMTP_TLS = original_tls

    def test_smtp_auth_error_returns_false(self):
        from providers.smtp_provider import SmtpProvider
        original_user = settings.SMTP_USERNAME
        original_pass = settings.SMTP_PASSWORD
        settings.SMTP_USERNAME = "bot@example.com"
        settings.SMTP_PASSWORD = "secret"
        try:
            with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
                mock_instance = MagicMock()
                mock_instance.login.side_effect = Exception("Authentication failed")
                mock_smtp.return_value = mock_instance
                provider = SmtpProvider()
                result = provider.send("test@example.com", "Subject", "<p>Hi</p>", 1, "test")
                assert result is False
        finally:
            settings.SMTP_USERNAME = original_user
            settings.SMTP_PASSWORD = original_pass

    def test_smtp_connection_error_returns_false(self):
        from providers.smtp_provider import SmtpProvider
        with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = TimeoutError("Connection timed out")
            provider = SmtpProvider()
            result = provider.send("test@example.com", "Subject", "<p>Hi</p>", 1, "test")
            assert result is False

    def test_smtp_sendmail_called_with_correct_args(self):
        from providers.smtp_provider import SmtpProvider
        with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
            mock_instance = MagicMock()
            mock_smtp.return_value = mock_instance
            provider = SmtpProvider()
            result = provider.send("alice@example.com", "Hello", "<p>Body</p>", 42, "test_type")
            mock_instance.sendmail.assert_called_once()
            args, _ = mock_instance.sendmail.call_args
            assert args[0] == settings.FROM_EMAIL
            assert args[1] == ["alice@example.com"]
            assert result is True

    def test_smtp_with_username_logs_in(self):
        from providers.smtp_provider import SmtpProvider
        original_user = settings.SMTP_USERNAME
        original_pass = settings.SMTP_PASSWORD
        settings.SMTP_USERNAME = "bot@example.com"
        settings.SMTP_PASSWORD = "secret"
        try:
            with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
                mock_instance = MagicMock()
                mock_smtp.return_value = mock_instance
                provider = SmtpProvider()
                provider.send("test@example.com", "S", "<p>B</p>", 1, "t")
                mock_instance.login.assert_called_once_with("bot@example.com", "secret")
        finally:
            settings.SMTP_USERNAME = original_user
            settings.SMTP_PASSWORD = original_pass

    def test_smtp_without_username_skips_login(self):
        from providers.smtp_provider import SmtpProvider
        original_user = settings.SMTP_USERNAME
        settings.SMTP_USERNAME = ""
        try:
            with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
                mock_instance = MagicMock()
                mock_smtp.return_value = mock_instance
                provider = SmtpProvider()
                provider.send("test@example.com", "S", "<p>B</p>", 1, "t")
                mock_instance.login.assert_not_called()
        finally:
            settings.SMTP_USERNAME = original_user


class TestConsoleProvider:
    def test_console_provider_returns_true(self):
        from providers.console_provider import ConsoleProvider
        provider = ConsoleProvider()
        result = provider.send("test@example.com", "Test", "<p>Hi</p>", 1, "test")
        assert result is True

    def test_console_provider_logs_output(self):
        from providers.console_provider import ConsoleProvider
        logger = logging.getLogger("st_core.email")
        original_level = logger.level
        logger.setLevel(logging.INFO)
        try:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.INFO)
            logger.addHandler(handler)
            provider = ConsoleProvider()
            provider.send("alice@example.com", "Welcome", "<p>Body</p>", 7, "welcome_email")
            logger.removeHandler(handler)
            output = stream.getvalue()
            assert "alice@example.com" in output
            assert "Welcome" in output
            assert "(console backend)" in output
        finally:
            logger.setLevel(original_level)

    def test_console_provider_body_preview(self):
        from providers.console_provider import ConsoleProvider
        logger = logging.getLogger("st_core.email")
        original_level = logger.level
        logger.setLevel(logging.INFO)
        try:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.INFO)
            logger.addHandler(handler)
            provider = ConsoleProvider()
            long_body = "<p>" + "A" * 1000 + "</p>"
            provider.send("test@example.com", "S", long_body, 1, "t")
            logger.removeHandler(handler)
            output = stream.getvalue()
            assert len(long_body) > 500
            assert "Body:" in output
            assert len(output) > 100
        finally:
            logger.setLevel(original_level)


class TestStubProviders:
    def test_resend_provider_returns_false(self):
        from providers.resend_provider import ResendProvider
        provider = ResendProvider()
        result = provider.send("test@example.com", "Test", "<p>Hi</p>", 1, "test")
        assert result is False

    def test_sendgrid_provider_returns_false(self):
        from providers.sendgrid_provider import SendgridProvider
        provider = SendgridProvider()
        result = provider.send("test@example.com", "Test", "<p>Hi</p>", 1, "test")
        assert result is False

    def test_resend_provider_logs_error(self):
        from providers.resend_provider import ResendProvider
        logger = logging.getLogger("st_core.email")
        original_level = logger.level
        logger.setLevel(logging.ERROR)
        try:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.ERROR)
            logger.addHandler(handler)
            provider = ResendProvider()
            provider.send("alice@example.com", "Subj", "<p>Body</p>", 5, "test_type")
            logger.removeHandler(handler)
            output = stream.getvalue()
            assert "NOT IMPLEMENTED" in output
            assert "alice@example.com" in output
            assert "Resend" in output
        finally:
            logger.setLevel(original_level)

    def test_sendgrid_provider_logs_error(self):
        from providers.sendgrid_provider import SendgridProvider
        logger = logging.getLogger("st_core.email")
        original_level = logger.level
        logger.setLevel(logging.ERROR)
        try:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.ERROR)
            logger.addHandler(handler)
            provider = SendgridProvider()
            provider.send("bob@example.com", "Subj", "<p>Body</p>", 3, "test_type")
            logger.removeHandler(handler)
            output = stream.getvalue()
            assert "NOT IMPLEMENTED" in output
            assert "bob@example.com" in output
            assert "SendGrid" in output
        finally:
            logger.setLevel(original_level)


class TestEmailEngineSMTP:
    def test_diagnose_includes_timeout(self, db_session):
        from services.email_engine import EmailEngine
        engine = EmailEngine(db_session)
        diag = engine.diagnose()
        assert "timeout" in diag
        assert diag["timeout"] == settings.SMTP_TIMEOUT

    def test_send_test_email_with_console_returns_success(self, db_session):
        from services.email_engine import EmailEngine
        engine = EmailEngine(db_session)
        result = engine.send_test_email("test@example.com")
        assert result["success"] is True
        assert result["backend"] == "log"

    def test_process_pending_retries_failed(self, db_session):
        lead = Lead(first_name="Retry", last_name="Test", email="retry@example.com",
                    download_token="tok_retry",
                    download_expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        db_session.add(lead)
        db_session.commit()
        entry = EmailQueue(
            lead_id=lead.id, email_type="test", subject="Retry",
            language="en", template_name="editorial_download",
            status=EmailStatus.FAILED, attempts=3,
            error_message="Previous failure",
            scheduled_for=datetime.now(timezone.utc),
        )
        db_session.add(entry)
        db_session.commit()
        from services.email_engine import EmailEngine
        engine = EmailEngine(db_session)
        result = engine.retry_email(entry.id)
        assert result is True
        db_session.refresh(entry)
        assert entry.status == EmailStatus.PENDING
        assert entry.attempts == 0

    def test_smtp_unreachable_via_engine(self, db_session):
        from services.email_engine import EmailEngine
        original_backend = settings.EMAIL_BACKEND
        original_host = settings.SMTP_HOST
        original_port = settings.SMTP_PORT
        settings.EMAIL_BACKEND = "smtp"
        settings.SMTP_HOST = "192.0.2.1"
        settings.SMTP_PORT = 25
        try:
            engine = EmailEngine(db_session)
            result = engine.send_test_email("test@example.com")
            assert result["success"] is False
            assert result["backend"] == "smtp"
        finally:
            settings.EMAIL_BACKEND = original_backend
            settings.SMTP_HOST = original_host
            settings.SMTP_PORT = original_port


class TestEmailLogging:
    def test_smtp_failure_logged(self, caplog):
        caplog.set_level(logging.ERROR)
        from providers.smtp_provider import SmtpProvider
        with patch("providers.smtp_provider.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = ConnectionRefusedError("Connection refused")
            provider = SmtpProvider()
            provider.send("test@example.com", "Test", "<p>Hi</p>", 1, "test")
            assert any("SMTP failed" in rec.message for rec in caplog.records)

    def test_stub_provider_logs_error_on_use(self, caplog):
        caplog.set_level(logging.ERROR)
        from providers.resend_provider import ResendProvider
        provider = ResendProvider()
        provider.send("test@example.com", "Test", "<p>Hi</p>", 1, "test")
        assert any("NOT IMPLEMENTED" in rec.message for rec in caplog.records)
