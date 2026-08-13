import enum
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    ForeignKey,
    func,
)

from app.db.base import Base
from sqlalchemy.orm import relationship

class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    ADMIN1 = "ADMIN1"
    GMF_HANDLER = "GMF_HANDLER"
    ENVELOPE_HANDLER = "ENVELOPE_HANDLER"
    MANAGER = "MANAGER"
    CUSTOMER = "CUSTOMER"

class PermissionRequestStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class TemplateCategory(enum.Enum):
    CLASSIC = "CLASSIC"
    MODERN = "MODERN"
    ENTERPRISE = "ENTERPRISE"
    MINIMAL = "MINIMAL"
    CUSTOM = "CUSTOM"

class TemplateApprovalStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class RunStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class NotificationEventType(enum.Enum):
    GMF_DETECTED = "GMF_DETECTED"
    TEST_GMF_RECEIVED = "TEST_GMF_RECEIVED"
    PREVIEW_GENERATED = "PREVIEW_GENERATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BATCH_STARTED = "BATCH_STARTED"
    BATCH_COMPLETED = "BATCH_COMPLETED"
    BATCH_FAILED = "BATCH_FAILED"
    ERROR = "ERROR"

class PdfGenerationStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class DeliveryStatus(enum.Enum):
    NOT_ENABLED = "NOT_ENABLED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class BillingRunItemOverallStatus(enum.Enum):
    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"
    READY_TO_SEND = "READY_TO_SEND"
    COMPLETED = "COMPLETED"

class BillingScheduleMode(enum.Enum):
    AUTOMATIC = "AUTOMATIC"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

class BillingApprovalStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

_template_category = Enum(TemplateCategory, name="template_category")

class User(Base):
    __tablename__ = "users"

    id            = Column(BigInteger, Identity(always=True), primary_key=True)
    email         = Column(Text, nullable=False, unique=True)
    role          = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.CUSTOMER)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    role_grants   = relationship("UserRoleGrant", foreign_keys="UserRoleGrant.user_id", back_populates="user", cascade="all, delete-orphan")

class InvoiceTemplate(Base):
    __tablename__ = "invoice_templates"
    __table_args__ = (
        Index("idx_invoice_templates_active", "is_active"),
        Index("idx_invoice_templates_base", "base_template_id"),
    )

    id                = Column(BigInteger, Identity(always=True), primary_key=True)
    name              = Column(Text, nullable=False)
    description       = Column(Text)
    template_code     = Column(Text, nullable=False, unique=True)
    is_active         = Column(Boolean, nullable=False, default=False)
    is_system_template = Column(Boolean, nullable=False, default=True)
    base_template_id  = Column(BigInteger, ForeignKey("invoice_templates.id", ondelete="SET NULL"), nullable=True)
    category          = Column(_template_category, nullable=False, default=TemplateCategory.CLASSIC)
    layout_type       = Column(Text, nullable=False, default="default") 
    cover_image_url   = Column(Text)
    template_layout   = Column(Text)  
    header_message    = Column(Text)
    footer_message    = Column(Text)
    promotion_message = Column(Text)
    theme_name        = Column(Text)
    theme_color       = Column(Text)
    approval_status   = Column(Enum(TemplateApprovalStatus, name="template_approval_status"), nullable=False, default=TemplateApprovalStatus.PENDING)
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Invoice(Base):
    __tablename__ = "invoices"

    id                 = Column(BigInteger, Identity(always=True), primary_key=True)
    account_number     = Column(Text, nullable=False)
    template_id        = Column(BigInteger, ForeignKey("invoice_templates.id", ondelete="SET NULL"), nullable=True)
    invoice_number     = Column(Text, nullable=False, unique=True)
    billing_date       = Column(Date, nullable=False)
    period_start       = Column(Date, nullable=False)
    period_end         = Column(Date, nullable=False)
    status             = Column(Text, nullable=False, default="GENERATED")
    pdf_path           = Column(Text)
    zip_path           = Column(Text)
    batch_name         = Column(Text)
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class BillingRun(Base):
    __tablename__ = "billing_runs"

    id             = Column(BigInteger, Identity(always=True), primary_key=True)
    batch_name     = Column(Text, nullable=False)
    cycle_number   = Column(Integer, nullable=True)  # 1-4 or None for test
    period_start   = Column(Date, nullable=False)
    period_end     = Column(Date, nullable=False)
    status         = Column(Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.PENDING)
    total_accounts = Column(Integer, nullable=False, default=0)
    succeeded      = Column(Integer, nullable=False, default=0)
    failed         = Column(Integer, nullable=False, default=0)
    started_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at    = Column(DateTime(timezone=True))
    output_path    = Column(Text)  # Base path to Output/<date>/<cycle>/ folder
    zip_path       = Column(Text)  # Legacy, kept for backwards compat
    
    failures = relationship("BillingRunFailure", backref="run", cascade="all, delete-orphan")

