"""
Module: tests.unit.conformance.test_container_hardening
Layer: tests
Purpose: The container runs as a non-root user, reports its own health, and ships no
         default credential (R5.5, CR-L16-07 / CR-L16-09).
Dependencies: pathlib, re, yaml
Used by: make test (pytest discovery), make check via test-cov

Measured before this landed: `grep -n "USER\\|HEALTHCHECK" Dockerfile` returned nothing
across all 35 lines, healthchecks existed on the neo4j and redis services but not on
app, and docker-compose.yml carried `NEO4J_AUTH: neo4j/password` — a shipped credential.
The runtime validators in config_validators.py reject the default password only in
staging/prod, so ENV=dev shipped it.

Static parse only — reads the Dockerfile and compose file, never invokes Docker.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCKERFILE = _REPO_ROOT / "Dockerfile"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_APP_SERVICE = "app"

# Credentials that must never appear literally in a committed compose file.
_SHIPPED_CREDENTIAL = re.compile(r"neo4j/password", re.I)


def _compose() -> dict[str, object]:
    """Return the parsed compose file."""
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


def _services() -> dict[str, dict[str, object]]:
    """Return the compose services mapping."""
    services = _compose().get("services")
    assert isinstance(services, dict), "docker-compose.yml declares no services"
    return services


def test_dockerfile_drops_to_a_non_root_user() -> None:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    users = re.findall(r"^USER\s+(\S+)", text, re.M)
    assert users, "Dockerfile has no USER directive; the container runs as root"
    assert users[-1] != "root", f"Dockerfile's last USER is {users[-1]!r}"


def test_dockerfile_declares_a_healthcheck() -> None:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^HEALTHCHECK\s", text, re.M), (
        "Dockerfile declares no HEALTHCHECK, so an app that has stopped serving still "
        "reports as running"
    )


def test_app_service_has_a_healthcheck() -> None:
    app = _services().get(_APP_SERVICE)
    assert isinstance(app, dict), "docker-compose.yml declares no app service"
    assert "healthcheck" in app, (
        "the app service has no healthcheck; neo4j and redis have had one all along, so "
        "`depends_on: service_healthy` cannot be used against the app"
    )


def test_compose_ships_no_default_credential() -> None:
    text = _COMPOSE.read_text(encoding="utf-8")
    offending = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), 1)
        if _SHIPPED_CREDENTIAL.search(line) and not line.lstrip().startswith("#")
    ]
    assert not offending, (
        "docker-compose.yml ships a default credential:\n  " + "\n  ".join(offending)
    )
