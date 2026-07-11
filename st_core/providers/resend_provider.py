import logging
from providers.interface import EmailProvider

logger = logging.getLogger("st_core.email")

class ResendProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        logger.info("Resend backend not yet implemented")
        logger.info("Would send to %s: %s", to, subject)
        return True
