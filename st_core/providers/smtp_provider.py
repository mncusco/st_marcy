import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from providers.interface import EmailProvider
from config import settings

logger = logging.getLogger("st_core.email")

class SmtpProvider(EmailProvider):
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
            msg["To"] = to
            msg["Subject"] = subject
            if settings.CONTACT_EMAIL:
                msg["Reply-To"] = settings.CONTACT_EMAIL

            plain_text = self._html_to_plain(html_body)
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            if settings.SMTP_SSL:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                if settings.SMTP_TLS:
                    server.starttls()

            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            server.sendmail(settings.FROM_EMAIL, [to], msg.as_string())
            server.quit()

            logger.info(
                "SMTP sent to=%s subject=%s lead_id=%d type=%s",
                to, subject, lead_id, email_type,
            )
            return True

        except Exception as e:
            logger.exception(
                "SMTP failed to=%s subject=%s lead_id=%d type=%s: %s",
                to, subject, lead_id, email_type, e,
            )
            return False

    def _html_to_plain(self, html: str) -> str:
        import re
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
