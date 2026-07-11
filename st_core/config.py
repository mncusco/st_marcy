import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str
    DATABASE_URL: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    CONTACT_EMAIL: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

os.makedirs("./database", exist_ok=True)
os.makedirs("./uploads", exist_ok=True)
