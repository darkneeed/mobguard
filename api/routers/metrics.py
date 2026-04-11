from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_container, get_session


router = APIRouter(prefix="/admin", tags=["metrics"])


@router.get("/metrics/quality")
def get_quality(
    module_id: str | None = Query(default=None),
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return container.store.get_quality_metrics(module_id=module_id)
