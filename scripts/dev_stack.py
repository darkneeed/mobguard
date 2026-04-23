from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


API_HOST = "127.0.0.1"
API_PORT = 8000
WEB_HOST = "127.0.0.1"
WEB_PORT = 5173
LOCAL_PANEL_BASE_URL = f"http://{API_HOST}:{API_PORT}"
ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StackLayout:
    root_dir: Path
    dev_dir: Path
    log_dir: Path
    env_dir: Path
    archive_dir: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "StackLayout":
        root = root_dir.resolve()
        dev_dir = root / "runtime" / "dev"
        return cls(
            root_dir=root,
            dev_dir=dev_dir,
            log_dir=dev_dir / "logs",
            env_dir=dev_dir / "env",
            archive_dir=dev_dir / "log-archive",
        )

    def ensure_dirs(self) -> None:
        self.dev_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.env_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def pid_path(self, name: str) -> Path:
        return self.dev_dir / f"{name}.pid"

    def stdout_log_path(self, name: str) -> Path:
        return self.log_dir / f"{name}.stdout.log"

    def stderr_log_path(self, name: str) -> Path:
        return self.log_dir / f"{name}.stderr.log"


@dataclass(frozen=True)
class ManagedProcessSpec:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str]
    port: int | None = None


@dataclass(frozen=True)
class StackContext:
    layout: StackLayout
    panel_env_path: Path
    panel_env_values: dict[str, str]
    module_root: Path | None
    module_env_path: Path | None
    module_env_values: dict[str, str]
    specs: list[ManagedProcessSpec]
    module_enabled: bool


def _read_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    ordered_keys: list[str] = []
    if not path.exists():
        return values, ordered_keys
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        if normalized_key not in ordered_keys:
            ordered_keys.append(normalized_key)
        values[normalized_key] = value.strip()
    return values, ordered_keys


