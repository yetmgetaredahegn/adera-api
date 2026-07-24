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
