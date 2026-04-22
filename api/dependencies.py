from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request

from .context import APIContainer
from .permissions import ROLE_OWNER, permissions_for_role, session_has_permission


def get_container(request: Request) -> APIContainer:
    return request.app.state.container


def get_session(request: Request) -> dict[str, Any]:
    container = get_container(request)
    session_token = request.cookies.get(container.session_cookie_name)
    if not session_token:
        raise HTTPException(status_code=401, detail="Missing session cookie")
    session = container.store.get_admin_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if not session.get("role"):
        if str(session.get("auth_method") or "").lower() == "local":
            session["role"] = ROLE_OWNER
        else:
            inferred_role = container.store.get_admin_role_for_tg_id(int(session.get("telegram_id") or 0))
            if inferred_role:
                session["role"] = inferred_role
    if not session.get("permissions") and session.get("role"):
        session["permissions"] = permissions_for_role(session["role"])
    return session


def require_permission(permission: str, *, require_owner_totp: bool = False) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def dependency(session: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
        if not session_has_permission(session, permission):
            raise HTTPException(status_code=403, detail="Permission denied")
        if require_owner_totp and str(session.get("role") or "").lower() == ROLE_OWNER:
            if not bool(session.get("totp_verified")):
                raise HTTPException(status_code=403, detail="Owner session requires TOTP verification")
        return session

    return dependency
