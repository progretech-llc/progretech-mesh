from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IdentityVerification:
    ok: bool
    provider: str
    subject: str | None = None
    fingerprint: str | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


class AgentIdentityVerifier:
    name = "base"

    def verify(self, assertion: dict[str, Any]) -> IdentityVerification:
        raise NotImplementedError
