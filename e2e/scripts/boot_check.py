"""
Module: boot_check
Layer: e2e (operational gate)
Purpose: Verify the running app container actually boots and is NOT a stale image,
         by polling GET /health until 200 and asserting its build SHA matches the
         expected source SHA (L9-01 boot gate / L9-05 staleness detection).
Dependencies: stdlib only (urllib) so it runs without the app venv.
Used by: `make boot-check`; recommended for CI (gate that the current tree builds
         a bootable image) once CI config changes are approved.

This guards against two failures the live review found:
  - L9-01: a deleted runtime asset (game_schema.yaml) made fresh builds unbootable.
  - L9-05: `docker-compose up -d` silently serving a stale image.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

_DEFAULT_RETRIES = 40
_DEFAULT_INTERVAL_S = 2.0


def _fetch_health(base_url: str) -> dict[str, object] | None:
    """GET {base_url}/health, returning the parsed `data` dict or None if unreachable."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 - local health probe
            if resp.status != 200:
                return None
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        return None
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, dict) else None


def _wait_for_health(base_url: str, retries: int, interval_s: float) -> dict[str, object]:
    """Poll /health until it returns 200, or exit non-zero after `retries`."""
    for attempt in range(1, retries + 1):
        data = _fetch_health(base_url)
        if data is not None:
            print(f"[boot-check] /health 200 after {attempt} attempt(s): {data}")
            return data
        time.sleep(interval_s)
    print(f"[boot-check] FAIL: /health never returned 200 after {retries} attempts.", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Poll health and optionally assert the running build SHA matches expectation."""
    parser = argparse.ArgumentParser(description="Verify the app boots and is not stale.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--expect-sha", default=None, help="If set, fail unless /health version matches.")
    parser.add_argument("--retries", type=int, default=_DEFAULT_RETRIES)
    parser.add_argument("--interval", type=float, default=_DEFAULT_INTERVAL_S)
    args = parser.parse_args()

    data = _wait_for_health(args.base_url, args.retries, args.interval)

    if args.expect_sha is not None:
        running = str(data.get("version", "")).strip()
        expected = args.expect_sha.strip()
        if running != expected:
            print(
                f"[boot-check] FAIL: stale image — /health version={running!r} "
                f"but source SHA={expected!r}. Rebuild with --build.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        print(f"[boot-check] OK: running build matches source SHA ({expected}).")
    print("[boot-check] PASS")


if __name__ == "__main__":
    main()
