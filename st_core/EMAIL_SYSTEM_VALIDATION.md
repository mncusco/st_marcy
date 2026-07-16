# Email Subsystem Validation Report

**Date:** 2026-07-15
**Validator:** opencode agent

## Summary

| Section | Checks | Pass | Fail |
|---|---|---|---|
| Provider Loading | 9 | 9 | 0 |
| Template Rendering | 44 | 44 | 0 |
| Queue & Send Pipeline | 8 | 8 | 0 |
| Retry Logic | 4 | 4 | 0 |
| Test Email | 4 | 4 | 0 |
| Queue Stats | 3 | 3 | 0 |
| Diagnostics | 5 | 5 | 0 |
| Error Handling | 2 | 2 | 0 |
| Max Retries | 1 | 1 | 0 |
| SMTP Specific | 3 | 3 | 0 |
| UTF-8 Encoding | 2 | 2 | 0 |
| **Total** | **87** | **87** | **0** |

## Provider Coverage

| Provider | Type | Status |
|---|---|---|
| ConsoleProvider | Real (log) | Instantiated, sends correctly |
| SmtpProvider | Real (smtplib) | Instantiated, fails gracefully on unreachable host |
| ResendProvider | **Stub** | Returns `True`, logs "not yet implemented" — **silent data loss risk** |
| SendgridProvider | **Stub** | Returns `True`, logs "not yet implemented" — **silent data loss risk** |

**Key finding:** Both ResendProvider and SendgridProvider are stubs that return `True` without sending. If `EMAIL_BACKEND=resend` or `EMAIL_BACKEND=sendgrid` is configured in production, all emails will be silently dropped.

## Template Coverage

- **7 template types:** editorial_download, followup_3_days, interview_invitation, approved, rejected, journey_reminder, completion
- **5 languages:** en, es, it, ru, sr
- **35/35 template files exist** (all combos)
- **Fallback** to English works for missing language (tested with `de`)
- **Missing template** raises `FileNotFoundError` (caught by engine, email marked FAILED)
- **UTF-8 rendering** preserves accented/Unicode characters (tested with `Mëtiñg`)

## Pipeline

- Queue ✅ → PENDING ✅ → Process ✅ → SENT ✅
- Future email: stays PENDING ✅
- Cancel: CANCELLED ✅
- Cancel non-existent: `False` ✅
- Orphan lead (missing Lead): FAILED ✅
- Bad template: FAILED ✅
- Max retries exhausted (3): FAILED ✅

## Retry Logic

- Retry FAILED email: resets to PENDING, attempts→0 ✅
- Retry SENT email: returns `False` ✅

## SMTP Provider

- `_html_to_plain()` works ✅
- Unreachable host caught by `except Exception` → returns `False` (no unhandled crash) ✅
- **No `timeout` parameter passed to `smtplib.SMTP()`** — defaults to `None` (blocking). On a non-responsive host, the thread will hang indefinitely. This is a **latent issue** for production SMTP use.

## Verdict: **EMAIL READY** (with caveats)

The email subsystem is **production ready for the `log` (ConsoleProvider) backend**, which is the current default. The queue, retry, cancellation, template rendering, and error handling pipelines all function correctly.

### Before switching to SMTP production, fix:
1. **Add `timeout` parameter** to `SmtpProvider.send()` (`smtplib.SMTP(host, port, timeout=10)`)
2. **Document SMTP env vars** in `.env.example` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_TLS`, `SMTP_SSL`, `FROM_EMAIL`, `FROM_NAME`, `EMAIL_BACKEND`, `EMAIL_MAX_RETRIES`)
3. **Do not deploy** with `EMAIL_BACKEND=resend` or `EMAIL_BACKEND=sendgrid` — both are stubs that silently discard emails
