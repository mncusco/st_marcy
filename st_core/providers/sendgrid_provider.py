import logging
from providers.interface import EmailProvider

logger = logging.getLogger("st_core.email")

class SendgridProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        logger.error(
            "SendGrid backend NOT IMPLEMENTED — email to=%s subject=%s lead_id=%d type=%s would be lost",
            to, subject, lead_id, email_type,
        )
        return False
