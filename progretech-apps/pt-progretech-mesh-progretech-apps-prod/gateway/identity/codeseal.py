from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from .base import AgentIdentityVerifier, IdentityVerification


class CodeSealIdentityVerifier(AgentIdentityVerifier):
    name = "codeseal"

    def _fail(self, error: str, **metadata) -> IdentityVerification:
        base = {"cryptographic_verification": False, "fail_closed": True}
        base.update(metadata)
        return IdentityVerification(ok=False, provider=self.name, error=error, metadata=base)

    @staticmethod
    def _expected(assertion, key: str) -> str:
        if isinstance(assertion, dict):
            return str(assertion.get(key) or "").strip()
        return str(getattr(assertion, key, "") or "").strip()

    @staticmethod
    def _evidence(assertion):
        # Production identity evidence must be explicit. Never reinterpret the
        # surrounding assertion itself as CodeSeal evidence when the dedicated
        # evidence field is absent.
        if isinstance(assertion, dict):
            evidence = assertion.get("codeseal_evidence")
            if evidence is None:
                evidence = assertion.get("evidence")
        else:
            evidence = getattr(assertion, "codeseal_evidence", None)
            if evidence is None:
                evidence = getattr(assertion, "evidence", None)
        return evidence if isinstance(evidence, dict) else {}

    @staticmethod
    def _parse_expiry(value: str):
        if not value:
            return None
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def verify(self, assertion):
        verifier_mode = os.environ.get("CODESEAL_VERIFIER_MODE", "unconfigured").strip().lower()
        if verifier_mode != "configured":
            return self._fail("Production CodeSeal verifier is not configured")

        verify_url = os.environ.get(
            "CODESEAL_VERIFY_URL",
            "https://codeseal.progretech.com/api/v1/verify",
        ).strip()
        parsed_url = urlsplit(verify_url)
        local_registry = os.environ.get('APP_ENV') != 'production' and parsed_url.hostname in {'localhost', '127.0.0.1', '::1'}
        if parsed_url.scheme != 'https' and not (parsed_url.scheme == 'http' and local_registry):
            return self._fail("CodeSeal verifier URL must use HTTPS")

        evidence = self._evidence(assertion)
        manifest = evidence.get("manifest")
        signature = str(evidence.get("registry_signature") or "").strip()
        registry_public_key = str(evidence.get("registry_public_key") or "")

        if not isinstance(manifest, dict) or not signature or not registry_public_key:
            return self._fail(
                "CodeSeal evidence is incomplete",
                reason="missing_manifest_signature_or_registry_key",
            )

        identity = manifest.get("mesh_identity")
        if not isinstance(identity, dict):
            return self._fail(
                "CodeSeal manifest is not bound to a Mesh identity",
                reason="missing_mesh_identity_binding",
            )

        expected_agent_id = self._expected(assertion, "agent_id")
        expected_agent_name = self._expected(assertion, "agent_name") or self._expected(assertion, "name")
        expected_public_key = self._expected(assertion, "public_key")

        bound_agent_id = str(identity.get("agent_id") or "").strip()
        bound_agent_name = str(identity.get("agent_name") or "").strip()
        bound_public_key = str(identity.get("public_key") or "").strip()

        if expected_agent_id and bound_agent_id != expected_agent_id:
            return self._fail("CodeSeal agent ID binding mismatch", reason="agent_id_mismatch")
        if expected_agent_name and bound_agent_name != expected_agent_name:
            return self._fail("CodeSeal agent name binding mismatch", reason="agent_name_mismatch")
        if expected_public_key and bound_public_key != expected_public_key:
            return self._fail("CodeSeal public key binding mismatch", reason="public_key_mismatch")
        if not bound_agent_id or not bound_public_key:
            return self._fail("CodeSeal Mesh identity binding is incomplete", reason="incomplete_mesh_identity")

        if identity.get("revoked") is True:
            return self._fail("CodeSeal Mesh identity is revoked", reason="identity_revoked")

        expires_at = str(identity.get("expires_at") or "").strip()
        if expires_at:
            try:
                expiry = self._parse_expiry(expires_at)
            except Exception:
                return self._fail("CodeSeal Mesh identity expiry is invalid", reason="invalid_expiry")
            if expiry <= datetime.now(timezone.utc):
                return self._fail("CodeSeal Mesh identity is expired", reason="identity_expired")

        timeout = float(os.environ.get("CODESEAL_VERIFY_TIMEOUT_SECONDS", "5"))
        payload = json.dumps(
            {
                "manifest": manifest,
                "registry_signature": signature,
                "registry_public_key": registry_public_key,
            },
            separators=(",", ":"),
        ).encode("utf-8")

        request = Request(
            verify_url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ProgreTech-Mesh-CodeSealVerifier/1.0",
            },
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return self._fail(
                "CodeSeal verification service rejected the request",
                reason="http_error",
                http_status=int(exc.code),
            )
        except (URLError, TimeoutError, OSError):
            return self._fail(
                "CodeSeal verification service is unavailable",
                reason="verifier_unavailable",
            )
        except Exception:
            return self._fail(
                "CodeSeal verification response could not be validated",
                reason="invalid_verifier_response",
            )

        trusted = bool(body.get("valid"))
        crypto_valid = bool(body.get("cryptographic_signature_valid"))
        key_known = bool(body.get("registry_key_known"))
        record_match = bool(body.get("registry_record_match"))
        algorithm = str(body.get("algorithm") or "")

        if status != 200 or not (trusted and crypto_valid and key_known and record_match):
            return self._fail(
                "CodeSeal evidence verification failed",
                reason="registry_verification_failed",
                http_status=status,
                cryptographic_signature_valid=crypto_valid,
                registry_key_known=key_known,
                registry_record_match=record_match,
                algorithm=algorithm or None,
                event_id=body.get("event_id"),
            )

        if algorithm.lower() != "ed25519":
            return self._fail(
                "CodeSeal returned an unexpected verification algorithm",
                reason="unexpected_algorithm",
                algorithm=algorithm or None,
            )

        return IdentityVerification(
            ok=True,
            provider=self.name,
            error=None,
            metadata={
                "cryptographic_verification": True,
                "fail_closed": True,
                "registry_key_known": True,
                "registry_record_match": True,
                "algorithm": "Ed25519",
                "event_id": body.get("event_id"),
                "agent_id": bound_agent_id,
                "agent_name": bound_agent_name or None,
                "public_key_bound": True,
                "expires_at": expires_at or None,
            },
        )
