"""M2.6 secrets guard — static check, no external deps.

Exits non-zero if:
- a real .env (not .env.example) is tracked by git, or
- any committed file (excluding .env.example) contains an obvious secret
  assignment with a value >= 12 chars that is NOT a known placeholder.

Run via: python scripts/check_secrets.py
Also invoked by tests/test_security_m26.py to keep the guard honest.
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|passw|token|client[_-]?secret|private[_-]?key)"
    r"[=:][\t ]*[\"']?([A-Za-z0-9_\-]{12,})"
)
# Values that are clearly placeholders, never flagged.
PLACEHOLDERS = {
    "change-this-to-a-random-secret-key",
    "dev-secret-key-change-in-production",
    "your-secret-key",
    "xxx",
}


def tracked_files():
    out = subprocess.run(
        ["git", "-C", REPO, "ls-files"], capture_output=True, text=True
    ).stdout.splitlines()
    return [f for f in out if f != ".env" and not f.endswith(".env.example")]


def check() -> int:
    findings = []

    # 1. A real .env must never be tracked.
    tracked = subprocess.run(
        ["git", "-C", REPO, "ls-files", ".env"], capture_output=True, text=True
    ).stdout.strip()
    if tracked:
        findings.append(f".env is tracked by git: {tracked}")

    # 2. Scan committed content for obvious secret literals.
    for f in tracked_files():
        try:
            content = subprocess.run(
                ["git", "-C", REPO, "show", f"HEAD:{f}"],
                capture_output=True, text=True,
            ).stdout
        except Exception:
            continue
        for m in SECRET_RE.finditer(content):
            val = m.group(2)
            if val in PLACEHOLDERS:
                continue
            findings.append(f"possible secret in {f}: {m.group(1)}={val[:6]}...")

    if findings:
        print("SECRETS CHECK FAILED:")
        for f in findings:
            print("  -", f)
        return 1
    print("SECRETS CHECK OK: no tracked secrets, .env not tracked.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
