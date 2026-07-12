import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import Task, TaskStatus, Reminder, ReminderType, Notification, LeadEvent, Lead

REMINDER_DELAYS = {
    ReminderType.FOLLOWUP_3D: timedelta(days=3),
    ReminderType.FOLLOWUP_7D: timedelta(days=7),
    ReminderType.FOLLOWUP_14D: timedelta(days=14),
    ReminderType.FOLLOWUP_30D: timedelta(days=30),
}

class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, title: str, lead_id: Optional[int] = None,
                    description: Optional[str] = None, priority: str = "normal",
                    due_at: Optional[datetime] = None,
                    assigned_to: Optional[str] = None,
                    created_by: Optional[str] = None) -> Task:
        task = Task(
            lead_id=lead_id,
            title=title,
            description=description,
            priority=priority,
            due_at=due_at,
            assigned_to=assigned_to,
            created_by=created_by,
        )
        self.db.add(task)
        self.db.flush()

        if lead_id:
            self._create_timeline_event(lead_id, "task_created",
                f"Task created: {title}", created_by=created_by)

        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task(self, task_id: int, **kwargs) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")

        old_status = task.status
        for key, value in kwargs.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)

        if "status" in kwargs and kwargs["status"] != old_status.value:
            new_status = kwargs["status"]
            if new_status == TaskStatus.COMPLETED.value:
                task.completed_at = datetime.utcnow()
            if task.lead_id:
                self._create_timeline_event(task.lead_id, "task_status_changed",
                    f"Task '{task.title}': {old_status.value} -> {new_status}")

        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False
        self.db.delete(task)
        self.db.commit()
        return True

    def get_task(self, task_id: int) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_lead_tasks(self, lead_id: int) -> list[Task]:
        return self.db.query(Task).filter(
            Task.lead_id == lead_id
        ).order_by(desc(Task.created_at)).all()

    def get_today_tasks(self) -> list[Task]:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today_start + timedelta(days=1)
        return self.db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.due_at >= today_start,
            Task.due_at < tomorrow,
        ).order_by(Task.due_at.asc()).all()

    def get_overdue_tasks(self) -> list[Task]:
        now = datetime.utcnow()
        return self.db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.due_at < now,
        ).order_by(Task.due_at.asc()).all()

    def create_reminder(self, lead_id: int, reminder_type: ReminderType,
                        title: str, message: Optional[str] = None,
                        base_date: Optional[datetime] = None) -> Reminder:
        delay = REMINDER_DELAYS.get(reminder_type, timedelta(days=3))
        remind_at = (base_date or datetime.utcnow()) + delay

        reminder = Reminder(
            lead_id=lead_id,
            reminder_type=reminder_type,
            title=title,
            message=message,
            remind_at=remind_at,
        )
        self.db.add(reminder)
        self.db.flush()

        self._create_timeline_event(lead_id, "reminder_created",
            f"Reminder set: {title}",
            f"Scheduled for {remind_at.strftime('%Y-%m-%d')}",
            metadata_json={"reminder_type": reminder_type.value, "remind_at": str(remind_at)})

        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def get_active_reminders(self) -> list[Reminder]:
        return self.db.query(Reminder).filter(
            Reminder.status == "active",
            Reminder.notified == False,
            Reminder.remind_at <= datetime.utcnow(),
        ).order_by(Reminder.remind_at.asc()).all()

    def mark_reminder_notified(self, reminder_id: int) -> Reminder:
        r = self.db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if r:
            r.notified = True
            r.notified_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(r)
        return r

    def create_notification(self, lead_id: Optional[int], title: str,
                            message: Optional[str] = None,
                            notification_type: str = "system") -> Notification:
        n = Notification(
            lead_id=lead_id,
            title=title,
            message=message,
            notification_type=notification_type,
        )
        self.db.add(n)
        self.db.commit()
        self.db.refresh(n)
        return n

    def get_unread_notifications(self, limit: int = 20) -> list[Notification]:
        return self.db.query(Notification).filter(
            Notification.read == False
        ).order_by(desc(Notification.created_at)).limit(limit).all()

    def mark_notification_read(self, notification_id: int) -> Optional[Notification]:
        n = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if n:
            n.read = True
            n.read_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(n)
        return n

    def get_lead_reminders(self, lead_id: int) -> list[Reminder]:
        return self.db.query(Reminder).filter(
            Reminder.lead_id == lead_id
        ).order_by(desc(Reminder.created_at)).all()

    def auto_create_followup_reminders(self, lead: Lead):
        now = datetime.utcnow()
        existing = {r.reminder_type for r in self.db.query(Reminder.reminder_type).filter(
            Reminder.lead_id == lead.id, Reminder.status == "active").all()}

        reminders_to_create = []
        if ReminderType.FOLLOWUP_3D not in existing:
            reminders_to_create.append(ReminderType.FOLLOWUP_3D)
        if ReminderType.FOLLOWUP_7D not in existing:
            reminders_to_create.append(ReminderType.FOLLOWUP_7D)
        if ReminderType.FOLLOWUP_14D not in existing:
            reminders_to_create.append(ReminderType.FOLLOWUP_14D)
        if ReminderType.FOLLOWUP_30D not in existing:
            reminders_to_create.append(ReminderType.FOLLOWUP_30D)

        for rtype in reminders_to_create:
            delay = REMINDER_DELAYS[rtype]
            title_map = {
                ReminderType.FOLLOWUP_3D: "3-Day Follow-up",
                ReminderType.FOLLOWUP_7D: "7-Day Follow-up",
                ReminderType.FOLLOWUP_14D: "14-Day Follow-up",
                ReminderType.FOLLOWUP_30D: "30-Day Follow-up",
            }
            self.create_reminder(
                lead_id=lead.id,
                reminder_type=rtype,
                title=title_map[rtype],
                message=f"Follow-up reminder for {lead.first_name} {lead.last_name}",
                base_date=now,
            )

    def _create_timeline_event(self, lead_id: int, event_type: str, title: str,
                               description: str = None, created_by: str = None,
                               metadata_json: dict = None):
        event = LeadEvent(
            lead_id=lead_id,
            event_type=event_type,
            title=title,
            description=description,
            metadata_json=json.dumps(metadata_json) if metadata_json else None,
            created_by=created_by,
        )
        self.db.add(event)
        self.db.flush()
