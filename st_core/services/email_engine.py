import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from config import settings
from models import EmailQueue, EmailStatus, Lead, LeadStatus
from schemas import EmailQueueResponse
from providers import ConsoleProvider, SmtpProvider, ResendProvider, SendgridProvider
from providers.interface import EmailSendError, SendOutcome

logger = logging.getLogger("st_core.email_engine")

BACKEND_MAP = {
    "log": ConsoleProvider,
    "console": ConsoleProvider,
    "smtp": SmtpProvider,
    "resend": ResendProvider,
    "sendgrid": SendgridProvider,
}

# Email che promettono un download: richiedono sempre un download_url valido.
DOWNLOAD_EMAIL_TYPES = ("editorial_download", "editorial_reactivation")

# Stati "attivi" (in pipeline): una sola entry per lead+email_type a questi stati.
ACTIVE_QUEUE_STATUSES = (EmailStatus.PENDING, EmailStatus.PROCESSING, EmailStatus.RETRY)

TEMPLATE_SUBJECTS: dict[str, str | dict[str, str | list[str]]] = {
    "editorial_download": {
        "en": "Your Free Editorial – ST Care",
        "it": "La tua guida gratuita – ST Care",
        "es": "Tu guía gratuita – ST Care",
        "ru": "Ваше бесплатное руководство – ST Care",
        "sr": "Vaš besplatni vodič – ST Care",
    },
    "followup_3_days": {
        "en": "The Forest Called You — Marcello",
        "it": "La foresta ti ha chiamato — Marcello",
        "es": "La selva te llamó — Marcello",
        "ru": "Лес позвал тебя — Марчелло",
        "sr": "Šuma te je pozvala — Marcello",
    },
    "interview_invitation": {
        "en": "Interview Invitation – ST Care",
        "it": "Invito al colloquio – ST Care",
        "es": "Invitación a entrevista – ST Care",
        "ru": "Приглашение на собеседование – ST Care",
        "sr": "Poziv za intervju – ST Care",
    },
    "approved": {
        "en": "Application Approved – ST Care",
        "it": "Candidatura approvata – ST Care",
        "es": "Solicitud aprobada – ST Care",
        "ru": "Заявка одобрена – ST Care",
        "sr": "Prijava odobrena – ST Care",
    },
    "rejected": {
        "en": "Application Update – ST Care",
        "it": "Aggiornamento candidatura – ST Care",
        "es": "Actualización de solicitud – ST Care",
        "ru": "Обновление заявки – ST Care",
        "sr": "Ažuriranje prijave – ST Care",
    },
    "journey_reminder": {
        "en": "Your Journey with ST Care",
        "it": "Il tuo viaggio con ST Care",
        "es": "Tu viaje con ST Care",
        "ru": "Ваше путешествие с ST Care",
        "sr": "Vaše putovanje sa ST Care",
    },
    "completion": {
        "en": "Thank You – ST Care",
        "it": "Grazie – ST Care",
        "es": "Gracias – ST Care",
        "ru": "Спасибо – ST Care",
        "sr": "Hvala – ST Care",
    },
    "editorial_reactivation": {
        "it": [
            "Il Ritiro nella Foresta Amazzonica — Una storia personale",
            "Marcello: come la foresta mi ha cambiato",
            "Il libro che ho scritto per te — Master Plant Dieta",
            "San Alejandro: il mio incontro con Maestro Chichi",
            "Scarica gratuitamente 'Il Ritiro nella Foresta Amazzonica'",
            "La dieta che non dimenticherai — una storia vera",
            "Cosa significa sedersi con la foresta",
            "Il regalo che la foresta mi ha fatto",
            "Maestro Chichi e il potere delle piante madri",
            "Un invito personale da Marcello",
        ],
        "en": [
            "Free Book: A Personal Story from the Amazon",
            "Marcello: How the Forest Changed Me",
            "Download Your Free Copy — Master Plant Dieta",
            "What Happens When You Sit with the Forest",
            "A Personal Invitation from Marcello",
        ],
        "es": [
            "Libro Gratuito: El Retiro en la Selva Amazónica",
            "Marcello: Cómo la Selva Me Cambió",
            "Descarga Gratis la Historia de San Alejandro",
            "Una Invitación Personal de Marcello",
        ],
        "ru": [
            "Бесплатная книга: Личная история из Амазонии",
            "Марчелло: Как лес изменил меня",
            "Скачайте бесплатно — Master Plant Dieta",
            "Что происходит, когда вы сидите с лесом",
            "Личное приглашение от Марчелло",
        ],
        "sr": [
            "Besplatna knjiga: Lična priča iz Amazona",
            "Markelo: Kako me je šuma promenila",
            "Preuzmite besplatno — Master Plant Dieta",
            "Šta se dešava kada sednete sa šumom",
            "Lični poziv od Markela",
        ],
    },
}


