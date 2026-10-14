# Mesh Factory office

`/factory` is the Mesh task board and live office. The owner creates work in
Intake; the selected Scrum Master assigns a connected agent or executes within
its own role, records progress, asks for clarification, and reviews the result.
OpenClaw remains the enrolled gateway and native agent runtime. Mesh owns the
coordination loop and the host-local task ledger.

`/mission-control` retains workstation, voice, resource and controller controls.
The cloud application relays authenticated requests to the owner's verified host.
It does not create a separate cloud task authority or simulate an offline host.

## Owner workflow

Select the connected execution host, then create a task with its description,
acceptance criteria and any dependencies. The normal creation flow requests
Scrum Master pickup. Leave assignment empty for the Scrum Master to choose, or
provide a preferred connected assignee. A task requiring owner approval waits
until answered; pausing the office prevents new execution admission.

The board has six columns:

| Column | Meaning |
| --- | --- |
| Intake | New work awaiting triage or an explicitly queued prerequisite. |
| Ready | Work eligible to start after required answers and dependencies. |
| Working | A host-admitted native coordination or execution turn. |
| Blocked | An owner question, execution failure or unresolved runtime receipt. |
| Review | Work needing review, unsupported response format or a reached turn limit. |
| Done | Owner-confirmed completion or an explicit evidenced Scrum Master result. |

Open a task to edit its title, description, assignment, priority and dependencies;
add comments; answer clarification; or delete it when safe. Move/reorder cards
with the board controls. Starting Working requires runtime admission rather than
a cosmetic status change. Deleting a prerequisite is rejected while another task
references it. Dependencies must be complete before dependent execution or Done.

Comments and answers persist across reloads. Answering an owner question can
request continuation through the same Scrum Master. A runtime reply alone does
not prove completion: the native path returns specialist results for Scrum Master
review and requires an explicit structured completion with evidence. Unsupported
text remains in Review with the returned result available for inspection.

Choose the Scrum Master through the agent dialog. The selected role keeps its
native identity, specialist role and memory. Changing the coordinator moves open
assignments and pending coordination mail only when no affected invocation is
running or uncertain. The dialog also links to the scoped agent terminal; the
terminal is an input/output surface, not an attachment to an arbitrary CLI process.

## Native coordination and persistence

Office data lives under `~/.progretech-mesh/factory-offices/`, namespaced by the
bound runtime and enrolled host. The Munder Difflin HiveManager ledger stores
tasks, comments, mailbox receipts and events. Additive migration preserves legacy
IDs, status values, assignments and unknown fields. Native jobs have separate
runtime receipts; losing a receipt never turns a task into Done.

An explicit `run` request persists `queued:true`. If a dependency or the Scrum
Master runtime is busy, the host waits and admits the task when ready. On host
roster recovery, only those explicit queued requests can resume. Browsing an
ordinary unqueued Intake card does not authorize execution.

The host journals an execution lease before calling OpenClaw, then binds the
actual job receipt. Deletion, reassignment and coordinator handoff are rejected
while that lease is active or uncertain. A restarted host cannot infer whether
an earlier native invocation stopped. Missing receipts remain protected for
runtime reconciliation; there is no automatic replay or fabricated cancellation.

Office pause prevents admission and the next coordination turn. It cannot undo
an already admitted model request. Coordination is bounded by the configured
iteration limit, default 8 and allowed 2–20; reaching the limit leaves Review.
Five recorded agent errors in the recent upstream breaker window pause the office.

## Bounded task tool for native agents

