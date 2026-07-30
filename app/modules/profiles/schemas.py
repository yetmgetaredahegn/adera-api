"""Company profile API contracts (M6, FR-6.1/6.2; docs/11_API_REFERENCE.md PRO-2/PRO-3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileIn(BaseModel):
    """PUT body — confirmed facts only (FR-6.1).

    sectors/capabilities are required non-empty: an org that confirms neither
    has nothing for matching or the grounded explanation to cite, so it can
    never usefully match — reject at the boundary rather than silently persist
    a profile that can't do its job. certifications/regions stay optional:
    many real orgs have neither, and "no certifications" / "serves anywhere"
    are legitimate answers, not missing data.
    """

    source_text: str = Field(min_length=1)
    sectors: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    certifications: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


class ProfileOut(BaseModel):
    """Never includes profile_embedding — no schema in this repo exposes a raw
    vector (mirrors TenderOut)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    source_text: str
    sectors: list[str]
    capabilities: list[str]
    certifications: list[str]
    regions: list[str]
    created_at: datetime
    updated_at: datetime
