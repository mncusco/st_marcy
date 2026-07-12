import enum

class LanguageCode(str, enum.Enum):
    EN = "en"
    IT = "it"
    ES = "es"
    RU = "ru"
    SR = "sr"

SUPPORTED_CODES = {e.value for e in LanguageCode}
SUPPORTED_NAMES = {
    "en": "Private Collector Guide English",
    "it": "Guida Privata Collezionista Italiano",
    "es": "Guía Privada del Coleccionista Español",
    "ru": "Частное руководство коллекционера Русский",
    "sr": "Privatni Vodič Kolekcionara Srpski",
}
FALLBACK = LanguageCode.EN


def normalize_language(lang: str | None) -> str:
    if not lang:
        return FALLBACK.value
    normalized = lang.lower().strip().split("-")[0].split("_")[0]
    if normalized in SUPPORTED_CODES:
        return normalized
    return FALLBACK.value


def detect_language(form_lang: str | None, accept_language: str | None = None) -> str:
    if form_lang:
        result = normalize_language(form_lang)
        if result in SUPPORTED_CODES:
            return result

    if accept_language:
        for part in accept_language.split(","):
            part = part.strip().split(";")[0].strip()
            code = part.lower().split("-")[0].split("_")[0]
            if code in SUPPORTED_CODES:
                return code

    return FALLBACK.value
