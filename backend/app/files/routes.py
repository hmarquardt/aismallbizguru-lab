from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import check_read_access, check_scope, get_optional_token, get_required_token
from app.db.models import ApiTokenModel
from app.files.schemas import FileListOut, FileOut
from app.files.service import FileServiceError, create_file, delete_file_record, get_file_metadata, list_files
from app.files.storage import StorageError, get_file


router = APIRouter(prefix="/api", tags=["files"])


def content_disposition_attachment(filename: str) -> str:
    fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in {'"', "\\", ";"} else "_"
        for char in filename
    ).strip()
    if not fallback:
        fallback = "download"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.post("/{app_id}/{resource}/{record_id}/files", status_code=status.HTTP_201_CREATED, response_model=FileOut)
def upload_file(
    app_id: str,
    resource: str,
    record_id: str,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
    file: Annotated[UploadFile, File()],
):
    check_scope(token, app_id, "write")
    try:
        content = file.file.read()
        fname = file.filename or "unnamed"
        ctype = file.content_type or "application/octet-stream"
        model = create_file(app_id, resource, record_id, fname, ctype, content, created_by_token_id=token.id)
        return FileOut.from_row(model)
    except FileServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_id}/{resource}/{record_id}/files", response_model=FileListOut)
def list_record_files(
    app_id: str,
    resource: str,
    record_id: str,
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)],
) -> FileListOut:
    check_read_access(token, app_id)
    try:
        files = list_files(app_id, resource, record_id)
        return FileListOut(files=[FileOut.from_row(f) for f in files], total=len(files))
    except FileServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/files/{file_id}")
def download_file(
    file_id: str,
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)] = None,
) -> StreamingResponse:
    model = get_file_metadata(file_id)
    if model is None or model.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    check_read_access(token, model.app_id)

    try:
        data_stream = get_file(model.object_key)
        return StreamingResponse(
            data_stream,
            media_type=model.content_type or "application/octet-stream",
            headers={"Content-Disposition": content_disposition_attachment(model.filename)},
        )
    except StorageError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/files/{file_id}")
def delete_file_endpoint(
    file_id: str,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> dict[str, str]:
    model = get_file_metadata(file_id)
    if model is None or model.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    check_scope(token, model.app_id, "write")

    try:
        delete_file_record(file_id)
        return {"status": "deleted"}
    except FileServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
