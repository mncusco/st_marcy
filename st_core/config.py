import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str
    DATABASE_URL: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    CONTACT_EMAIL: str
    SECRET_KEY: str

    EDITORIAL_FILES: dict = {
        "en": "Il_Ritiro_Nella_Selva_EN.pdf",
        "it": "Il_Ritiro_Nella_Selva_IT.pdf",
        "es": "Il_Ritiro_Nella_Selva_ES.pdf",
        "ru": "Il_Ritiro_Nella_Selva_RU.pdf",
        "sr": "Il_Ritiro_Nella_Selva_SR.pdf",
    }

    EDITORIAL_FILES_DIR: str = "./ebooks"
    EMAIL_BACKEND: str = "log"
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: list[str] = ["en", "it", "es", "ru", "sr"]
    EDITORIAL_DIRECTORY: str = "./editorials"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

os.makedirs("./database", exist_ok=True)
os.makedirs("./uploads", exist_ok=True)
os.makedirs(settings.EDITORIAL_FILES_DIR, exist_ok=True)
os.makedirs("./logs/emails", exist_ok=True)
os.makedirs(settings.EDITORIAL_DIRECTORY, exist_ok=True)
for _lang in settings.SUPPORTED_LANGUAGES:
    os.makedirs(os.path.join(settings.EDITORIAL_DIRECTORY, _lang), exist_ok=True)
