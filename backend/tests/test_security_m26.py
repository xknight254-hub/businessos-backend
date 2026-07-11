"""M2.6 secrets management checks."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _git(args):
    return subprocess.run(
        ["git", "-C", str(REPO)] + args,
        capture_output=True, text=True,
    )


def test_env_is_gitignored():
    # A real .env must never be committable.
    res = _git(["check-ignore", "-v", ".env"])
    assert res.returncode == 0, ".env is NOT gitignored — secrets could be committed"
    assert ".env" in res.stdout


def test_no_tracked_secrets():
    # Run the static secrets guard; it must exit 0.
    script = REPO / "scripts" / "check_secrets.py"
    if not script.exists():
        # If the script is missing, fall back to direct grep of tracked files.
        out = _git(["ls-files"])
        import re
        SECRET_RE = re.compile(
            r"(?i)(api[_-]?key|secret|passw|token|client[_-]?secret|private[_-]?key)"
            r"[=:][\t ]*[\"']?([A-Za-z0-9_\-]{12,})"
        )
        offenders = []
        for f in out.stdout.splitlines():
            if f == ".env" or f.endswith(".env.example"):
                continue
            content = _git(["show", f"HEAD:{f}"]).stdout
            for m in SECRET_RE.finditer(content):
                offenders.append((f, m.group(1)))
        assert not offenders, f"possible secrets: {offenders}"
        return
    res = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, cwd=str(REPO),
    )
    assert res.returncode == 0, f"secrets check failed:\n{res.stdout}\n{res.stderr}"
