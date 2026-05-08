from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StrEnum(str, Enum):
    pass


class FieldType(StrEnum):
    string = "string"
    text = "text"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    datetime = "datetime"
    json = "json"
    list = "list"


class AuthDefaults(BaseModel):
    default_read: Literal["public", "private", "token"] = "private"
    default_write: Literal["private", "token"] = "token"


class FieldConfig(BaseModel):
    type: FieldType
    required: bool = False
    label: str | None = None
    description: str | None = None
    default: Any = None


class FileSettings(BaseModel):
    enabled: bool = False
    allowed_types: list[str] = Field(default_factory=list)
    max_size_mb: int | None = None

    @field_validator("max_size_mb")
    @classmethod
    def validate_max_size(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_size_mb must be greater than zero")
        return value


class ResourceConfig(BaseModel):
    label: str
    fields: dict[str, FieldConfig] = Field(default_factory=dict)
    files: FileSettings = Field(default_factory=FileSettings)


class AppConfig(BaseModel):
    title: str
    description: str | None = None
    config_version: str | None = None
    auth: AuthDefaults = Field(default_factory=AuthDefaults)
    resources: dict[str, ResourceConfig] = Field(default_factory=dict)


class AppsConfig(BaseModel):
    apps: dict[str, AppConfig] = Field(default_factory=dict)

    @field_validator("apps")
    @classmethod
    def validate_apps(cls, value: dict[str, AppConfig]) -> dict[str, AppConfig]:
        if not value:
            raise ValueError("at least one app must be configured")
        return value
