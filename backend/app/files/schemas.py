from pydantic import BaseModel


class FileOut(BaseModel):
    id: str
    app_id: str
    resource: str | None
    record_id: str | None
    filename: str
    content_type: str | None
    size_bytes: int | None
    checksum: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "FileOut":
        return cls(
            id=row.id,
            app_id=row.app_id,
            resource=row.resource,
            record_id=row.record_id,
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            checksum=row.checksum,
            created_at=row.created_at,
        )


class FileListOut(BaseModel):
    files: list[FileOut]
    total: int