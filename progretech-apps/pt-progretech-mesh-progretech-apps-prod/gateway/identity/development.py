from __future__ import annotations

from .base import AgentIdentityVerifier, IdentityVerification


class DevelopmentIdentityVerifier(AgentIdentityVerifier):
    """
    Development-only identity verifier.

    This preserves the existing CS-* development scaffolding but deliberately does
    not claim cryptographic CodeSeal verification.
    """
    name = "development"

    def verify(self, assertion):
        agent_id = str(assertion.get("agent_id", "")).strip()
        identity = str(assertion.get("identity", "")).strip()

        if not agent_id or not identity:
            return IdentityVerification(
                ok=False,
                provider=self.name,
                error="agent_id and identity are required",
            )

        return IdentityVerification(
            ok=True,
            provider=self.name,
            subject=agent_id,
            fingerprint=identity,
            metadata={
                "development_only": True,
                "cryptographic_verification": False,
            },
        )
