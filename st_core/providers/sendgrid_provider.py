import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError
from providers.interface import EmailProvider
from config import settings

logger = logging.getLogger("st_core.email")

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class SendgridProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        api_key = settings.SENDGRID_API_KEY if hasattr(settings, "SENDGRID_API_KEY") and settings.SENDGRID_API_KEY else ""
        if not api_key:
            logger.error("SENDGRID_API_KEY not configured")
            return False

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to}],
                    "subject": subject,
                }
            ],
            "from": {"email": settings.FROM_EMAIL, "name": settings.FROM_NAME},
            "content": [
                {"type": "text/plain", "value": self._html_to_plain(html_body)},
                {"type": "text/html", "value": html_body},
            ],
        }
        if settings.CONTACT_EMAIL:
            payload["reply_to"] = {"email": settings.CONTACT_EMAIL}

        data = json.dumps(payload).encode("utf-8")
        req = Request(
            SENDGRID_API_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            resp = urlopen(req, timeout=30)
            status = resp.status
            resp.read()
            if 200 <= status < 300:
                logger.info("SendGrid sent to=%s subject=%s lead_id=%d type=%s", to, subject, lead_id, email_type)
                return True
            else:
                logger.error("SendGrid returned status %d for to=%s", status, to)
                return False
        except URLError as e:
            logger.exception("SendGrid failed to=%s subject=%s: %s", to, subject, e)
            return False
        except Exception as e:
            logger.exception("SendGrid unexpected error to=%s: %s", to, e)
            return False

    def _html_to_plain(self, html: str) -> str:
        import re
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
