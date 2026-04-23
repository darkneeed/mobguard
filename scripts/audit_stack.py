from __future__ import annotations

import argparse
import json
import threading
import time
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .dev_stack import API_HOST, API_PORT, StackRunner, build_stack_context
from .synthetic_ingest import feed_access_log


DEFAULT_WORKLOAD_SHAPE = {
    "inbound_tags": ["TAG", "LTE", "MOBILE"],
    "feed_count": 120,
    "feed_interval_seconds": 0.02,
}

LOCK_SIGNAL_PATTERNS = (
    "database is locked",
    "database_locked",
    "query_timeout",
    "sqlite",
)


def _build_opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def _request_json(opener, method: str, url: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method, headers=headers)
    started_at = time.perf_counter()
    try:
        with opener.open(request, timeout=15) as response:
            raw_body = response.read()
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            return {
                "ok": True,
                "status": response.getcode(),
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "body": body if isinstance(body, dict) else {"raw": body},
            }
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            body = {"raw": raw_body}
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "body": body,
        }
    except URLError as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "body": {"error": str(exc.reason)},
        }


def _wait_for_ready(opener, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    url = f"http://{API_HOST}:{API_PORT}/ready"
    while time.time() < deadline:
        result = _request_json(opener, "GET", url)
        if result["ok"] and result["status"] == 200:
            return result
        time.sleep(0.5)
    raise TimeoutError("Local API did not become ready in time")


def _load_workload_shape(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return dict(DEFAULT_WORKLOAD_SHAPE)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "inbound_tags": list(payload.get("inbound_tags") or DEFAULT_WORKLOAD_SHAPE["inbound_tags"]),
        "feed_count": int(payload.get("feed_count") or DEFAULT_WORKLOAD_SHAPE["feed_count"]),
        "feed_interval_seconds": float(
            payload.get("feed_interval_seconds") or DEFAULT_WORKLOAD_SHAPE["feed_interval_seconds"]
        ),
    }


def _login_local(opener, base_url: str, panel_env_values: dict[str, str]) -> dict[str, Any]:
    username = str(panel_env_values.get("PANEL_LOCAL_USERNAME") or "").strip()
    password = str(panel_env_values.get("PANEL_LOCAL_PASSWORD") or "").strip()
    if not username or not password:
        return {"ok": False, "skipped": True, "reason": "local_credentials_missing"}
    result = _request_json(
        opener,
        "POST",
        f"{base_url}/admin/auth/local/login",
        payload={"username": username, "password": password},
    )
    body = result.get("body", {})
    result["auth_mode"] = "session" if result["ok"] and "requires_totp" not in body else "challenge"
    return result


def _measure_authenticated_endpoints(opener, base_url: str) -> dict[str, Any]:
    measurements: dict[str, Any] = {
        "overview": _request_json(opener, "GET", f"{base_url}/admin/metrics/overview"),
        "modules": _request_json(opener, "GET", f"{base_url}/admin/modules"),
        "reviews": _request_json(opener, "GET", f"{base_url}/admin/reviews?page=1&page_size=25"),
        "data_cases": _request_json(opener, "GET", f"{base_url}/admin/data/cases?page=1&page_size=25"),
        "data_events": _request_json(opener, "GET", f"{base_url}/admin/data/events?page=1&page_size=50"),
        "me": _request_json(opener, "GET", f"{base_url}/admin/me"),
    }
    review_items = measurements["reviews"].get("body", {}).get("items", [])
    if review_items:
        first_case_id = review_items[0]["id"]
        measurements["review_detail"] = _request_json(opener, "GET", f"{base_url}/admin/reviews/{first_case_id}")
    else:
        measurements["review_detail"] = {"ok": False, "skipped": True, "reason": "no_review_cases"}
    return measurements


def _count_log_signals(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    counts: dict[str, int] = {}
    for pattern in LOCK_SIGNAL_PATTERNS:
        counts[pattern] = sum(1 for line in lines if pattern in line.lower())
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a repeatable local MobGuard audit pass.")
    parser.add_argument("--start", action="store_true", help="Start the local dev stack before auditing.")
    parser.add_argument("--stop", action="store_true", help="Stop the local dev stack after auditing.")
    parser.add_argument("--no-module", action="store_true", help="Do not expect or start the sibling module repo.")
    parser.add_argument("--with-feed", action="store_true", help="Append synthetic module access-log lines during the audit.")
    parser.add_argument("--shape-file", help="Optional workload-shape JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    context = build_stack_context(include_module=False if args.no_module else None)
    runner = StackRunner(context.layout)
    if args.start:
        runner.start(context.specs)

    opener = _build_opener()
    ready = _wait_for_ready(opener)
    base_url = f"http://{API_HOST}:{API_PORT}"
    workload_shape = _load_workload_shape(Path(args.shape_file) if args.shape_file else None)

    report: dict[str, Any] = {
        "ready": ready,
        "workload_shape": workload_shape,
        "health": _request_json(opener, "GET", f"{base_url}/health"),
        "auth_start": _request_json(opener, "POST", f"{base_url}/admin/auth/telegram/start"),
    }
    login_result = _login_local(opener, base_url, context.panel_env_values)
    report["local_auth"] = login_result

    if login_result.get("ok") and login_result.get("auth_mode") == "session":
        report["baseline"] = _measure_authenticated_endpoints(opener, base_url)
    else:
        report["baseline"] = {"skipped": True, "reason": "authenticated_session_unavailable"}

    feeder_result: dict[str, Any] | None = None
    if args.with_feed and context.module_enabled and context.module_env_values.get("ACCESS_LOG_PATH"):
        access_log_path = Path(context.module_env_values["ACCESS_LOG_PATH"])
        feeder_result = {}

        def _run_feeder() -> None:
            feeder_result.update(
                feed_access_log(
                    access_log_path,
                    count=int(workload_shape["feed_count"]),
                    interval_seconds=float(workload_shape["feed_interval_seconds"]),
                    inbound_tags=list(workload_shape["inbound_tags"]),
                )
            )

        feeder_thread = threading.Thread(target=_run_feeder, daemon=True)
        feeder_thread.start()
        time.sleep(0.5)
        if login_result.get("ok") and login_result.get("auth_mode") == "session":
            report["under_load"] = _measure_authenticated_endpoints(opener, base_url)
        else:
            report["under_load"] = {"skipped": True, "reason": "authenticated_session_unavailable"}
        feeder_thread.join(timeout=10)
    else:
        report["under_load"] = {"skipped": True, "reason": "synthetic_feed_disabled_or_module_missing"}
    report["synthetic_feed"] = feeder_result or {"skipped": True}

    report["sqlite_signals"] = {
        "api_stderr": _count_log_signals(context.layout.stderr_log_path("api")),
        "web_stderr": _count_log_signals(context.layout.stderr_log_path("web")),
    }
    if context.module_enabled:
        report["sqlite_signals"]["module_stderr"] = _count_log_signals(context.layout.stderr_log_path("module"))

    output_dir = context.layout.dev_dir / "audits"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"audit-{time.strftime('%Y%m%dT%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)

    if args.stop:
        runner.stop([spec.name for spec in context.specs])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
