import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from core.languages import normalize_language, SUPPORTED_CODES
from models import EditorialEdition, DownloadEvent, Lead

logger = logging.getLogger("st_core.editorial_service")

EDITORIAL_NAMES: dict[str, str] = {
    "en": "Private Collector Guide English",
    "it": "Guida Privata Collezionista Italiano",
    "es": "Guía Privada del Coleccionista Español",
    "ru": "Частное руководство коллекционера Русский",
    "sr": "Privatni Vodič Kolekcionara Srpski",
}


def get_or_create_editorial(db: Session, language: str) -> EditorialEdition:
    lang = normalize_language(language)
    edition = db.query(EditorialEdition).filter(EditorialEdition.language == lang).first()
    if edition:
        return edition

    edition = EditorialEdition(
        language=lang,
        name=EDITORIAL_NAMES.get(lang, f"Editorial {lang.upper()}"),
        file_path=f"{settings.EDITORIAL_DIRECTORY}/{lang}/editorial.pdf",
        version="1.0",
        active=True,
    )
    db.add(edition)
    db.flush()
    logger.info("Created editorial edition for language '%s' (id=%d)", lang, edition.id)
    return edition


def assign_editorial_to_lead(db: Session, lead: Lead) -> EditorialEdition:
    lang = normalize_language(lead.language)
    edition = get_or_create_editorial(db, lang)
    lead.editorial_edition_id = edition.id
    lead.editorial_assigned_at = datetime.utcnow()
    db.flush()
    logger.info("Assigned editorial %d (lang=%s) to lead %d", edition.id, lang, lead.id)
    return edition


def record_download_event(
    db: Session,
    lead: Lead,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> DownloadEvent:
    event = DownloadEvent(
        lead_id=lead.id,
        editorial_id=lead.editorial_edition_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    db.flush()
    logger.info("Recorded download event for lead %d (editorial %s)", lead.id, lead.editorial_edition_id)
    return event


def seed_editorials(db: Session) -> dict[str, EditorialEdition]:
    editions: dict[str, EditorialEdition] = {}
    for code in SUPPORTED_CODES:
        edition = get_or_create_editorial(db, code)
        editions[code] = edition
    return editions
