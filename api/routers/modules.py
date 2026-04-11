from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ..dependencies import get_container, get_session
from ..schemas.modules import EventBatchRequest, ModuleHeartbeatRequest, ModuleRegisterRequest
from ..services import modules as module_service


router = APIRouter(tags=["modules"])


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return token.strip()


@router.post("/module/register")
def register_module(
    payload: ModuleRegisterRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.register_module(container, payload.model_dump(), _bearer_token(authorization))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/module/heartbeat")
def module_heartbeat(
    payload: ModuleHeartbeatRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.record_module_heartbeat(container, payload.model_dump(), _bearer_token(authorization))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/module/config")
def module_config(
    module_id: str = Query(...),
    protocol_version: str = Query(default="v1"),
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        module = container.store.authenticate_module(module_id, _bearer_token(authorization))
        if protocol_version != "v1":
            raise ValueError(f"Unsupported module protocol version: {protocol_version}")
        return module_service.get_module_config(container, module)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/module/events/batch")
async def module_events_batch(
    payload: EventBatchRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return await module_service.ingest_module_events(
            container,
            payload.model_dump(),
            _bearer_token(authorization),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/modules")
def admin_list_modules(
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return module_service.list_modules(container)