class BillingRunItem(Base):
    __tablename__ = "billing_run_items"

    id             = Column(BigInteger, Identity(always=True), primary_key=True)
    billing_run_id = Column(BigInteger, ForeignKey("billing_runs.id", ondelete="CASCADE"), nullable=False)
    account_number = Column(Text, nullable=True)
    invoice_id     = Column(BigInteger, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    template_id    = Column(BigInteger, ForeignKey("invoice_templates.id", ondelete="SET NULL"), nullable=True)
    pdf_status     = Column(Enum(PdfGenerationStatus, name="pdf_generation_status"), nullable=False, default=PdfGenerationStatus.PENDING)
    overall_status = Column(Enum(BillingRunItemOverallStatus, name="billing_run_item_overall_status"), nullable=False, default=BillingRunItemOverallStatus.PENDING)
    failure_reason = Column(Text)
    retry_count    = Column(Integer, nullable=False, default=0)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class BillingSchedule(Base):
    __tablename__ = "billing_schedules"

    id                 = Column(BigInteger, Identity(always=True), primary_key=True)
    name               = Column(Text, nullable=False, default="Monthly SLT billing")
    day_of_month       = Column(Integer, nullable=False, default=1)
    run_time           = Column(Text, nullable=False, default="02:00")
    timezone           = Column(Text, nullable=False, default="Asia/Colombo")
    schedule_mode      = Column(Enum(BillingScheduleMode, name="billing_schedule_mode"), nullable=False, default=BillingScheduleMode.AUTOMATIC)
    is_active          = Column(Boolean, nullable=False, default=True)
    approval_lead_days = Column(Integer, nullable=False, default=1)
    approval_email     = Column(Text)
    last_triggered_period = Column(Text)
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at         = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class BillingRunApproval(Base):
    __tablename__ = "billing_run_approvals"

    id                  = Column(BigInteger, Identity(always=True), primary_key=True)
    billing_schedule_id = Column(BigInteger, ForeignKey("billing_schedules.id", ondelete="CASCADE"), nullable=False)
    billing_run_id      = Column(BigInteger, ForeignKey("billing_runs.id", ondelete="SET NULL"), nullable=True)
    batch_name          = Column(Text, nullable=False)
    period              = Column(Text, nullable=False)
    status              = Column(Enum(BillingApprovalStatus, name="billing_approval_status"), nullable=False, default=BillingApprovalStatus.PENDING)
    requested_to        = Column(Text)
    requested_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at          = Column(DateTime(timezone=True))
    approved_at         = Column(DateTime(timezone=True))
    rejected_at         = Column(DateTime(timezone=True))
    decided_by_user_id  = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class BillingRunFailure(Base):
    __tablename__ = "billing_run_failures"

    id             = Column(BigInteger, Identity(always=True), primary_key=True)
    billing_run_id = Column(BigInteger, ForeignKey("billing_runs.id", ondelete="CASCADE"), nullable=False)
    account_number = Column(Text, nullable=True)
    error_message  = Column(Text, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class GmfUploadStatus(enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    GENERATING = "GENERATING"
    PARTIALLY_PROCESSED = "PARTIALLY_PROCESSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GmfUpload(Base):
    __tablename__ = "gmf_uploads"

    id                = Column(BigInteger, Identity(always=True), primary_key=True)
    filename          = Column(Text, nullable=False)
    file_path         = Column(Text, nullable=False)
    folder_type       = Column(Text, nullable=False)  # e.g. 'Test_GMFs', 'Cycle_1'
    cycle_number      = Column(Integer, nullable=True)  # 1-4, None for Test_GMFs
    template_detected = Column(Text, nullable=True)     # e.g. 'nonvat_home'
    status            = Column(Enum(GmfUploadStatus, name="gmf_upload_status"), nullable=False, default=GmfUploadStatus.PENDING_APPROVAL)
    detected_at       = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at      = Column(DateTime(timezone=True))
    error_message     = Column(Text)
    rejection_reason  = Column(Text)
    billing_run_id    = Column(BigInteger, ForeignKey("billing_runs.id", ondelete="SET NULL"), nullable=True)
    processed_records_count = Column(Integer, nullable=False, default=0)
    total_records_count     = Column(Integer, nullable=False, default=0)
    template_breakdown      = Column(Text, nullable=True)


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id         = Column(BigInteger, Identity(always=True), primary_key=True)
    event_type = Column(Enum(NotificationEventType, name="notification_event_type"), nullable=False)
    title      = Column(Text, nullable=False)
    message    = Column(Text, nullable=False)
    upload_id  = Column(BigInteger, ForeignKey("gmf_uploads.id", ondelete="SET NULL"), nullable=True)
    run_id     = Column(BigInteger, ForeignKey("billing_runs.id", ondelete="SET NULL"), nullable=True)
    is_read    = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key   = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)


class TemplateHistory(Base):
    __tablename__ = "template_history"

    id            = Column(BigInteger, Identity(always=True), primary_key=True)
    template_name = Column(Text, nullable=False)
    action        = Column(Text, nullable=False)  # 'APPROVED' or 'REJECTED'
    filename      = Column(Text)
    reason        = Column(Text)
    timestamp     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EnvelopeHistory(Base):
    __tablename__ = "envelope_history"

    id            = Column(BigInteger, Identity(always=True), primary_key=True)
    template_name = Column(Text, nullable=False)
    action        = Column(Text, nullable=False)  # 'APPROVED' or 'REJECTED'
    filename      = Column(Text)
    reason        = Column(Text)
    timestamp     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Envelope Portal Models ────────────────────────────────────────────────

class EnvelopeType(enum.Enum):
    LARGE = "LARGE"
    MEDIUM = "MEDIUM"
    SELF_SEAL = "SELF_SEAL"

class EnvelopeArtworkStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"     # submitted for admin approval
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REPLACED = "REPLACED"       # superseded by a newer upload
    REMOVED = "REMOVED"         # manually removed by uploader


class EnvelopeTemplate(Base):
    __tablename__ = "envelope_templates"

    id             = Column(BigInteger, Identity(always=True), primary_key=True)
    envelope_type  = Column(Enum(EnvelopeType, name="envelope_type_enum"), nullable=False, unique=True)
    display_name   = Column(Text, nullable=False)
    base_pdf_path  = Column(Text, nullable=False)  # relative path to empty PDF template
    # Placeholder box coordinates in PDF points (auto-detected or manual)
    box_x0         = Column(Integer, nullable=True)
    box_y0         = Column(Integer, nullable=True)
    box_x1         = Column(Integer, nullable=True)
    box_y1         = Column(Integer, nullable=True)
    rotation_deg   = Column(Integer, nullable=False, default=0)
    fit_mode       = Column(Text, nullable=False, default="cover")
    # Image validation constraints (flexible ranges)
    min_width      = Column(Integer, nullable=False, default=800)
    min_height     = Column(Integer, nullable=False, default=250)
    aspect_min     = Column(Integer, nullable=False, default=70)   # x100: 0.70 = 70
    aspect_max     = Column(Integer, nullable=False, default=350)  # x100: 3.50 = 350
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    artworks = relationship("EnvelopeArtwork", back_populates="template", lazy="dynamic")


class EnvelopeArtwork(Base):
    __tablename__ = "envelope_artworks"

    id                    = Column(BigInteger, Identity(always=True), primary_key=True)
    envelope_template_id  = Column(BigInteger, ForeignKey("envelope_templates.id", ondelete="CASCADE"), nullable=False)
    original_filename     = Column(Text, nullable=False)
    campaign_name         = Column(Text, nullable=True)        # optional custom campaign title
    image_path            = Column(Text, nullable=False)       # stored artwork image
    image_width           = Column(Integer, nullable=False)
    image_height          = Column(Integer, nullable=False)
    output_pdf_path       = Column(Text, nullable=True)        # generated composite PDF
    preview_png_path      = Column(Text, nullable=True)        # generated PNG preview
    status                = Column(Enum(EnvelopeArtworkStatus, name="envelope_artwork_status_enum"), nullable=False, default=EnvelopeArtworkStatus.ACTIVE)
    rejection_reason      = Column(Text, nullable=True)
    uploaded_by           = Column(Text, nullable=True)        # user email or ID
    created_at            = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    replaced_at           = Column(DateTime(timezone=True), nullable=True)

    template = relationship("EnvelopeTemplate", back_populates="artworks")


# ── Access Control Models ─────────────────────────────────────────────────

class UserRoleGrant(Base):
    """Junction table: a user can hold multiple portal roles."""
    __tablename__ = "user_role_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_role_grant"),
    )

    id         = Column(BigInteger, Identity(always=True), primary_key=True)
    user_id    = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role       = Column(Enum(UserRole, name="user_role"), nullable=False)
    granted_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user       = relationship("User", foreign_keys=[user_id], back_populates="role_grants")
    granter    = relationship("User", foreign_keys=[granted_by])


class PermissionRequest(Base):
    """A request by a user (new or existing) to gain access to one or more portal roles."""
    __tablename__ = "permission_requests"

    id           = Column(BigInteger, Identity(always=True), primary_key=True)
    email        = Column(Text, nullable=False)        # requester email (from Microsoft)
    requested_roles = Column(Text, nullable=False)     # JSON array of role names
    reason       = Column(Text, nullable=True)
    status       = Column(
        Enum(PermissionRequestStatus, name="permission_request_status"),
        nullable=False,
        default=PermissionRequestStatus.PENDING,
    )
    reviewed_by  = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at  = Column(DateTime(timezone=True), nullable=True)
    rejection_note = Column(Text, nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reviewer = relationship("User", foreign_keys=[reviewed_by])
