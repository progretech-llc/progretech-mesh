from __future__ import annotations

import os

from .codeseal import CodeSealIdentityVerifier
from .development import DevelopmentIdentityVerifier


def build_identity_verifier():
    requested = os.environ.get("MESH_AGENT_IDENTITY_MODE", "development").strip().lower()
    if requested == "codeseal":
        return CodeSealIdentityVerifier()
    return DevelopmentIdentityVerifier()
