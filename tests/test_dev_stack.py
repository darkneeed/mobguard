import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.dev_stack import ManagedProcessSpec, StackLayout, StackRunner, merge_env_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DevStackTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="mobguard-dev-stack-")
        self.root = Path(self.temp_dir.name)
        self.layout = StackLayout.from_root(self.root)
        self.layout.ensure_dirs()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_merge_env_files_prefers_local_override_without_touching_source_files(self):
        base_env = self.root / ".env"
        override_env = self.root / ".env.local.dev"
        output_env = self.layout.env_dir / "merged.env"
        base_env.write_text("PANEL_LOCAL_USERNAME=owner\nSESSION_COOKIE_SECURE=true\n", encoding="utf-8")
        override_env.write_text("SESSION_COOKIE_SECURE=false\nPANEL_LOCAL_BYPASS_TOTP=true\n", encoding="utf-8")

        merged = merge_env_files(
            base_env_path=base_env,
            override_env_path=override_env,
            output_env_path=output_env,
            defaults={"EXTRA_FLAG": "1"},
        )

        self.assertEqual(merged["PANEL_LOCAL_USERNAME"], "owner")
        self.assertEqual(merged["SESSION_COOKIE_SECURE"], "false")
        self.assertEqual(merged["PANEL_LOCAL_BYPASS_TOTP"], "true")
        self.assertEqual(merged["EXTRA_FLAG"], "1")
        self.assertIn("PANEL_LOCAL_BYPASS_TOTP=true", output_env.read_text(encoding="utf-8"))

    def test_runner_start_stop_restart_and_stale_pid_cleanup(self):
        runner = StackRunner(self.layout)
        spec = ManagedProcessSpec(
            name="api",
            command=[sys.executable, "-c", "import time; time.sleep(300)"],
            cwd=self.root,
            env={},
        )

        first_status = runner.start([spec])[0]
        self.addCleanup(lambda: runner.stop(["api"]))
        self.assertTrue(first_status["running"])
        first_pid = first_status["pid"]

        second_status = runner.start([spec])[0]
        second_pid = second_status["pid"]
        self.assertTrue(second_status["running"])
        self.assertNotEqual(first_pid, second_pid)

        stopped = runner.stop(["api"])[0]
        self.assertTrue(stopped["stopped"])
        self.assertFalse(self.layout.pid_path("api").exists())

        self.layout.pid_path("api").write_text("999999\n", encoding="utf-8")
        stale = runner.process_status("api")
        self.assertFalse(stale["running"])
        self.assertTrue(stale["stale_pid_removed"])
        self.assertFalse(self.layout.pid_path("api").exists())

    @unittest.skipUnless(shutil.which("sh"), "POSIX shell is unavailable")
    def test_shell_wrapper_smoke_help(self):
        result = subprocess.run(
            [shutil.which("sh"), str(PROJECT_ROOT / "scripts" / "start-stack.sh"), "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("powershell") or shutil.which("pwsh"), "PowerShell is unavailable")
    def test_powershell_wrapper_smoke_help(self):
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        result = subprocess.run(
            [powershell, "-ExecutionPolicy", "Bypass", "-File", str(PROJECT_ROOT / "scripts" / "start-stack.ps1"), "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
