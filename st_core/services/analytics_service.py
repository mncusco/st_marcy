from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import Lead, LeadStatus, DownloadEvent


class AnalyticsService:

    def __init__(self, db: Session):
        self.db = db

    def get_conversion_metrics(self):
        total_leads = self.db.query(func.count(Lead.id)).scalar() or 0
        downloads = self.db.query(func.count(Lead.id)).filter(
            Lead.downloaded_editorial == True
        ).scalar() or 0
        interviews = self.db.query(func.count(Lead.id)).filter(
            Lead.status.in_([LeadStatus.INTERVIEW, LeadStatus.APPROVED,
                             LeadStatus.BOOKED, LeadStatus.COMPLETED])
        ).scalar() or 0
        approved = self.db.query(func.count(Lead.id)).filter(
            Lead.status.in_([LeadStatus.APPROVED, LeadStatus.BOOKED,
                             LeadStatus.COMPLETED])
        ).scalar() or 0
        booked = self.db.query(func.count(Lead.id)).filter(
            Lead.status.in_([LeadStatus.BOOKED, LeadStatus.COMPLETED])
        ).scalar() or 0
        completed = self.db.query(func.count(Lead.id)).filter(
            Lead.status == LeadStatus.COMPLETED
        ).scalar() or 0

        def pct(part, total):
            return round((part / total) * 100, 1) if total else 0.0

        return {
            "total_leads": total_leads,
            "downloads": downloads,
            "interviews": interviews,
            "approved": approved,
            "booked": booked,
            "completed": completed,
            "lead_to_download": pct(downloads, total_leads),
            "download_to_interview": pct(interviews, downloads) if downloads else 0.0,
            "interview_to_approved": pct(approved, interviews) if interviews else 0.0,
            "approved_to_booked": pct(booked, approved) if approved else 0.0,
            "booked_to_completed": pct(completed, booked) if booked else 0.0,
        }

    def get_lead_sources(self):
        rows = self.db.query(
            Lead.utm_source,
            Lead.utm_campaign,
            Lead.referrer,
            func.count(Lead.id).label("cnt"),
        ).group_by(
            Lead.utm_source, Lead.utm_campaign, Lead.referrer
        ).all()

        buckets = {"organic": 0, "instagram": 0, "facebook": 0, "direct": 0, "other": 0}
        for r in rows:
            src = (r.utm_source or "").strip().lower()
            ref = (r.referrer or "").strip().lower()
            campaign = (r.utm_campaign or "").strip().lower()

            if src == "organic" or "google" in ref or "search" in ref:
                buckets["organic"] += r.cnt
            elif src == "instagram" or "ig" in src or "instagram" in ref:
                buckets["instagram"] += r.cnt
            elif src == "facebook" or "fb" in src or "facebook" in ref:
                buckets["facebook"] += r.cnt
            elif not src and not ref:
                buckets["direct"] += r.cnt
            else:
                buckets["other"] += r.cnt

        return buckets

    def get_download_statistics(self):
        total = self.db.query(func.count(DownloadEvent.id)).scalar() or 0
        unique_leads = self.db.query(func.count(
            func.distinct(DownloadEvent.lead_id)
        )).scalar() or 0
        return {"total_downloads": total, "unique_leads": unique_leads}

    def get_pipeline_value(self):
        stages = [
            "NEW", "CONTACTED", "INTERVIEW",
            "APPROVED", "BOOKED", "COMPLETED",
            "REJECTED", "ARCHIVED"
        ]
        counts = {}
        for s in stages:
            counts[s] = self.db.query(func.count(Lead.id)).filter(
                Lead.status == LeadStatus(s)
            ).scalar() or 0
        return counts

    def get_monthly_leads(self, months: int = 6):
        since = datetime.now(timezone.utc) - timedelta(days=months * 30)
        rows = self.db.query(
            func.strftime("%Y-%m", Lead.created_at).label("month"),
            func.count(Lead.id).label("cnt"),
        ).filter(
            Lead.created_at >= since
        ).group_by(
            func.strftime("%Y-%m", Lead.created_at)
        ).order_by("month").all()
        return [{"month": r.month, "count": r.cnt} for r in rows]
