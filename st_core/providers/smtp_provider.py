import logging
from providers.interface import EmailProvider
from config import settings

logger = logging.getLogger("st_core.email")

class SmtpProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        logger.info("SMTP backend not yet implemented")
        logger.info("Would send to %s: %s", to, subject)
        return True
