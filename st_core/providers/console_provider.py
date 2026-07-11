import logging
from providers.interface import EmailProvider

logger = logging.getLogger("st_core.email")

class ConsoleProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        logger.info("=" * 60)
        logger.info("EMAIL (console backend)")
        logger.info("To: %s", to)
        logger.info("Subject: %s", subject)
        logger.info("Lead ID: %d | Type: %s", lead_id, email_type)
        logger.info("Body: %s", html_body[:500])
        logger.info("=" * 60)
        return True
