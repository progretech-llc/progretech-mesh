# Agent activity, availability and Factory coordination

Fleet cards open the selected agent conversation when clicked. Mesh and Factory
have separate Wake up / Sleep controls backed by the same durable per-role
workday control. Sleep pauses the selected role and requests cancellation of its
native sessions; Wake resumes it after model preload when local Ollama supports
preload. Other agents using the same model keep their model loaded. A loaded
model alone does not mean an agent is awake. Controls require the current host
adapter, an enrolled role, and the local workday controller.

Chat requests return a host job immediately. Polling reports observed milestones:
waiting for a model slot, model loading, model ready, processing a request, and
preparing the generated reply for delivery. Final replies use a single gateway
response because runtime postprocessing can replace token-stream output. Processing is an operational status, not hidden reasoning.
Mesh jobs serialize model use and wait for observed native work to become idle;
this is not a global admission controller for every external inference client.
A failed or timed-out reply is never automatically resent. New chat chooses a
fresh role session and preserves existing runtime history. Conversations remain
in the current browser page; jobs survive navigation for up to 30 minutes after
completion but do not survive host restart.

Task and terminal snapshot buttons use the authenticated host management route
for the exact selected role. They show bounded Mesh progress, availability and
selected-role Factory task metadata. They do not run a shell or expose another
role's conversation. Last reply result metadata colors fleet indicators and
Factory nodes; error nodes pulse red. No reply text is stored in the signal files.

Factory nodes float gently unless reduced motion is requested or the node is
manually positioned. Dotted directed lines represent recorded mailbox handoffs
or native sessions_send tool completions (delivery is not inferred). Wavy lines
join agents recorded as active on the same task. Clicking or keyboard-activating
a line shows its recorded task and responsibilities. Missing task parts are
explicitly shown as unreported; proximity never creates a relationship.

Selecting an OpenClaw role opens direct chat, progress and shared controls.
Selecting an office worker opens its mailbox and recent activity. Pending mailbox
items can be added, edited, prioritized or removed. Starting a mission claims only
items included in its bounded input context, preserving them as delivered context
for review. Delivery does not mean completion. Only pending items can be changed; claimed context remains in history. Sending a mailbox message by itself does not start a mission.

Local diagnostic evidence showed Qwen's advertised 262144-token context exceeding
a 32768-token runtime budget. Aligning its advertised limit to the effective budget
mitigates overflow. It does not prove every provider HTTP 400 has the same cause;
request-format failures remain explicit, with a fresh-conversation recovery option.
