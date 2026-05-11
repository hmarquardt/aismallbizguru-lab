from pydantic import BaseModel

from app.settings import get_settings


class FileOut(BaseModel):
    id: str
    app_id: str
    resource: str | None
    record_id: str | None
    filename: str
    content_type: str | None
    size_bytes: int | None
    checksum: str | None
    created_by_token_id: str | None = None
    created_at: str
    url: str
    download_url: str

    @classmethod
    def from_row(cls, row) -> "FileOut":
        path = f"/api/files/{row.id}"
        url = f"{str(get_settings().base_url).rstrip('/')}{path}"
        return cls(
            id=row.id,
            app_id=row.app_id,
            resource=row.resource,
            record_id=row.record_id,
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            checksum=row.checksum,
            created_by_token_id=getattr(row, "created_by_token_id", None),
            created_at=row.created_at,
            url=url,
            download_url=url,
        )


class FileListOut(BaseModel):
    files: list[FileOut]
    total: int
