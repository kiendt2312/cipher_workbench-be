from __future__ import annotations

import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

PIPELINE_RANK = {
    "core": 0,
    "services": 1,
    "api": 2,
    "main": 3,
}
ALLOWED_APP_TARGETS = {
    "core": set(),
    "services": {"core", "services", "config", "errors"},
    "api": {"core", "services", "api", "config", "errors", "db", "history"},
    "errors": {"errors"},
    "config": set(),
    "db": {"db", "config"},
    "history": {"history", "db", "errors"},
    "main": {"core", "services", "api", "errors", "config", "main", "db"},
}
ALLOWED_EXTERNAL_ROOTS = {
    "core": set(),
    "services": set(),
    "api": {"fastapi", "pydantic", "starlette"},
    "errors": set(),
    "config": set(),
    "db": {"sqlalchemy"},
    "history": {"sqlalchemy"},
    "main": {"fastapi", "jinja2", "pydantic", "starlette", "uvicorn"},
}
FORBIDDEN_CORE_IMPORTS = (
    "fastapi",
    "starlette",
    "pydantic",
    "app.api",
    "app.services",
    "app.config",
    "app.errors",
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    reason: str

    def render(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.line}: {self.reason}"


def _source_component(path: Path, app_root: Path) -> str:
    relative = path.relative_to(app_root)
    if len(relative.parts) == 1:
        return relative.stem
    return relative.parts[0]


def _current_package(path: Path, app_root: Path) -> str:
    parent_parts = path.relative_to(app_root).parts[:-1]
    return ".".join(("app", *parent_parts))


def _imported_modules(path: Path, app_root: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _current_package(path, app_root)
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative_name = "." * node.level + (node.module or "")
                module = importlib.util.resolve_name(relative_name, package)
            else:
                module = node.module or ""
            if module in {"app", "app.errors"}:
                if module != "app":
                    imports.append((module, node.lineno))
                imports.extend(
                    (
                        module if alias.name == "*" else f"{module}.{alias.name}",
                        node.lineno,
                    )
                    for alias in node.names
                )
            else:
                imports.append((module, node.lineno))

    return imports


def _app_component(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != "app":
        return None
    return parts[1] if len(parts) > 1 else "app"


def _allowed_external_roots(path: Path, source: str) -> set[str]:
    if source == "errors" and path.name == "handlers.py":
        return {"fastapi", "starlette"}
    return ALLOWED_EXTERNAL_ROOTS[source]


def _violations_for(path: Path, app_root: Path) -> list[Violation]:
    source = _source_component(path, app_root)
    violations: list[Violation] = []

    if source not in ALLOWED_APP_TARGETS:
        return violations

    for module, line in _imported_modules(path, app_root):
        root_module = module.split(".")[0]
        target = _app_component(module)

        if (
            source == "errors"
            and path.stem in {"exceptions", "messages"}
            and (module == "app.errors.handlers" or module.startswith("app.errors.handlers."))
        ):
            violations.append(
                Violation(
                    path,
                    line,
                    f"errors/{path.name} may not depend on framework adapter {module!r}",
                )
            )
            continue

        if target is not None and target not in ALLOWED_APP_TARGETS[source]:
            if source == "core":
                reason = f"core may import only the standard library, found {module!r}"
            elif (
                source in PIPELINE_RANK
                and target in PIPELINE_RANK
                and PIPELINE_RANK[target] > PIPELINE_RANK[source]
            ):
                reason = (
                    f"upward dependency {source} -> {target} violates "
                    "main -> api -> services -> core"
                )
            else:
                reason = f"{source} may not import {module!r}"
            violations.append(Violation(path, line, reason))
            continue

        if target is not None:
            continue

        if root_module in sys.stdlib_module_names:
            continue

        if root_module not in _allowed_external_roots(path, source):
            if source == "core":
                reason = f"core may import only the standard library, found {module!r}"
            elif source == "errors" and path.stem in {"exceptions", "messages"}:
                reason = f"errors/{path.name} must remain framework-independent, found {module!r}"
            else:
                reason = f"{source} import {module!r} is outside the documented allow-list"
            violations.append(Violation(path, line, reason))

    return violations


def _find_violations(app_root: Path) -> list[Violation]:
    return [
        violation
        for path in sorted(app_root.rglob("*.py"))
        for violation in _violations_for(path, app_root)
    ]


def test_application_dependency_direction() -> None:
    violations = _find_violations(APP_ROOT)
    rendered = "\n".join(violation.render(APP_ROOT) for violation in violations)
    assert not violations, rendered


def test_layering_guard_detects_every_forbidden_core_import(tmp_path: Path) -> None:
    core = tmp_path / "core"
    core.mkdir()

    for module in FORBIDDEN_CORE_IMPORTS:
        (core / "bad.py").write_text(f"import {module}\n", encoding="utf-8")
        violations = _find_violations(tmp_path)

        assert len(violations) == 1
        assert "core may import only the standard library" in violations[0].reason


def test_layering_guard_detects_upward_dependency(tmp_path: Path) -> None:
    services = tmp_path / "services"
    services.mkdir()

    for source in ("from app.api import routes_text\n", "from app import api\n"):
        (services / "bad.py").write_text(source, encoding="utf-8")
        violations = _find_violations(tmp_path)

        assert len(violations) == 1
        assert "services -> api" in violations[0].reason


def test_services_reject_unlisted_third_party_but_allow_same_layer(tmp_path: Path) -> None:
    services = tmp_path / "services"
    services.mkdir()
    bad = services / "bad.py"

    bad.write_text("import httpx\n", encoding="utf-8")
    violations = _find_violations(tmp_path)
    assert len(violations) == 1
    assert "outside the documented allow-list" in violations[0].reason

    bad.write_text("from app.services import helpers\n", encoding="utf-8")
    assert not _find_violations(tmp_path)


def test_framework_independent_errors_reject_handler_import(tmp_path: Path) -> None:
    errors = tmp_path / "errors"
    errors.mkdir()
    (errors / "exceptions.py").write_text("from app.errors import handlers\n", encoding="utf-8")

    violations = _find_violations(tmp_path)

    assert len(violations) == 1
    assert "may not depend on framework adapter" in violations[0].reason


def test_framework_adapter_allows_only_fastapi_and_starlette(tmp_path: Path) -> None:
    errors = tmp_path / "errors"
    errors.mkdir()
    handler = errors / "handlers.py"

    handler.write_text(
        "from fastapi import Request\nfrom starlette.responses import JSONResponse\n",
        encoding="utf-8",
    )
    assert not _find_violations(tmp_path)

    handler.write_text("import httpx\n", encoding="utf-8")
    violations = _find_violations(tmp_path)
    assert len(violations) == 1
    assert "outside the documented allow-list" in violations[0].reason


def test_framework_independent_errors_reject_framework_imports(tmp_path: Path) -> None:
    for filename in ("messages.py", "exceptions.py"):
        case_root = tmp_path / filename.removesuffix(".py")
        errors = case_root / "errors"
        errors.mkdir(parents=True)
        (errors / filename).write_text("import fastapi\n", encoding="utf-8")
        violations = _find_violations(case_root)

        assert len(violations) == 1
        assert "must remain framework-independent" in violations[0].reason
