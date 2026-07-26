from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:password@localhost:5432/slt_ebill"
    output_dir: Path = Path("./output")
    # gmf_drive_path: Path = Path("G:/My Drive/SLT_GMF_Uploads")
    gmf_drive_path: Path = Path("./local_gmf_uploads")
    queue_incoming_dir: Path = Path("./queue/incoming")
    queue_pending_dir: Path = Path("./queue/pending")
    gmf_scan_interval_seconds: int = 5
    log_level: str = "INFO"

    # JWT / Auth
    azure_client_id: str = ""
    azure_tenant_id: str = ""
    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Short-lived signed PDF link tokens
    pdf_token_secret: str = "change-me-pdf-token-secret"
    pdf_token_expire_seconds: int = 300

    # Scheduler / Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Notifications — Email
    email_backend: str = "smtp"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "SLT Billing <billing@slt.lk>"
    email_use_signed_link: bool = False

    # Notifications — SMS
    sms_backend: str = "console"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""

    # Notifications — general
    notify_max_attempts: int = 3

    # CORS — JSON array of allowed origins (override in production)
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # AWS — region + S3 bucket for PDF storage and SES email
    aws_region: str = "ap-southeast-1"
    s3_bucket: str = "slt-bill-pdfs-prod"


settings = Settings()
