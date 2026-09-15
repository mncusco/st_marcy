from abc import ABC, abstractmethod
from typing import Optional


class EmailSendError(Exception):
    """Raised by a provider when the send fails, carrying the upstream error message."""
    pass


class SendOutcome:
    """Esito di un invio. `provider_id` è l'ID restituito dal provider (es. message id Resend)."""

    __slots__ = ("ok", "provider_id")

    def __init__(self, ok: bool, provider_id: Optional[str] = None):
        self.ok = ok
        self.provider_id = provider_id

    def __bool__(self) -> bool:
        return self.ok


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        ...
