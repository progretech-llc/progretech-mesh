# Optional Google Analytics

The hosted product uses destination `G-7VCZVY3N3Z` only after an explicit stored opt-in. New consent controls use `progretech.analytics.consent.v1`; Manabi retains its existing optional-services choice. Declining does not affect the product. Local origins, offline operation and failed preference storage send no analytics. Withdrawal removes the measurement frame and clears only this product's prefixed GA cookies, preserving workspace data.

Google runs in a fixed same-origin measurement document with a generic product title, canonical root URL and empty referrer. It receives no parent route, query, fragment, title, form values, task/document data or account identity. This deliberately reports coarse site-level visits. The document isolates normal Google automatic DOM measurement; it is **not** a security boundary against a malicious same-origin third-party script. No cross-domain linking or extra advertising consent is introduced.

The Google tag is fetched in browser tests; collection endpoints are intercepted locally so test events are not delivered. Coverage includes seeded private URL/title canaries, denial, grant, repeat grant, withdrawal/reload, offline transitions, storage failure and localhost. Public deployment evidence is separate from fixture evidence. The Google Analytics account/report UI is not verified by these tests.

Only mesh.progretech.com is enabled. Local/offline Mesh and factory-host controls are excluded. The app CSP remains restrictive; only the fixed frame permits Google script/connect.
