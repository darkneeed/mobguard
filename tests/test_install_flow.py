import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _find_usable_shell():
    candidates = []
    shell = shutil.which("sh")
    if shell:
        candidates.append(shell)

    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Git\bin\sh.exe",
                r"C:\Program Files\Git\usr\bin\sh.exe",
            ]
        )

    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "exit 0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return candidate
    return None


POSIX_SHELL = _find_usable_shell()


@unittest.skipUnless(POSIX_SHELL, "usable POSIX shell is unavailable")
class InstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-install-")
        self.root = Path(self.temp_dir)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.command_log = self.root / "command.log"

        shutil.copy2(PROJECT_ROOT / "install.sh", self.root / "install.sh")
        shutil.copy2(PROJECT_ROOT / ".env.example", self.root / ".env.example")
        shutil.copy2(PROJECT_ROOT / "config.json", self.root / "config.json")

        (self.root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "mobguard.py").write_text("print('mobguard')\n", encoding="utf-8")

        self._make_executable(self.root / "install.sh")
        self._write_stub(
            "docker",
            """#!/usr/bin/env sh
set -eu
log_file="${TEST_LOG:?}"

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
  printf '%s\\n' 'Docker Compose version v2.0.0'
  exit 0
fi

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "up" ]; then
  printf '%s\\n' 'compose up -d --build' >> "$log_file"
  exit 0
fi

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "ps" ]; then
  printf '%s\\n' 'compose ps' >> "$log_file"
  exit 0
fi

printf 'unsupported docker call: %s\\n' "$*" >&2
exit 1
""",
        )
        self._write_stub(
            "caddy",
            """#!/usr/bin/env sh
set -eu
printf '%s\\n' 'v2.0.0'
""",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_existing_asn_db_allows_empty_maxmind_key(self):
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir()
        (runtime_dir / "GeoLite2-ASN.mmdb").write_bytes(b"existing-mmdb")
        self._write_env(required_tokens=True, maxmind_key="")

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Найдена существующая ASN-база", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_missing_asn_db_downloads_when_maxmind_key_is_present(self):
        self._write_env(required_tokens=True, maxmind_key="test-maxmind-key")
        self._write_stub(
            "curl",
            """#!/usr/bin/env sh
set -eu
output=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$output" ] || exit 1
printf '%s' 'archive' > "$output"
""",
        )
        self._write_stub(
            "tar",
            """#!/usr/bin/env sh
set -eu
dest=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-C" ]; then
    dest="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$dest" ] || exit 1
mkdir -p "$dest/GeoLite2-ASN_FAKE"
printf '%s' 'mmdb' > "$dest/GeoLite2-ASN_FAKE/GeoLite2-ASN.mmdb"
""",
        )

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "runtime" / "GeoLite2-ASN.mmdb").exists())
        self.assertIn("Скачиваю GeoLite2-ASN.mmdb с MaxMind", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_missing_asn_db_without_key_warns_and_finishes_preparation(self):
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir()
        config_payload = '{"settings": {"shadow_mode": true}, "admin_tg_ids": [1]}\n'
        db_payload = b"sqlite-placeholder"

        (self.root / ".env").write_text(
            "\n".join(
                [
                    "TG_MAIN_BOT_TOKEN=",
                    "TG_ADMIN_BOT_TOKEN=",
                    "TG_ADMIN_BOT_USERNAME=",
                    "PANEL_TOKEN=",
                    "IPINFO_TOKEN=",
                    "MAXMIND_LICENSE_KEY=",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (runtime_dir / "config.json").write_text(config_payload, encoding="utf-8")
        (runtime_dir / "bans.db").write_bytes(db_payload)

        result = self._run_install()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("ASN-база не найдена", output)
        self.assertIn("Подготовительный этап завершён", output)
        self.assertTrue((runtime_dir / "health").exists())
        self.assertEqual((runtime_dir / "config.json").read_text(encoding="utf-8"), config_payload)
        self.assertEqual((runtime_dir / "bans.db").read_bytes(), db_payload)
        self.assertNotIn("compose up -d --build", self._read_log())

    def _run_install(self):
        env = os.environ.copy()
        env["PATH"] = str(self.bin_dir) + os.pathsep + env.get("PATH", "")
        env["TEST_LOG"] = str(self.command_log)
        return subprocess.run(
            [POSIX_SHELL, str(self.root / "install.sh")],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def _write_env(self, required_tokens, maxmind_key):
        values = {
            "TG_MAIN_BOT_TOKEN": "tg-main" if required_tokens else "",
            "TG_ADMIN_BOT_TOKEN": "tg-admin" if required_tokens else "",
            "TG_ADMIN_BOT_USERNAME": "adminbot" if required_tokens else "",
            "PANEL_TOKEN": "panel-token" if required_tokens else "",
            "IPINFO_TOKEN": "ipinfo-token" if required_tokens else "",
            "MAXMIND_LICENSE_KEY": maxmind_key,
        }
        payload = "".join(f"{key}={value}\n" for key, value in values.items())
        (self.root / ".env").write_text(payload, encoding="utf-8")

    def _write_stub(self, name, content):
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8", newline="\n")
        self._make_executable(path)

    def _make_executable(self, path):
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _read_log(self):
        if not self.command_log.exists():
            return ""
        return self.command_log.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
