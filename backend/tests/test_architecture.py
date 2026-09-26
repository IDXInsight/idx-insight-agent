"""Dependency-direction checks enforced by static import analysis."""

import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "idx_insight"

PROVIDER_MODULES = {"idx_insight.llm.gemini", "idx_insight.llm.groq", "idx_insight.llm.http",
                    "idx_insight.llm.mock"}
VENDOR_SDKS = {"anthropic", "openai", "groq", "google", "httpx", "requests"}


def imports(path: pathlib.Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def modules(subpackage: str) -> list[pathlib.Path]:
    return sorted((PACKAGE / subpackage).glob("*.py"))


def test_agent_brain_depends_only_on_the_llm_interface():
    for path in modules("agent"):
        for name in imports(path):
            assert name not in PROVIDER_MODULES, f"{path.name} imports provider {name}"
            assert name.split(".")[0] not in VENDOR_SDKS, f"{path.name} imports SDK {name}"


def test_agent_brain_reaches_sectors_only_through_the_service_layer():
    for path in modules("agent"):
        for name in imports(path):
            assert name not in {"idx_insight.sectors.mock_adapter", "idx_insight.sectors.mock_data"}, \
                f"{path.name} depends on the mock Sectors implementation"


def test_analytics_is_pure():
    for path in modules("analytics"):
        for name in imports(path):
            assert not name.startswith(("idx_insight.llm", "idx_insight.sectors",
                                        "idx_insight.agent")), f"{path.name} imports {name}"


def test_provider_code_is_isolated_to_its_modules():
    for path in PACKAGE.rglob("*.py"):
        if path.parent.name == "llm":
            continue
        for name in imports(path):
            assert name not in {"idx_insight.llm.gemini", "idx_insight.llm.groq",
                                "idx_insight.llm.http"}, f"{path} imports provider {name}"


def test_no_anthropic_runtime_dependency():
    pyproject = (PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "anthropic" not in pyproject
    for path in PACKAGE.rglob("*.py"):
        assert "anthropic" not in {n.split(".")[0] for n in imports(path)}
