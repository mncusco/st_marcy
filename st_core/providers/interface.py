from abc import ABC, abstractmethod


class EmailSendError(Exception):
    """Raised by a provider when the send fails, carrying the upstream error message."""
    pass


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        ...
