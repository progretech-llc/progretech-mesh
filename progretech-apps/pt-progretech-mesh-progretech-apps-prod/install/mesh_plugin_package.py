from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import ipaddress
from urllib.parse import urlparse
from pathlib import Path
from urllib.request import Request, urlopen


MAX_PACKAGE_BYTES = 8 * 1024 * 1024
EXPECTED_PACKAGE_ID = "progretech-mesh-openclaw"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_member(member: tarfile.TarInfo) -> bool:
    name = Path(member.name)
    if name.is_absolute() or ".." in name.parts:
        return False
    if member.issym() or member.islnk() or member.isdev():
        return False
    return True


def fetch_and_stage_plugin(package: dict, *, state_dir: Path) -> Path:
    if package.get("package_id") != EXPECTED_PACKAGE_ID:
        raise ValueError("unexpected Mesh plugin package id")
    if package.get("runtime") != "openclaw":
        raise ValueError("Mesh plugin package is not for OpenClaw")

    url = str(package.get("url") or "").strip()
    expected_sha = str(package.get("sha256") or "").strip().lower()

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"https", "http"}:
        raise ValueError("Mesh plugin package URL must use HTTP or HTTPS")
    if parsed_url.scheme == "http":
        host = (parsed_url.hostname or "").lower()
        private_ok = host in {"localhost", "::1"}
        if not private_ok:
            try:
                private_ok = ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
            except ValueError:
                private_ok = False
        if not private_ok:
            raise ValueError("HTTP Mesh plugin package URL is allowed only for loopback/private-LAN hosts")
    if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise ValueError("Mesh plugin package SHA-256 is invalid")

    req = Request(url, headers={"Accept": "application/gzip", "User-Agent": "ProgreTech-Mesh-Agent/1"})
    with urlopen(req, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_PACKAGE_BYTES:
            raise ValueError("Mesh plugin package exceeds size limit")
        data = response.read(MAX_PACKAGE_BYTES + 1)

    if len(data) > MAX_PACKAGE_BYTES:
        raise ValueError("Mesh plugin package exceeds size limit")
    actual_sha = _sha256_bytes(data)
    if actual_sha != expected_sha:
        raise ValueError("Mesh plugin package integrity verification failed")

    # CodeSeal is intentionally fail-closed when an enrollment asserts that it is verified.
    signature = package.get("signature") or {}
    if signature.get("codeseal_verified") is True:
        raise ValueError(
            "Enrollment claims CodeSeal verification, but the local CodeSeal package verifier "
            "is not installed yet"
        )

    staging_root = state_dir / "packages" / EXPECTED_PACKAGE_ID / str(package.get("version") or "unknown")
    temp_root = Path(tempfile.mkdtemp(prefix="mesh-plugin-", dir=str(state_dir)))
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = tf.getmembers()
            if not members or any(not _safe_member(m) for m in members):
                raise ValueError("Mesh plugin package contains an unsafe archive member")
            tf.extractall(temp_root, members=members)

        extracted = temp_root / "progretech-mesh"
        required = ["openclaw.plugin.json", "package.json", "index.js"]
        if not extracted.is_dir() or any(not (extracted / name).is_file() for name in required):
            raise ValueError("Mesh plugin package is missing required OpenClaw plugin files")

        manifest = json.loads((extracted / "openclaw.plugin.json").read_text(encoding="utf-8"))
        if manifest.get("id") != "progretech-mesh":
            raise ValueError("Mesh plugin manifest id is invalid")

        package_json = json.loads((extracted / "package.json").read_text(encoding="utf-8"))
        if package_json.get("name") != "@progretech/openclaw-mesh":
            raise ValueError("Mesh plugin package name is invalid")
        if str(package_json.get("version")) != str(package.get("version")):
            raise ValueError("Mesh plugin version does not match enrollment")

        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extracted), str(staging_root))
        try:
            os.chmod(staging_root, 0o700)
        except OSError:
            pass
        return staging_root
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