Gateway credentials may be literal tokens or OpenClaw SecretRefs. For SecretRefs,
Mesh uses the official authenticated gateway CLI against the configured loopback
URL, retaining the exact role, session, explicit model override and idempotency
key. The CLI uses the scoped Mesh session and no outbound delivery; it omits the
HTTP-only `mesh` channel label, which is not a registered gateway delivery
channel. The gateway agent RPC also has no per-turn `max_tokens` field, so the
HTTP path’s 384-token chatter cap is unavailable on this transport; the existing
role/model configuration and bounded request timeout apply. Mesh does not extract secret values, fall back to embedded execution or
replay a failed request. A missing terminal transport receipt preserves the
mission lease for runtime reconciliation.
OpenClaw's `replayInvalid` flag can accompany a successful tool-using turn: it
means that repeating the request may repeat side effects. Mesh consumes the
matching terminal reply once while retaining its no-replay policy. Native errors,
error payloads, aborts, timeouts and pending continuations still prevent completion.
Failed host jobs retain only bounded transport-owned diagnostic categories and
flags, never native prompts, reply text or tool output.
When a successful executor turn returns plain text, Mesh sends it to the Scrum
Master as unverified review context alongside the persisted task comments. Scrum
must independently check evidence, request a bounded repair, or ask clarification.
A plain-text Scrum decision still remains in Review; only a structured,
evidence-bearing Scrum completion can close the card. This review uses the same
coordination turn limit and does not replay the executor request.
An executor rejected specifically for model memory headroom can also return to
Scrum when the host job proves native dispatch never started. Scrum can select
another available role, self-execute or ask clarification; the host does not
automatically retry the refused role, evict models or change configuration.
Missing or positive dispatch markers and other failures retain the existing
Blocked/uncertain behavior. An initial Scrum admission refusal stays Blocked.

Task comments and matching events carry a host-owned origin. `native-tool` means
the bounded CLI accepted an update against the current task, actor and run
capability; `native-reply` means the host parsed the model’s final response.
Public requests and model JSON cannot choose these origins. A completion claim
alone is not evidence that a native tool ran.

Each admitted actor receives a command for `control_center/office_task.py` with
a capability scoped to its current task, actor and execution lease. Through its
normal native command tool it may send one JSON object on stdin:

```json
{"action":"comment","text":"Observed progress or evidence"}
```

`question` accepts the same text field and asks the owner for clarification.
The Scrum Master may use `delegate` with `to` set to an office agent ID and
`text` describing the bounded assignment. After asking or delegating, the actor
ends its turn so the host can route the next step. Final structured proposals
support delegation, self-execution, questions, review and evidenced completion.

Only the active actor can use the capability; a stale or different actor is
rejected. Each actor claims only its own pending mailbox and reads its own office
memory. The run capability is absent from browser snapshots and must not be
written to durable memory. Browser requests cannot invoke internal mission
operations or supply an agent author identity. These controls bind cooperative
host-local execution; they are not an OS sandbox between processes sharing a user.

## Activity, chatter and memory

Fleet and Factory project the same host-local native roster. Display names are
not identity keys. Existing enrolled credentials, runtime bindings, archived
history and communication settings survive release installation. Legacy aliases
remain explicit in `~/.progretech-mesh/office-runtime-bindings.json`.

Activity and relationships come from recorded native work, delegation, handoffs
and dispatched conversation turns. Queued or approaching chatter alone does not
draw a conversation link. Chatter requires active tab consent and participant
availability. An unrelated busy role is not a global veto, but the shared
inference slot and hardware resource checks still apply.

Role status and recovery distinguish observed work, sleep, idle, errors and
unknown observations. Diagnostics may inspect availability and model preparation;
they do not replay a failed task or prove productive recovery. Unknown or stale
observations remain unknown. Native role controls and active-session steering
remain host-derived and scoped; acceptance confirms delivery, not completion.

Memory indicators report bounded checkpoint metadata. A verified reviewed lesson,
a reviewed activity record and an automatic metadata receipt are different claims.
Private memory, raw transcripts, tool arguments and provider payloads are not part
of this status projection. Reviewed cross-client context may be published with
`scripts/share-agent-context.py`; it remains distinct from task execution authority.

## Relay contract

The existing same-origin owner endpoint remains
`POST /api/agents/<agent_id>/office` with `{operation,args}`. It requires an owned,
verified, connected gateway and applies the same strict validator on the host.

