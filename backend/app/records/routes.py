from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import check_scope, get_required_token
from app.db.models import ApiTokenModel
from app.records.schemas import RecordCreate, RecordListOut, RecordOut, RecordUpdate
from app.records.service import RecordError, create_record, get_record, list_records, soft_delete_record, update_record


router = APIRouter(prefix="/api", tags=["records"])


def _record_out_from_model(model) -> RecordOut:
    import json
    data = json.loads(model.data_json) if isinstance(model.data_json, str) else model.data_json
    return RecordOut(
        id=model.id,
        app_id=model.app_id,
        resource=model.resource,
        data=data,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


@router.get("/{app_id}/{resource}", response_model=RecordListOut)
def record_list(
    app_id: str,
    resource: str,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> RecordListOut:
    check_scope(token, app_id, "read")
    try:
        records = list_records(app_id, resource)
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return RecordListOut(
        records=[_record_out_from_model(r) for r in records],
        total=len(records),
    )


@router.post("/{app_id}/{resource}", status_code=status.HTTP_201_CREATED, response_model=RecordOut)
def record_create(
    app_id: str,
    resource: str,
    body: RecordCreate,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> RecordOut:
    check_scope(token, app_id, "write")
    try:
        model = create_record(app_id, resource, body.data)
        return _record_out_from_model(model)
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_id}/{resource}/{record_id}", response_model=RecordOut)
def record_get(
    app_id: str,
    resource: str,
    record_id: str,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> RecordOut:
    check_scope(token, app_id, "read")
    model = get_record(record_id)
    if model is None or model.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    if model.app_id != app_id or model.resource != resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return _record_out_from_model(model)


@router.patch("/{app_id}/{resource}/{record_id}", response_model=RecordOut)
def record_update(
    app_id: str,
    resource: str,
    record_id: str,
    body: RecordUpdate,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> RecordOut:
    check_scope(token, app_id, "write")
    try:
        model = update_record(record_id, body.data)
        return _record_out_from_model(model)
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{app_id}/{resource}/{record_id}")
def record_delete(
    app_id: str,
    resource: str,
    record_id: str,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> dict[str, str]:
    check_scope(token, app_id, "write")
    try:
        soft_delete_record(record_id)
        return {"status": "deleted"}
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_400_BAD_REQUEST, detail=str(e))
