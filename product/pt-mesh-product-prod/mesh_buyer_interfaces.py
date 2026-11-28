"""Structural buyer integration contracts for Mesh source consumers.

These types do not authenticate users, create sessions, choose a storage backend,
or change the running Flask application. A buyer adapter must bind them to the
existing verified identity and owner-scoping rules before any use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True, slots=True)
class BuyerPrincipal:
    """Verified actor and canonical Mesh owner identifiers; never credentials."""

    subject_id: str
    owner_id: str


class BuyerIdentityProvider(Protocol):
    """Expose the principal established by an existing trusted login flow."""

    def current_principal(self) -> BuyerPrincipal | None:
        """Return the current verified principal, or None when unauthenticated."""
        ...


class BuyerScopedStorage(Protocol):
    """Store buyer records under server-derived ownership, not request input."""

    def get(self, principal: BuyerPrincipal, key: str) -> Mapping[str, object] | None:
        """Read one record in the principal's authorized owner scope."""
        ...

    def put(self, principal: BuyerPrincipal, key: str, value: Mapping[str, object]) -> None:
        """Replace one record in the principal's authorized owner scope."""
        ...

    def delete(self, principal: BuyerPrincipal, key: str) -> bool:
        """Delete one record in the principal's authorized owner scope."""
        ...


class BuyerConfiguration(Protocol):
    """Separate ordinary settings from secret retrieval and secret handling."""

    def value(self, name: str) -> str | None:
        """Read a non-secret setting from the buyer's approved config source."""
        ...

    def secret(self, name: str) -> str | None:
        """Read a secret for direct use by its authorized subsystem only."""
        ...


@dataclass(frozen=True, slots=True)
class BuyerIntegration:
    """An explicit bundle of buyer-supplied adapters; no default is installed."""

    identity: BuyerIdentityProvider
    storage: BuyerScopedStorage
    configuration: BuyerConfiguration