| Operation | Exact args |
| --- | --- |
| `task.create` | `title, description, assignee, dependsOn, needsApproval` |
| `task.update` | `id, title, description, assignee, dependsOn, priority` |
| `task.move` | `id, stage, index` |
| `task.delete` | `id` |
| `task.comment`, `task.question` | `id, text` |
| `task.approve` | `id, answer` |
| `run` | `id` |

Stages are `intake|ready|working|blocked|review|done`. Legacy status values remain
`todo|doing|blocked|done`. The roster exposes `isScrumMaster`; `isDirector` remains
an internal compatibility alias. A running task exposes `running:true` without
its capability.

`task.create` returns `result.id`. Immediate `run` admission returns a `job_id`,
`task_id`, `state:queued` and `provider:openclaw`. Waiting acceptance returns
`job_id:null` and `state:waiting_dependencies|waiting_runtime`. This is a retained
run request, not a completed mission. Snapshot polling reports its later state.

## Source and host deployment

The full 2,354-file tracked source tree from Munder Difflin commit
`2a5a5858ddf11885fe9c3980df0b9b1dfdace9a8` is retained under
`vendor/munder-difflin/` with MIT licensing. `UPSTREAM.json` identifies the single
Mesh inbox-provider extension. The executable adapter imports upstream
HiveManager, CircuitBreaker and ControlRegistry with their transitive modules.
Upstream Electron/CLI agent processes are retained as source, not launched by
Mesh. The Mesh UI does not use the upstream pixel-art interface.

Ship the matching cloud validator and host adapter together. Host requirements
remain Node 20+ and Git. `office/engine.mjs` is prebundled; npm is build-only:

```sh
cd office
npm ci
npm run build
```

The host must receive `control_center/office*.py`, `rend_bridge.py`,
`mesh_runtime.py`, `handoffs.py` and the generated bundle from the reviewed
release. Preserve all enrolled credentials and host application state. Cloud
publication alone does not update a running local bridge.

`install/mesh-host-server.py` reads the installed release manifest and starts
`control_center.run_rend` from that source using the host's invoked interpreter.
Wait for current native requests before restarting any bridge or gateway.
Inspect the actual unit on the target workstation: on the reviewed 2026-10-13
host it is `progretech-control-center.service`; generic updater scripts still
name legacy units and must not be used blindly. Rollback changes the source
manifest and restarts that verified bridge, preserving task state and receipts.

## Optional CrewAI compatibility

CrewAI remains available only for explicitly configured host environments and
compatibility tooling. It is not required for the normal connected-native Scrum
flow and is not a prerequisite for creating or assigning board tasks.

An administrator may create a separate supported Python environment, install
`requirements-office.txt`, and configure `~/.progretech-mesh/factory-runtimes.json`
with its executable, approved workspace, permitted roles and model endpoint.
Browser users cannot supply executable paths or credentials. Use the existing
factory-provider configuration contract and keep tracing/telemetry disabled.
The optional `tests/test_office_crewai.py` uses the actual framework with a
deterministic offline LLM; without that separate environment it is skipped.

## Validation and remaining limits

`tests/test_office_board.py` checks real bundled-ledger persistence, legacy
migration, cycles/dependent deletion, actor/lease boundaries, admission receipt
failure, queued dependency continuation, clarification and deterministic native
Scrum review. Office route tests cover session, origin, ownership, trust and
connection checks. Chatter tests cover participant-specific admission, resource
checks and tab-consent expiry. Runtime tests preserve existing host controls.

Deterministic receipts prove the adapter's behavior, not native model quality.
Actual native qualification requires a bounded task on the selected installed
host, real delegation/progress receipts and review of its claimed evidence.
Models may return unsupported output; that remains in Review. Unknown native
execution requires runtime reconciliation. Shared inference capacity can delay
idle participants. Neither a successful deployment nor a passing transport check
establishes sustained whole-fleet acceptance.

Installed factory helper commands resolve from `~/ptinternal/bin` first, with
`~/Rend/bin` retained only when the canonical helper is absent on older hosts.
This applies to actual role controls and host image activity receipts. New
handoff proposals use the established PT_CONTEXT deliverable directories;
legacy artifact locations remain readable without receiving new publications.
