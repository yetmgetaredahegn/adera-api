"""Auth API contracts (AUTH-1..4, docs/11_API_REFERENCE.md §1)."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.identity.models import OrgType


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    org_name: str
    org_type: OrgType
    country: str
    timezone: str = "Africa/Addis_Ababa"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    is_verified: bool
    # Platform admin (master plan P6, the founder-operator persona) -- distinct
    # from an org's own OrgRole. The web client uses this to gate /dashboard/admin
    # for real instead of a local demo flag.
    is_staff: bool


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    org_type: OrgType
    country: str
    timezone: str


class MeOut(BaseModel):
    user: UserOut
    org: OrgOut


class RegisterOut(BaseModel):
    """AUTH-1 response. Carries `org` and `audience_note` (ADR-029) so a
    `local`-type org learns immediately what it can and can't do here rather
    than discovering an empty feed later — a silent gap is indistinguishable
    from a bug (see `identity.service.require_bidder_audience`)."""

    user: UserOut
    org: OrgOut
    audience_note: str | None = None
