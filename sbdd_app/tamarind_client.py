"""Thin client for the Tamarind Bio API (https://app.tamarind.bio/api).

Every claim below was verified against the live account (repo root .env,
TAMARIND_API_KEY), not guessed from the JS-rendered docs page:
- GET  /api/openapi.json           - full OpenAPI spec (source of truth)
- GET  /api/tools/gromacs/schema   - exact GROMACS settings JSON Schema
- PUT  /api/upload/{filename}      - 308-redirects to a CloudFront/S3 PUT;
                                      MUST follow redirects, body is raw bytes
                                      (Content-Type: application/octet-stream)
- GET  /api/files                  - uploaded files show up by plain filename,
                                      which is exactly what job settings expect
                                      (server auto-resolves to <email>/<name>)
- POST /api/validate-job           - free dry-run validation, use before
                                      spending credits on /api/submit-job
"""
import os
from pathlib import Path

import requests

BASE_URL = "https://app.tamarind.bio"
_ENV_PATH = Path(__file__).parent.parent / ".env"


def _load_api_key() -> str:
    key = os.environ.get("TAMARIND_API_KEY")
    if key:
        return key
    # MCP servers are launched directly (see .mcp.json), not through a shell
    # that sources .env, so read it ourselves.
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            if line.startswith("TAMARIND_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(
        f"TAMARIND_API_KEY not set and not found in {_ENV_PATH} - "
        "add TAMARIND_API_KEY=<key> to the repo root .env file"
    )


def _headers() -> dict:
    return {"x-api-key": _load_api_key()}


def upload_file(local_path: str) -> str:
    """Upload a local file, return the filename to reference in job settings."""
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(local_path)
    resp = requests.put(
        f"{BASE_URL}/api/upload/{p.name}",
        headers={**_headers(), "Content-Type": "application/octet-stream"},
        data=p.read_bytes(),
        allow_redirects=True,  # the API 308s to the real storage endpoint
        timeout=60,
    )
    resp.raise_for_status()
    return p.name


def list_files() -> list:
    resp = requests.get(f"{BASE_URL}/api/files", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def validate_job(job_type: str, settings: dict) -> dict:
    """Free dry-run - returns {"valid": bool, "normalized": {...}} or raises
    with the API's error detail on invalid input."""
    resp = requests.post(
        f"{BASE_URL}/api/validate-job",
        headers=_headers(),
        json={"jobName": "validate-only", "type": job_type, "settings": settings},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise ValueError(f"Tamarind validation failed: {resp.text}")
    return resp.json()


def submit_job(job_name: str, job_type: str, settings: dict) -> dict:
    """Actually submits and spends credits. Call validate_job first."""
    resp = requests.post(
        f"{BASE_URL}/api/submit-job",
        headers=_headers(),
        json={"jobName": job_name, "type": job_type, "settings": settings},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise ValueError(f"Tamarind job submission failed: {resp.text}")
    return resp.json()


def get_job(job_name: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/api/jobs", headers=_headers(), params={"jobName": job_name}, timeout=15
    )
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs", [])
    return jobs[0] if jobs else {}


def get_result(job_name: str) -> str:
    """Returns an S3 presigned URL to the results zip, or raises if not ready
    (the API itself holds the request open for up to ~290s on short jobs -
    see /api/result in the OpenAPI spec)."""
    resp = requests.post(
        f"{BASE_URL}/api/result", headers=_headers(), json={"jobName": job_name}, timeout=300
    )
    if resp.status_code == 202:
        raise TimeoutError(f"result not ready yet (still aggregating): {resp.json()}")
    resp.raise_for_status()
    return resp.json()
