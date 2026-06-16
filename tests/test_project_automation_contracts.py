from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "Credit Card AI Payment Advisor"


if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib


def test_github_actions_ci_runs_python_and_frontend_quality_gates():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    content = workflow.read_text(encoding="utf-8")

    assert "pull_request:" in content
    assert "push:" in content
    assert "branches: [main]" in content
    assert "uv sync" in content
    assert (
        "uv run pytest tests/test_mcp_tools.py tests/test_recommend_stream_integration.py "
        "tests/test_chat_contract.py tests/test_project_automation_contracts.py -q"
    ) in content
    assert "uv run python -m scraper.run validate" in content
    assert "working-directory: Credit Card AI Payment Advisor" in content
    assert "npm ci" in content
    assert "npm run build" in content


def test_pyproject_declares_pytest_as_dev_dependency():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dev_dependencies = pyproject["dependency-groups"]["dev"]

    assert any(dep.startswith("pytest") for dep in dev_dependencies)


def test_frontend_declares_local_e2e_scripts_and_playwright_dependency():
    package_json = json.loads((FRONTEND_ROOT / "package.json").read_text(encoding="utf-8"))

    assert package_json["scripts"]["test:e2e"] == "playwright test"
    assert package_json["scripts"]["test:e2e:headed"] == "playwright test --headed"
    assert "@playwright/test" in package_json["devDependencies"]


def test_vite_proxy_can_target_local_backend_for_e2e():
    vite_config = (FRONTEND_ROOT / "vite.config.ts").read_text(encoding="utf-8")

    assert "process.env.VITE_API_PROXY_TARGET" in vite_config
    assert "https://ctbc-payment-advisor.onrender.com" in vite_config
