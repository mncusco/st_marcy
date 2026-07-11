import json
from datetime import datetime
from sqlalchemy.orm import Session
from models import CandidateAnalysis, Lead


class AIService:

    def __init__(self, db: Session):
        self.db = db

    def analyze_candidate(self, lead: Lead) -> CandidateAnalysis:
        existing = self.db.query(CandidateAnalysis).filter(
            CandidateAnalysis.lead_id == lead.id
        ).first()
        if existing:
            return existing

        score = 75
        strengths = json.dumps([
            "Showed interest by downloading editorial material",
            "Provided complete contact information",
        ])
        concerns = json.dumps([
            "No prior academic record verified",
        ])
        summary = (
            f"{lead.first_name} {lead.last_name} expressed interest "
            f"in the exchange program. Further assessment is needed "
            f"to evaluate academic eligibility."
        )
        recommendation = "Proceed with interview to assess language proficiency and motivation."

        analysis = CandidateAnalysis(
            lead_id=lead.id,
            score=score,
            summary=summary,
            strengths=strengths,
            concerns=concerns,
            recommendation=recommendation,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get_analysis(self, lead_id: int) -> CandidateAnalysis | None:
        return self.db.query(CandidateAnalysis).filter(
            CandidateAnalysis.lead_id == lead_id
        ).first()

    def get_recent_analyses(self, limit: int = 10):
        return (
            self.db.query(CandidateAnalysis)
            .order_by(CandidateAnalysis.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_analysis_stats(self):
        rows = self.db.query(CandidateAnalysis).all()
        if not rows:
            return {"total": 0, "avg_score": 0, "high": 0, "medium": 0, "low": 0}
        scores = [r.score for r in rows]
        avg = sum(scores) / len(scores)
        high = sum(1 for s in scores if s >= 80)
        medium = sum(1 for s in scores if 60 <= s < 80)
        low = sum(1 for s in scores if s < 60)
        return {
            "total": len(rows),
            "avg_score": round(avg, 1),
            "high": high,
            "medium": medium,
            "low": low,
        }