class EmailEngine:
    def __init__(self, db: Session):
        self.db = db

    def _get_backend(self):
        key = settings.EMAIL_BACKEND.lower()
        cls = BACKEND_MAP.get(key, ConsoleProvider)
        return cls()

    @staticmethod
    def _call_backend(backend, **kwargs) -> SendOutcome:
        send_verbose = getattr(backend, "send_verbose", None)
        if callable(send_verbose):
            return send_verbose(**kwargs)
        ok = backend.send(**kwargs)
        return SendOutcome(ok=ok, provider_id=None)

    def send_test_email(self, to: str) -> dict:
        try:
            html_body = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f2ec;color:#2c2c2c;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e8e3da;padding:40px;">
<div style="text-align:center;margin-bottom:30px;"><span style="font-size:24px;letter-spacing:2px;color:#2d5a27;">ST</span> <span style="font-size:24px;letter-spacing:2px;color:#b89a5a;">CARE</span></div>
<h1 style="font-size:20px;font-weight:400;letter-spacing:1px;color:#2d5a27;text-align:center;">Test Email</h1>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">This is a test email from ST CORE.</p>
<p style="font-size:14px;line-height:1.6;">Backend: <strong>{settings.EMAIL_BACKEND}</strong></p>
<p style="font-size:14px;line-height:1.6;">If you received this, your email configuration is working correctly.</p>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">— ST CORE</p>
</div></body></html>"""
            backend = self._get_backend()
            outcome = self._call_backend(
                backend,
                to=to,
                subject=f"Test Email from ST CORE ({settings.EMAIL_BACKEND})",
                html_body=html_body,
                lead_id=0,
                email_type="test",
            )
            return {
                "success": outcome.ok,
                "backend": settings.EMAIL_BACKEND,
                "to": to,
                "provider_message_id": outcome.provider_id,
            }
        except Exception as e:
            logger.exception("Test email failed: %s", e)
            return {"success": False, "error": str(e)}

    def diagnose(self) -> dict:
        results = {
            "backend": settings.EMAIL_BACKEND,
            "host": getattr(settings, "SMTP_HOST", None),
            "port": getattr(settings, "SMTP_PORT", None),
            "tls": getattr(settings, "SMTP_TLS", False),
            "ssl": getattr(settings, "SMTP_SSL", False),
            "username_configured": bool(getattr(settings, "SMTP_USERNAME", None)),
            "password_configured": bool(getattr(settings, "SMTP_PASSWORD", None)),
            "from_email": getattr(settings, "FROM_EMAIL", None),
            "from_name": getattr(settings, "FROM_NAME", None),
            "contact_email": getattr(settings, "CONTACT_EMAIL", None),
            "timeout": getattr(settings, "SMTP_TIMEOUT", 30),
            "retry_count": getattr(settings, "EMAIL_MAX_RETRIES", 3),
            "queue_stats": self.get_queue_stats(),
            "connection_test": None,
            "latency_ms": None,
            "error": None,
        }
        if settings.EMAIL_BACKEND.lower() in ("smtp",):
            import smtplib
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(settings.SMTP_TIMEOUT)
            try:
                start = time.time()
                timeout = settings.SMTP_TIMEOUT
                if settings.SMTP_SSL:
                    server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
                else:
                    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
                    server.ehlo()
                    if settings.SMTP_TLS:
                        server.starttls()
                        server.ehlo()
                results["latency_ms"] = round((time.time() - start) * 1000)
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    results["auth_test"] = "ok"
                results["connection_test"] = "ok"
                server.quit()
            except Exception as e:
                results["connection_test"] = "fail"
                results["error"] = str(e)
            finally:
                sock.close()
        else:
            results["connection_test"] = "skipped"
        last_sent = (
            self.db.query(EmailQueue)
            .filter(EmailQueue.status == EmailStatus.SENT)
            .order_by(EmailQueue.sent_at.desc())
            .first()
        )
        last_failed = (
            self.db.query(EmailQueue)
            .filter(EmailQueue.status == EmailStatus.FAILED)
            .order_by(EmailQueue.created_at.desc())
            .first()
        )
        results["last_sent_at"] = last_sent.sent_at.isoformat() if last_sent else None
        results["last_sent_to"] = (
            self.db.query(Lead.email).filter(Lead.id == last_sent.lead_id).scalar()
            if last_sent else None
        )
        results["last_failed_at"] = last_failed.created_at.isoformat() if last_failed else None
        results["last_failed_error"] = last_failed.error_message if last_failed else None
        return results

    def render_template(self, template_name: str, language: str, context: dict) -> str:
        import os
        from jinja2 import Environment, FileSystemLoader

        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
        loader = FileSystemLoader(templates_dir, encoding="utf-8")
        env = Environment(loader=loader)

        paths = [f"{language}/{template_name}.html"]
        if language != "en":
            paths.append(f"en/{template_name}.html")

        for tmpl in paths:
            try:
                t = env.get_template(tmpl)
                return t.render(**context)
            except Exception as e:
                logger.debug("Template %s not found: %s", tmpl, e)
                continue

        raise FileNotFoundError(f"Template not found in any language: {template_name}")

    def _resolve_subject(self, subject: str | dict[str, str | list[str]], language: str) -> str:
        if isinstance(subject, dict):
            lang_subj = subject.get(language, subject.get("en"))
            if isinstance(lang_subj, list):
                return str(random.choice(lang_subj))
            return str(lang_subj) if lang_subj else str(subject.get(list(subject.keys())[0]))
        return subject

    def _find_active(self, lead_id: int, email_type: str) -> EmailQueue | None:
        return (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.lead_id == lead_id,
                EmailQueue.email_type == email_type,
                EmailQueue.status.in_(ACTIVE_QUEUE_STATUSES),
            )
            .order_by(EmailQueue.created_at.asc())
            .first()
        )

    @staticmethod
    def resolve_download_url(lead: Lead, payload: dict | None) -> str | None:
        """URL di download effettivo per una email che promette il libro.

        Usa payload['download_url']; se assente ma il lead ha un token valido,
        lo ricostruisce dal token (copre le righe storiche con payload parziale).
        """
        payload = payload or {}
        url = payload.get("download_url")
        if url:
            return str(url)
        token = payload.get("download_token") or getattr(lead, "download_token", None)
        if token:
            return f"{str(settings.PUBLIC_URL).rstrip('/')}/download/{token}"
        return None

    def queue_email(
        self,
        lead: Lead,
        email_type: str,
        subject: str | dict[str, str],
        template_name: str,
        payload: Optional[dict] = None,
        scheduled_for: Optional[datetime] = None,
        dedupe: bool = True,
    ) -> EmailQueue | None:
        """Accoda un'email con protezione anti-duplicati.

        Se esiste già una entry attiva (PENDING/PROCESSING) per lo stesso
        lead+email_type, restituisce quella esistente. Il vincolo unico
        parziale sul DB è il backstop contro le race condition tra worker.
        """
        lang = lead.language or "en"
        normalized = lang.lower().split("-")[0]
        if normalized not in ("en", "it", "es", "ru", "sr"):
            normalized = "en"

        resolved_subject = self._resolve_subject(subject, normalized)

        if dedupe:
            existing = self._find_active(lead.id, email_type)
            if existing:
                logger.info(
                    "Queue skipped (duplicate): existing %s for lead %d (id=%d)",
                    email_type, lead.id, existing.id,
                )
                return existing

        entry = EmailQueue(
            lead_id=lead.id,
            email_type=email_type,
            subject=resolved_subject,
            language=normalized,
            status=EmailStatus.PENDING,
            template_name=template_name,
            payload_json=json.dumps(payload) if payload else None,
            scheduled_for=scheduled_for or datetime.now(timezone.utc),
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._find_active(lead.id, email_type)
            if existing:
                logger.info(
                    "Queue deduped via unique index for %s lead %d (id=%d)",
                    email_type, lead.id, existing.id,
                )
                return existing
            raise
        self.db.refresh(entry)
        logger.info("Queued %s email for lead %d (id=%d)", email_type, lead.id, entry.id)
        return entry

    def cancel_email(self, email_id: int) -> bool:
        entry = self.db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
        if not entry or entry.status in (EmailStatus.SENT, EmailStatus.CANCELLED):
            return False
        entry.status = EmailStatus.CANCELLED
        self.db.commit()
        return True

    def retry_email(self, email_id: int) -> bool:
        entry = self.db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
        if not entry or entry.status != EmailStatus.FAILED:
            return False
        entry.status = EmailStatus.PENDING
        entry.attempts = 0
        entry.error_message = None
        self.db.commit()
        return True

    def _render_and_send(self, entry: EmailQueue) -> SendOutcome:
        lead = self.db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if not lead:
            logger.error("Lead %d not found for email %d", entry.lead_id, entry.id)
            raise EmailSendError(f"Lead {entry.lead_id} not found")

        payload = json.loads(entry.payload_json) if entry.payload_json else {}
        public_url = str(settings.PUBLIC_URL).rstrip("/")
        base = f"{public_url}/track/click/{entry.id}"
        download_url = self.resolve_download_url(lead, payload)
        if download_url:
            from urllib.parse import quote
            payload["download_url"] = download_url
            payload["click_url"] = f"{base}?url={quote(download_url)}"
            payload["tracking_pixel_url"] = f"{public_url}/track/open/{entry.id}.png"
        context = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "email": lead.email,
            "language": entry.language,
            "queue_id": entry.id,
            "public_url": public_url,
            "_contact_email": settings.CONTACT_EMAIL,
            **payload,
        }
        html_body = self.render_template(entry.template_name, entry.language, context)

        backend = self._get_backend()
        return self._call_backend(
            backend,
            to=lead.email,
            subject=entry.subject,
            html_body=html_body,
            lead_id=lead.id,
            email_type=entry.email_type,
        )

    def _claim_pending(self, limit: int, only_types: list[str] | None = None,
                       exclude_types: list[str] | None = None) -> list[EmailQueue]:
        """Reclama atomicamente le entry PENDING/RETRY pronte, con lock anti-race.

        La transizione PENDING|RETRY→PROCESSING avviene con una singola UPDATE
        condizionale: in caso di worker concorrenti solo uno vince. Registra
        last_attempt_at per recuperare eventuali PROCESSING rimaste orfane.
        """
        now = datetime.now(timezone.utc)
        query = self.db.query(EmailQueue.id).filter(
            EmailQueue.status.in_([EmailStatus.PENDING, EmailStatus.RETRY]),
            EmailQueue.scheduled_for <= now,
            EmailQueue.attempts < settings.EMAIL_MAX_RETRIES,
        )
        if only_types:
            query = query.filter(EmailQueue.email_type.in_(only_types))
        if exclude_types:
            query = query.filter(~EmailQueue.email_type.in_(exclude_types))
        query = query.order_by(EmailQueue.created_at.asc()).limit(limit)

        is_pg = self.db.get_bind().dialect.name == "postgresql"
        if is_pg:
            query = query.with_for_update(skip_locked=True)

        ids = [r[0] for r in query.all()]
        if not ids:
            return []

        claimed = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.id.in_(ids),
                EmailQueue.status.in_([EmailStatus.PENDING, EmailStatus.RETRY]),
            )
            .update(
                {
                    EmailQueue.status: EmailStatus.PROCESSING,
                    EmailQueue.attempts: EmailQueue.attempts + 1,
                    EmailQueue.last_attempt_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        if claimed == 0:
            return []

        return (
            self.db.query(EmailQueue)
            .filter(EmailQueue.id.in_(ids))
            .order_by(EmailQueue.created_at.asc())
            .all()
        )

    def _recover_stale_processing(self) -> int:
        """Recupero PROCESSING rimaste orfane dopo un crash del worker.

        Se una entry è PROCESSING da oltre EMAIL_PROCESSING_STALE_SECONDS senza
        commit, l'esito dell'invio è sconosciuto: la marca FAILED (mai ri-invio
        automatico → nessuna duplicazione involontaria; un admin decide il retry).
        """
        grace = settings.EMAIL_PROCESSING_STALE_SECONDS
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=grace)
        stale = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.status == EmailStatus.PROCESSING,
                EmailQueue.last_attempt_at < cutoff,
            )
            .all()
        )
        for entry in stale:
            entry.status = EmailStatus.FAILED
            entry.error_message = (
                entry.error_message
                or "Worker interrupted before commit — send status unknown, review before resending"
            )
            logger.error(
                "EMAIL RECOVERED stale PROCESSING queue=%d lead=%d type=%s attempts=%d",
                entry.id, entry.lead_id, entry.email_type, entry.attempts,
            )
        if stale:
            self.db.commit()
        return len(stale)

    def _mark_email_sent(self, entry: EmailQueue) -> None:
        """Avanzamento CRM: NEW → EMAIL_SENT alla prima email inviata con successo."""
        try:
            from services.lead_service import advance_funnel_status
            lead = self.db.query(Lead).filter(Lead.id == entry.lead_id).first()
            if lead:
                advance_funnel_status(self.db, lead, LeadStatus.EMAIL_SENT)
        except Exception as e:
            logger.exception("Failed to advance funnel status on email sent for lead %d: %s", entry.lead_id, e)

    def process_pending(self, batch_size: int = 20, only_types: list[str] | None = None,
                        exclude_types: list[str] | None = None) -> int:
        """Processa la coda. SENT viene impostato SOLO se il provider conferma
        l'invio (HTTP 2xx per Resend). Errori temporanei → RETRY con backoff
        esponenziale; esauriti i tentativi → FAILED finale con l'errore reale."""
        self._recover_stale_processing()
        max_retries = settings.EMAIL_MAX_RETRIES
        entries = self._claim_pending(batch_size, only_types=only_types, exclude_types=exclude_types)
        sent_count = 0

        for entry in entries:
            error_msg = None
            outcome = None
            try:
                outcome = self._render_and_send(entry)
            except EmailSendError as e:
                outcome = None
                error_msg = str(e)
            except Exception as e:
                logger.exception("Unhandled error sending email %d: %s", entry.id, e)
                outcome = None
                error_msg = f"{type(e).__name__}: {e}"

            if outcome is not None and outcome.ok:
                entry.status = EmailStatus.SENT
                entry.sent_at = datetime.now(timezone.utc)
                entry.provider_message_id = outcome.provider_id
                entry.last_provider_response = outcome.provider_id or "ok"
                entry.error_message = None
                sent_count += 1
                logger.info(
                    "EMAIL SENT queue=%d lead=%d type=%s provider_id=%s",
                    entry.id, entry.lead_id, entry.email_type, outcome.provider_id,
                )
                self._mark_email_sent(entry)
            else:
                entry.last_provider_response = error_msg or "provider did not accept"
                if entry.attempts >= max_retries:
                    entry.status = EmailStatus.FAILED
                    entry.error_message = error_msg or f"Failed after {entry.attempts} attempts"
                    logger.error(
                        "EMAIL FAILED queue=%d lead=%d type=%s attempts=%d error=%s",
                        entry.id, entry.lead_id, entry.email_type, entry.attempts, entry.error_message,
                    )
                else:
                    backoff = self._backoff_seconds(entry.attempts)
                    entry.status = EmailStatus.RETRY
                    entry.scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                    entry.error_message = error_msg or f"Attempt {entry.attempts}/{max_retries} failed"
                    logger.warning(
                        "EMAIL RETRY queue=%d lead=%d type=%s attempts=%d backoff=%ds error=%s",
                        entry.id, entry.lead_id, entry.email_type, entry.attempts, backoff, entry.error_message,
                    )
            self.db.commit()

        return sent_count

    @staticmethod
    def _backoff_seconds(attempts: int) -> int:
        base = settings.EMAIL_RETRY_BACKOFF_BASE_SECONDS
        cap = settings.EMAIL_RETRY_BACKOFF_MAX_SECONDS
        return min(base * (2 ** max(0, attempts - 1)), cap)

    def get_queue_stats(self):
        total = self.db.query(func.count(EmailQueue.id)).scalar() or 0
        pending = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.PENDING)
            .scalar()
            or 0
        )
        processing = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.PROCESSING)
            .scalar()
            or 0
        )
        retry = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.RETRY)
            .scalar()
            or 0
        )
        failed = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.FAILED)
            .scalar()
            or 0
        )
        sent = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.SENT)
            .scalar()
            or 0
        )
        cancelled = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.CANCELLED)
            .scalar()
            or 0
        )
        total_retries = (
            self.db.query(func.sum(EmailQueue.attempts))
            .filter(EmailQueue.status != EmailStatus.PENDING)
            .scalar()
            or 0
        )
        max_retries = settings.EMAIL_MAX_RETRIES
        return {
            "total": total,
            "pending": pending,
            "processing": processing,
            "retry": retry,
            "failed": failed,
            "sent": sent,
            "cancelled": cancelled,
            "total_retries": total_retries,
            "max_retries": max_retries,
        }

    def get_recent_emails(self, limit: int = 50):
        entries = (
            self.db.query(EmailQueue)
            .order_by(EmailQueue.created_at.desc())
            .limit(limit)
            .all()
        )
        return [EmailQueueResponse.model_validate(e) for e in entries]
