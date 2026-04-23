from __future__ import annotations

import argparse
import itertools
import random
import time
from datetime import datetime
from pathlib import Path


DEFAULT_TAGS = ("TAG", "LTE", "MOBILE")


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _build_access_line(identifier: str, ip: str, tag: str) -> str:
    return f"{_utcnow()} accepted [{tag}] email: {identifier} from tcp:{ip}:443\n"


def feed_access_log(
    access_log_path: Path,
    *,
    count: int,
    interval_seconds: float,
    inbound_tags: list[str] | None = None,
    identity_prefix: str = "synthetic-user",
) -> dict[str, object]:
    tags = [tag for tag in (inbound_tags or list(DEFAULT_TAGS)) if str(tag).strip()]
    if not tags:
        tags = list(DEFAULT_TAGS)
    access_log_path.parent.mkdir(parents=True, exist_ok=True)
    ip_octets = itertools.cycle(range(10, 250))
    written = 0
    with access_log_path.open("a", encoding="utf-8") as handle:
        for index in range(max(int(count), 0)):
            identifier = f"{identity_prefix}-{index % 25:02d}"
            ip = f"10.77.{next(ip_octets)}.{random.randint(2, 254)}"
            handle.write(_build_access_line(identifier, ip, tags[index % len(tags)]))
            handle.flush()
            written += 1
            if interval_seconds > 0:
                time.sleep(interval_seconds)
    return {
        "access_log_path": str(access_log_path),
        "written": written,
        "tags": tags,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append synthetic module access-log lines for local profiling.")
    parser.add_argument("--access-log", required=True, help="Target access log file path.")
    parser.add_argument("--count", type=int, default=100, help="How many synthetic access-log lines to append.")
    parser.add_argument("--interval", type=float, default=0.0, help="Delay between lines, in seconds.")
    parser.add_argument("--tag", action="append", dest="tags", help="Inbound tag to cycle through.")
    parser.add_argument("--identity-prefix", default="synthetic-user", help="Prefix for synthetic identities.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = feed_access_log(
        Path(args.access_log),
        count=args.count,
        interval_seconds=args.interval,
        inbound_tags=args.tags,
        identity_prefix=args.identity_prefix,
    )
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