def _write_env_file(path: Path, values: dict[str, str], ordered_keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized_keys = list(ordered_keys)
    for key in sorted(values):
        if key not in serialized_keys:
            serialized_keys.append(key)
    payload = "\n".join(f"{key}={values[key]}" for key in serialized_keys if key in values)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def merge_env_files(
    *,
    base_env_path: Path,
    override_env_path: Path | None,
    output_env_path: Path,
    defaults: dict[str, str] | None = None,
    forced_values: dict[str, str] | None = None,
) -> dict[str, str]:
    base_values, ordered_keys = _read_env_file(base_env_path)
    merged_values = dict(base_values)
    if override_env_path and override_env_path.exists():
        override_values, override_keys = _read_env_file(override_env_path)
        for key in override_keys:
            if key not in ordered_keys:
                ordered_keys.append(key)
        merged_values.update(override_values)
    for key, value in (defaults or {}).items():
        if key not in merged_values or merged_values.get(key, "") == "":
            merged_values[key] = value
            if key not in ordered_keys:
                ordered_keys.append(key)
    for key, value in (forced_values or {}).items():
        merged_values[key] = value
        if key not in ordered_keys:
            ordered_keys.append(key)
    _write_env_file(output_env_path, merged_values, ordered_keys)
    return merged_values


def _default_npm_bin() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _select_base_env_path(root_dir: Path) -> Path:
    env_path = root_dir / ".env"
    if env_path.exists():
        return env_path
    return root_dir / ".env.example"


def resolve_module_root(panel_root: Path) -> Path | None:
    candidate = panel_root.parent / "module"
    return candidate if candidate.exists() else None


def _module_local_override_ready(module_root: Path | None) -> bool:
    return bool(module_root and (module_root / ".env.local.dev").exists())


def build_stack_context(root_dir: Path = ROOT_DIR, *, include_module: bool | None = None) -> StackContext:
    layout = StackLayout.from_root(root_dir)
    layout.ensure_dirs()

    panel_env_path = layout.env_dir / "panel.env"
    panel_env_values = merge_env_files(
        base_env_path=_select_base_env_path(layout.root_dir),
        override_env_path=layout.root_dir / ".env.local.dev",
        output_env_path=panel_env_path,
        defaults={"SESSION_COOKIE_SECURE": "false"},
    )

    specs = [
        ManagedProcessSpec(
            name="api",
            command=[
                sys.executable,
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
                "--reload",
            ],
            cwd=layout.root_dir,
            env={
                "MOBGUARD_ENV_FILE": str(panel_env_path),
                "PYTHONUNBUFFERED": "1",
            },
            port=API_PORT,
        ),
        ManagedProcessSpec(
            name="web",
            command=[
                _default_npm_bin(),
                "run",
                "dev",
                "--",
                "--host",
                WEB_HOST,
                "--port",
                str(WEB_PORT),
                "--strictPort",
            ],
            cwd=layout.root_dir / "web",
            env={},
            port=WEB_PORT,
        ),
    ]

    module_root = resolve_module_root(layout.root_dir)
    module_env_path: Path | None = None
    module_env_values: dict[str, str] = {}
    module_enabled = False
    if include_module is None:
        include_module = bool(
            module_root
            and (
                _module_local_override_ready(module_root)
                or (module_root / "runtime-logs" / "local-dev" / "module.pid").exists()
            )
        )
    if include_module and module_root:
        module_layout = module_root / "runtime-logs" / "local-dev"
        module_env_path = module_layout / "env" / "module.env"
        default_access_log = module_layout / "access.log"
        default_access_log.parent.mkdir(parents=True, exist_ok=True)
        default_access_log.touch(exist_ok=True)
        module_env_values = merge_env_files(
            base_env_path=_select_base_env_path(module_root),
            override_env_path=module_root / ".env.local.dev",
            output_env_path=module_env_path,
            defaults={"ACCESS_LOG_PATH": str(default_access_log)},
            forced_values={"PANEL_BASE_URL": LOCAL_PANEL_BASE_URL},
        )
        specs.append(
            ManagedProcessSpec(
                name="module",
                command=[sys.executable, "mobguard-module.py"],
                cwd=module_root,
                env={
                    "MOBGUARD_MODULE_ENV_FILE": str(module_env_path),
                    "PYTHONUNBUFFERED": "1",
                },
            )
        )
        module_enabled = True

    return StackContext(
        layout=layout,
        panel_env_path=panel_env_path,
        panel_env_values=panel_env_values,
        module_root=module_root,
        module_env_path=module_env_path,
        module_env_values=module_env_values,
        specs=specs,
        module_enabled=module_enabled,
    )


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process_handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _port_owner_pid(port: int) -> int | None:
    if port <= 0:
        return None
    if os.name == "nt":
        try:
            output = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        try:
            return int(output) if output else None
        except ValueError:
            return None
    try:
        output = subprocess.run(
            ["sh", "-lc", f"lsof -ti tcp:{port} -sTCP:LISTEN | head -n 1"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return int(output) if output else None
    except ValueError:
        return None


def _panel_api_is_ready() -> bool:
    try:
        with urlopen(f"http://{API_HOST}:{API_PORT}/ready", timeout=2) as response:
            raw_body = response.read()
    except (OSError, URLError):
        return False
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and str(payload.get("status") or "").lower() == "ok"


def _wait_for_port_owner(port: int, *, timeout_seconds: float = 15.0) -> int | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        owner_pid = _port_owner_pid(port)
        if owner_pid:
            return owner_pid
        time.sleep(0.2)
    return None


def _windows_child_pids(parent_pid: int) -> list[int]:
    if os.name != "nt" or parent_pid <= 0:
        return []
    try:
        output = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    f"Get-CimInstance Win32_Process -Filter \"ParentProcessId = {parent_pid}\" "
                    "| Select-Object -ExpandProperty ProcessId"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    child_pids: list[int] = []
    for line in output.splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            child_pids.append(int(value))
        except ValueError:
            continue
    return child_pids


def _terminate_pid_tree(pid: int) -> None:
    if not _is_pid_running(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        return

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 3
    while time.time() < deadline:
        if not _is_pid_running(pid):
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _safe_archive_name(path: Path) -> Path:
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    candidate = path / timestamp
    suffix = 1
    while candidate.exists():
        candidate = path / f"{timestamp}-{suffix:02d}"
        suffix += 1
    return candidate


def tail_lines(path: Path, *, lines: int = 40) -> list[str]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return content[-max(int(lines), 1) :]


class StackRunner:
    def __init__(self, layout: StackLayout):
        self.layout = layout
        self.layout.ensure_dirs()

    def cleanup_stale_pid(self, name: str) -> bool:
        pid_path = self.layout.pid_path(name)
        if not pid_path.exists():
            return False
        raw_pid = pid_path.read_text(encoding="utf-8", errors="ignore").strip()
        try:
            pid = int(raw_pid)
        except ValueError:
            pid_path.unlink(missing_ok=True)
            return True
        if _is_pid_running(pid):
            return False
        pid_path.unlink(missing_ok=True)
        return True

    def rotate_logs(self, names: list[str]) -> Path | None:
        log_paths = []
        for name in names:
            for path in (self.layout.stdout_log_path(name), self.layout.stderr_log_path(name)):
                if path.exists() and path.stat().st_size > 0:
                    log_paths.append(path)
        if not log_paths:
            return None
        archive_dir = _safe_archive_name(self.layout.archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        for path in log_paths:
            try:
                path.rename(archive_dir / path.name)
            except PermissionError:
                # Keep the active log file in place when another process still owns the handle.
                continue
        return archive_dir

    def process_status(self, name: str, *, port: int | None = None) -> dict[str, Any]:
        stale_removed = self.cleanup_stale_pid(name)
        pid_path = self.layout.pid_path(name)
        pid: int | None = None
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text(encoding="utf-8", errors="ignore").strip())
            except ValueError:
                pid = None
        port_owner_pid = _port_owner_pid(port or 0) if port else None
        return {
            "name": name,
            "pid": pid,
            "running": bool(pid and _is_pid_running(pid)),
            "port_open": _is_port_open(API_HOST, port) if port else False,
            "port_owner_pid": port_owner_pid,
            "stale_pid_removed": stale_removed,
            "pid_path": str(pid_path),
            "stdout_log": str(self.layout.stdout_log_path(name)),
            "stderr_log": str(self.layout.stderr_log_path(name)),
        }

    def stop_process(self, name: str) -> dict[str, Any]:
        pid_path = self.layout.pid_path(name)
        status = self.process_status(name)
        pid = status.get("pid")
        stopped = False
        if pid and _is_pid_running(int(pid)):
            _terminate_pid_tree(int(pid))
            stopped = True
        elif name == "api" and status.get("port_open") and _panel_api_is_ready():
            owner_pid = int(status.get("port_owner_pid") or 0)
            candidate_pids = _windows_child_pids(owner_pid) if owner_pid else []
            if not candidate_pids and owner_pid:
                candidate_pids = [owner_pid]
            for candidate_pid in candidate_pids:
                if candidate_pid > 0 and _is_pid_running(candidate_pid):
                    _terminate_pid_tree(candidate_pid)
                    stopped = True
            if stopped:
                deadline = time.time() + 5
                while time.time() < deadline and _is_port_open(API_HOST, API_PORT):
                    time.sleep(0.2)
        pid_path.unlink(missing_ok=True)
        return {
            **status,
            "stopped": stopped,
        }

    def start_process(self, spec: ManagedProcessSpec) -> dict[str, Any]:
        self.stop_process(spec.name)
        if spec.port and _is_port_open(API_HOST, spec.port):
            owner_pid = _port_owner_pid(spec.port)
            raise RuntimeError(
                f"Port {spec.port} is already in use"
                f"{f' by PID {owner_pid}' if owner_pid else ''}; stop the conflicting process before starting {spec.name}."
            )

        stdout_path = self.layout.stdout_log_path(spec.name)
        stderr_path = self.layout.stderr_log_path(spec.name)
        env = {**os.environ, **spec.env}
        spawn_kwargs: dict[str, Any] = {
            "cwd": str(spec.cwd),
            "env": env,
            "stdout": stdout_path.open("ab"),
            "stderr": stderr_path.open("ab"),
        }
        if os.name == "nt":
            spawn_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            spawn_kwargs["start_new_session"] = True

        process = subprocess.Popen(spec.command, **spawn_kwargs)
        spawn_kwargs["stdout"].close()
        spawn_kwargs["stderr"].close()
        tracked_pid = process.pid
        if spec.port:
            owner_pid = _wait_for_port_owner(spec.port)
            if owner_pid:
                tracked_pid = owner_pid
        self.layout.pid_path(spec.name).write_text(f"{tracked_pid}\n", encoding="utf-8")
        return self.process_status(spec.name, port=spec.port)

    def start(self, specs: list[ManagedProcessSpec]) -> list[dict[str, Any]]:
        self.stop([spec.name for spec in specs])
        self.rotate_logs([spec.name for spec in specs])
        return [self.start_process(spec) for spec in specs]

    def stop(self, names: list[str]) -> list[dict[str, Any]]:
        return [self.stop_process(name) for name in names]


def _print_status_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        pid = row.get("pid") or "-"
        running = "running" if row.get("running") else "stopped"
        port_state = ""
        if row.get("port_open"):
            port_state = " port-open"
        print(f"{row['name']}: {running} pid={pid}{port_state}")
        if row.get("port_owner_pid"):
            print(f"  port owner pid: {row['port_owner_pid']}")
        print(f"  pid: {row['pid_path']}")
        print(f"  out: {row['stdout_log']}")
        print(f"  err: {row['stderr_log']}")


def cmd_start(args: argparse.Namespace) -> int:
    context = build_stack_context(ROOT_DIR, include_module=False if args.no_module else None)
    runner = StackRunner(context.layout)
    statuses = runner.start(context.specs)
    _print_status_rows(statuses)
    print(f"panel env: {context.panel_env_path}")
    if context.module_enabled and context.module_env_path:
        print(f"module env: {context.module_env_path}")
    elif resolve_module_root(ROOT_DIR) and not args.no_module:
        print("module: skipped (create ../module/.env.local.dev to opt into local collector launch)")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    context = build_stack_context(ROOT_DIR, include_module=False if args.no_module else None)
    runner = StackRunner(context.layout)
    statuses = runner.stop([spec.name for spec in context.specs])
    _print_status_rows(statuses)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    context = build_stack_context(ROOT_DIR, include_module=False if args.no_module else None)
    runner = StackRunner(context.layout)
    rows = [runner.process_status(spec.name, port=spec.port) for spec in context.specs]
    _print_status_rows(rows)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    context = build_stack_context(ROOT_DIR, include_module=False if args.no_module else None)
    names = [args.name] if args.name else [spec.name for spec in context.specs]
    for name in names:
        print(f"== {name} stdout ==")
        for line in tail_lines(context.layout.stdout_log_path(name), lines=args.lines):
            print(line)
        print(f"== {name} stderr ==")
        for line in tail_lines(context.layout.stderr_log_path(name), lines=args.lines):
            print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local MobGuard dev stack launcher.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start the local API, web, and optional module stack.")
    start_parser.add_argument("--no-module", action="store_true", help="Do not attempt to start the sibling module repo.")
    start_parser.set_defaults(func=cmd_start)

    stop_parser = subparsers.add_parser("stop", help="Stop managed local dev stack processes.")
    stop_parser.add_argument("--no-module", action="store_true", help="Only stop panel-managed processes.")
    stop_parser.set_defaults(func=cmd_stop)

    status_parser = subparsers.add_parser("status", help="Show managed local dev stack status.")
    status_parser.add_argument("--no-module", action="store_true", help="Only inspect panel-managed processes.")
    status_parser.set_defaults(func=cmd_status)

    logs_parser = subparsers.add_parser("logs", help="Tail managed local dev stack logs.")
    logs_parser.add_argument("--name", choices=["api", "web", "module"], help="Limit log output to one process.")
    logs_parser.add_argument("--lines", type=int, default=40, help="How many trailing log lines to print.")
    logs_parser.add_argument("--no-module", action="store_true", help="Only inspect panel-managed processes.")
    logs_parser.set_defaults(func=cmd_logs)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
