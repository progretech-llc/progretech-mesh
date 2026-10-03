# Owner conversation synchronization

The workstation owns an append-only text feed for each configured named agent at
`/mnt/pt-context/agents/shared/conversation-sync/events.sqlite3`. This is chat
application state, not MemPalace or the task ledger. Existing task ledgers remain
authoritative. No historical chat archives are imported automatically.

The `progretech-conversation-sync` OpenClaw plugin captures owner messages and
replies, projects text into established native main sessions and explicitly bound
Telegram owner chats, and supplies bounded, project-scoped cross-interface context.
Mesh publishes the exact submitted owner text and final postprocessed result,
including local media jobs. Factory task changes become labelled status messages.
Internal system/subagent provenance, scheduled work and office chatter are excluded.

Mesh Fleet, Factory and agent terminals read the host's recent feed through the
existing authenticated `communication.get` relay. The current view shows the most
recent 100 entries; the underlying store retains older entries. Each surface keeps
its own execution session and task controls. Display mirrors never submit prompts.

OpenHands Agent Server 1.49.6 has an authenticated POST
`/api/conversations/{id}/events/sync` display projection for the exact named-role ACP
bridge. It appends deterministic assistant display events under the SDK state lock,
without calling `send_message`, `run`, or changing task/goal state. The adapter
updates the most recent conversation for each role. Busy conversations are deferred.
SDK upgrades require revalidating the small event-router patch. Existing OpenHands
bridge edits are preserved by before/after hash checks during installation.

Mirrors contain text and absolute file paths only. Media directives and Markdown
image embeds are converted to file notices. Telegram uses text-only `sendMessage`.
Originating Mesh replies receive download buttons; other Mesh tabs do not receive
automatic attachment cards. Native channel attachments retain their original
channel delivery. OpenHands retains its existing output-file capabilities; this
adapter does not add a binary attachment protocol to ACP.

New Mesh generated files go to `/mnt/pt-context/deliverables/mesh-<agent>/`;
Mesh prompt uploads go to `/mnt/pt-context/job-artifacts/mesh-attachments-<runtime>/`.
The actual PT_CONTEXT mount is mandatory. Existing files are retained in place.
Attachment paths are validated, symlinks refused, and only published files enter
the downloadable catalog. Imagen and Odexi are included in the artifact role map.
Reference-image prompts stay with the role's tool workflow instead of being sent
to the standalone text-only image generator.

## Delivery and operation

Unique source event IDs prevent duplicate records. External sends claim their
outbox record before sending. A timeout or crash is left uncertain rather than
blindly replayed; the `deliveries` table distinguishes acknowledged and uncertain
sends. Telegram/API outages therefore do not launch tasks again. Uncertain sends
need reconciliation against the destination before any manual replay. The original
interface still owns request cancellation and attachment delivery.

Bindings are derived only from existing configured roles, Telegram account mappings
and a single explicit existing owner. Tokens stay in their original configuration
or token files. The binding file is local, mode 0600. Unknown owners and roles are
not auto-enrolled. Additional tools need an explicit adapter and owner binding;
sharing a model or a MemPalace identity alone cannot synchronize their UI.

Install from the reviewed task checkout with:

```
python3 conversation_sync/install.py --evidence /mnt/pt-context/job-artifacts/agent-chat-sync-20261003
openclaw config validate
```

The evidence directory contains the exact OpenHands before/after source used by the
installer. Source or manifest changes to an installed plugin require
`openclaw plugins reload progretech-conversation-sync`. No gateway restart is needed.
Restart OpenHands only when its conversations are idle after applying the server
patch. Mesh uses its normal installed-release pointer and host/local services.

To stop mirroring, disable only `plugins.entries.progretech-conversation-sync` in
the existing OpenClaw configuration. Preserve its database and delivery receipts.
Restore the exact backed-up OpenHands bridge/router only after checking for later
edits. Local Mesh rollback uses the prior installation record. Do not replay the
shared feed into an agent as new prompts or import it into durable memory.
