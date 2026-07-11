"""M3.1 / M3.3 — module convention conformance."""
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parent.parent / "app" / "modules"

REQUIRED_FILES = [
    "router.py", "service.py", "repository.py", "schemas.py",
    "models.py", "permissions.py", "tasks.py", "events.py",
]

EXPECTED_MODULES = {
    "auth", "inventory", "crm", "sales", "accounting",
    "procurement", "payroll", "hr", "analytics", "ai",
    "automation", "notifications",
}


def test_all_12_modules_present():
    present = {p.name for p in MODULES_DIR.iterdir() if p.is_dir()}
    missing = EXPECTED_MODULES - present
    assert not missing, f"Missing modules: {missing}"


def test_each_module_has_canonical_files():
    for mod in sorted(EXPECTED_MODULES):
        d = MODULES_DIR / mod
        for fname in REQUIRED_FILES:
            f = d / fname
            assert f.exists(), f"{mod} missing {fname}"
        assert (d / "tests" / "__init__.py").exists(), f"{mod} missing tests/__init__.py"


def test_routers_import_cleanly():
    import importlib
    for mod in sorted(EXPECTED_MODULES):
        m = importlib.import_module(f"app.modules.{mod}")
        assert hasattr(m, "router"), f"{mod} has no `router` export"


def test_no_raw_db_in_canonical_routers():
    """M3.2 guarantee: the 4 canonically-folded module routers depend on
    repositories, not the raw session. (auth/ai/automation are re-export
    shims pending their own fold and are excluded.)"""
    import subprocess
    canonical = ["inventory", "crm", "sales", "accounting"]
    bad = []
    for mod in canonical:
        rf = MODULES_DIR / mod / "router.py"
        out = subprocess.run(
            ["grep", "-nE", r"db\.execute|select\(|func\.", str(rf)],
            capture_output=True, text=True,
        ).stdout.strip()
        for line in out.splitlines():
            if "AsyncSession" in line:
                continue
            bad.append(f"{rf}: {line}")
    assert not bad, f"Raw DB usage in canonical routers:\n" + "\n".join(bad)
