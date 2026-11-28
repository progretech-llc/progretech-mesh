# Shared ProgreTech sign-in

Production Mesh sign-in now uses the ProgreTech broker hosted by CodeSeal. Its existing verified users table is the canonical account database; email verification and optional authenticator remain centralized. The Mesh callback validates state, S256 PKCE, issuer, audience and verified email. Mesh subscriptions and purchases are independent of Atlas and CodeSeal.

Verified legacy Firebase accounts are looked up only as ownership aliases during transition. Their existing Mesh owner UID is retained; new accounts use the canonical ProgreTech subject. An unavailable alias lookup fails closed instead of changing agent ownership silently. No new Firebase user record is created.

Deploy the CodeSeal broker first. Keep existing Firebase project configuration for legacy ownership lookup, plus agent identity, replay protection and service secrets. `MESH_AUTH_MODE=progretech-shared` selects shared sign-in. `/login` links to `/auth/progretech/login`. Development authentication remains governed by existing development-only checks.

Validation: `tests/test_progretech_shared_auth.py` checks state and audience separation; the existing ownership, agent management and production guard suites remain required. Runtime readiness does not claim live email delivery from static configuration.
