"""M1 — Identity & Organization (FR-1.1, FR-1.2, FR-1.6)."""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import SoftDelete, Timestamps, UUIDPk


class OrgType(enum.StrEnum):
    """FR-1.6 — the most load-bearing enum in the product.

    Drives eligibility logic (M16), currency display, and channel defaults. A
    tender an org's type cannot bid on is down-ranked and labeled, never silently
    hidden (FR-7.6).
    """

    LOCAL = "local"
    DIASPORA = "diaspora"
    FOREIGN = "foreign"


class OrgRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class User(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)


class Org(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "orgs"

    name: Mapped[str] = mapped_column(String(255))
    org_type: Mapped[OrgType] = mapped_column(pg_enum(OrgType, "org_type"), index=True)
    # ISO-3166 alpha-2. Ethiopia is "ET"; a diaspora org's country is where it
    # is registered, which is what eligibility turns on — not where the founder was born.
    country: Mapped[str] = mapped_column(String(2))
    # IANA name (e.g. "Africa/Addis_Ababa", "America/Los_Angeles"). NFR-INTL-1:
    # everything is stored UTC and rendered here.
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Addis_Ababa")


class OrgMember(UUIDPk, Timestamps, Base):
    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[OrgRole] = mapped_column(pg_enum(OrgRole, "org_role"))
