import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import check_read_access, check_scope, get_optional_token, get_required_token
from app.config.loader import get_registry
from app.db.models import ApiTokenModel
from app.files.schemas import FileOut
from app.files.service import FileServiceError, list_files
from app.records.schemas import RecordCreate, RecordListOut, RecordOut, RecordUpdate
from app.records.service import RecordError, create_record, get_record, list_records, soft_delete_record, update_record


router = APIRouter(prefix="/api", tags=["records"])


class WildlifeTripFromObservations(BaseModel):
    title: str = Field(min_length=1)
    observation_ids: list[str] = Field(default_factory=list)
    observation_local_ids: list[str] = Field(default_factory=list)
    local_trip_id: str | None = None


def _record_out_from_model(model) -> RecordOut:
    data = json.loads(model.data_json) if isinstance(model.data_json, str) else model.data_json
    files = _files_for_record(model.app_id, model.resource, model.id)
    _add_image_url_fallback(data, files)
    return RecordOut(
        id=model.id,
        app_id=model.app_id,
        resource=model.resource,
        data=data,
        created_by_token_id=getattr(model, "created_by_token_id", None),
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
        files=files,
    )


def _files_for_record(app_id: str, resource: str, record_id: str) -> list[FileOut]:
    resource_config = get_registry().get_resource(app_id, resource)
    if resource_config is None or not resource_config.files.enabled:
        return []
    try:
        return [FileOut.from_row(file) for file in list_files(app_id, resource, record_id)]
    except FileServiceError:
        return []


def _add_image_url_fallback(data: dict, files: list[FileOut]) -> None:
    if any(data.get(key) for key in ("photo_url", "photo", "image")):
        return
    for file in files:
        if file.content_type and file.content_type.startswith("image/"):
            data["photo_url"] = file.url
            return


def _record_data(model) -> dict:
    return json.loads(model.data_json) if isinstance(model.data_json, str) else model.data_json


def _number_values(observations: list[dict], field_name: str) -> list[float]:
    values = []
    for observation in observations:
        value = observation.get(field_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def _coordinate_pairs(observations: list[dict]) -> list[tuple[float, float]]:
    pairs = []
    for observation in observations:
        latitude = observation.get("latitude")
        longitude = observation.get("longitude")
        if (
            isinstance(latitude, (int, float))
            and not isinstance(latitude, bool)
            and isinstance(longitude, (int, float))
            and not isinstance(longitude, bool)
        ):
            pairs.append((float(latitude), float(longitude)))
    return pairs


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _most_common(values: list[str]) -> str | None:
    counts: dict[str, int] = {}
    for value in values:
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _compact_dict(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


def _record_created_at_string(model) -> str:
    if hasattr(model.created_at, "isoformat"):
        return model.created_at.isoformat()
    return str(model.created_at)


def _build_trip_from_observations(title: str, local_trip_id: str | None, observation_models) -> dict:
    observations = [_record_data(model) for model in observation_models]
    coordinates = _coordinate_pairs(observations)
    latitudes = [latitude for latitude, _longitude in coordinates]
    longitudes = [longitude for _latitude, longitude in coordinates]
    temps_f = _number_values(observations, "temperatureF")
    pressures_hpa = _number_values(observations, "barometricPressureHpa")
    created_times = sorted(
        value for value in (observation.get("createdAt") for observation in observations)
        if isinstance(value, str) and value
    )
    categories = sorted({
        observation.get("category")
        for observation in observations
        if isinstance(observation.get("category"), str) and observation.get("category")
    })
    habitats = sorted({
        observation.get("habitat")
        for observation in observations
        if isinstance(observation.get("habitat"), str) and observation.get("habitat")
    })
    weather_conditions = [
        observation.get("weatherCondition") or observation.get("weatherStatus")
        for observation in observations
        if isinstance(observation.get("weatherCondition") or observation.get("weatherStatus"), str)
    ]
    subject_summaries = [
        observation.get("subjectCommonName") or observation.get("summary")
        for observation in observations
        if observation.get("subjectCommonName") or observation.get("summary")
    ]

    return _compact_dict({
        "localTripId": local_trip_id or f"trip-{uuid.uuid4().hex[:12]}",
        "title": title,
        "startedAt": created_times[0] if created_times else _record_created_at_string(observation_models[0]),
        "endedAt": created_times[-1] if len(created_times) > 1 else None,
        "observationLocalIds": [
            observation.get("localId") for observation in observations if observation.get("localId")
        ],
        "observationRecordIds": [model.id for model in observation_models],
        "observationCount": len(observations),
        "categories": categories,
        "subjectSummaries": subject_summaries,
        "centerLatitude": _average(latitudes),
        "centerLongitude": _average(longitudes),
        "boundingBox": {
            "minLatitude": min(latitudes),
            "maxLatitude": max(latitudes),
            "minLongitude": min(longitudes),
            "maxLongitude": max(longitudes),
        } if latitudes and longitudes else None,
        "weatherSummary": _most_common(weather_conditions),
        "dominantWeatherCondition": _most_common(weather_conditions),
        "minTemperatureF": min(temps_f) if temps_f else None,
        "maxTemperatureF": max(temps_f) if temps_f else None,
        "avgTemperatureF": _average(temps_f),
        "avgBarometricPressureHpa": _average(pressures_hpa),
        "habitats": habitats,
        "needsReview": True,
        "reviewStatus": "needs-review",
        "routeGeoJson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[longitude, latitude] for latitude, longitude in coordinates],
                },
                "properties": {"name": title},
            }],
        } if len(coordinates) >= 2 else {"type": "FeatureCollection", "features": []},
    })


@router.post("/wildlife-field-recorder/trips/from-observations", status_code=status.HTTP_201_CREATED, response_model=RecordOut)
def create_wildlife_trip_from_observations(
    body: WildlifeTripFromObservations,
    token: Annotated[ApiTokenModel, Depends(get_required_token)],
) -> RecordOut:
    check_scope(token, "wildlife-field-recorder", "write")
    if not body.observation_ids and not body.observation_local_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one observation is required")

    observation_models = list_records("wildlife-field-recorder", "observations")
    selected = []
    local_ids = set(body.observation_local_ids)
    record_ids = set(body.observation_ids)
    requested_order = {
        identifier: index
        for index, identifier in enumerate([*body.observation_ids, *body.observation_local_ids])
    }
    for model in observation_models:
        data = _record_data(model)
        if model.id in record_ids or data.get("localId") in local_ids:
            selected.append(model)

    if not selected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching observations found")

    selected.sort(
        key=lambda model: min(
            requested_order.get(model.id, len(requested_order)),
            requested_order.get(_record_data(model).get("localId"), len(requested_order)),
        )
    )

    try:
        model = create_record(
            "wildlife-field-recorder",
            "trips",
            _build_trip_from_observations(body.title, body.local_trip_id, selected),
            created_by_token_id=token.id,
        )
        return _record_out_from_model(model)
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_id}/{resource}", response_model=RecordListOut)
def record_list(
    app_id: str,
    resource: str,
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)],
) -> RecordListOut:
    check_read_access(token, app_id)
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
        model = create_record(app_id, resource, body.data, created_by_token_id=token.id)
        return _record_out_from_model(model)
    except RecordError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_id}/{resource}/{record_id}", response_model=RecordOut)
def record_get(
    app_id: str,
    resource: str,
    record_id: str,
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)],
) -> RecordOut:
    check_read_access(token, app_id)
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
