from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .runtime_state import list_auto_decisions


def list_decisions_auto(container: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        return list_auto_decisions(container.store, filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
