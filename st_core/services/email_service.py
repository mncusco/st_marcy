from __future__ import annotations

class EmailService:
    def send_editorial(self, to_email: str, language: str) -> bool:
        raise NotImplementedError

    def send_followup(self, to_email: str, lead_id: int) -> bool:
        raise NotImplementedError

    def send_interview(self, to_email: str, lead_id: int, scheduled_date: str) -> bool:
        raise NotImplementedError
