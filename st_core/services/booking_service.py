from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import (
    Retreat, RetreatStatus, Booking, BookingStatus,
    Payment, PaymentType, PaymentMethod,
    Participant, RoomAssignment, Lead
)


class BookingService:
    def __init__(self, db: Session):
        self.db = db

    # ── Retreats ──────────────────────────────────

    def create_retreat(self, name: str, description: str = None,
                       location: str = None, start_date: datetime = None,
                       end_date: datetime = None, max_participants: int = 10,
                       price: float = 0.0, currency: str = "EUR",
                       status: str = None) -> Retreat:
        retreat = Retreat(
            name=name,
            description=description,
            location=location,
            start_date=start_date,
            end_date=end_date,
            max_participants=max_participants,
            price=price,
            currency=currency,
            status=RetreatStatus(status or "DRAFT"),
        )
        self.db.add(retreat)
        self.db.commit()
        self.db.refresh(retreat)
        return retreat

    def get_retreat(self, retreat_id: int) -> Optional[Retreat]:
        return self.db.query(Retreat).filter(Retreat.id == retreat_id).first()

    def list_retreats(self, active_only: bool = True) -> list[Retreat]:
        q = self.db.query(Retreat)
        if active_only:
            q = q.filter(Retreat.status == RetreatStatus.ACTIVE)
        return q.order_by(Retreat.start_date.desc()).all()

    def get_upcoming_retreats(self, limit: int = 10) -> list[Retreat]:
        now = datetime.utcnow()
        return (
            self.db.query(Retreat)
            .filter(Retreat.status == RetreatStatus.ACTIVE, Retreat.start_date >= now)
            .order_by(Retreat.start_date.asc())
            .limit(limit)
            .all()
        )

    # ── Capacity ──────────────────────────────────

    def get_confirmed_seats(self, retreat_id: int) -> int:
        result = (
            self.db.query(func.coalesce(func.sum(Booking.seats_reserved), 0))
            .filter(
                Booking.retreat_id == retreat_id,
                Booking.status.in_([BookingStatus.RESERVED, BookingStatus.CONFIRMED]),
            )
            .scalar()
        )
        return result or 0

    def get_waiting_count(self, retreat_id: int) -> int:
        return (
            self.db.query(func.count(Booking.id))
            .filter(
                Booking.retreat_id == retreat_id,
                Booking.status == BookingStatus.WAITING,
            )
            .scalar()
        ) or 0

    def seats_available(self, retreat_id: int) -> int:
        retreat = self.get_retreat(retreat_id)
        if not retreat:
            return 0
        used = self.get_confirmed_seats(retreat_id)
        return max(0, retreat.max_participants - used)

    # ── Bookings ──────────────────────────────────

    def create_booking(self, lead_id: int, retreat_id: int,
                       seats_reserved: int = 1, notes: str = None) -> Booking:
        retreat = self.get_retreat(retreat_id)
        if not retreat:
            raise ValueError("Retreat not found")

        available = self.seats_available(retreat_id)
        is_waiting = available < seats_reserved

        status = BookingStatus.WAITING if is_waiting else BookingStatus.RESERVED
        deposit_amount = retreat.price * 0.3

        booking = Booking(
            lead_id=lead_id,
            retreat_id=retreat_id,
            status=status,
            seats_reserved=seats_reserved,
            total_amount=retreat.price * seats_reserved,
            deposit_amount=deposit_amount * seats_reserved,
            notes=notes,
        )
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)

        self._create_event(lead_id, "booking_created",
                           f"Booking {'waiting' if is_waiting else 'reserved'} for {retreat.name}")

        return booking

    def confirm_booking(self, booking_id: int) -> Optional[Booking]:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking or booking.status != BookingStatus.RESERVED:
            return None
        booking.status = BookingStatus.CONFIRMED
        self.db.commit()
        self.db.refresh(booking)
        self._create_event(booking.lead_id, "booking_confirmed",
                           f"Booking confirmed for retreat {booking.retreat_id}")
        return booking

    def cancel_booking(self, booking_id: int) -> Optional[Booking]:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return None
        old_status = booking.status
        booking.status = BookingStatus.CANCELLED
        self.db.commit()
        self.db.refresh(booking)
        self._create_event(booking.lead_id, "booking_cancelled",
                           f"Booking cancelled for retreat {booking.retreat_id}")

        if old_status in (BookingStatus.RESERVED, BookingStatus.CONFIRMED):
            self._promote_waiting(booking.retreat_id)

        return booking

    def complete_booking(self, booking_id: int) -> Optional[Booking]:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return None
        booking.status = BookingStatus.COMPLETED
        self.db.commit()
        self.db.refresh(booking)
        self._create_event(booking.lead_id, "booking_completed",
                           f"Booking completed for retreat {booking.retreat_id}")
        return booking

    def get_lead_bookings(self, lead_id: int) -> list[Booking]:
        return (
            self.db.query(Booking)
            .filter(Booking.lead_id == lead_id)
            .order_by(Booking.created_at.desc())
            .all()
        )

    def get_booking(self, booking_id: int) -> Optional[Booking]:
        return self.db.query(Booking).filter(Booking.id == booking_id).first()

    # ── Payments ──────────────────────────────────

    def record_payment(self, booking_id: int, amount: float,
                       payment_type: str = "DEPOSIT",
                       payment_method: str = None,
                       notes: str = None) -> Payment:
        booking = self.get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")

        payment = Payment(
            booking_id=booking_id,
            amount=amount,
            payment_type=PaymentType(payment_type),
            payment_method=PaymentMethod(payment_method) if payment_method else None,
            notes=notes,
            paid_at=datetime.utcnow(),
        )
        self.db.add(payment)

        if payment_type == "DEPOSIT":
            booking.deposit_paid = True
        elif payment_type == "BALANCE":
            booking.balance_paid = True

        self.db.commit()
        self.db.refresh(payment)
        self._create_event(booking.lead_id, "payment_recorded",
                           f"{payment_type} payment of {amount} recorded for booking {booking_id}")
        return payment

    def get_booking_payments(self, booking_id: int) -> list[Payment]:
        return (
            self.db.query(Payment)
            .filter(Payment.booking_id == booking_id)
            .order_by(Payment.created_at.desc())
            .all()
        )

    # ── Participants ──────────────────────────────

    def add_participant(self, booking_id: int, first_name: str, last_name: str,
                        email: str = None, passport_number: str = None,
                        nationality: str = None, date_of_birth: datetime = None,
                        special_requirements: str = None) -> Participant:
        participant = Participant(
            booking_id=booking_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            passport_number=passport_number,
            nationality=nationality,
            date_of_birth=date_of_birth,
            special_requirements=special_requirements,
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def get_booking_participants(self, booking_id: int) -> list[Participant]:
        return (
            self.db.query(Participant)
            .filter(Participant.booking_id == booking_id)
            .all()
        )

    # ── Dashboard Stats ───────────────────────────

    def get_booking_stats(self) -> dict:
        booked = self.db.query(func.count(Booking.id)).filter(
            Booking.status.in_([BookingStatus.RESERVED, BookingStatus.CONFIRMED])
        ).scalar() or 0
        waiting = self.db.query(func.count(Booking.id)).filter(
            Booking.status == BookingStatus.WAITING
        ).scalar() or 0
        total_seats = self.db.query(func.coalesce(func.sum(Retreat.max_participants), 0)).filter(
            Retreat.status == RetreatStatus.ACTIVE
        ).scalar() or 0
        used_seats = self.db.query(func.coalesce(func.sum(Booking.seats_reserved), 0)).filter(
            Booking.status.in_([BookingStatus.RESERVED, BookingStatus.CONFIRMED])
        ).scalar() or 0
        revenue = self.db.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
        pending_deposits = self.db.query(func.count(Booking.id)).filter(
            Booking.status.in_([BookingStatus.RESERVED, BookingStatus.CONFIRMED]),
            Booking.deposit_paid == False
        ).scalar() or 0
        pending_balance = self.db.query(func.count(Booking.id)).filter(
            Booking.status.in_([BookingStatus.RESERVED, BookingStatus.CONFIRMED]),
            Booking.balance_paid == False
        ).scalar() or 0
        return {
            "seats_available": max(0, total_seats - used_seats),
            "booked": booked,
            "waiting": waiting,
            "revenue": revenue,
            "pending_deposits": pending_deposits,
            "pending_balance": pending_balance,
        }

    # ── Internals ─────────────────────────────────

    def _promote_waiting(self, retreat_id: int):
        waiting = (
            self.db.query(Booking)
            .filter(
                Booking.retreat_id == retreat_id,
                Booking.status == BookingStatus.WAITING,
            )
            .order_by(Booking.created_at.asc())
            .first()
        )
        if waiting:
            available = self.seats_available(retreat_id)
            if available >= waiting.seats_reserved:
                waiting.status = BookingStatus.RESERVED
                self.db.commit()
                self._create_event(waiting.lead_id, "booking_promoted",
                                   f"Promoted from waiting list for retreat {retreat_id}")

    def _create_event(self, lead_id: int, event_type: str, title: str):
        try:
            from services.lead_service import LeadService
            LeadService._create_event(self.db, lead_id, event_type, title, title)
        except Exception:
            pass
