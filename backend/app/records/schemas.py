from typing import Any

from pydantic import BaseModel, Field

from app.files.schemas import FileOut


class RecordCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class RecordUpdate(BaseModel):
    data: dict[str, Any] | None = None


class RecordOut(BaseModel):
    id: str
    app_id: str
    resource: str
    data: dict[str, Any]
    created_by_token_id: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    files: list[FileOut] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: Any) -> "RecordOut":
        import json

        data = json.loads(row.data_json) if isinstance(row.data_json, str) else row.data_json
        return cls(
            id=row.id,
            app_id=row.app_id,
            resource=row.resource,
            data=data,
            created_by_token_id=getattr(row, "created_by_token_id", None),
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )


class RecordListOut(BaseModel):
    records: list[RecordOut]
    total: int
