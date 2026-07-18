import json
import logging
import urllib.request
import urllib.error
from providers.interface import EmailProvider
from config import settings

logger = logging.getLogger("st_core.email")


class ResendProvider(EmailProvider):
    API_URL = "https://api.resend.com/emails"

    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        api_key = settings.RESEND_API_KEY
        if not api_key:
            logger.error("RESEND_API_KEY not configured")
            return False

        payload = json.dumps({
            "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
            "to": [to],
            "subject": subject,
            "html": html_body,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=30)
            body = resp.read()
            logger.info("Resend OK to=%s subject=%s lead_id=%d type=%s status=%d", to, subject, lead_id, email_type, resp.status)
            return True
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            logger.error("Resend HTTP %d to=%s lead_id=%d type=%s: %s", e.code, to, lead_id, email_type, error_body)
            return False
        except urllib.error.URLError as e:
            logger.error("Resend network error to=%s lead_id=%d type=%s: %s", to, lead_id, email_type, e.reason)
            return False
