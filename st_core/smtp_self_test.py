"""
SMTP Self-Test - verifies SMTP connectivity and sends one test email.

Usage:
    python smtp_self_test.py

Reads configuration from .env (or environment variables).
Safe to run multiple times - no side effects beyond one test email.
"""

import os
import sys
import time
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.CRITICAL, force=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

PASS = "[OK]"
FAIL = "[FAIL]"


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(label, ok, detail=""):
    icon = PASS if ok else FAIL
    msg = f"  {icon} {label}"
    if detail:
        msg += f" - {detail}"
    print(msg)
    return ok


def main():
    print("SMTP Self-Test - ST CORE")
    print("=" * 60)

    # ── Configuration ──
    section("Configuration")
    backend = settings.EMAIL_BACKEND
    check("EMAIL_BACKEND", backend == "smtp",
          f"current value: {backend!r} (expected 'smtp')")

    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    username = settings.SMTP_USERNAME
    has_password = bool(settings.SMTP_PASSWORD)
    tls = settings.SMTP_TLS
    ssl = settings.SMTP_SSL
    timeout = settings.SMTP_TIMEOUT
    from_email = settings.FROM_EMAIL
    from_name = settings.FROM_NAME

    check("SMTP_HOST", bool(host), f"{host}")
    check("SMTP_PORT", isinstance(port, int) and port > 0, f"{port}")
    check("SMTP_USERNAME", bool(username), repr(username))
    check("SMTP_PASSWORD configured", has_password, "yes" if has_password else "MISSING")
    check("SMTP_TLS or SMTP_SSL", tls or ssl, f"TLS={tls} SSL={ssl}")
    check("SMTP_TIMEOUT", timeout > 0, f"{timeout}s")
    check("FROM_EMAIL", bool(from_email), f"{from_email}")

    if backend != "smtp":
        print(f"\n  {FAIL} Set EMAIL_BACKEND=smtp in .env, then re-run.")
        sys.exit(1)

    # ── Connection ──
    section("Connection")
    start = time.time()
    server = None
    try:
        if ssl:
            check("Connecting with SMTP_SSL", True, f"{host}:{port} (timeout={timeout}s)")
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            check("Connecting with SMTP", True, f"{host}:{port} (timeout={timeout}s)")
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            if tls:
                check("Starting TLS", True)
                server.starttls()
                server.ehlo()
        elapsed = round((time.time() - start) * 1000)
        check("Connection established", True, f"{elapsed}ms")
    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        check("Connection established", False, f"after {elapsed}ms")
        print(f"\n  {FAIL} Connection failed: {e}")
        sys.exit(1)

    # ── Authentication ──
    section("Authentication")
    if username:
        try:
            server.login(username, settings.SMTP_PASSWORD)
            check("SMTP login", True, f"user={username}")
        except smtplib.SMTPAuthenticationError as e:
            check("SMTP login", False, f"Authentication rejected: {e}")
            server.quit()
            sys.exit(1)
        except Exception as e:
            check("SMTP login", False, f"Error: {e}")
            server.quit()
            sys.exit(1)
    else:
        check("SMTP login (no username)", True, "skipped - no credentials configured")

    # ── Send Test Email ──
    section("Send Test Email")
    to = settings.CONTACT_EMAIL or username or "test@example.com"
    subject = f"SMTP Self-Test from ST CORE - {time.strftime('%Y-%m-%d %H:%M:%S')}"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f2ec;color:#2c2c2c;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e8e3da;padding:40px;">
<div style="text-align:center;margin-bottom:30px;">
<span style="font-size:24px;letter-spacing:2px;color:#2d5a27;">ST</span>
<span style="font-size:24px;letter-spacing:2px;color:#b89a5a;">CARE</span>
</div>
<h1 style="font-size:20px;font-weight:400;letter-spacing:1px;color:#2d5a27;text-align:center;">SMTP Self-Test</h1>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">This email confirms SMTP is working.</p>
<p style="font-size:14px;line-height:1.6;"><strong>Host:</strong> {host}:{port}</p>
<p style="font-size:14px;line-height:1.6;"><strong>TLS:</strong> {tls} <strong>SSL:</strong> {ssl}</p>
<p style="font-size:14px;line-height:1.6;"><strong>From:</strong> {from_name} &lt;{from_email}&gt;</p>
<p style="font-size:14px;line-height:1.6;"><strong>Sent at:</strong> {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</p>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">— ST CORE</p>
</div></body></html>"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText("This is a test email from ST CORE.\n\nSMTP is working.\n", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        send_start = time.time()
        server.sendmail(from_email, [to], msg.as_string())
        send_elapsed = round((time.time() - send_start) * 1000)
        check("Email sent", True, f"to={to} ({send_elapsed}ms)")
    except Exception as e:
        check("Email sent", False, str(e))
        try:
            server.quit()
        except Exception:
            pass
        sys.exit(1)

    # ── Cleanup ──
    server.quit()
    total_elapsed = round((time.time() - start) * 1000)
    check("Connection closed", True)

    section("Result")
    print(f"\n  {PASS} SMTP production ready")
    print(f"  Total time: {total_elapsed}ms")
    print(f"  Test email sent to: {to}")
    print(f"\n  {'='*58}")
    print(f"  You can now use EMAIL_BACKEND=smtp in .env")
    print(f"  {'='*58}")


if __name__ == "__main__":
    main()
