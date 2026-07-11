from abc import ABC, abstractmethod

class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, html_body: str, lead_id: int, email_type: str) -> bool:
        ...
