from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = Field(min_length=1, max_length=2048)
    host: str | None = Field(default=None, max_length=255)
    path: str | None = Field(default=None, max_length=1024)
    query: str | None = Field(default=None, max_length=1024)
    title: str | None = Field(default=None, max_length=512)


class ReferrerPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str | None = Field(default=None, max_length=2048)
    domain: str | None = Field(default=None, max_length=255)


class UtmPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str | None = Field(default=None, max_length=255)
    medium: str | None = Field(default=None, max_length=255)
    campaign: str | None = Field(default=None, max_length=255)
    term: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=255)


class ClientPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str | None = Field(default=None, max_length=64)
    timezone: str | None = Field(default=None, max_length=128)
    screen_width: int | None = Field(default=None, ge=0, le=100000)
    screen_height: int | None = Field(default=None, ge=0, le=100000)
    viewport_width: int | None = Field(default=None, ge=0, le=100000)
    viewport_height: int | None = Field(default=None, ge=0, le=100000)
    user_agent: str | None = Field(default=None, max_length=2048)


class PerformancePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    load_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    navigation_type: str | None = Field(default=None, max_length=64)


class AnalyticsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    site_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(default="pageview", min_length=1, max_length=64)
    visitor_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    occurred_at: str = Field(min_length=1, max_length=64)
    page: PagePayload
    referrer: ReferrerPayload | None = None
    utm: UtmPayload | None = None
    client: ClientPayload | None = None
    performance: PerformancePayload | None = None
    event_name: str | None = Field(default=None, max_length=255)
    target_url: str | None = Field(default=None, max_length=2048)
    value_number: float | None = None
    value_text: str | None = Field(default=None, max_length=1024)
    props: dict | None = None

