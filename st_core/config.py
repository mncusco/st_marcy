import os
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str
    DATABASE_URL: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    CONTACT_EMAIL: str
    SECRET_KEY: str

    DEBUG: bool = False

    EDITORIAL_FILES: dict = {
        "en": "Il_Ritiro_Nella_Selva_EN.pdf",
        "it": "Il_Ritiro_Nella_Selva_IT.pdf",
        "es": "Il_Ritiro_Nella_Selva_ES.pdf",
        "ru": "Il_Ritiro_Nella_Selva_RU.pdf",
        "sr": "Il_Ritiro_Nella_Selva_SR.pdf",
    }

    EDITORIAL_FILES_DIR: str = "./ebooks"
    EMAIL_BACKEND: str = "log"
    EMAIL_MAX_RETRIES: int = 3
    RESEND_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_TIMEOUT: int = 30
    FROM_EMAIL: str = "noreply@shamanictravels.com"
    FROM_NAME: str = "ST Care"
    PUBLIC_URL: str = "https://www.shamanictravels.com"
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: list[str] = ["en", "it", "es", "ru", "sr"]
    EDITORIAL_DIRECTORY: str = "./editorials"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

if settings.DEBUG:
    warnings.warn("DEBUG mode is ON — disable for production", RuntimeWarning)

_insecure_keys = ("change_me", "dev-secret-key-not-for-production", "CHANGE_THIS")
if settings.SECRET_KEY in _insecure_keys or len(settings.SECRET_KEY) < 16:
    warnings.warn(
        "SECRET_KEY is weak or default — generate a strong random key for production",
        RuntimeWarning,
    )
if settings.ADMIN_PASSWORD in _insecure_keys or settings.ADMIN_PASSWORD == "change_me":
    warnings.warn(
        "ADMIN_PASSWORD is the default value — change immediately for production",
        RuntimeWarning,
    )

os.makedirs("./database", exist_ok=True)
os.makedirs("./uploads", exist_ok=True)
os.makedirs(settings.EDITORIAL_FILES_DIR, exist_ok=True)
os.makedirs("./logs/emails", exist_ok=True)
os.makedirs("./logs", exist_ok=True)
os.makedirs(settings.EDITORIAL_DIRECTORY, exist_ok=True)
for _lang in settings.SUPPORTED_LANGUAGES:
    os.makedirs(os.path.join(settings.EDITORIAL_DIRECTORY, _lang), exist_ok=True)
