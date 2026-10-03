// engine.ts
import { readFileSync as readFileSync2, writeFileSync as writeFileSync2, mkdirSync as mkdirSync2, renameSync as renameSync2, unlinkSync as unlinkSync2 } from "node:fs";
import { join as join3, isAbsolute as isAbsolute3 } from "node:path";
import { randomUUID } from "node:crypto";

// ../vendor/munder-difflin/src/main/hive.ts
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  renameSync,
  readdirSync,
  statSync,
  lstatSync,
  realpathSync,
  rmSync,
  appendFileSync,
  symlinkSync,
  unlinkSync,
  copyFileSync,
  cpSync,
  chmodSync
} from "node:fs";
import { join as join2, dirname as dirname2, basename as basename2, isAbsolute as isAbsolute2, relative as relative2 } from "node:path";
import { homedir as homedir2 } from "node:os";
import { spawnSync, spawn } from "node:child_process";
import { randomBytes, createHash } from "node:crypto";

// ../vendor/munder-difflin/src/shared/claudeCommands.ts
var COMMAND_GROUPS = [
  {
    title: "SESSION",
    items: [
      { cmd: "/clear", kind: "slash", desc: "Start a fresh conversation and reclaim the full context window. The old one stays in /resume." },
      { cmd: "/resume", kind: "slash", desc: "Pick or search a past session to continue.", usage: "/resume auth refactor" },
      { cmd: "/rewind", kind: "slash", desc: "Roll code AND conversation back to an earlier checkpoint." },
      { cmd: "/compact", kind: "slash", desc: "Summarize the conversation so far to free context without losing the thread.", usage: "/compact keep the auth decisions" },
      { cmd: "claude -c", kind: "cli", desc: "Continue the most recent session in this directory." },
      { cmd: "claude -r", kind: "cli", desc: "Resume \u2014 pick or search a past session.", usage: "claude -r auth" },
      { cmd: "claude --fork-session", kind: "cli", desc: "When resuming, branch into a new session id instead of reusing the original." }
    ]
  },
  {
    title: "CONTEXT & MEMORY",
    items: [
      { cmd: "/context", kind: "slash", desc: "Visualize what is filling the context window, with optimization hints." },
      { cmd: "/memory", kind: "slash", desc: "Open the project & user CLAUDE.md memory files for editing." },
      { cmd: "/init", kind: "slash", desc: "Scan the repo and generate a CLAUDE.md capturing its conventions." },
      { cmd: "# ", kind: "slash", desc: "Quick memory: start a line with # to append a durable note to memory.", usage: "# always run prettier before committing" },
      { cmd: "claude --add-dir ../other-repo", kind: "cli", desc: "Grant the session read/write access to an extra directory." }
    ]
  },
  {
    title: "MODELS & EFFORT",
    items: [
      { cmd: "/model", kind: "slash", desc: "Switch the model for this session (saved as default); arrows tune effort.", usage: "/model opus" },
      { cmd: "/effort", kind: "slash", desc: "Set reasoning effort: low / medium / high / xhigh / max.", usage: "/effort high" },
      { cmd: "/fast", kind: "slash", desc: "Toggle fast mode \u2014 Opus with faster output, no model downgrade." },
      { cmd: "claude --model claude-sonnet-4-6[1m]", kind: "cli", desc: "Launch on a specific model. The [1m] suffix selects the 1M-token window (Dwight)." },
      { cmd: "claude --fallback-model sonnet", kind: "cli", desc: "Auto-fall back to another model when the primary is unavailable." }
    ]
  },
  {
    title: "PLAN & EXECUTE",
    items: [
      { cmd: "/plan", kind: "slash", desc: "Enter plan mode \u2014 design the change before any edits.", usage: "/plan refactor the auth module" },
      { cmd: "/goal", kind: "slash", desc: "Set a goal condition; Claude keeps working across turns until it is met.", usage: "/goal all tests pass" },
      { cmd: "/batch", kind: "slash", desc: "Decompose a large change into parallel units in git worktrees.", usage: "/batch migrate components to v2" },
      { cmd: "/diff", kind: "slash", desc: "Open the interactive diff viewer for the current changes." },
      { cmd: "/run", kind: "slash", desc: "Launch and drive the project app to see a change actually working." },
      { cmd: "/verify", kind: "slash", desc: "Build, run, and observe to confirm a change does what it should." },
      { cmd: "claude --worktree feat/x", kind: "cli", desc: "Start the session in an isolated git worktree." }
    ]
  },
  {
    title: "REVIEW & GIT",
    items: [
      { cmd: "/code-review", kind: "slash", desc: 'Hunt correctness bugs in the diff. --fix applies them, --comment posts inline; "ultra" runs a cloud deep review.', usage: "/code-review high --fix" },
      { cmd: "/simplify", kind: "slash", desc: "Cleanup-only pass over changed code (reuse/simplify) \u2014 no bug hunt." },
      { cmd: "/review", kind: "slash", desc: "Review a pull request in this session.", usage: "/review 123" },
      { cmd: "/security-review", kind: "slash", desc: "Scan pending changes for security vulnerabilities." },
      { cmd: "/ultrareview", kind: "slash", desc: "Multi-agent cloud review of the current branch / a PR." }
    ]
  },
  {
    title: "SUBAGENTS & BACKGROUND",
    items: [
      { cmd: "claude agents", kind: "cli", desc: "Open the agent view across your live + background Claude sessions." },
      { cmd: "claude agents --json", kind: "cli", desc: "Print live sessions as JSON \u2014 scriptable fleet status." },
      { cmd: "/agents", kind: "slash", desc: "Create and manage custom subagents for delegated work." },
      { cmd: "/fork", kind: "slash", desc: "Spawn a background subagent that inherits the full conversation.", usage: "/fork implement the perf fix" },
      { cmd: "/background", kind: "slash", desc: "Detach the current session so it keeps running in the background." },
      { cmd: "/tasks", kind: "slash", desc: "View and manage everything running in the background." },
      { cmd: "/stop", kind: "slash", desc: "Stop the current background session (when attached)." },
      { cmd: "claude --agent reviewer", kind: "cli", desc: "Start the session using a specific agent configuration." }
    ]
  },
  {
    title: "TOOLS & PERMISSIONS",
    items: [
      { cmd: "/permissions", kind: "slash", desc: "View and edit which tools are allowed / asked / denied." },
      { cmd: "/hooks", kind: "slash", desc: "View the configured lifecycle hooks (PreToolUse, Stop, etc.)." },
      { cmd: "claude --permission-mode bypassPermissions", kind: "cli", desc: 'Run without per-tool approval prompts (this is what "auto mode" uses).' },
      { cmd: 'claude --allowedTools "Bash(git *) Edit Read"', kind: "cli", desc: "Pre-allow specific tools so they never prompt." }
    ]
  },
  {
    title: "MCP & PLUGINS",
    items: [
      { cmd: "/mcp", kind: "slash", desc: "List/manage connected MCP servers and authenticate (OAuth)." },
      { cmd: "/plugin", kind: "slash", desc: "Manage plugins (list, install, enable, disable)." },
      { cmd: "claude mcp list", kind: "cli", desc: "List configured MCP servers and their health." },
      { cmd: "claude mcp add <name> <command>", kind: "cli", desc: "Register a new MCP server (stdio or HTTP)." }
    ]
  },
  {
    title: "USAGE & COST",
    items: [
      { cmd: "/usage", kind: "slash", desc: "Session cost, plan limits, and a breakdown by skill / subagent / MCP." },
      { cmd: "/status", kind: "slash", desc: "Account, active model, version, and connection status." },
      { cmd: 'claude -p "..." --max-budget-usd 5', kind: "cli", desc: "Cap the dollar spend for a headless run." },
      { cmd: "claude --max-turns 20", kind: "cli", desc: "Limit agentic turns (a coarse runaway guard)." }
    ]
  },
  {
    title: "AUTOMATION (HEADLESS)",
    items: [
      { cmd: 'claude -p "your prompt"', kind: "cli", desc: "Print mode: run one prompt non-interactively and exit.", usage: 'cat log | claude -p "summarize"' },
      { cmd: 'claude -p "..." --output-format json', kind: "cli", desc: "Headless with structured JSON (result, usage, cost)." },
      { cmd: 'claude -p "..." --output-format stream-json', kind: "cli", desc: "Streaming JSON events for live consumption." },
      { cmd: 'claude -p "..." --json-schema <schema>', kind: "cli", desc: "Force the headless result to match a JSON Schema." },
      { cmd: 'claude --append-system-prompt "..."', kind: "cli", desc: "Append extra instructions to the default system prompt." }
    ]
  },
  {
    title: "CONFIG",
    items: [
      { cmd: "/config", kind: "slash", desc: "Open Settings: theme, model, output style, preferences." },
      { cmd: "/theme", kind: "slash", desc: "Change the color theme (auto / light / dark / colorblind / custom)." },
      { cmd: "/statusline", kind: "slash", desc: "Configure the Claude Code status line." }
    ]
  },
  {
    title: "HELP & DIAGNOSTICS",
    items: [
      { cmd: "/help", kind: "slash", desc: "List every available slash command." },
      { cmd: "/doctor", kind: "slash", desc: "Diagnose installation / health issues (press f to auto-fix)." },
      { cmd: "/debug", kind: "slash", desc: "Enable debug logging and troubleshoot the current session." },
      { cmd: "/release-notes", kind: "slash", desc: "Browse the Claude Code changelog by version." },
      { cmd: "/remote-control", kind: "slash", desc: "Expose this session for control from claude.ai / your phone." }
    ]
  }
];

// ../vendor/munder-difflin/src/shared/codexCommands.ts
var CODEX_COMMAND_GROUPS = [
  {
    title: "SESSION",
    items: [
      { cmd: "/clear", kind: "slash", desc: "Start a fresh chat without quitting \u2014 clears the conversation context." },
      // Verified present in the codex 0.137.0 binary's own command table. It was
      // missing here while providerAutomation sent it, so the two disagreed.
      // Unlike Claude's, this one ignores any trailing focus text.
      { cmd: "/compact", kind: "slash", desc: "Summarize the conversation so far to stay under the context limit." },
      { cmd: "/help", kind: "slash", desc: "List every available slash command." },
      { cmd: "/copy", kind: "slash", desc: "Copy the latest model output to the clipboard." },
      { cmd: "/logout", kind: "slash", desc: "Clear locally stored credentials." },
      { cmd: "/rename", kind: "slash", desc: "Rename the current conversation." }
    ]
  },
  {
    title: "UI & PREFERENCES",
    items: [
      { cmd: "/theme", kind: "slash", desc: "Toggle between light and dark themes." },
      { cmd: "/vim", kind: "slash", desc: "Toggle Vim key-bindings in the input box." },
      { cmd: "/raw", kind: "slash", desc: "Toggle raw (unformatted) output for the model response." }
    ]
  },
  {
    title: "MEMORY & SKILLS",
    items: [
      { cmd: "/memories", kind: "slash", desc: "View and manage what Codex has remembered about you." },
      { cmd: "/skills", kind: "slash", desc: "Browse and manage installed Codex skills / extensions." },
      { cmd: "/hooks", kind: "slash", desc: "View the configured lifecycle hooks." }
    ]
  },
  {
    title: "APPROVALS & PERMISSIONS",
    items: [
      { cmd: "codex --dangerously-bypass-approvals-and-sandbox", kind: "cli", desc: "Skip ALL approval prompts AND drop the OS sandbox (full filesystem access). Munder Difflin no longer uses this for auto mode; it keeps the sandbox and adds the hive agent folder via --add-dir." },
      { cmd: "codex -a never -s workspace-write", kind: "cli", desc: "Never prompt for approval (-a never) but keep the sandbox scoped to the project workspace (-s workspace-write). What Munder Difflin uses for auto mode; the hive agent folder is added with --add-dir <dir>." },
      { cmd: "codex -a untrusted", kind: "cli", desc: "Only run trusted commands without asking; escalate to the user for anything else." },
      { cmd: "codex -s danger-full-access", kind: "cli", desc: "Remove all sandbox restrictions (fine-grained flag \u2014 pair with -a for full control)." }
    ]
  },
  {
    title: "AUTOMATION (HEADLESS)",
    items: [
      { cmd: 'codex -p "your prompt"', kind: "cli", desc: "Non-interactive print mode: run one prompt and exit.", usage: 'codex -p "summarise this file"' },
      { cmd: "CODEX_NON_INTERACTIVE=1 codex", kind: "cli", desc: "Suppress all interactive installer / first-run prompts. Set automatically by Munder Difflin in auto mode." }
    ]
  },
  {
    title: "CONFIG",
    items: [
      { cmd: "codex --model <model>", kind: "cli", desc: "Choose the model (e.g. o4-mini, o3).", usage: "codex --model o4-mini" },
      { cmd: "codex --provider <provider>", kind: "cli", desc: "Select the API provider (openai, azure, anthropic\u2026).", usage: "codex --provider openai" }
    ]
  }
];

// ../vendor/munder-difflin/src/shared/grokCommands.ts
var GROK_COMMAND_GROUPS = [
  {
    title: "SESSION",
    items: [
      { cmd: "/new", kind: "slash", desc: "Start a fresh session and clear the current context." },
      { cmd: "/load", kind: "slash", desc: "Load a previous workspace session.", usage: "/load [workspace] [session]" },
      { cmd: "/compact", kind: "slash", desc: "Compact conversation history while retaining the important working context.", usage: "/compact keep the current task and next step" },
      { cmd: "grok --resume <session-id>", kind: "cli", desc: "Resume an existing Grok session by ID or title." }
    ]
  },
  {
    title: "MODELS & PERMISSIONS",
    items: [
      { cmd: "/model", kind: "slash", desc: "Switch the model used by the current session." },
      { cmd: "grok --model grok-4.6", kind: "cli", desc: "Launch Grok with the Grok 4.6 coding model (the CLI default)." },
      { cmd: "/always-approve", kind: "slash", desc: "Toggle automatic approval of tool executions." },
      { cmd: "grok --permission-mode bypassPermissions", kind: "cli", desc: "Launch in always-approve mode. Munder uses this when Auto Mode is on." }
    ]
  },
  {
    title: "TOOLS & WORKFLOW",
    items: [
      { cmd: "/rewind", kind: "slash", desc: "Rewind to a previous prompt and restore its file state." },
      { cmd: "/hooks-list", kind: "slash", desc: "Show lifecycle hooks active in this session." },
      { cmd: "/skills", kind: "slash", desc: "List or load installed skills." },
      { cmd: "/multiline", kind: "slash", desc: "Toggle multiline prompt entry." }
    ]
  }
];

// ../vendor/munder-difflin/src/shared/agentProvider.ts
var AGENT_PROVIDER_PRESETS = [
  {
    id: "claude",
    label: "Claude Code",
    defaultCommand: "claude",
    commandGroups: COMMAND_GROUPS,
    autoModeFlag: "--permission-mode bypassPermissions",
    supportsModel: true,
    modelFlag: "--model",
    autoFlag: "--permission-mode bypassPermissions",
    hiveAware: true,
    canReceiveInbox: true,
    // Longest-context Claude variant — matches the "give Michael a bigger model"
    // advisory and the Recommended tag on the orchestrator picker.
    recommendedOrchestratorModel: "claude-opus-4-8[1m]",
    resumeFlag: "--resume",
    // Official Claude Code install (npm global). Used by the missing-CLI auto-install.
    installCommand: "npm install -g @anthropic-ai/claude-code",
    // Anthropic's official native installer — a standalone binary, no node/npm.
    // The only rung of the ladder that works on a machine with no Node at all.
    nativeInstallCommand: {
      posix: "curl -fsSL https://claude.ai/install.sh | bash",
      win32: "powershell -c irm https://claude.ai/install.ps1 ^| iex"
    },
    docsUrl: "https://docs.claude.com/en/docs/claude-code"
  },
  {
    id: "codex",
    label: "Codex \xB7 GPT",
    defaultCommand: "codex",
    commandGroups: CODEX_COMMAND_GROUPS,
    // Auto mode: never prompt (-a never) but KEEP codex's OS sandbox, scoped to the
    // workspace (-s workspace-write). The app used to spawn with
    // `--dangerously-bypass-approvals-and-sandbox` for one reason only: a hive
    // worker must write to its agent folder at <harnessHome>/hive/agents/<id>/,
    // a different path tree from cwd, which workspace-write blocked. That is a
    // path-layout problem, not a reason to drop the sandbox: codex's documented
    // `--add-dir <DIR>` makes extra directories writable alongside the workspace,
    // and the hive spawn path (hive.ts, which knows the agent dir) appends it.
    // So: approvals off, sandbox on, hive housekeeping still works.
    autoModeFlag: "-a never -s workspace-write",
    autoFlag: "-a never -s workspace-write",
    // Any of these on a command line means the user already chose a posture
    // (including the old full bypass) — do not stack ours on top.
    autoStanceTokens: ["-a", "--ask-for-approval", "-s", "--sandbox", "--full-auto", "--dangerously-bypass-approvals-and-sandbox"],
    // Suppresses first-run interactive prompts (directory-trust gate, installer).
    nonInteractiveEnv: { CODEX_NON_INTERACTIVE: "1" },
    supportsModel: true,
    modelFlag: "--model",
    // Codex is NOT hiveAware in the Claude-flag sense: it has no
    // `--append-system-prompt`/`--settings`. The hive protocol is injected as
    // Codex's INITIAL prompt, which it takes POSITIONALLY (`codex "<prompt>"`) —
    // hence initialPromptFlag is undefined and hive.ts appends it as a trailing arg.
    hiveAware: false,
    // …but Codex DOES expose a Claude-style hooks system (hooks.json / config.toml
    // [hooks]; PreToolUse/PostToolUse/Stop/…), so it gets full hive parity via the
    // 'codex' bridge: a per-agent CODEX_HOME/hooks.json wired to the cth-hook shim
    // (see hive.installCodexHooks). Stop→drain works natively (Codex's Stop honors
    // {decision:'block',reason} = continue-with-prompt, exactly like Claude).
    hookBridge: "codex",
    // Inbox drains via the codex-hook bridge's Stop→drain (the renderer's idle
    // inbox-wake nudge remains as a harmless fallback for an idle worker).
    canReceiveInbox: true,
    initialPromptFlag: void 0,
    positionalInitialPrompt: true,
    // Codex's long-context coding model for the orchestrator role. // TODO-verify
    // the exact codex CLI model id (couldn't install the codex CLI to confirm).
    recommendedOrchestratorModel: "gpt-5-codex",
    // Codex resumes via a SUBCOMMAND, not a flag: `codex resume [OPTIONS]
    // [SESSION_ID]`. A `--resume <id>` flag does not exist, which is why restarts
    // used to silently start a brand-new session instead of continuing.
    resumeFlag: void 0,
    resumeSubcommand: "resume",
    // Official OpenAI Codex CLI install (npm global). Used by the missing-CLI auto-install.
    installCommand: "npm install -g @openai/codex",
    docsUrl: "https://github.com/openai/codex"
  },
  {
    id: "grok",
    label: "Grok \xB7 xAI",
    defaultCommand: "grok",
    commandGroups: GROK_COMMAND_GROUPS,
    // Grok documents bypassPermissions as the CLI/config spelling of its
    // always-approve mode. Deny rules and lifecycle gates still take precedence.
    autoModeFlag: "--permission-mode bypassPermissions",
    autoFlag: "--permission-mode bypassPermissions",
    supportsModel: true,
    modelFlag: "--model",
    hiveAware: false,
    // Grok supports Claude-compatible lifecycle events but sends camelCase
    // payloads. The bridge normalizes them before forwarding to HookServer.
    hookBridge: "grok",
    canReceiveInbox: true,
    // `grok [PROMPT]` accepts the initial hive protocol as a positional prompt.
    positionalInitialPrompt: true,
    // Grok resumes interactively with `grok --resume <session-id-or-title>`.
    resumeFlag: "--resume"
  },
  {
    id: "kimi",
    label: "Kimi Code",
    defaultCommand: "kimi",
    commandGroups: [],
    // Kimi --auto handles every approval and does not stop to ask questions,
    // matching Munder Difflin's autonomous Claude/Codex default.
    autoModeFlag: "--auto",
    autoFlag: "--auto",
    supportsModel: true,
    modelFlag: "--model",
    hiveAware: false,
    // Kimi's interactive TUI has no positional initial-prompt form. It supports
    // lifecycle hooks, but Munder Difflin does not yet install a Kimi hook bridge,
    // so mail must bounce rather than being delivered with no drain path.
    canReceiveInbox: false
  },
  {
    // Google's official Gemini CLI. Unlike Antigravity (`agy`), this is the
    // open-source `@google/gemini-cli` binary and uses Gemini's native settings
    // hooks (BeforeTool/AfterTool/BeforeAgent/AfterAgent/SessionStart).
    id: "gemini",
    label: "Gemini CLI",
    defaultCommand: "gemini",
    commandGroups: [],
    // `--yolo` is deprecated upstream; approval-mode is the current spelling.
    autoModeFlag: "--approval-mode=yolo",
    autoFlag: "--approval-mode=yolo",
    supportsModel: true,
    modelFlag: "--model",
    hiveAware: false,
    bridge: { kind: "hooks", shim: "gemini" },
    canReceiveInbox: true,
    // Keep the TUI alive after processing the hive protocol seed.
    initialPromptFlag: "-i",
    recommendedOrchestratorModel: "pro",
    resumeFlag: "--resume",
    installCommand: "npm install -g @google/gemini-cli",
    docsUrl: "https://github.com/google-gemini/gemini-cli"
  },
  {
    id: "antigravity",
    label: "Antigravity \xB7 Gemini",
    defaultCommand: "agy",
    commandGroups: [],
    autoModeFlag: "--dangerously-skip-permissions",
    supportsModel: true,
    modelFlag: "--model",
    autoFlag: "--dangerously-skip-permissions",
    hiveAware: false,
    hookBridge: "agy",
    // installAgyHooks() → ~/.gemini/.../hooks.json (translating shim)
    canReceiveInbox: true,
    // via the agy-hook bridge (Stop→drain); verified agy honors hook decisions
    initialPromptFlag: "-i",
    // agy --prompt-interactive: orient the session, then continue
    recommendedOrchestratorModel: "Gemini 3.1 Pro (High)",
    // agy takes the display-name label
    resumeFlag: "--conversation"
    // agy: resume a previous conversation by ID
  },
  {
    // qwen-code — the Qwen CLI (a gemini-cli fork) driving any OpenAI-compatible
    // endpoint (OPENAI_BASE_URL). It has no hook surface, so it rides a PROXY
    // bridge (bridge.kind==='proxy'), with the OpenAI usage/tool-call shape.
    id: "qwen",
    label: "Qwen (local available)",
    defaultCommand: "qwen",
    commandGroups: [],
    // gemini-cli heritage: --yolo auto-approves all actions. // TODO-verify
    autoModeFlag: "--yolo",
    supportsModel: true,
    modelFlag: "--model",
    autoFlag: "--yolo",
    hiveAware: false,
    // SPIKE/TODO-verify: confirm qwen-code reads OPENAI_BASE_URL for its upstream
    // ('serve' inboxDelivery is reserved for a later qwen-serve HTTP push path).
    bridge: { kind: "proxy", api: "openai", baseUrlEnv: "OPENAI_BASE_URL", inboxDelivery: "terminal" },
    canReceiveInbox: true,
    // gemini-cli style interactive-orient flag. // TODO-verify
    initialPromptFlag: "-i",
    // Qwen's long-context coder model for the orchestrator. // TODO-verify
    recommendedOrchestratorModel: "qwen3-coder-plus",
    resumeFlag: void 0
  },
  {
    // OpenCode — the TypeScript AI coding agent (opencode.ai / anomalyco/opencode,
    // ex sst/opencode). NOT the archived Go opencode-ai/opencode (→ Crush). Run as
    // its interactive TUI in a PTY (like codex), oriented by --prompt.
    id: "opencode",
    label: "OpenCode",
    defaultCommand: "opencode",
    commandGroups: [],
    // OpenCode's TUI exposes no skip-permissions FLAG; headless auto-approve is a
    // config concern (permission:allow). To keep auto-mode gated behind the floor
    // `config.autoMode` toggle (Pam guardrail #2), the permission JSON is NOT a
    // static nonInteractiveEnv — spawnAgentCore builds OPENCODE_CONFIG_CONTENT
    // dynamically (permission:allow only when autoMode is on; + a local provider
    // block when a base-URL is set). So no auto flag is spliced onto the command.
    autoModeFlag: "",
    autoFlag: "",
    supportsModel: true,
    modelFlag: "--model",
    // value form: provider/model, e.g. anthropic/claude-sonnet-4-5
    hiveAware: false,
    // no --append-system-prompt/--settings; protocol rides in via --prompt
    // NATIVE PLUGIN bridge (god Decision 1): OpenCode has no Claude-shaped Stop hook,
    // but its plugin API DOES expose a real lifecycle event (session.idle). A bundled
    // per-agent plugin drains the inbox on idle and posts HIVE_SOCK payloads — the
    // same Stop→drain semantics as codex's hooks, provider-agnostic, no traffic
    // interception. Modeled as a `hooks` bridge with a new `opencode` shim so it
    // reuses the existing hooks dispatch arm (installOpenCodePlugin, sibling of
    // installCodexHooks). The config-injection proxy is the documented fallback only.
    bridge: { kind: "hooks", shim: "opencode" },
    // god-eligible. NOTE: the plugin bridge is architecturally verified (event surface
    // + payload contract) but its live runtime (auto-load + session.idle firing +
    // injection) is UNVERIFIED pending BYOK keys / a local LLM. The renderer idle
    // inbox-wake nudge (useHive.ts) is the guaranteed fallback so a god still drains.
    canReceiveInbox: true,
    initialPromptFlag: "--prompt",
    // opencode --prompt "<orchestrator/worker brief>"
    // NO recommended model — deliberately. This used to preselect
    // `anthropic/claude-sonnet-4-5` under the comment "OpenCode's own default",
    // which was wrong on both halves: it is not OpenCode's default, and it is a
    // BYOK slug that resolves only for a user who has authenticated Anthropic
    // inside OpenCode. Without that key OpenCode SILENTLY falls back to whatever
    // it can reach (observed live on Windows: "DeepSeek V4 Flash Free" via
    // OpenCode Zen) while every surface in this app went on reporting Claude
    // Sonnet 4.5 — the picker said one model, the agent ran another, and nothing
    // flagged the divergence. Undefined means buildSpawnCommand emits no
    // `--model` at all, so OpenCode uses the model the user actually configured;
    // every BYOK slug in the OpenCode model catalog stays one click away for
    // whoever has the key.
    recommendedOrchestratorModel: void 0,
    // Capturing the TUI session id for resume is unverified; spawn fresh on respawn
    // (protocol re-injected as the initial prompt), matching codex.
    resumeFlag: void 0,
    installCommand: "npm install -g opencode-ai@latest",
    // trusted, hardcoded
    // Node-free installers, for the rung that runs when npm is absent AND no Node
    // installer could be resolved (offline / unsupported platform) — until now
    // OpenCode had none, so that rung printed a manual hint and installed nothing.
    // Both are trusted, hardcoded constants and contain no double-quotes (the
    // win32 form is wrapped verbatim in `cmd /d /s /c "…"`).
    //
    // Unlike Claude, OpenCode ships NO standalone Windows one-liner: opencode.ai
    // serves the POSIX install script but has no `install.ps1` (verified 404), and
    // its docs list Chocolatey/Scoop as the Windows-native routes. `-y` because the
    // banner runs the command unattended in the agent terminal. Honest limitation:
    // this rung needs Chocolatey already present; when it isn't, the user sees
    // choco's own "not recognized" error plus the banner's existing "run the
    // command above manually" fallback — no worse off than the manual-only text.
    nativeInstallCommand: {
      posix: "curl -fsSL https://opencode.ai/install | bash",
      win32: "choco install opencode -y"
    },
    docsUrl: "https://opencode.ai/docs"
  },
  {
    // Crush — Charmbracelet's Go TUI coding agent (charmbracelet/crush), successor to
    // the archived Go opencode-ai/opencode. Non-hiveAware. Its hook surface is
    // Claude-shaped but exposes ONLY PreToolUse today (NO Stop/SessionEnd) — so a
    // hooks bridge can't drain on turn-end. Hence a PROXY bridge (qwen tier): a
    // loopback sidecar observes its LLM traffic and SYNTHESIZES the Stop→drain.
    id: "crush",
    label: "Crush \xB7 Charm",
    defaultCommand: "crush",
    commandGroups: [],
    // No CODEX_NON_INTERACTIVE analogue. First-run onboarding is suppressed by the
    // harness-written per-agent CRUSH_GLOBAL_CONFIG (provider+model+key pre-seeded),
    // set in env at spawn by installCrushConfig — NOT via this field.
    nonInteractiveEnv: void 0,
    autoModeFlag: "--yolo",
    // -y: accept all permissions (dangerous; unsandboxed). Gated by config.autoMode.
    autoFlag: "--yolo",
    supportsModel: true,
    modelFlag: "--model",
    // value format: provider/model-id, e.g. anthropic/claude-..., openai/gpt-4o
    hiveAware: false,
    // PROXY bridge. baseUrlEnv is an INTENTIONALLY INERT sentinel: Crush has NO
    // base-URL env override, so the generic proxy env-rewrite does nothing for it.
    // Real routing is via a per-agent CRUSH_GLOBAL_CONFIG whose provider base_url
    // points at the loopback (installCrushConfig, special-cased in the proxy arm).
    // Do NOT "fix" this to a real env var — it would have no effect.
    bridge: { kind: "proxy", api: "openai", baseUrlEnv: "CRUSH_PROXY_BASE_URL", inboxDelivery: "terminal" },
    // OpenAI-WIRE default so the out-of-box Crush god routes through the proxy
    // cleanly (the proxy serves one wire-shape; an anthropic/* default would route to
    // the wrong upstream — Dwight verify-crush MF1). Advisory/editable; non-OpenAI-wire
    // Crush-via-proxy is on-device live-verify. // exact long-context id humanQA
    recommendedOrchestratorModel: "openai/gpt-4o",
    // god-eligible via the proxy bridge (terminal inbox delivery on synthesized idle).
    // Live runtime (proxy parse of Crush traffic + synthesized Stop) is UNVERIFIED
    // pending keys; the renderer idle nudge is the guaranteed drain fallback.
    canReceiveInbox: true,
    // Bare `crush` is an interactive Bubble Tea TUI on a Cobra root command: the
    // first positional is parsed as a SUBCOMMAND, so a positional seed dies with
    // `unknown command "You are…"` (ondev-b live repro / spec-crush MF3). Crush has
    // NO --prompt flag either. So neither flag nor positional works → deliver the
    // protocol by TYPING it into the TUI after boot (renderer nudge path).
    initialPromptFlag: void 0,
    seedDelivery: "type-into-tui",
    resumeFlag: "--session",
    // Crush supports resume by id (also --continue for most-recent)
    installCommand: "npm install -g @charmland/crush",
    // trusted, hardcoded (brew/go/winget also valid)
    docsUrl: "https://github.com/charmbracelet/crush"
  },
  {
    // Pi (Pi Coding Agent, earendil-works; npm @earendil-works/pi-coding-agent).
    // Terminal-first, headless-driveable, 15-provider BYOK. Non-hiveAware, but has a
    // rich pi.on(event) lifecycle (tool_call→PreToolUse, agent_end→Stop, …). Bridged
    // via a bundled per-agent extension (installPiHooks) that posts HIVE_SOCK payloads
    // and auto-approves tools — a `hooks` bridge with a new `pi` shim.
    id: "pi",
    label: "Pi",
    defaultCommand: "pi",
    commandGroups: [],
    // pi has NO yolo flag. `--approve` is per-run PROJECT trust (accept the cwd so pi
    // doesn't prompt to trust the folder); the actual tool auto-allow lives INSIDE the
    // bridge extension's tool_call handler, which respects the floor auto-state via
    // HIVE_AUTO_APPROVE env (Pam guardrail #5). Gated by config.autoMode like the rest.
    autoModeFlag: "--approve",
    autoFlag: "--approve",
    // Suppress first-run version-check / telemetry chatter in the PTY. // humanQA exact names
    nonInteractiveEnv: { PI_SKIP_VERSION_CHECK: "1", PI_TELEMETRY: "0" },
    supportsModel: true,
    modelFlag: "--model",
    // value form: provider/model, e.g. anthropic/claude-sonnet-4-5 (thinking via :high)
    hiveAware: false,
    // HOOKS bridge via the new `pi` shim (installPiHooks). NOTE: only the structured
    // `bridge` is set (NOT the legacy hookBridge) — bridgeOf returns preset.bridge
    // first, so a hookBridge:'pi' would be dead weight + force a second union widening.
    bridge: { kind: "hooks", shim: "pi" },
    recommendedOrchestratorModel: "anthropic/claude-sonnet-4-5",
    // god-eligible. Live runtime (whether the extension auto-continues from agent_end,
    // or we lean on the renderer idle nudge) is UNVERIFIED pending keys. Renderer nudge
    // is the guaranteed drain fallback either way.
    canReceiveInbox: true,
    initialPromptFlag: void 0,
    // positional, like codex: pi "<prompt>"
    resumeFlag: "--session",
    // --ignore-scripts: don't run the package's postinstall on the user's machine.
    installCommand: "npm install -g --ignore-scripts @earendil-works/pi-coding-agent",
    docsUrl: "https://pi.dev/docs/latest"
  },
  {
    // GitHub Copilot CLI (`copilot`, npm @github/copilot). Driven in print mode:
    // `copilot -p "<prompt>" -s --allow-all-tools --no-ask-user [--model]`, the
    // documented non-interactive shape (single prompt, clean stdout, exits when
    // done). Non-hiveAware: it has no --append-system-prompt/--settings, so the
    // hive identity+protocol rides in as the initial prompt via `-p`.
    id: "copilot",
    label: "Copilot",
    defaultCommand: "copilot",
    commandGroups: [],
    // Non-interactive autonomy: -s prints only the agent's final response (clean
    // stdout), --allow-all-tools never blocks on a permission prompt (env:
    // COPILOT_ALLOW_ALL), --no-ask-user disables the ask_user tool so it never
    // stops to ask. Gated by the floor `config.autoMode` toggle like the rest.
    autoModeFlag: "-s --allow-all-tools --no-ask-user",
    autoFlag: "-s --allow-all-tools --no-ask-user",
    supportsModel: true,
    modelFlag: "--model",
    // e.g. claude-sonnet-4.5 (default), gpt-5.4, or 'auto'
    hiveAware: false,
    // no --append-system-prompt/--settings; protocol rides in via -p
    initialPromptFlag: "-p",
    // copilot -p "<orchestrator/worker brief>" runs it non-interactively
    recommendedOrchestratorModel: "claude-sonnet-4.5",
    // Copilot's default; user may pick gpt-5.4
    // Copilot supports session resume by id (`--resume=<id>`); attached only when a
    // prior session id was recorded (no hook bridge captures it yet → best-effort).
    resumeFlag: "--resume",
    // Print mode exits per turn and there is no hook bridge to drain on idle, so a
    // copilot worker can't receive routed inbox mail (it bounces to the god).
    canReceiveInbox: false,
    installCommand: "npm install -g @github/copilot",
    // trusted, hardcoded
    docsUrl: "https://docs.github.com/copilot/concepts/agents/about-copilot-cli"
  },
  {
    // Cursor Agent CLI (`cursor-agent`, https://cursor.com/docs/cli). The official
    // installer puts `cursor-agent` on PATH; `agent` is a shorter alias. Interactive
    // TUI by default (no `-p`), so the session stays alive for hive mail via the
    // renderer idle / work-order path — same class as Crush. Print mode (`-p`) is
    // available for scripts but exits per turn; this preset intentionally does
    // NOT use `-p` so Michael and workers remain god-eligible / inbox-capable.
    // Models (including cheap gpt-5.6-luna-*) bill against Cursor credits via the
    // logged-in CLI — there is no separate "plain OpenAI API" path for Luna.
    id: "cursor",
    label: "Cursor",
    defaultCommand: "cursor-agent",
    commandGroups: [],
    // --force/--yolo: allow tool calls without confirmations. --trust: skip the
    // workspace trust prompt so unattended Mac Mini spawns do not stall. Gated by
    // the floor config.autoMode toggle like every other engine.
    autoModeFlag: "--force --trust",
    autoFlag: "--force --trust",
    supportsModel: true,
    modelFlag: "--model",
    // e.g. gpt-5.6-luna-high, auto, composer-2.5
    hiveAware: false,
    // No Cursor hook bridge yet — mail delivery uses the terminal work-order /
    // idle-nudge fallback (same honesty as Crush before its proxy is verified).
    canReceiveInbox: true,
    // `cursor-agent` parses early argv as Cobra-style commands (login, models, mcp, …).
    // A long hive protocol string must NOT ride as a positional — type it into
    // the TUI after boot instead (Crush pattern).
    initialPromptFlag: void 0,
    seedDelivery: "type-into-tui",
    recommendedOrchestratorModel: "gpt-5.6-luna-high",
    resumeFlag: "--resume",
    // Official install is a curl|bash script (not npm). Prefer the native rung so
    // a node-free machine can still self-heal. Trusted hardcoded constants only.
    nativeInstallCommand: {
      posix: "curl https://cursor.com/install -fsS | bash",
      win32: "irm https://cursor.com/install?win32=true | iex"
    },
    docsUrl: "https://cursor.com/docs/cli/install"
  },
  {
    id: "custom",
    label: "Custom",
    defaultCommand: "",
    commandGroups: [],
    autoModeFlag: "",
    supportsModel: false,
    autoFlag: "",
    hiveAware: false,
    canReceiveInbox: false
    // no inbox-drain path → mail bounces to the god
  }
];
function providerPreset(provider) {
  return AGENT_PROVIDER_PRESETS.find((p) => p.id === provider) ?? AGENT_PROVIDER_PRESETS[0];
}
function isClaudeProvider(provider) {
  return provider === "claude";
}
function isHiveAwareProvider(provider) {
  return providerPreset(provider ?? "claude").hiveAware;
}
function canReceiveInbox(provider) {
  if (provider === "mesh") return true;
  return providerPreset(provider ?? "claude").canReceiveInbox;
}
function bridgeOf(provider) {
  const preset = providerPreset(provider ?? "claude");
  if (preset.bridge) return preset.bridge;
  if (preset.hookBridge) return { kind: "hooks", shim: preset.hookBridge };
  return void 0;
}

// ../vendor/munder-difflin/src/shared/mcpCatalog.ts
var MCP_CATALOG = [
  // ─── Safe, read-only, no-secret — shipped ON ──────────────────────────────
  {
    id: "sequential-thinking",
    label: "Sequential Thinking",
    description: "Structured step-by-step reasoning scratchpad. No I/O, no secrets.",
    spec: { command: "npx", args: ["-y", "@modelcontextprotocol/server-sequential-thinking"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  {
    id: "time",
    label: "Time",
    description: "Current time and timezone conversions.",
    // Reference time server ships as Python. // TODO-verify transport (uvx vs an npm port)
    spec: { command: "uvx", args: ["mcp-server-time"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  {
    id: "fetch",
    label: "Fetch",
    description: "Fetch a URL and return its content as markdown (read-only HTTP GET).",
    // Reference fetch server ships as Python. // TODO-verify transport (uvx vs an npm port)
    spec: { command: "uvx", args: ["mcp-server-fetch"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  {
    id: "context7",
    label: "Context7 Docs",
    description: "Up-to-date library/framework documentation lookups.",
    spec: { command: "npx", args: ["-y", "@upstash/context7-mcp"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  {
    id: "filesystem",
    label: "Filesystem (cwd)",
    description: "Read/edit files within the agent workspace only (scoped to cwd at spawn).",
    // The trailing arg is the allowed root — Workstream 3 replaces this placeholder
    // with the agent cwd at merge time so it is NEVER whole-disk.
    spec: { command: "npx", args: ["-y", "@modelcontextprotocol/server-filesystem", "<cwd>"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  {
    id: "git",
    label: "Git (cwd)",
    description: "Inspect git status/log/diff for the workspace repo (scoped to cwd at spawn).",
    // Reference git server ships as Python; `--repository <cwd>` is set at merge time.
    // TODO-verify transport (uvx vs an npm port).
    spec: { command: "uvx", args: ["mcp-server-git", "--repository", "<cwd>"] },
    tier: "safe-readonly",
    defaultEnabled: true
  },
  // ─── Write / secret — shipped OFF, consent-gated ──────────────────────────
  {
    id: "github-token",
    label: "GitHub",
    description: "Read/write GitHub issues, PRs, and repos. Requires a personal access token.",
    spec: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-github"],
      env: { GITHUB_PERSONAL_ACCESS_TOKEN: "" }
    },
    tier: "secret",
    defaultEnabled: false
  },
  {
    id: "db",
    label: "Database",
    description: "Query a SQL database. Requires a connection string.",
    // TODO-verify exact server package for the user's DB engine (Postgres assumed).
    spec: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-postgres"],
      env: { DATABASE_URL: "" }
    },
    tier: "secret",
    defaultEnabled: false
  },
  {
    id: "email-calendar",
    label: "Email & Calendar",
    description: "Read/send mail and read/write calendar events. Requires account credentials.",
    // TODO-verify provider package (Gmail/Google Calendar assumed).
    spec: { command: "npx", args: ["-y", "@modelcontextprotocol/server-gsuite"], env: { GOOGLE_OAUTH_TOKEN: "" } },
    tier: "secret",
    defaultEnabled: false
  },
  {
    id: "search-with-key",
    label: "Web Search",
    description: "Keyed web search. Requires a search-provider API key.",
    // TODO-verify provider package (Brave Search assumed).
    spec: { command: "npx", args: ["-y", "@modelcontextprotocol/server-brave-search"], env: { BRAVE_API_KEY: "" } },
    tier: "secret",
    defaultEnabled: false
  }
];

// ../vendor/munder-difflin/src/shared/broadcast.ts
function selectBroadcastTargets(agents, fromId) {
  return Object.keys(agents).filter((id) => {
    const agent2 = agents[id];
    if (!agent2) return false;
    if (id === fromId) return false;
    if (agent2.isAssistant) return false;
    if (agent2.archived) return false;
    return true;
  });
}

// ../vendor/munder-difflin/src/shared/agentRole.ts
var TRANSIENT_ROLE_RE = /^(on\s+)?standby$|^(idle|awaiting|paused|resumed|working|thinking|archived|starting up|reconnecting…?|running the floor|a fresh harness)$/i;
function isDurableRole(text) {
  const value = (text ?? "").trim();
  if (!value) return false;
  return !TRANSIENT_ROLE_RE.test(value);
}
function preferredAgentRole(candidate, fallback, isGod = false) {
  const incoming = (candidate ?? "").trim();
  const existing = (fallback ?? "").trim();
  if (isDurableRole(incoming)) return incoming;
  if (isDurableRole(existing)) return existing;
  if (incoming) return incoming;
  if (existing) return existing;
  return isGod ? "orchestrator (god)" : "agent";
}

// ../vendor/munder-difflin/src/shared/taskLedger.ts
function isRawTask(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function idOf(value) {
  if (!isRawTask(value)) return null;
  return typeof value.id === "string" && value.id ? value.id : null;
}
function mergeTaskLedger(existing, incoming) {
  const incomingList = Array.isArray(incoming) ? incoming : [];
  const existingList = Array.isArray(existing) ? existing : [];
  const byId = /* @__PURE__ */ new Map();
  for (const entry of existingList) {
    const id = idOf(entry);
    if (id && !byId.has(id)) byId.set(id, entry);
  }
  return incomingList.map((entry) => {
    const id = idOf(entry);
    if (!id) return entry;
    const prior = byId.get(id);
    return prior ? { ...prior, ...entry } : entry;
  });
}

// ../vendor/munder-difflin/src/main/fs.ts
import { constants } from "node:fs";
import { basename, dirname, isAbsolute, join, normalize, relative, resolve, sep } from "node:path";
import { homedir } from "node:os";
var READ_FLAGS = constants.O_RDONLY | (constants.O_NOFOLLOW | 0) | (constants.O_NONBLOCK | 0);
var WRITE_FLAGS = constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | (constants.O_NOFOLLOW | 0);
var MAX_READ_BYTES = 2 * 1024 * 1024;
var MAX_BINARY_READ_BYTES = 10 * 1024 * 1024;
function expandTilde(p) {
  if (typeof p !== "string") return p;
  const t = p.trim();
  if (!t) return p;
  let out = t;
  if (t === "~") out = homedir();
  else if (t.startsWith("~/") || t.startsWith("~\\")) out = join(homedir(), t.slice(2));
  if (!isAbsolute(out)) return t;
  return resolve(out);
}

// ../vendor/munder-difflin/src/shared/godIdentity.ts
var DEFAULT_GOD_NAME = "Michael";
function resolveGodName(persistedName) {
  const trimmed = persistedName?.trim();
  return trimmed ? trimmed : DEFAULT_GOD_NAME;
}

// ../vendor/munder-difflin/src/main/hive.ts
var HOP_CAP = 12;
function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}
function stamp() {
  return (/* @__PURE__ */ new Date()).toISOString().replace(/[:.]/g, "-");
}
function shortRand() {
  return randomBytes(3).toString("hex");
}
var PROXY_BIND_ATTEMPTS = 3;
var PROXY_BIND_BACKOFF_MS = [250, 750];
var MINE_IGNORE_LINES = ["settings.json", "cursor.json", "inbox/", "outbox/", ".codex/"];
function ensureMineIgnore(agentDir) {
  const path = join2(agentDir, ".gitignore");
  let existing = "";
  try {
    if (existsSync(path)) existing = readFileSync(path, "utf8");
  } catch {
    return;
  }
  const have = new Set(existing.split("\n").map((l) => l.trim()));
  const missing = MINE_IGNORE_LINES.filter((l) => !have.has(l));
  if (missing.length === 0) return;
  const prefix = existing && !existing.endsWith("\n") ? existing + "\n" : existing;
  try {
    writeFileSync(path, prefix + missing.join("\n") + "\n", "utf8");
  } catch {
  }
}
function redactSecrets(text) {
  if (typeof text !== "string" || !text) return typeof text === "string" ? text : "";
  let s = text;
  s = s.replace(/-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----/g, "[redacted]");
  s = s.replace(/\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}/g, "[redacted]");
  s = s.replace(
    /(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|xox[bpaors]-[A-Za-z0-9-]{10,}|xapp-[A-Za-z0-9-]{10,}|gh[posru]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[A-Za-z0-9_-]{20,})/g,
    "[redacted]"
  );
  s = s.replace(/\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}/gi, "$1 [redacted]");
  s = s.replace(
    /\b((?:[a-z0-9]+[_-])*(?:api[_-]?key|secret[_-]?access[_-]?key|secret|token|password|passwd|pwd|access[_-]?token|refresh[_-]?token|client[_-]?secret|signing[_-]?secret|webhook[_-]?secret|auth[_-]?token|bot[_-]?token|private[_-]?key))(\s*[:=]\s*)(["']?)[^\s"',}]{6,}\3/gi,
    (_m, k) => `${k}=[redacted]`
  );
  return s;
}
function repairLiteralLineBreaksInJsonStrings(raw) {
  let text = "";
  let inString = false;
  let escaped = false;
  let changed = false;
  for (const ch of raw) {
    if (!inString) {
      text += ch;
      if (ch === '"') inString = true;
      continue;
    }
    if (escaped) {
      text += ch;
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      text += ch;
      escaped = true;
      continue;
    }
    if (ch === '"') {
      text += ch;
      inString = false;
      continue;
    }
    if (ch === "\n") {
      text += "\\n";
      changed = true;
      continue;
    }
    if (ch === "\r") {
      text += "\\r";
      changed = true;
      continue;
    }
    text += ch;
  }
  return { text, changed };
}
var HiveManager = class {
  /**
   * @param getHome  Lazily resolve harnessHome so the hive follows config changes.
   * @param emit     Optional sink for renderer-facing events (set by the main
   *                 process to `webContents.send`). Used to animate routed
   *                 messages on the office floor; a no-op in tests/headless.
   */
  constructor(getHome, emit) {
    this.getHome = getHome;
    this.emit = emit;
  }
  getHome;
  emit;
  routerTimer = null;
  /** The embedded OTLP collector's loopback URL, set by the main process once the
   *  collector is bound (telemetry.ts). null = telemetry off → no OTel env is
   *  injected at spawn (the transcript reconciler remains the cost source). */
  _otelEndpoint = null;
  /** Point newly-spawned agents at the live telemetry collector. Call after the
   *  collector starts; only affects spawns made afterwards. */
  setOtelEndpoint(url) {
    this._otelEndpoint = url;
  }
  /** The collector URL agents are pointed at, or null when telemetry is off. */
  otelEndpoint() {
    return this._otelEndpoint;
  }
  /** What the app running this hive actually IS: its version, and whether it is a
   *  packaged build or a local dev run.
   *
   *  Agents could not see this before, and it cost real time. A multi-agent
   *  investigation into anomalous file modes ran for hours before the explanation
   *  turned out to be that the operator had quit a downloaded build and started a
   *  local one, which inherits the launching shell's umask instead of Finder's
   *  022. No agent could observe that, several published conclusions had to be
   *  withdrawn, and log.jsonl carried no app-start marker to notice the switch
   *  from either. */
  _runtime = null;
  setRuntimeInfo(info) {
    this._runtime = info;
  }
  runtimeInfo() {
    return this._runtime;
  }
  /** Whether config.orchestratorMaySpawn is on, mirrored here so the prompt
   *  builder can decide whether to tell god the spawn queue is available. Set at
   *  bootstrap and on every config write; hive.ts deliberately does not import
   *  the config module. */
  _maySpawn = false;
  setOrchestratorMaySpawn(on) {
    this._maySpawn = on;
  }
  orchestratorMaySpawn() {
    return this._maySpawn;
  }
  // — paths —
  root() {
    const home2 = this.getHome();
    return home2 ? join2(home2, "hive") : null;
  }
  enabled() {
    return this.root() !== null;
  }
  agentDir(id) {
    return join2(this.root(), "agents", id);
  }
  /** IPC endpoint the cth-hook shim talks to (Phase 1 autonomy).
   *  On POSIX this is a Unix-domain socket file under the hive root. On Windows,
   *  Node's `net` IPC uses named pipes (a flat `\\.\pipe\` namespace, not the
   *  filesystem), so a raw file path fails to bind with EACCES — derive a stable,
   *  per-root pipe name instead. Both the server (`listen`) and the shim
   *  (`createConnection`) read this same value, so they stay in sync. */
  sockPath() {
    const root = this.root();
    if (!root) return null;
    if (process.platform === "win32") {
      const id = createHash("sha1").update(root).digest("hex").slice(0, 12);
      return `\\\\.\\pipe\\munder-difflin-${id}`;
    }
    return join2(root, "hooks.sock");
  }
  shimPath() {
    const root = this.root();
    return root ? join2(root, "bin", "cth-hook.cjs") : null;
  }
  /** The proxy-bridge sidecar (qwen). Pure-Node loopback reverse-proxy that
   *  observes a hookless CLI's LLM traffic and synthesizes the same HIVE_SOCK
   *  payloads the hook shims emit. Written in ensureHive alongside cth-hook.cjs. */
  proxyShimPath() {
    const root = this.root();
    return root ? join2(root, "bin", "hive-proxy.cjs") : null;
  }
  /**
   * The BUNDLED-NODE launcher: `<root>/bin/hive-node` (POSIX) / `hive-node.cmd`
   * (Windows). Every `.cjs` shim in the hive is executed through it.
   *
   * Why it exists: hooks are run by the agent CLI through a plain
   * `/bin/sh -c` with a bare `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. A user whose
   * node comes from nvm (PATH set only by an interactive login shell) has NO node
   * there, so a hook written as `node "<shim>"` exits **127 — command not found**
   * and every payload is silently lost: no live status, no Stop→inbox drain, no
   * session ids. Electron's own binary IS a full Node runtime under
   * `ELECTRON_RUN_AS_NODE=1`, and it is guaranteed present (it is us).
   *
   * A wrapper SCRIPT rather than an inline `ELECTRON_RUN_AS_NODE=1 "<exe>" …`
   * prefix because that prefix is POSIX-sh syntax — it is a hard error under
   * cmd.exe, which is what runs hook commands on Windows. The wrapper also gives
   * agents a `$HIVE_NODE` they can invoke directly (running the Electron binary
   * WITHOUT the env var would launch a second app window, not a script).
   *
   * Rewritten on every bootstrap, so an app update/move re-bakes execPath.
   */
  nodeLauncherPath() {
    const root = this.root();
    if (!root) return null;
    return join2(root, "bin", process.platform === "win32" ? "hive-node.cmd" : "hive-node");
  }
  /** Write the launcher described above. Best-effort: on failure callers fall
   *  back to bare `node`, i.e. exactly the pre-fix behavior. */
  writeNodeLauncher() {
    const p = this.nodeLauncherPath();
    if (!p) return;
    try {
      if (process.platform === "win32") {
        writeFileSync(p, `@echo off\r
set ELECTRON_RUN_AS_NODE=1\r
"${process.execPath}" %*\r
`, "utf8");
      } else {
        writeFileSync(p, `#!/bin/sh
ELECTRON_RUN_AS_NODE=1 exec "${process.execPath}" "$@"
`, "utf8");
        chmodSync(p, 493);
      }
    } catch (e) {
      console.error("[hive] writeNodeLauncher failed:", e);
    }
  }
  /** The launcher path if it is actually on disk, else null (→ callers fall back
   *  to bare `node`, i.e. exactly the pre-fix behavior — never worse than before). */
  nodeLauncher() {
    const p = this.nodeLauncherPath();
    return p && existsSync(p) ? p : null;
  }
  /** The ABSOLUTE bundled-node command to BAKE into any text an agent is expected
   *  to run (`<launcher> <script> …`), falling back to bare `node`.
   *
   *  Exactly the value of the agent's `HIVE_NODE` env var — but agent-facing text
   *  must never spell it as `$HIVE_NODE`: that is POSIX shell syntax. A Windows
   *  agent runs its commands through cmd.exe/PowerShell, where `$HIVE_NODE`
   *  expands to NOTHING (cmd) or to an undefined variable (PowerShell), so every
   *  such instruction is dead on arrival there. The absolute path is correct on
   *  every platform and needs no expansion at all. */
  nodeCommand() {
    return this.nodeLauncher() ?? "node";
  }
  /**
   * `<root>/bin/runtime` — the same bundled-node trick as `hive-node`, but the
   * wrapper is NAMED `node`, so anything that resolves `node` off PATH finds one.
   *
   * `hive-node` only covers commands WE generate. It does nothing for node that
   * the agent's own work needs at runtime: an MCP server declared as
   * `node ./server.js`, a provider CLI that shells out to node, a `.cjs` helper an
   * agent wrote itself. On a machine with no system node those all die with 127
   * exactly like the hooks did.
   *
   * This dir is APPENDED to the agent's PATH (see pty.spawn), never prepended: a
   * user who has their own node keeps their own version — we are strictly the
   * fallback. Prepending would silently swap every agent's node for Electron's
   * (20.18.1 as of Electron 32.3.3) underneath the user's own projects.
   *
   * NOTE: `node` only — deliberately no `npm`/`npx`. Electron bundles the Node
   * RUNTIME, not the npm CLI (which is ~12MB of JS we do not ship), so an `npm`
   * wrapper here could only be a stub that fails confusingly. A missing `npm` is
   * the honest signal; the install ladder (main/cliInstall.ts) detects it and
   * installs a REAL system Node — which brings npm with it. This shim is only the
   * last resort for when that install could not run (offline, or a platform with
   * no official installer).
   */
  runtimeBinDir() {
    const root = this.root();
    return root ? join2(root, "bin", "runtime") : null;
  }
  /** Write the `node` shim described above. Best-effort: on failure the dir is
   *  simply absent from PATH and behavior is exactly as before. */
  writeRuntimeShims() {
    const dir = this.runtimeBinDir();
    if (!dir) return;
    try {
      mkdirSync(dir, { recursive: true });
      if (process.platform === "win32") {
        writeFileSync(
          join2(dir, "node.cmd"),
          `@echo off\r
set ELECTRON_RUN_AS_NODE=1\r
"${process.execPath}" %*\r
`,
          "utf8"
        );
      } else {
        const p = join2(dir, "node");
        writeFileSync(p, `#!/bin/sh
ELECTRON_RUN_AS_NODE=1 exec "${process.execPath}" "$@"
`, "utf8");
        chmodSync(p, 493);
      }
    } catch (e) {
      console.error("[hive] writeRuntimeShims failed:", e);
    }
  }
  /** Build a hook command string that runs `script` under the guaranteed node,
   *  DOUBLE-QUOTED (safe for paths with spaces). */
  nodeRun(script, ...args2) {
    const launcher = this.nodeLauncher();
    return [launcher ? `"${launcher}"` : "node", `"${script}"`, ...args2].join(" ");
  }
  /** Same, but UNQUOTED — only for configs or platforms that cannot preserve
   *  embedded quotes. POSIX JSON hook configs must use nodeRun() because the
   *  user-selected hive path may legitimately contain spaces. */
  nodeRunUnquoted(script, ...args2) {
    return [this.nodeLauncher() ?? "node", script, ...args2].join(" ");
  }
  /** One proxy sidecar per live proxy-tier agent, keyed by agentId. Spawned in
   *  ensureAgent, killed on PTY exit / removeAgent / app quit (index.ts) — so a
   *  dead agent never leaks an orphan loopback listener. */
  proxyChildren = /* @__PURE__ */ new Map();
  // — bootstrap —
  /** Create the hive skeleton + git repo if missing. Idempotent. */
  ensureHive() {
    const root = this.root();
    if (!root) return;
    mkdirSync(join2(root, "agents"), { recursive: true });
    writeFileSync(join2(root, "PROTOCOL.md"), PROTOCOL_MD, "utf8");
    const registry = join2(root, "registry.json");
    if (!existsSync(registry)) {
      this.writeJson(registry, { godId: null, agents: {} });
    }
    const userCodexHome = join2(homedir2(), ".codex");
    for (const [id, agent2] of Object.entries(this.registry().agents)) {
      const codexHome = join2(root, "agents", id, ".codex");
      if (agent2.provider === "codex" && existsSync(codexHome)) {
        this.exposeCodexDataDirs(codexHome, userCodexHome, id);
      }
    }
    const board = join2(root, "board.md");
    if (!existsSync(board)) {
      writeFileSync(board, "# Hive board\n\n_Shared plans live here. The god agent is the scribe._\n", "utf8");
    }
    const tasks = join2(root, "tasks.json");
    if (!existsSync(tasks)) this.writeJson(tasks, { tasks: [] });
    const log2 = join2(root, "log.jsonl");
    if (!existsSync(log2)) writeFileSync(log2, "", "utf8");
    writeFileSync(join2(root, "COMMANDS.md"), COMMANDS_MD, "utf8");
    const gitignore = join2(root, ".gitignore");
    const want = ["fleet.json", "hooks.sock", "cost-ledger.jsonl", "crashes/", ".DS_Store"];
    let lines = [];
    if (existsSync(gitignore)) {
      try {
        lines = readFileSync(gitignore, "utf8").split("\n");
      } catch {
        lines = [];
      }
    }
    const missing = want.filter((w) => !lines.includes(w));
    if (missing.length) writeFileSync(gitignore, [...lines.filter(Boolean), ...missing].join("\n") + "\n", "utf8");
    mkdirSync(join2(root, "bin"), { recursive: true });
    writeFileSync(this.shimPath(), HOOK_SHIM, "utf8");
    writeFileSync(this.proxyShimPath(), PROXY_BRIDGE_SHIM, "utf8");
    this.writeNodeLauncher();
    this.writeRuntimeShims();
    if (!existsSync(join2(root, ".git"))) {
      this.git(["init", "-q"], root);
      this.commit("hive: init");
    }
  }
  /** Validate an agent's cwd the way a spawn does — it must be an ABSOLUTE path
   *  that exists as a directory. Surfaced as `cwdValid` on the registry entry so
   *  the roster reliably exposes whether a worker's working directory is usable.
   *  Best-effort; never throws (a stat error degrades to invalid). */
  cwdValidity(cwd) {
    if (!cwd || typeof cwd !== "string") return { valid: false, issue: "missing" };
    cwd = expandTilde(cwd);
    if (!isAbsolute2(cwd)) return { valid: false, issue: "not-absolute" };
    try {
      return statSync(cwd).isDirectory() ? { valid: true, issue: null } : { valid: false, issue: "not-a-directory" };
    } catch {
      return { valid: false, issue: "missing-dir" };
    }
  }
  /**
   * Ensure an agent's workspace + registry entry, returning the spawn injection
   * (provider-specific args + env) that makes the process hive-aware.
   */
  async ensureAgent(meta, opts = {}) {
    const root = this.root();
    if (!root) return { args: [], env: {} };
    this.ensureHive();
    const dir = this.agentDir(meta.id);
    mkdirSync(join2(dir, "inbox", ".done"), { recursive: true });
    mkdirSync(join2(dir, "outbox", ".sent"), { recursive: true });
    const reg = this.registry();
    const prev = reg.agents[meta.id];
    if (meta.cwd) meta = { ...meta, cwd: expandTilde(meta.cwd) };
    const role = preferredAgentRole(meta.role, prev?.role, !!meta.isGod);
    meta = { ...meta, role };
    const identity = join2(dir, "identity.md");
    writeFileSync(identity, this.identityText(meta), "utf8");
    if (opts.skillsDir) this.copyBundledSkills(opts.skillsDir, join2(dir, ".claude", "skills"));
    const memory = join2(dir, "memory.md");
    if (!existsSync(memory)) {
      writeFileSync(memory, `# Memory \u2014 ${meta.name} (${meta.id})

_Append durable facts, decisions, and context below._
`, "utf8");
    }
    ensureMineIgnore(dir);
    const cursor = join2(dir, "cursor.json");
    if (!existsSync(cursor)) this.writeJson(cursor, { lastProcessed: null });
    const cwd = this.cwdValidity(meta.cwd);
    reg.agents[meta.id] = {
      ...prev,
      ...meta,
      capabilities: meta.capabilities ?? prev?.capabilities ?? [],
      role,
      status: "idle",
      cwdValid: cwd.valid,
      // A (re)spawn always means a live terminal — clear any prior archived flag.
      archived: false,
      lastSeen: Date.now()
    };
    if (meta.isGod) reg.godId = meta.id;
    this.atomicWriteJson(join2(root, "registry.json"), reg);
    this.appendLog({ kind: "spawn", agentId: meta.id, name: meta.name, isGod: !!meta.isGod });
    if (!cwd.valid) {
      this.appendLog({ kind: "cwd_invalid", agentId: meta.id, cwd: meta.cwd, issue: cwd.issue });
    }
    this.commit(`hive: register ${meta.id}`);
    const env = {
      AGENT_ID: meta.id,
      AGENT_NAME: meta.name,
      HIVE_ROOT: root,
      AGENT_DIR: dir
    };
    env.HIVE_NODE = this.nodeCommand();
    if (opts.theme) env.COLORFGBG = opts.theme === "dark" ? "15;0" : "0;15";
    const claudeProvider = isClaudeProvider(meta.provider ?? "claude");
    if (!isHiveAwareProvider(meta.provider)) {
      const preset = providerPreset(meta.provider ?? "claude");
      const flag = preset.initialPromptFlag;
      const prompt = this.injectedPrompt(meta, dir, root, opts.semanticMemory ?? false, opts.knowledgeGraph ?? false, opts.kgCliPath);
      const preArgs = [];
      let degraded;
      const desc = bridgeOf(meta.provider);
      const sock2 = this.sockPath();
      if (desc && sock2) {
        env.HIVE_SOCK = sock2;
        try {
          if (desc.kind === "hooks") {
            if (desc.shim === "agy") this.installAgyHooks();
            else if (desc.shim === "codex") {
              env.CODEX_HOME = this.installCodexHooks(dir, meta.id);
              preArgs.push("--dangerously-bypass-hook-trust");
              for (const d of this.sandboxWritableDirs(meta, dir, root, opts.extraWritableDirs)) preArgs.push("--add-dir", d);
            } else if (desc.shim === "pi") {
              env.PI_CODING_AGENT_DIR = this.installPiHooks(dir);
            } else if (desc.shim === "opencode") {
              env.OPENCODE_CONFIG_DIR = this.installOpenCodePlugin(dir, opts.theme);
            } else if (desc.shim === "gemini") {
              env.GEMINI_CLI_SYSTEM_SETTINGS_PATH = this.installGeminiHooks(dir);
            } else if (desc.shim === "grok") this.installGrokHooks();
          } else if (desc.kind === "proxy") {
            const spawnTs = String(Date.now());
            const sessionId = `proxy-${meta.id}-${createHash("sha1").update(root + meta.id + spawnTs).digest("hex").slice(0, 12)}`;
            env.HIVE_PROXY_SESSION = sessionId;
            const upstream = process.env[desc.baseUrlEnv] || (desc.api === "anthropic" ? "https://api.anthropic.com" : "https://api.openai.com/v1");
            const port = await this.startProxyBridgeWithRetry(meta.id, { sock: sock2, sessionId, api: desc.api, upstream });
            if (port > 0) {
              const loopback = `http://127.0.0.1:${port}`;
              if (meta.provider === "crush") {
                const crush = this.installCrushConfig(dir, loopback, desc.api, opts.theme);
                env.CRUSH_GLOBAL_CONFIG = dir;
                env.CRUSH_GLOBAL_DATA = crush.data;
              } else {
                env[desc.baseUrlEnv] = loopback;
              }
            } else {
              degraded = `${meta.name} is running without hive events: its proxy bridge did not bind after ${PROXY_BIND_ATTEMPTS} attempts. Live status, cost and inbox wake will not work for this session. Respawn the agent to try again.`;
              console.error(`[hive] proxy bridge for ${meta.id} did not bind \u2014 spawning without hive events`);
              this.appendLog({ kind: "proxy-degraded", agentId: meta.id, name: meta.name, provider: meta.provider, attempts: PROXY_BIND_ATTEMPTS });
              this.emit?.("hive:degraded", { agentId: meta.id, name: meta.name, reason: "proxy-bind", message: degraded });
            }
          }
        } catch (e) {
          console.error(`[hive] install ${desc.kind} bridge failed:`, e);
        }
      }
      const deg = degraded ? { degraded } : {};
      if (preset.seedDelivery === "type-into-tui") return { args: [...preArgs], env, seedPrompt: prompt, ...deg };
      if (flag) return { args: [...preArgs, flag, prompt], env, ...deg };
      if (preset.positionalInitialPrompt) return { args: [...preArgs, prompt], env, ...deg };
      return { args: preArgs, env, ...deg };
    }
    if (claudeProvider && this._otelEndpoint) {
      env.CLAUDE_CODE_ENABLE_TELEMETRY = "1";
      env.OTEL_METRICS_EXPORTER = "otlp";
      env.OTEL_LOGS_EXPORTER = "otlp";
      env.OTEL_EXPORTER_OTLP_PROTOCOL = "http/json";
      env.OTEL_EXPORTER_OTLP_ENDPOINT = this._otelEndpoint;
      env.OTEL_METRIC_EXPORT_INTERVAL = "5000";
      env.OTEL_LOGS_EXPORT_INTERVAL = "2000";
      env.OTEL_RESOURCE_ATTRIBUTES = `agent.id=${meta.id},agent.name=${meta.name}`;
    }
    const args2 = [];
    if (!claudeProvider) return { args: args2, env };
    args2.push("--append-system-prompt", this.injectedPrompt(meta, dir, root, opts.semanticMemory ?? false, opts.knowledgeGraph ?? false, opts.kgCliPath));
    const sock = this.sockPath();
    const shim = this.shimPath();
    if (sock && shim) {
      env.HIVE_SOCK = sock;
      const settingsPath2 = join2(dir, "settings.json");
      this.writeJson(settingsPath2, this.hookSettings(shim, meta.cwd, opts.mcpDefaults, opts.theme, this.sandboxWritableDirs(meta, dir, root, opts.extraWritableDirs)));
      args2.push("--settings", settingsPath2);
    }
    return { args: args2, env };
  }
  /** Update the durable job string (hire role) without respawning. Refreshes
   *  registry.json + identity.md so the floor editor and the hive stay aligned. */
  patchAgentRole(id, role) {
    const root = this.root();
    if (!root) return { ok: false, error: "hive disabled" };
    const next = role.trim();
    if (!next) return { ok: false, error: "empty role" };
    try {
      const reg = this.registry();
      const agent2 = reg.agents[id];
      if (!agent2) return { ok: false, error: "unknown agent" };
      if (agent2.role === next) return { ok: true };
      agent2.role = next;
      agent2.lastSeen = Date.now();
      this.writeJson(join2(root, "registry.json"), reg);
      writeFileSync(join2(this.agentDir(id), "identity.md"), this.identityText(agent2), "utf8");
      this.appendLog({ kind: "role", agentId: id, role: next });
      this.commit(`hive: role ${id}`);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  }
  /**
   * Flip an agent's archived flag and persist the registry. Closing a terminal
   * tab archives the agent (retained + flagged, NOT deleted); a (re)spawn clears
   * it. No-op if the agent isn't registered or the flag is already set the way
   * asked. Best-effort — never throws, so a dying PTY/kill handler can't crash.
   */
  setArchived(id, archived) {
    const root = this.root();
    if (!root) return;
    try {
      const reg = this.registry();
      const agent2 = reg.agents[id];
      if (!agent2 || agent2.archived === archived) return;
      agent2.archived = archived;
      agent2.lastSeen = Date.now();
      this.atomicWriteJson(join2(root, "registry.json"), reg);
      this.appendLog({ kind: "archive", agentId: id, archived });
      this.commit(`hive: ${archived ? "archive" : "unarchive"} ${id}`);
    } catch {
    }
  }
  /**
   * Change an agent's display name without changing its durable identity.
   * The registry key, agent directory, session id, and every mailbox path remain
   * keyed by `id`; only the human-facing name is updated.
   *
   * `fleet.json` is patched in the same operation so god's next prompt receives
   * the new name immediately rather than waiting for the periodic fleet refresh.
   */
  /**
   * Put an agent on hold, or take it off, and tell Michael immediately.
   *
   * `fleet.json` is patched in the same operation for the same reason
   * `renameAgent` does it: god's roster is injected from that file on its next
   * prompt, and waiting up to 8s for the periodic refresh means one more
   * dispatch can still land on someone the human has just claimed.
   */
  setAgentHold(id, hold) {
    const root = this.root();
    if (!root) return { ok: false, error: "hive disabled (no harnessHome)" };
    try {
      const reg = this.registry();
      const agent2 = reg.agents[id];
      if (!agent2) return { ok: false, error: "Agent not found" };
      if (!!agent2.onHold === hold) return { ok: true, onHold: hold };
      agent2.onHold = hold;
      this.writeJson(join2(root, "registry.json"), reg);
      const fleetPath = join2(root, "fleet.json");
      if (existsSync(fleetPath)) {
        try {
          const fleet = this.readJson(fleetPath, {});
          if (Array.isArray(fleet.agents)) {
            const row = fleet.agents.find((candidate) => candidate.id === id);
            if (row) {
              row.onHold = hold;
              this.writeJson(fleetPath, fleet);
            }
          }
        } catch {
        }
      }
      this.appendLog({ kind: "agent-hold", id, onHold: hold });
      return { ok: true, onHold: hold };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  }
  renameAgent(id, name) {
    const root = this.root();
    if (!root) return { ok: false, error: "hive disabled (no harnessHome)" };
    const nextName = name.trim();
    if (!nextName) return { ok: false, error: "Name is required" };
    try {
      const reg = this.registry();
      const agent2 = reg.agents[id];
      if (!agent2) return { ok: false, error: "Agent not found" };
      if (agent2.name === nextName) return { ok: true, name: nextName };
      const previousName = agent2.name;
      agent2.name = nextName;
      this.writeJson(join2(root, "registry.json"), reg);
      const fleetPath = join2(root, "fleet.json");
      if (existsSync(fleetPath)) {
        try {
          const fleet = this.readJson(fleetPath, {});
          if (Array.isArray(fleet.agents)) {
            const row = fleet.agents.find((candidate) => candidate.id === id);
            if (row) {
              row.name = nextName;
              this.writeJson(fleetPath, fleet);
            }
          }
        } catch {
        }
      }
      this.appendLog({ kind: "rename", agentId: id, previousName, name: nextName });
      this.commit(`hive: rename ${id}`);
      return { ok: true, name: nextName };
    } catch {
      return { ok: false, error: "Could not rename agent" };
    }
  }
  /**
   * Persist the agent's Claude Code session_id (Lane A #6.6a). Captured from hook
   * payloads; written only when it actually changes (a new session), so this is a
   * no-op on the vast majority of hook events. The id is the `--resume` key for
   * idempotent resume after a crash/restart AND the accounting/dedup key for cost
   * samples. Best-effort — never throws into a hook handler.
   */
  recordSession(agentId, sessionId) {
    const root = this.root();
    if (!root || !sessionId) return;
    try {
      const reg = this.registry();
      const agent2 = reg.agents[agentId];
      if (!agent2 || agent2.sessionId === sessionId) return;
      agent2.sessionId = sessionId;
      agent2.lastSeen = Date.now();
      this.atomicWriteJson(join2(root, "registry.json"), reg);
      this.appendLog({ kind: "session", agentId, sessionId });
      this.commit(`hive: session ${agentId}`);
    } catch {
    }
  }
  /** The last known session_id for an agent, or undefined. Used to build a
   *  `claude --resume <id>` spawn so a restarted agent resumes its thread. */
  lastSession(agentId) {
    return this.registry().agents[agentId]?.sessionId;
  }
  /** Claude Code settings that route every relevant hook through the shim, plus
   *  (W3) the default MCP bundle merged into this PER-SESSION settings file. cwd
   *  scopes the filesystem/git servers; cfg (the consent map) gates which servers
   *  are written. Claude-only — this is invoked solely on the Claude spawn path. */
  /**
   * Directories a sandboxed agent may write BESIDES its cwd: its own agent
   * folder (hive housekeeping) and the hive root (research deliverables; the
   * board and tasks.json for god; outbox delivery is done by main, not the agent).
   * This is what lets auto mode keep the OS sandbox on — the old full-bypass
   * posture existed only because these paths sit outside the project cwd.
   */
  sandboxWritableDirs(meta, dir, root, extra) {
    const out = [dir, root, ...extra ?? []].filter((d) => typeof d === "string" && d.length > 0);
    return Array.from(new Set(out));
  }
  hookSettings(shim, cwd, cfg, theme, writableDirs = []) {
    const cmd = this.nodeRun(shim);
    const entry = (matcher) => ({
      ...matcher ? { matcher } : {},
      hooks: [{ type: "command", command: cmd }]
    });
    const mcpServers = this.buildDefaultMcpServers(cwd, cfg);
    return {
      // Match the TUI's truecolor palette to the harness terminal theme —
      // PER SESSION, so the user's global Claude theme (their own terminals
      // outside the app) is never touched.
      //
      // 'auto', not the literal light/dark. Pinning the value matched the theme at
      // SPAWN and then ignored every change: Claude Code supports DEC 2031 theme
      // notifications, but a pinned theme has nothing to reconsider, so flipping
      // the app left a running agent painting its message blocks in the old
      // palette (black highlight on a cream terminal). 'auto' is the value that
      // listens. The terminal reports the current theme the moment the CLI enables
      // 2031, so startup still matches without pinning anything.
      ...theme ? { theme: "auto" } : {},
      // W3 — default skills/MCP bundle. Written into the PER-SESSION settings file
      // only (never ~/.claude), so the user's own MCP servers are never clobbered;
      // Claude merges this additively. Omitted entirely when empty so a settings
      // file with no enabled servers is unchanged from before.
      ...Object.keys(mcpServers).length ? { mcpServers } : {},
      // The status line gets the session status JSON after every response —
      // including context_window.{total_input_tokens,context_window_size},
      // the only clean programmatic source for the session's REAL context
      // window. The shim prints a compact in-terminal gauge and forwards the
      // payload to the harness (agent-card context gauge, exact limit).
      statusLine: { type: "command", command: `${cmd} --status`, padding: 0 },
      // Native OS sandbox for Bash subprocesses (macOS Seatbelt / Linux bubblewrap).
      // Auto mode spawns with `--permission-mode bypassPermissions`, which only
      // silences PROMPTS; the sandbox is a separate, opt-in layer that was never
      // switched on. Verified live (claude 2.1.239): with this block, bypass mode
      // still writes cwd and the listed dirs but `touch $HOME/x` fails with
      // "Operation not permitted". Two layers are needed: `sandbox.filesystem`
      // governs Bash children, `permissions.additionalDirectories` governs the
      // Edit/Write tools; with only one the agent deadlocks on its own inbox.
      // failIfUnavailable stays false: a platform without a sandbox (Windows)
      // runs as before rather than refusing to spawn.
      ...writableDirs.length ? {
        sandbox: { enabled: true, filesystem: { allowWrite: writableDirs } },
        permissions: { additionalDirectories: writableDirs }
      } : {},
      hooks: {
        Stop: [entry()],
        SubagentStop: [entry()],
        PreToolUse: [entry("*")],
        PostToolUse: [entry("*")],
        UserPromptSubmit: [entry()],
        Notification: [entry()],
        SessionStart: [entry()],
        // #5C: surface mid-`/compact` so an agent boxing up its context reads as
        // 'compacting' on the floor instead of looking frozen.
        PreCompact: [entry()],
        PostCompact: [entry()]
      }
    };
  }
  /**
   * W3 — build the per-agent `mcpServers` map from the default catalog. Includes a
   * server only when it's enabled (catalog ∩ consent), scopes filesystem/git to the
   * agent cwd (never whole-disk), and namespaces every id `munder-<id>` so a server
   * of the same name in the user's own ~/.claude is never clobbered. A write/secret
   * server is included ONLY on an explicit `enabled:true` consent — never via a
   * default — so a malformed/partial config can't silently arm a keyed server.
   */
  buildDefaultMcpServers(cwd, cfg) {
    const out = {};
    for (const e of MCP_CATALOG) {
      const consented = cfg?.[e.id]?.enabled;
      const enabled = consented ?? e.defaultEnabled;
      if (!enabled) continue;
      if (e.tier !== "safe-readonly" && consented !== true) continue;
      const args2 = e.spec.args.map((a) => a === "<cwd>" ? cwd : a);
      out[`munder-${e.id}`] = {
        command: e.spec.command,
        args: args2,
        ...e.spec.env ? { env: e.spec.env } : {}
      };
    }
    return out;
  }
  /**
   * W3 — refresh an agent's bundled skills from the app-resources `skills/` dir.
   * Mirrors `identity.md`: overwritten every spawn so the shipped safe set tracks
   * the app. Best-effort and fully tolerant — a missing/empty source dir is a no-op
   * (Kevin populates the resource dir in lp-manifest), and any IO error is swallowed
   * so skill provisioning can never block a spawn.
   */
  copyBundledSkills(srcDir, destDir) {
    try {
      if (!existsSync(srcDir)) return;
      const copyTree = (from, to) => {
        const entries = readdirSync(from, { withFileTypes: true });
        if (!entries.length) return;
        mkdirSync(to, { recursive: true });
        for (const ent of entries) {
          const s = join2(from, ent.name);
          const d = join2(to, ent.name);
          if (ent.isDirectory()) copyTree(s, d);
          else if (ent.isFile()) copyFileSync(s, d);
        }
      };
      copyTree(srcDir, destDir);
    } catch (e) {
      console.error("[hive] copyBundledSkills failed:", e);
    }
  }
  /**
   * W1 — start a proxy-bridge sidecar for a hookless proxy-tier agent (qwen).
   * Spawns `<root>/bin/hive-proxy.cjs` under Node, which binds a loopback port and
   * reports it back as a one-line `{"port":N}` on stdout. Resolves the bound port
   * (or 0 on failure, so the caller degrades gracefully without redirecting the
   * CLI). Idempotent: any prior sidecar for the agent is killed first, so a respawn
   * never leaks a listener. Tracked in `proxyChildren` for teardown.
   */
  /** startProxyBridge with a short retry ladder. Every attempt kills the previous
   *  sidecar first (startProxyBridge is idempotent), so a retry never leaks a
   *  listener. Resolves the bound port, or 0 once every attempt has failed. */
  async startProxyBridgeWithRetry(agentId, cfg) {
    for (let attempt = 1; attempt <= PROXY_BIND_ATTEMPTS; attempt++) {
      const port = await this.startProxyBridge(agentId, cfg);
      if (port > 0) return port;
      if (attempt < PROXY_BIND_ATTEMPTS) {
        console.warn(`[hive] proxy bridge for ${agentId} did not bind (attempt ${attempt}/${PROXY_BIND_ATTEMPTS}), retrying`);
        await new Promise((r) => setTimeout(r, PROXY_BIND_BACKOFF_MS[attempt - 1] ?? 1e3));
      }
    }
    return 0;
  }
  startProxyBridge(agentId, cfg) {
    this.stopProxyBridge(agentId);
    const script = this.proxyShimPath();
    if (!script) return Promise.resolve(0);
    return new Promise((resolve2) => {
      let settled = false;
      const settle = (port) => {
        if (!settled) {
          settled = true;
          resolve2(port);
        }
      };
      let child;
      try {
        child = spawn(process.execPath, [script], {
          env: {
            ...process.env,
            // Run the .cjs under Electron's bundled Node, not as a second app window.
            ELECTRON_RUN_AS_NODE: "1",
            HIVE_SOCK: cfg.sock,
            AGENT_ID: agentId,
            UPSTREAM_BASE_URL: cfg.upstream,
            HIVE_PROXY_SESSION: cfg.sessionId,
            HIVE_PROXY_API: cfg.api
          },
          // Read the port line from stdout; never inherit stdio (the sidecar must
          // never write into the agent's terminal or leak request bodies to a log).
          stdio: ["ignore", "pipe", "ignore"]
        });
      } catch (e) {
        console.error(`[hive] startProxyBridge spawn failed for ${agentId}:`, e);
        return settle(0);
      }
      this.proxyChildren.set(agentId, child);
      let buf = "";
      child.stdout?.setEncoding("utf8");
      child.stdout?.on("data", (d) => {
        if (settled) return;
        buf += d;
        const nl = buf.indexOf("\n");
        if (nl === -1) return;
        try {
          const msg = JSON.parse(buf.slice(0, nl));
          if (typeof msg.port === "number" && msg.port > 0) settle(msg.port);
          else settle(0);
        } catch {
          settle(0);
        }
      });
      child.on("error", () => settle(0));
      child.on("exit", () => {
        if (this.proxyChildren.get(agentId) === child) this.proxyChildren.delete(agentId);
        settle(0);
      });
      setTimeout(() => settle(0), 4e3).unref?.();
    });
  }
  /** Kill the proxy sidecar for an agent, if any. Idempotent; never throws. */
  stopProxyBridge(agentId) {
    const child = this.proxyChildren.get(agentId);
    if (!child) return;
    this.proxyChildren.delete(agentId);
    try {
      child.kill();
    } catch {
    }
  }
  /** Kill every live proxy sidecar (app quit). Best-effort. */
  stopAllProxyBridges() {
    for (const id of [...this.proxyChildren.keys()]) this.stopProxyBridge(id);
  }
  /**
   * Drain an agent's inbox for the Stop hook. Returns whether to block-to-continue
   * and the message text to feed back. Uses the per-agent cursor so a message is
   * surfaced exactly once (no infinite loop).
   */
  drainForStop(agentId) {
    const dir = this.agentDir(agentId);
    if (!existsSync(dir)) return { block: false };
    const cursorPath = join2(dir, "cursor.json");
    const cursor = this.readJson(cursorPath, { lastProcessed: null });
    const fresh = this.inbox(agentId).filter((m) => !cursor.lastProcessed || m.id > cursor.lastProcessed).sort((a, b) => a.id < b.id ? -1 : 1);
    if (fresh.length === 0) return { block: false };
    cursor.lastProcessed = fresh[fresh.length - 1].id;
    this.atomicWriteJson(cursorPath, cursor);
    this.appendLog({ kind: "drain", agentId, count: fresh.length });
    const lines = fresh.map((m) => `- [from ${m.from}, ${m.act}] ${m.subject}: ${m.body}`).join("\n");
    const reason = [
      `You have ${fresh.length} new hive message(s) in your inbox. Address them before finishing:`,
      lines,
      // Native separators (join, not string-concatenated `/`) so a Windows agent is
      // handed a path its own shell/tools accept, not `C:\…\agents\god/inbox/`.
      `Open the files in ${join2(dir, "inbox")} for full detail, act on each, then move handled ones to ${join2(dir, "inbox", ".done")}. Reply via your outbox if a message requires it.`
    ].join("\n");
    return { block: true, reason };
  }
  // — agent-facing text —
  identityText(meta) {
    const caps = (meta.capabilities ?? []).join(", ") || "\u2014";
    return [
      `# ${meta.name} (${meta.id})`,
      "",
      `- Role: ${meta.role ?? (meta.isGod ? "orchestrator (god)" : "agent")}`,
      `- Capabilities: ${caps}`,
      `- Working directory: ${meta.cwd}`,
      meta.isGod ? "- You are the **god / orchestrator**. You run the floor \u2014 keep awareness of the whole team, delegate execution, and personally own only the important calls (decomposition, sign-offs, conflicts, integration), not the grunt work." : "",
      meta.isGod ? "- Monitor the team with `fleet.json` (live per-agent status/tokens/cost/breaker) and `registry.json`; full command reference in `COMMANDS.md`. `claude agents` does NOT list your hive siblings." : "",
      ""
    ].filter(Boolean).join("\n");
  }
  /**
   * The system-prompt prefix injected into every spawn via --append-system-prompt.
   *
   * 🔒 PROMPT-CACHE INVARIANT — keep this prefix VOLATILE-FREE. It interpolates
   * only values stable for an agent's whole lifetime (name, id, dir, root,
   * semanticMemory). Do NOT add dates, UUIDs, counters, board/registry state, or
   * any `Date.now()`-derived text here: a prefix that changes per spawn defeats
   * Anthropic's prompt cache (re-priming the whole system prompt every turn).
   * Volatile context belongs on the live channels — the inbox (hive messages) and
   * the PTY — never baked into this prefix. (Lane A #6.1.)
   *
   * 🪟 NO SHELL SYNTAX. Every path and command here is written the way the AGENT
   * will actually type it, on the platform it is running on. That rules out two
   * habits that were silently Windows-only breakage:
   *  - `$VAR` — POSIX-only. Under cmd.exe `$HIVE_NODE`/`$KG_CLI` expand to nothing
   *    and under PowerShell to an undefined variable, so those instructions were
   *    dead on every Windows floor. Bake the ABSOLUTE resolved path instead: it is
   *    platform-independent, needs no expansion, and stays prompt-cache-stable.
   *  - `'…' + '/inbox/'` — string-concatenating separators told a Windows agent to
   *    read `C:\Users\x\hive\agents\god/inbox/`. Use join() so the agent's own
   *    tooling gets a path it can pass straight to its shell.
   */
  injectedPrompt(meta, dir, root, semanticMemory, knowledgeGraph, kgCliPath) {
    const inDir = (...parts) => join2(dir, ...parts);
    const inRoot = (...parts) => join2(root, ...parts);
    const godRegistry = meta.isAssistant ? this.registry() : null;
    const godNameForPrompt = godRegistry ? resolveGodName(godRegistry.agents[godRegistry.godId ?? "god"]?.name) : "";
    const ctxLine = "LIVE CONTEXT: each agent row in the LIVE ROSTER carries a `ctx NN%` tag \u2014 its live context-window occupancy. Treat it as the real headroom signal when routing: prefer an agent with a LOW `ctx` for a big task; treat a HIGH `ctx` (near 100%) as busy rather than idle, even if the cumulative token count looks modest.";
    const memoryLine = semanticMemory ? 'Semantic memory: the whole hive shares a searchable MemPalace at the path in your MEMPALACE_PALACE_PATH environment variable. To recall relevant past knowledge across the team, run `mempalace search "<query>"`; run `mempalace wake-up` at the start of a task for a memory digest. Your notes in memory.md are mined into the palace automatically \u2014 write durable facts there.' : "";
    const hiveNode = this.nodeCommand();
    const kgCli = kgCliPath || (process.platform === "win32" ? "%KG_CLI%" : "$KG_CLI");
    const knowledgeLine = knowledgeGraph ? `Enterprise knowledge: this organisation has a private Knowledge Graph of its own documents, policies, and business context. When a task needs that context \u2014 company-specific facts, house style, internal processes \u2014 query it instead of guessing: run \`"${hiveNode}" "${kgCli}" search "<query>"\` for ranked passages, \`"${hiveNode}" "${kgCli}" list\` to see what is available, and \`"${hiveNode}" "${kgCli}" get <id>\` for a full document. (That first path is the harness's bundled Node \u2014 use it instead of bare \`node\`, which may not be on your PATH.)` : "";
    const rt = this.runtimeInfo();
    const runtimeLine = rt ? `RUNNING BUILD: Munder Difflin v${rt.version}, ${rt.packaged ? "packaged app" : "local dev build"}${rt.appPath ? `, from ${rt.appPath}` : ""}. Say this version if asked which one is running, and do not assume behaviour from an older one. A local dev build inherits the launching shell's environment (umask included) where a packaged app does not, so file modes and inherited env can legitimately differ between the two. \`log.jsonl\` records an \`app-start\` event on every launch, which is how you spot a restart or a build switch.` : "";
    const spawnQueueLine = meta.isGod && this.orchestratorMaySpawn() ? `SPAWNING A WORKER: you can start an ephemeral worker yourself by writing ONE JSON file into ${inRoot("spawn-requests")}/<id>.json. Required: \`objective\` (what the worker must do) and \`cwd\` (the repo it runs in). Optional: \`name\`, \`command\`, \`provider\`, \`model\`, \`isolate\` (default true = its own git worktree), \`tokenCap\`, and \`slack\` ({channel, thread_ts}) to route its failures back to a thread. The harness polls that directory, spawns \`worker-<id>\`, and moves the request to \`spawn-requests/.done/\` on success or \`.failed/\` with a reason. This is the ONLY way you can spawn; a hire manifest under research/hires/ needs the human to confirm it in the UI, so it is not a route you can complete on your own. Reuse an existing agent first, as above \u2014 a worker is a fresh spend every time.` : "";
    const godLine = meta.isGod ? `You are the GOD / ORCHESTRATOR of this hive \u2014 your job is to ORCHESTRATE, not to implement: maintain live situational awareness and delegate the work. (1) AWARENESS \u2014 always know what is going on: keep an accurate picture of every agent (active vs archived/idle), the task board, and all in-flight work; drain your inbox continually and triage every other agent's requests, answering clarifications so the team runs autonomously. (2) DELEGATE \u2014 decompose work and fan it out to the hive agents via their inboxes (route messages and assign owners; do not do their jobs); do NOT take on grunt implementation yourself. Stay aware of who is already on the floor and delegate OPPORTUNISTICALLY: BEFORE you spawn anything, CHECK THE LIVE ROSTER (active agents in registry.json + their state in fleet.json) and prefer routing to an EXISTING agent that fits \u2014 above all when the request names one ("ask Pam to\u2026", "have Jim\u2026"), route to that agent instead of reflexively creating a new one. Reuse an idle or already-running agent whose role matches; only spawn a fresh agent when no existing one is a sensible fit, and say that you checked. One capable owner beats a duplicate. (3) OWN ONLY THE IMPORTANT, high-leverage things \u2014 task decomposition, dispatch decisions, sign-offs, conflict resolution, branch integration, and final QA \u2014 and remain the sole scribe of board.md. You are otherwise fully autonomous \u2014 there is NO separate approval queue. For the genuinely critical (destructive actions, spending real money, scope changes, unresolvable conflicts), ask the human directly in your own session and let the tool-permission prompt gate the action; the human approves natively, including remotely from their phone via /remote-control. Keep the team unblocked. When you DISPATCH a task, write it as a 4-part contract so the agent can run autonomously: (1) OBJECTIVE \u2014 the concrete goal; (2) OUTPUT \u2014 the expected deliverable/format; (3) TOOLS \u2014 what to use or avoid, and any references to read instead of re-deriving; (4) BOUNDARIES \u2014 scope limits + the definition of done. Pass references (file paths, message ids, board sections), not pasted content \u2014 keep dispatches short. MONITOR the floor by reading ${inRoot("fleet.json")} (live per-agent tokens, cost, status, last tool, breaker level, inbox backlog) and ${inRoot("registry.json")} \u2014 note that running 'claude agents' will NOT list your hive's sibling agents. A full Claude Code command reference is at ${inRoot("COMMANDS.md")} (slash commands act ONLY on your own session; CLI commands run in your shell and can target the fleet). You periodically receive scheduler / "Heartbeat" standup requests \u2014 on each, review every agent via fleet.json, re-engage anyone stalled, over-budget, or breaker-armed, and keep board.md and tasks.json accurate. In tasks.json, ALWAYS set each task's "assignee" to the worker's agent id the moment you dispatch it, and NEVER clear it on status changes \u2014 a done card must still say who did the work (the human reads the board by who-did-what). HUMAN FEEDBACK is first-class in the ledger: when a task can only proceed with the human's input \u2014 a QUESTION to answer OR an ACTION only the human can perform (create an account, approve a purchase, provide credentials/screenshots, test on their device) \u2014 set its status to "blocked" and append the concrete ask to the card's "humanQA" array (push {"q":"...","askedAt":"<iso>"}; phrase actions as clear to-dos; keep every past entry \u2014 the history documents the card's decisions). WRITE THE ASK SHORT AND IN MARKDOWN. The human reads it on a CARD, not in a terminal, so an ask longer than a short paragraph plus its options (roughly 700 characters) is a report, not a question \u2014 cut the narrative, keep the decision. Open with ONE **bold** sentence saying exactly what you need from them; put paths, commands, values and identifiers in \`backticks\`; give each option or step its own "-" bullet or "1." number; leave a blank line between paragraphs (a single newline is a line break, so each option stays on its own line). When the ask originates in another agent's report, REWRITE it into that shape \u2014 never paste the report body in as the question, and never make the human read the investigation to find the decision. The harness surfaces open questions on the office floor's ASK ME board; the human's answer lands in the same entry ("a") AND arrives as an inbox message to you \u2014 read it, act on it, and unblock the card so work continues. Do NOT park human questions in separate files (no HumanQuestion.md) and never sit waiting on the human in your own session. Steward the token budget.` : meta.isAssistant ? `You are ${godNameForPrompt}'s PREP ASSISTANT. You will be handed short, possibly vague instructions (each begins with "ENRICH TASK:"). For each one: (1) figure out which project it concerns and cd into the most relevant repo \u2014 you start in ${godNameForPrompt}'s home directory; (2) gather concrete context READ-ONLY (exact file paths, current state, relevant code, conventions, active branch, gotchas) \u2014 NEVER modify, create, or delete files; (3) rewrite the instruction into ONE clear, self-contained prompt that ${godNameForPrompt} can execute autonomously, preserving the user's original intent without inventing scope. Then deliver it: write ONE message JSON into your outbox with "to":"god", "act":"request", a short subject, and the finished prompt as the body. Do NOT perform the task yourself \u2014 your only output is the improved prompt sent to ${godNameForPrompt}.` : 'For anything ambiguous, cross-cutting, or needing sign-off, address a message to "god".';
    const guardrailsLine = 'Guardrails: a circuit breaker watches the floor \u2014 a "Circuit breaker: steer/constrain" message means you are looping or overspending, so STOP repeating, summarize what you tried, and follow it. Be token-frugal (a floor-wide or per-agent token budget can pause you). The shared plan has two parts: board.md (freeform; god is the sole scribe) and tasks.json (structured kanban \u2014 todo/doing/blocked/done).';
    const slackLine = meta.isGod ? 'SLACK REPLIES: When composing a Slack reply (or writing the `result` field of a Slack-origin kanban card), you MUST: (1) directly address what the user asked \u2014 never a bare "done"; (2) include the relevant specifics, outcome, and details; (3) format for Slack mrkdwn \u2014 open with a short *bold* headline, use bullet points for multiple items, wrap code/paths in `backtick` blocks, keep it concise (no walls of text). When finishing a Slack-origin task, always write a complete, user-facing, well-formatted `result` on the kanban card \u2014 the system posts it verbatim to Slack as the done reply.' : `SLACK REPLIES: If god dispatches you a task that came from Slack, it will include an exact \`"${hiveNode}" "<helper>" --channel \u2026 --thread \u2026 --text "\u2026"\` reply command \u2014 when you finish, run it VERBATIM to post your result back to that thread yourself. The reply must be SUBSTANTIVE Slack mrkdwn (a short *bold* headline + the actual outcome/specifics/links), NEVER a bare "done".`;
    return [
      `You are "${meta.name}" (${meta.id}), an autonomous agent in a collaborating hive of Claude agents.`,
      `Your private workspace is ${dir}. The shared hive is ${root}. Full protocol: ${inRoot("PROTOCOL.md")}.`,
      "",
      "HIVE PROTOCOL \u2014 follow it every task:",
      `1. At the START of a task, read ${inDir("memory.md")} and EVERY file in ${inDir("inbox")} (messages other agents sent you). After handling an inbox message, move its file into ${inDir("inbox", ".done")}.`,
      `2. Record durable facts, decisions, and context by appending to ${inDir("memory.md")}.`,
      `3. To ask another agent for something or share information, write ONE message JSON into ${inDir("outbox")} (schema in PROTOCOL.md). NEVER write into another agent's folder \u2014 the orchestrator delivers your outbox.`,
      "4. At the END of a task, append what you learned to memory.md so future-you remembers.",
      guardrailsLine,
      memoryLine,
      knowledgeLine,
      godLine,
      spawnQueueLine,
      runtimeLine,
      slackLine,
      ctxLine,
      `Env vars available to you: AGENT_ID, AGENT_NAME, HIVE_ROOT, AGENT_DIR.`
    ].filter(Boolean).join("\n");
  }
  // — messaging —
  /** Normalize a partial message into a full HiveMessage. */
  normalize(partial, from) {
    const act = partial.act ?? "inform";
    return {
      id: partial.id ?? `${stamp()}-${shortRand()}`,
      conversation: partial.conversation ?? `conv-${shortRand()}`,
      in_reply_to: partial.in_reply_to ?? null,
      from: partial.from ?? from,
      to: partial.to ?? "god",
      act,
      subject: partial.subject ?? "",
      body: partial.body ?? "",
      hops: typeof partial.hops === "number" ? partial.hops : 0,
      requires_reply: partial.requires_reply ?? ["request", "query", "propose"].includes(act),
      needs_human: partial.needs_human ?? false,
      created_at: partial.created_at ?? (/* @__PURE__ */ new Date()).toISOString()
    };
  }
  /** Atomically deliver a message into a recipient agent's inbox.
   *  Returns false when the recipient has no inbox, so the caller can bounce and
   *  log the drop rather than let the message vanish. */
  deliver(msg, toId) {
    const inbox = join2(this.agentDir(toId), "inbox");
    if (!existsSync(inbox)) return false;
    this.atomicWriteJson(join2(inbox, `${msg.id}.json`), msg);
    return true;
  }
  /** Inject a message directly (used by the orchestrator / UI / tests). */
  send(partial, from = "system") {
    const msg = this.normalize(partial, from);
    this.routeMessage(msg);
    this.commit(`hive: msg ${msg.from}\u2192${msg.to} (${msg.act})`);
    return msg;
  }
  routeMessage(msg) {
    if (msg.hops > HOP_CAP) {
      this.appendLog({ kind: "drop", reason: "hop-cap", from: msg.from, to: msg.to, id: msg.id });
      return;
    }
    const reg = this.registry();
    const godId = reg.godId ?? "god";
    const resolveTo = (to) => to === "human" || to === "god" ? godId : to;
    const targets = msg.to === "broadcast" ? selectBroadcastTargets(reg.agents, msg.from) : [resolveTo(msg.to)].filter((t) => t !== msg.from);
    const delivered = [];
    for (const t of targets) {
      if (reg.agents[t]?.isAssistant) {
        this.deliver({
          ...msg,
          to: godId,
          subject: `[bounced \u2014 "${t}" is the send-only prep assistant; route work to a real agent] ${msg.subject}`
        }, godId);
        continue;
      }
      if (t !== godId && !canReceiveInbox(reg.agents[t]?.provider)) {
        if (!this.emitTerminalHandoff(msg, t)) {
          this.deliver({
            ...msg,
            to: godId,
            subject: `[undeliverable \u2014 "${t}" runs ${reg.agents[t]?.provider ?? "a hookless CLI"} and the terminal handoff failed (renderer unavailable); relay this to it] ${msg.subject}`
          }, godId);
        } else delivered.push(t);
        continue;
      }
      const proxyDesc = bridgeOf(reg.agents[t]?.provider);
      if (t !== godId && proxyDesc?.kind === "proxy" && proxyDesc.inboxDelivery === "terminal") {
        if (!this.emitTerminalHandoff(msg, t)) {
          this.deliver({
            ...msg,
            to: godId,
            subject: `[undeliverable \u2014 "${t}" runs ${reg.agents[t]?.provider ?? "a proxy-tier CLI"} and the terminal handoff failed (renderer unavailable); relay this to it] ${msg.subject}`
          }, godId);
        } else delivered.push(t);
        continue;
      }
      if (this.deliver(msg, t)) {
        delivered.push(t);
        continue;
      }
      this.appendLog({ kind: "drop", reason: "no-inbox", from: msg.from, to: t, id: msg.id });
      if (t !== godId) {
        this.deliver({
          ...msg,
          to: godId,
          subject: `[undeliverable \u2014 no agent "${t}" on this floor; check the id against the roster] ${msg.subject}`
        }, godId);
      }
    }
    this.appendLog({ kind: "message", from: msg.from, to: msg.to, act: msg.act, subject: msg.subject, id: msg.id, delivered });
    this.emitMessage(msg, targets);
    try {
      this.routedObserver?.(msg, targets);
    } catch {
    }
  }
  /** Observer invoked for EVERY routed message with its resolved targets.
   *  Used by main-process features that react to hive traffic (closing time). */
  routedObserver = null;
  setRoutedObserver(cb) {
    this.routedObserver = cb;
  }
  /** Tell the renderer a message was routed, with its resolved recipients, so
   *  the floor can fly an envelope from the sender to each one. Best-effort. */
  emitMessage(msg, targets) {
    this.emit?.("hive:message", {
      id: msg.id,
      from: msg.from,
      to: msg.to,
      act: msg.act,
      subject: msg.subject,
      targets,
      // Coral-tints the floor envelope for a message the agent flagged for the
      // human (now routed to the god proxy). Cosmetic only — no queue behind it.
      needsHuman: msg.to === "human"
    });
  }
  /** Non-Claude providers cannot drain hive inbox; hand direct mail to the
   *  renderer so it can queue a terminal work order for the target PTY. */
  emitTerminalHandoff(msg, targetId) {
    const delivered = this.emit?.("hive:terminalHandoff", {
      id: msg.id,
      from: msg.from,
      to: targetId,
      act: msg.act,
      subject: msg.subject,
      body: msg.body,
      requiresReply: msg.requires_reply,
      createdAt: msg.created_at
    }) === true;
    this.appendLog({
      kind: "terminal-handoff",
      from: msg.from,
      to: targetId,
      act: msg.act,
      subject: msg.subject,
      id: msg.id,
      delivered
    });
    return delivered;
  }
  // — router: drain outboxes → inboxes —
  /** Poll-based router. Cheap and robust vs fs.watch quirks on macOS. */
  startRouter(intervalMs = 1500) {
    if (this.routerTimer || !this.enabled()) return;
    this.routerTimer = setInterval(() => {
      try {
        this.routeOnce();
      } catch {
      }
    }, intervalMs);
  }
  stopRouter() {
    if (this.routerTimer) {
      clearInterval(this.routerTimer);
      this.routerTimer = null;
    }
  }
  routeOnce() {
    const root = this.root();
    if (!root) return 0;
    const agentsDir = join2(root, "agents");
    if (!existsSync(agentsDir)) return 0;
    let routed = 0;
    for (const id of readdirSync(agentsDir)) {
      const outbox = join2(agentsDir, id, "outbox");
      if (!existsSync(outbox)) continue;
      for (const f of readdirSync(outbox)) {
        if (!f.endsWith(".json")) continue;
        const full = join2(outbox, f);
        try {
          const raw = readFileSync(full, "utf8");
          let partial;
          try {
            partial = JSON.parse(raw);
          } catch {
            const repaired = repairLiteralLineBreaksInJsonStrings(raw);
            if (!repaired.changed) {
              this.appendLog({ kind: "drop", reason: "malformed-json", from: id, file: f });
              try {
                renameSync(full, join2(outbox, ".sent", `bad-${f}`));
              } catch {
              }
              continue;
            }
            try {
              partial = JSON.parse(repaired.text);
            } catch {
              this.appendLog({ kind: "drop", reason: "malformed-json", from: id, file: f });
              try {
                renameSync(full, join2(outbox, ".sent", `bad-${f}`));
              } catch {
              }
              continue;
            }
            this.appendLog({
              kind: "outbox-repair",
              from: id,
              file: f,
              repair: "literal-line-break"
            });
          }
          const msg = this.normalize(partial, id);
          msg.from = id;
          this.routeMessage(msg);
          renameSync(full, join2(outbox, ".sent", f));
          routed++;
        } catch {
          try {
            renameSync(full, join2(outbox, ".sent", `bad-${f}`));
          } catch {
          }
        }
      }
    }
    if (routed > 0) this.commit(`hive: routed ${routed} message(s)`);
    return routed;
  }
  // — read helpers (for IPC / UI) —
  registry() {
    const root = this.root();
    if (!root) return { godId: null, agents: {} };
    return this.readJson(join2(root, "registry.json"), { godId: null, agents: {} });
  }
  board() {
    const root = this.root();
    return root && existsSync(join2(root, "board.md")) ? readFileSync(join2(root, "board.md"), "utf8") : "";
  }
  tasks() {
    const root = this.root();
    return root ? this.readJson(join2(root, "tasks.json"), { tasks: [] }) : { tasks: [] };
  }
  /** Persist the task ledger to hive/tasks.json and commit it. Mirrors the
   *  board/message persist pattern: write JSON, log the change, single-commit.
   *
   *  MERGES by card id instead of clobbering. Callers hold PARTIAL models of a
   *  card — the renderer's kanban parser knows nine fields, the god writes as
   *  many as the work needs (`result`, the verbatim Slack reply posted back to
   *  the user; `repo`; `scope`; `origin`; `commit`; …). A wholesale write meant
   *  one small edit through the UI deleted every unmodelled field on EVERY card
   *  on the board. Now an unmentioned field keeps its on-disk value.
   *
   *  Deleting a card still works: the incoming list IS the membership, so a card
   *  dropped from it (TasksKanban dismiss, the voice delete_task action) is
   *  gone. Merging protects fields, never card membership. */
  writeTasks(tasks) {
    const root = this.root();
    if (!root) return;
    this.ensureHive();
    const path = join2(root, "tasks.json");
    const current = this.readJson(path, { tasks: [] });
    const merged = mergeTaskLedger(current?.tasks, tasks);
    this.writeJson(path, { tasks: merged });
    this.appendLog({ kind: "tasks", count: merged.length });
    this.commit(`hive: tasks (${merged.length})`);
  }
  /** Append one card against the latest on-disk ledger. Renderer callers must
   *  use this instead of re-writing a collection they read before another
   *  source (webhook, Slack, god, voice) added work. Idempotent by task id. */
  addTask(task) {
    const ledger = this.tasks();
    const tasks = Array.isArray(ledger?.tasks) ? ledger.tasks : [];
    if (tasks.some((current) => current?.id === task.id)) return false;
    this.writeTasks([...tasks, task]);
    return true;
  }
  /** Patch one card against the latest on-disk ledger, preserving unrelated
   *  cards and fields (notably webhook.tokenHash and Slack thread metadata). */
  patchTask(id, patch) {
    const ledger = this.tasks();
    const tasks = Array.isArray(ledger?.tasks) ? ledger.tasks : [];
    const index = tasks.findIndex((task) => task?.id === id);
    if (index < 0) return false;
    const next = tasks.slice();
    next[index] = { ...tasks[index], ...patch, id };
    this.writeTasks(next);
    return true;
  }
  /** Delete only the named card from the latest on-disk ledger. */
  deleteTask(id) {
    const ledger = this.tasks();
    const tasks = Array.isArray(ledger?.tasks) ? ledger.tasks : [];
    const next = tasks.filter((task) => task?.id !== id);
    if (next.length === tasks.length) return false;
    this.writeTasks(next);
    return true;
  }
  memory(id) {
    const p = join2(this.agentDir(id), "memory.md");
    return existsSync(p) ? readFileSync(p, "utf8") : "";
  }
  /** Whether an agent has recorded NON-TRIVIAL memory — i.e. has appended real
   *  notes beyond the boilerplate header ensureAgent seeds. Lets the voice
   *  read-layer answer "what has the team remembered" and enumerate who has
   *  anything worth reading (every registered agent technically has a memory.md,
   *  but most of the floor's history lives in a handful of them). Cheap: reads a
   *  small markdown file; never throws. Works for ANY id, active OR archived. */
  hasMemory(id) {
    const p = join2(this.agentDir(id), "memory.md");
    if (!existsSync(p)) return false;
    try {
      return readFileSync(p, "utf8").trim().length > 200;
    } catch {
      return false;
    }
  }
  inbox(id) {
    return this.listMessages(join2(this.agentDir(id), "inbox"));
  }
  /** Read an agent's OUTBOX (messages it has authored/sent). Symmetric with
   *  inbox(); the router drains live outbox files into recipients' inboxes and
   *  archives the original under outbox/.sent, so a sent message survives there. */
  outbox(id) {
    return this.listMessages(join2(this.agentDir(id), "outbox"));
  }
  /**
   * Voice read-layer: recent message CONTENT (inbox + outbox bodies) for the
   * operator briefing, REDACTED main-side. This is the message-content half of
   * the voice query surface (the activity half is logTail()).
   *
   * Modes:
   *   - { id }                → the single message with that id, wherever it lives.
   *   - { agentId }           → recent messages in that agent's mailbox only.
   *   - {}                    → recent messages across the whole floor, newest first.
   * `limit` caps the list (default 12, max 40); `includeArchived` (default true)
   * also reads the handled subfolders (inbox/.done, outbox/.sent).
   *
   * SECURITY: every subject + body is passed through redactSecrets() here, in
   * main, so no secret and no raw body ever crosses IPC. Delivered messages exist
   * in both the sender's outbox/.sent and the recipient's inbox/.done; we dedup
   * by message id so each appears once.
   */
  voiceMessages(opts = {}) {
    const root = this.root();
    if (!root) return [];
    const agentsDir = join2(root, "agents");
    if (!existsSync(agentsDir)) return [];
    const wantId = typeof opts.id === "string" ? opts.id.trim() : "";
    const onlyAgent = typeof opts.agentId === "string" ? opts.agentId.trim() : "";
    const includeArchived = opts.includeArchived !== false;
    let owners;
    try {
      owners = onlyAgent ? [onlyAgent] : readdirSync(agentsDir).filter((id) => !id.startsWith(".") && existsSync(this.agentDir(id)));
    } catch {
      return [];
    }
    const seen = /* @__PURE__ */ new Set();
    const out = [];
    for (const owner of owners) {
      const base = this.agentDir(owner);
      const folders = [
        { dir: join2(base, "inbox"), direction: "inbox", archived: false },
        { dir: join2(base, "outbox"), direction: "outbox", archived: false }
      ];
      if (includeArchived) {
        folders.push({ dir: join2(base, "inbox", ".done"), direction: "inbox", archived: true });
        folders.push({ dir: join2(base, "outbox", ".sent"), direction: "outbox", archived: true });
      }
      for (const f of folders) {
        for (const m of this.listMessages(f.dir)) {
          if (!m || typeof m.id !== "string" || seen.has(m.id)) continue;
          seen.add(m.id);
          if (wantId && m.id !== wantId) continue;
          out.push({
            id: m.id,
            conversation: m.conversation,
            from: m.from,
            to: m.to,
            act: m.act,
            subject: redactSecrets(m.subject),
            body: redactSecrets(m.body),
            requires_reply: !!m.requires_reply,
            direction: f.direction,
            owner,
            archived: f.archived,
            created_at: m.created_at
          });
        }
      }
    }
    out.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    if (wantId) return out.slice(0, 1);
    const lim = typeof opts.limit === "number" && isFinite(opts.limit) ? Math.max(1, Math.min(40, Math.round(opts.limit))) : 12;
    return out.slice(0, lim);
  }
  /** Count undrained inbox messages for an agent (cheap — for the fleet snapshot). */
  inboxBacklog(id) {
    const dir = join2(this.agentDir(id), "inbox");
    if (!existsSync(dir)) return 0;
    try {
      return readdirSync(dir).filter((f) => f.endsWith(".json")).length;
    } catch {
      return 0;
    }
  }
  /** Install the Antigravity (`agy`) lifecycle-hook bridge: write the normalizer
   *  shim and merge a `munder-hive` hook group into agy's global hooks.json so a
   *  Gemini worker reports PreToolUse/PostToolUse/Stop/PreInvocation/PostInvocation
   *  to this HookServer (live status + guarded idle delivery), reusing the Claude pipeline.
   *
   *  Two agy-isms handled: (1) antigravity-cli#49 — agy LOADS hooks from
   *  `~/.gemini/antigravity-cli/hooks.json` but TRIGGERS from `~/.gemini/config/
   *  hooks.json`, so we write BOTH; (2) on Windows commands go to cmd.exe and
   *  agy mangles embedded quotes, so that platform retains the legacy form.
   *  Runtime-scoped by AGENT_ID (the shim no-ops for non-hive agy sessions), so
   *  this global config never disturbs the user's own `agy` usage. Best-effort,
   *  idempotent (only our own group is overwritten). */
  installAgyHooks() {
    const root = this.root();
    if (!root) return;
    const shim = join2(root, "bin", "agy-hook.cjs");
    mkdirSync(join2(root, "bin"), { recursive: true });
    writeFileSync(shim, AGY_HOOK_SHIM, "utf8");
    const command = (event) => process.platform === "win32" ? this.nodeRunUnquoted(shim, event) : this.nodeRun(shim, event);
    const tool = (event) => ({
      matcher: "*",
      hooks: [{ type: "command", command: command(event), timeout: 0 }]
    });
    const plain = (event) => ({
      hooks: [{ type: "command", command: command(event), timeout: 0 }]
    });
    const group = {
      PreToolUse: [tool("PreToolUse")],
      PostToolUse: [tool("PostToolUse")],
      PreInvocation: [plain("PreInvocation")],
      PostInvocation: [plain("PostInvocation")],
      Stop: [plain("Stop")]
    };
    const gem = join2(homedir2(), ".gemini");
    for (const p of [join2(gem, "config", "hooks.json"), join2(gem, "antigravity-cli", "hooks.json")]) {
      try {
        mkdirSync(dirname2(p), { recursive: true });
        let existing = {};
        if (existsSync(p)) {
          try {
            existing = JSON.parse(readFileSync(p, "utf8"));
          } catch {
            existing = {};
          }
        }
        existing["munder-hive"] = group;
        writeFileSync(p, JSON.stringify(existing, null, 2), "utf8");
      } catch {
      }
    }
  }
  /** Official Google Gemini CLI lifecycle bridge. Gemini's hook payload is
   *  already snake_case; the shim maps event names into HookServer's common
   *  vocabulary and translates deny/steering replies back to Gemini.
   *
   *  The system settings path is per agent. Gemini merges object and array
   *  settings across layers, so auth and user settings remain in their normal
   *  GEMINI_CLI_HOME while this trusted bridge stays isolated. */
  installGeminiHooks(dir) {
    const home2 = join2(dir, ".gemini-hive");
    const settingsPath2 = join2(home2, "system-settings.json");
    try {
      mkdirSync(home2, { recursive: true });
      const shim = join2(home2, "gemini-hook.cjs");
      writeFileSync(shim, GEMINI_HOOK_SHIM, "utf8");
      const hook = (name, matcher) => ({
        ...matcher ? { matcher } : {},
        sequential: true,
        hooks: [{
          name: `munder-hive-${name}`,
          type: "command",
          command: process.platform === "win32" ? this.nodeRunUnquoted(shim) : this.nodeRun(shim),
          timeout: 3e4
        }]
      });
      const settings2 = {
        hooksConfig: { enabled: true, notifications: false },
        hooks: {
          SessionStart: [hook("session-start")],
          BeforeAgent: [hook("before-agent")],
          BeforeTool: [hook("before-tool", ".*")],
          AfterTool: [hook("after-tool", ".*")],
          AfterAgent: [hook("after-agent")]
        }
      };
      writeFileSync(settingsPath2, JSON.stringify(settings2, null, 2), "utf8");
    } catch (e) {
      console.error("[hive] installGeminiHooks failed:", e);
    }
    return settingsPath2;
  }
  /** Codex lifecycle-hook bridge → full hive parity for a `codex` worker (live
   *  status + Stop→inbox-drain), the codex counterpart of installAgyHooks().
   *
   *  Codex's hook contract is already Claude-shaped: snake_case stdin
   *  (hook_event_name/tool_name/tool_input/session_id/cwd) and a matching response
   *  contract, where `Stop` honoring {decision:'block',reason} means "continue,
   *  using reason as the next prompt" — exactly what drainForStop() returns. So we
   *  reuse the Claude `cth-hook` shim VERBATIM (no translator, unlike agy) and let
   *  HookServer handle everything unchanged.
   *
   *  ISOLATION: rather than mutate the user's global Codex configuration (which
   *  also holds their login), we point this worker at a PER-AGENT CODEX_HOME
   *  (`<dir>/.codex`, alongside Claude's settings.json) holding our own config.toml
   *  with `[hooks]` tables — so the hooks fire ONLY for hive workers and a personal
   *  `codex` run is untouched. Rollout directories are linked into that isolated
   *  home from namespaced paths under the standard global scan roots. The user's
   *  ~/.codex/auth.json is linked in and their config.toml is copied + extended
   *  (login + model/provider/trust settings still apply).
   *  Returns the CODEX_HOME path for the caller to put in the worker's env. */
  installCodexHooks(dir, agentId) {
    const home2 = join2(dir, ".codex");
    try {
      mkdirSync(home2, { recursive: true });
      const userHome = join2(homedir2(), ".codex");
      const authSrc = join2(userHome, "auth.json");
      const authDest = join2(home2, "auth.json");
      if (existsSync(authSrc) && !existsSync(authDest)) {
        try {
          symlinkSync(authSrc, authDest);
        } catch {
          try {
            copyFileSync(authSrc, authDest);
          } catch {
          }
        }
      }
      const packagesSrc = join2(userHome, "packages");
      const packagesDest = join2(home2, "packages");
      if (existsSync(packagesSrc) && !existsSync(packagesDest)) {
        try {
          symlinkSync(packagesSrc, packagesDest, process.platform === "win32" ? "junction" : "dir");
        } catch {
        }
      }
      const shim = this.shimPath();
      let config = existsSync(join2(userHome, "config.toml")) ? readFileSync(join2(userHome, "config.toml"), "utf8") : "";
      if (shim) {
        const events2 = [
          "PreToolUse",
          "PostToolUse",
          "Stop",
          "SubagentStop",
          "SessionStart",
          "UserPromptSubmit",
          "PreCompact",
          "PostCompact"
        ];
        const command = process.platform === "win32" ? this.nodeRunUnquoted(shim) : this.nodeRun(shim);
        config += "\n# --- munder-hive lifecycle hooks (auto-generated; do not edit) ---\n";
        for (const ev of events2) {
          config += `
[[hooks.${ev}]]
[[hooks.${ev}.hooks]]
type = "command"
command = ${JSON.stringify(command)}
timeout = 30
`;
        }
      }
      writeFileSync(join2(home2, "config.toml"), config, "utf8");
      this.exposeCodexDataDirs(home2, userHome, agentId);
    } catch (e) {
      console.error("[hive] installCodexHooks failed:", e);
    }
    return home2;
  }
  exposeCodexDataDirs(home2, userHome, agentId) {
    for (const kind of ["sessions", "archived_sessions"]) {
      try {
        this.exposeCodexDataDir(home2, userHome, agentId, kind);
      } catch (e) {
        console.error(`[hive] exposeCodexDataDir(${kind}) failed:`, e);
      }
    }
  }
  moveCodexDataDir(from, to) {
    try {
      renameSync(from, to);
    } catch (e) {
      if (e.code !== "EXDEV") throw e;
      cpSync(from, to, { recursive: true, force: false, errorOnExist: true });
      rmSync(from, { recursive: true, force: true });
    }
  }
  exposeCodexDataDir(home2, userHome, agentId, kind) {
    const root = this.root();
    if (!root) return;
    if (!agentId || basename2(agentId) !== agentId || agentId === "." || agentId === "..") {
      throw new Error(`invalid agent id: ${agentId}`);
    }
    const source = join2(home2, kind);
    const scanRoot = join2(userHome, kind, "munder-difflin");
    const hiveId = createHash("sha1").update(root).digest("hex").slice(0, 12);
    const target = join2(scanRoot, hiveId, agentId);
    let sourceStat = null;
    try {
      sourceStat = lstatSync(source);
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
    }
    if (sourceStat?.isSymbolicLink()) {
      let current = null;
      try {
        current = realpathSync(source);
      } catch (e) {
        if (e.code !== "ENOENT") throw e;
        unlinkSync(source);
        sourceStat = null;
      }
      if (current) {
        const rel = relative2(realpathSync(scanRoot), current);
        const scope = dirname2(rel);
        if (rel && !rel.startsWith("..") && !isAbsolute2(rel) && dirname2(scope) === "." && basename2(rel) === agentId) return;
        throw new Error(`${source} points outside ${scanRoot}`);
      }
    }
    if (sourceStat && !sourceStat.isDirectory()) throw new Error(`${source} is not a directory`);
    mkdirSync(dirname2(target), { recursive: true });
    if (sourceStat) {
      if (existsSync(target)) {
        if (readdirSync(target).length > 0) throw new Error(`${source} and ${target} both contain data`);
        rmSync(target, { recursive: true, force: true });
      }
      this.moveCodexDataDir(source, target);
    } else if (!existsSync(target)) {
      mkdirSync(target, { recursive: true });
    }
    try {
      symlinkSync(target, source, process.platform === "win32" ? "junction" : "dir");
    } catch (e) {
      if (!existsSync(source) && existsSync(target)) {
        try {
          this.moveCodexDataDir(target, source);
        } catch {
        }
      }
      throw e;
    }
  }
  /** Remove rollout directories moved under the user's standard Codex scan
   *  roots before a full hive reset removes the isolated CODEX_HOME links. */
  removeExposedCodexData() {
    const root = this.root();
    if (!root) return;
    const agents = join2(root, "agents");
    if (!existsSync(agents)) return;
    const userHome = join2(homedir2(), ".codex");
    for (const entry of readdirSync(agents, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      for (const kind of ["sessions", "archived_sessions"]) {
        const source = join2(agents, entry.name, ".codex", kind);
        try {
          if (!lstatSync(source).isSymbolicLink()) continue;
          const target = realpathSync(source);
          const scanRoot = realpathSync(join2(userHome, kind, "munder-difflin"));
          const rel = relative2(scanRoot, target);
          const scope = dirname2(rel);
          if (!rel || rel.startsWith("..") || isAbsolute2(rel) || dirname2(scope) !== "." || basename2(rel) !== entry.name) continue;
          rmSync(target, { recursive: true, force: true });
        } catch (e) {
          if (e.code !== "ENOENT") {
            console.error("[hive] removeExposedCodexData failed:", e);
          }
        }
      }
    }
  }
  /** Pi (earendil-works) bridge. Pi has a rich `pi.on(event, …)` lifecycle but no
   *  Claude-shaped hook file; instead we drop a bundled EXTENSION into a PER-AGENT
   *  PI_CODING_AGENT_DIR (so the user's global ~/.pi is never mutated) that, when Pi
   *  loads it, posts cth-hook-shaped payloads to HIVE_SOCK on tool_call/agent_end and
   *  auto-approves tool calls when the floor is in auto mode (HIVE_AUTO_APPROVE).
   *  Emitting an `agent_end`→`Stop` keeps the harness status in step (→ idle), which
   *  lets the renderer idle inbox-wake nudge deliver mail. Returns the per-agent dir
   *  for PI_CODING_AGENT_DIR.
   *
   *  LIVE-UNVERIFIED: Pi's exact extension-discovery path + event API need BYOK keys
   *  to confirm; this is written best-effort and wrapped so a wrong guess can never
   *  break the spawn. The renderer nudge is the guaranteed drain regardless. */
  installPiHooks(dir) {
    const home2 = join2(dir, ".pi-agent");
    try {
      const extDir = join2(home2, "extensions");
      mkdirSync(extDir, { recursive: true });
      writeFileSync(join2(extDir, "hive-bridge.js"), PI_EXTENSION, "utf8");
      const manifest = { name: "munder-hive-bridge", version: "0.3.1", main: "extensions/hive-bridge.js", auto: true };
      writeFileSync(join2(home2, "extensions.json"), JSON.stringify(manifest, null, 2), "utf8");
      const userPiDir = join2(homedir2(), ".pi", "agent");
      for (const fileName of ["models.json", "models-store.json"]) {
        try {
          const data = readFileSync(join2(userPiDir, fileName), "utf8");
          writeFileSync(join2(home2, fileName), data, "utf8");
        } catch (e) {
          if (e.code !== "ENOENT") console.error(`[hive] installPiHooks copy ${fileName} failed:`, e);
        }
      }
    } catch (e) {
      console.error("[hive] installPiHooks failed:", e);
    }
    return home2;
  }
  /** OpenCode (anomalyco/opencode) bridge — god Decision 1 (native plugin, not proxy).
   *  OpenCode has no Claude-shaped Stop hook, but its plugin API exposes a real
   *  `session.idle` lifecycle event. We drop a bundled PLUGIN into a PER-AGENT config
   *  dir's `plugin/` folder (OpenCode auto-loads `*.js` plugins from there) that posts
   *  HIVE_SOCK payloads on tool.execute.before/after + session.idle — the same
   *  Stop→drain semantics as codex's hooks, provider-agnostic, no traffic interception.
   *  Returns the config dir for OPENCODE_CONFIG_DIR (isolates from ~/.config/opencode).
   *
   *  LIVE-UNVERIFIED: plugin auto-load + session.idle firing + the inject path need
   *  BYOK keys to confirm; written best-effort, wrapped so it can't break the spawn.
   *  The renderer idle inbox-wake nudge is the guaranteed drain fallback. */
  installOpenCodePlugin(dir, theme) {
    const home2 = join2(dir, ".opencode");
    try {
      if (theme) {
        mkdirSync(home2, { recursive: true });
        const choice = { theme: "system" };
        writeFileSync(join2(home2, "tui.json"), JSON.stringify({ $schema: "https://opencode.ai/tui.json", ...choice }, null, 2), "utf8");
        writeFileSync(join2(home2, "opencode.json"), JSON.stringify({ $schema: "https://opencode.ai/config.json", ...choice }, null, 2), "utf8");
      }
      for (const name of ["plugin", "plugins"]) {
        const pluginDir = join2(home2, name);
        mkdirSync(pluginDir, { recursive: true });
        writeFileSync(join2(pluginDir, "hive-bridge.js"), OPENCODE_PLUGIN, "utf8");
      }
    } catch (e) {
      console.error("[hive] installOpenCodePlugin failed:", e);
    }
    return home2;
  }
  /** Crush (charmbracelet/crush) proxy routing. Crush has NO base-URL env override, so
   *  the generic proxy env-rewrite is a no-op for it; instead we write a per-agent
   *  CRUSH_GLOBAL_CONFIG whose standard providers' `base_url` all point at the loopback
   *  proxy (so whatever model the worker picks, its LLM traffic routes through the
   *  sidecar → synthesized Status/Stop/cost → status goes idle → the terminal
   *  work-order + renderer nudge deliver mail). A per-agent CRUSH_GLOBAL_DATA isolates
   *  session state from the user's global ~/.config/crush. Keys ride BYOK env vars
   *  (Crush reads ANTHROPIC_API_KEY/OPENAI_API_KEY/… directly), so none are written
   *  here. `api` follows the proxy's wire shape (advisory). Returns the config + data
   *  paths for the spawn env.
   *
   *  LIVE-UNVERIFIED: the single-upstream proxy serves one provider/endpoint shape at a
   *  time — for full synthesized events pick a model whose provider matches the
   *  configured upstream (or a local OpenAI-compatible endpoint). Cross-provider mixing
   *  is humanQA; the renderer nudge still delivers mail regardless. */
  installCrushConfig(dir, loopbackUrl, api, theme) {
    const config = join2(dir, "crush.json");
    const data = join2(dir, ".crush-data");
    try {
      mkdirSync(data, { recursive: true });
      const wireProvider = api === "anthropic" ? "anthropic" : "openai";
      const providers = { [wireProvider]: { base_url: loopbackUrl } };
      const options = theme ? { tui: { transparent: true } } : void 0;
      writeFileSync(config, JSON.stringify(options ? { providers, options } : { providers }, null, 2), "utf8");
    } catch (e) {
      console.error("[hive] installCrushConfig failed:", e);
    }
    return { config, data };
  }
  /** Grok lifecycle-hook bridge → live hive status, session capture, guarded
   *  inbox delivery, and operator gates for `grok` workers.
   *
   *  Grok supports the same hook events and decision vocabulary as Claude Code,
   *  but its stdin payload uses camelCase keys. A small adapter normalizes those
   *  keys to HookServer's Claude-shaped contract. The hook is installed in the
   *  user's global Grok hook directory because global hooks are trusted and
   *  Grok sessions/resume stay in the user's normal GROK_HOME. The adapter is
   *  strictly scoped by AGENT_ID, so ordinary Grok sessions exit without doing
   *  anything. Best-effort and idempotent. */
  installGrokHooks() {
    const root = this.root();
    if (!root) return;
    try {
      const shim = join2(root, "bin", "grok-hook.cjs");
      mkdirSync(join2(root, "bin"), { recursive: true });
      writeFileSync(shim, GROK_HOOK_SHIM, "utf8");
      const tool = (matcher) => ({
        ...matcher ? { matcher } : {},
        // Let Grok apply its event-aware defaults (5s normally, 600s for Stop).
        // Grok is a HOOK bridge (not a proxy sidecar), so it is hit by the same
        // `node: command not found` 127 — bundled node here too.
        hooks: [{ type: "command", command: this.nodeRun(shim) }]
      });
      const hooks = {
        PreToolUse: [tool(".*")],
        PostToolUse: [tool(".*")],
        Stop: [tool()],
        SubagentStop: [tool(".*")],
        SessionStart: [tool(".*")],
        UserPromptSubmit: [tool()],
        PreCompact: [tool(".*")],
        PostCompact: [tool(".*")]
      };
      const hookDir = join2(homedir2(), ".grok", "hooks");
      mkdirSync(hookDir, { recursive: true });
      writeFileSync(
        join2(hookDir, "munder-hive.json"),
        JSON.stringify({ hooks }, null, 2),
        "utf8"
      );
    } catch (e) {
      console.error("[hive] installGrokHooks failed:", e);
    }
  }
  /** Write the live fleet snapshot Michael reads (`fleet.json`, gitignored).
   *  Best-effort — called from a timer, must never throw. */
  writeFleetSnapshot(snapshot2) {
    const root = this.root();
    if (!root) return;
    try {
      writeFileSync(join2(root, "fleet.json"), JSON.stringify(snapshot2, null, 2), "utf8");
    } catch {
    }
  }
  /** Is this agent the hive's god/orchestrator? */
  isGod(agentId) {
    try {
      const reg = this.registry();
      return reg.godId === agentId || !!reg.agents[agentId]?.isGod;
    } catch {
      return false;
    }
  }
  /**
   * A compact, one-shot LIVE ROSTER line built from `fleet.json` — injected into
   * god's context as `additionalContext` on SessionStart and every
   * UserPromptSubmit (see HookServer).
   *
   * Why: fleet.json/registry.json are always fresh on disk (8s snapshot +
   * archiveOrphanedAgents on boot + PTY-exit archiving), but god's CONTEXT is not.
   * After an app restart god resumes a session whose transcript still describes
   * the OLD floor, and it will happily message agents that no longer exist. It is
   * told to read fleet.json, but "told to" is not "always knows" — so we push the
   * truth in on every turn instead. One line, so the cost is negligible.
   *
   * `ctxOf` (optional, supplied by HookServer) lets the caller layer the LIVE
   * context-window occupancy on top of the disk snapshot — each agent gets a
   * `ctx NN%` so god can see at a glance whose context is nearly full when it
   * routes work. fleet.json only carries cumulative `tokens`, which is a spend
   * figure, not how full the CURRENT window is; the real occupancy lives in
   * HookServer.contextById (from the statusLine shim). Omitted when the callback
   * is absent or an agent has no Status tick yet.
   *
   * Returns null when there is nothing to say (no hive, no snapshot, no agents),
   * so the hook stays a no-op rather than injecting noise.
   */
  rosterContext(ctxOf) {
    const root = this.root();
    if (!root) return null;
    try {
      const raw = readFileSync(join2(root, "fleet.json"), "utf8");
      const snap = JSON.parse(raw);
      const agents = Array.isArray(snap.agents) ? snap.agents : [];
      if (!agents.length) return null;
      const ago = (s) => typeof s !== "number" ? "unknown" : s < 90 ? `${s}s ago` : s < 5400 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago`;
      const MAX = 24;
      const shown = agents.slice(0, MAX);
      let anyCtx = false;
      let anyHold = false;
      const rows = shown.map((a) => {
        const bits = [
          a.role ?? "agent",
          typeof a.lastActiveSecAgo === "number" ? `active ${ago(a.lastActiveSecAgo)}` : "no activity yet"
        ];
        if (a.tokens) bits.push(`${Math.round(a.tokens / 1e3)}k tok`);
        if (a.usd) bits.push(`$${a.usd.toFixed(2)}`);
        if (a.inboxBacklog) bits.push(`inbox ${a.inboxBacklog}`);
        if (a.breaker && a.breaker !== "ok" && a.breaker !== "none") bits.push(`breaker ${a.breaker}`);
        if (a.isGod) bits.push("you");
        if (a.onHold) {
          bits.push("ON HOLD \u2014 1:1 with the human");
          anyHold = true;
        }
        const cw = ctxOf?.(a.id);
        if (cw && cw.limit > 0) {
          const pct = Math.max(0, Math.min(100, Math.round(cw.tokens / cw.limit * 100)));
          bits.push(`ctx ${pct}%`);
          anyCtx = true;
        }
        return `${a.id}${a.name ? ` "${a.name}"` : ""} (${bits.join(", ")})`;
      });
      const more = agents.length > shown.length ? ` +${agents.length - shown.length} more` : "";
      const age = typeof snap.ts === "number" ? ago(Math.round((Date.now() - snap.ts) / 1e3)) : "unknown";
      return `[LIVE ROSTER \u2014 auto-injected from ${join2(root, "fleet.json")}, snapshot ${age}] ${agents.length} ACTIVE agent(s): ${rows.join("; ")}.${more} This is the CURRENT floor and it SUPERSEDES any roster earlier in this conversation \u2014 agents you remember that are absent here have been archived or killed, so do not message them. ` + (anyCtx ? "`ctx NN%` = live window occupancy; absent = not yet reported (unknown, not empty). " : "") + (anyHold ? "An agent marked `ON HOLD \u2014 1:1 with the human` is UNAVAILABLE: the human is working with them directly. Do NOT message them, do NOT dispatch to them, and do NOT count them when picking an owner. Route to someone else, or say the work is waiting. They are still running and their terminal is alive, so this is not a reason to archive them or spawn a replacement. The human flips it off when they are done. " : "") + "Route work to someone on this list before spawning anyone new.";
    } catch {
      return null;
    }
  }
  logTail(n = 200) {
    const root = this.root();
    if (!root || !existsSync(join2(root, "log.jsonl"))) return [];
    const lines = readFileSync(join2(root, "log.jsonl"), "utf8").trim().split("\n").filter(Boolean);
    return lines.slice(-n).map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return { raw: l };
      }
    });
  }
  listMessages(dir) {
    if (!existsSync(dir)) return [];
    return readdirSync(dir).filter((f) => f.endsWith(".json")).sort().map((f) => {
      try {
        return JSON.parse(readFileSync(join2(dir, f), "utf8"));
      } catch {
        return null;
      }
    }).filter((m) => m !== null);
  }
  /**
   * Record an agent's process exit so a death has a durable cause.
   *
   * Before this, an agent killed by its provider crashing was archived with
   * `{kind:'archive', agentId, archived:true}` and NOTHING else — no exit code,
   * no signal, no output. A two-second SIGILL death and a completed agent were
   * indistinguishable in the only record the hive keeps, and the crash banner
   * lived solely in a UI terminal pane. Observed live 2026-08-24: Michael's
   * `claude` CLI panicked 923ms into startup and left no trace on disk.
   *
   * Split by design:
   *   - log.jsonl  gets structured, non-sensitive fields (code, signal, path).
   *   - crashes/   gets the raw tail, and is gitignored — see ensureHive.
   * A normal exit writes nothing at all; this is a diagnostic, not an audit log.
   */
  recordAgentExit(agentId, info) {
    const root = this.root();
    if (!root) return;
    const { exitCode, signal, tail, command } = info;
    const abnormal = typeof signal === "number" && signal !== 0 || typeof exitCode === "number" && exitCode !== 0;
    if (!abnormal) return;
    let tailPath = null;
    if (tail && tail.length) {
      try {
        const dir = join2(root, "crashes");
        mkdirSync(dir, { recursive: true });
        const stamp2 = (/* @__PURE__ */ new Date()).toISOString().replace(/[:.]/g, "-");
        const safeId = agentId.replace(/[^A-Za-z0-9._-]/g, "_");
        const p = join2(dir, `${stamp2}-${safeId}.log`);
        const header = [
          `agent:    ${agentId}`,
          `exitCode: ${String(exitCode)}`,
          `signal:   ${String(signal)}`,
          command ? `command:  ${command}` : null,
          `captured: ${(/* @__PURE__ */ new Date()).toISOString()}`,
          `--- last ${tail.length} bytes of pty output ---`,
          ""
        ].filter(Boolean).join("\n");
        writeFileSync(p, header + tail, "utf8");
        tailPath = p;
      } catch {
      }
    }
    this.appendLog({
      kind: "agent-exit",
      agentId,
      exitCode: exitCode ?? null,
      signal: signal ?? null,
      abnormal: true,
      tailPath
    });
  }
  // — log —
  appendLog(event) {
    const root = this.root();
    if (!root) return;
    const line = JSON.stringify({ ts: Date.now(), ...event }) + "\n";
    try {
      appendFileSync(join2(root, "log.jsonl"), line, "utf8");
    } catch {
    }
  }
  /**
   * Append one cost sample to the durable, append-only ledger at
   * `<root>/cost-ledger.jsonl` (Lane A #6.6d). This is the SOLE durable cost
   * store; its row is exactly the shape Kevin (#4) reserves for the cost_ledger
   * SQLite table, so migration is a mechanical INSERT…SELECT.
   *
   * 🔒 PII: persist ONLY the allowlisted AgentUsageSample — NEVER a raw OTel
   * record (those carry user.email / account / org / hashed-user-id). The sample
   * is PII-free by construction upstream (the provider's normalize step), so we
   * add no redaction here; we just must not widen what we write. The file lives
   * at the hive ROOT, so `mempalace mine` (which only scans per-agent dirs) never
   * ingests it — no palace noise, no MINE_IGNORE entry needed.
   *
   * Like appendLog: append to disk now (durable immediately), let it ride the
   * next natural commit. Best-effort — never throws into the beat.
   */
  appendCostLedger(sample) {
    const root = this.root();
    if (!root) return;
    const row = {
      agent_id: sample.agentId,
      session_id: sample.sessionId,
      ts: sample.ts,
      input: sample.input,
      output: sample.output,
      cache_read: sample.cacheRead,
      cache_creation: sample.cacheCreation,
      model: sample.model,
      usd: sample.usd
    };
    try {
      appendFileSync(join2(root, "cost-ledger.jsonl"), JSON.stringify(row) + "\n", "utf8");
    } catch {
    }
  }
  // — json + atomic io —
  readJson(p, fallback) {
    try {
      return JSON.parse(readFileSync(p, "utf8"));
    } catch {
      return fallback;
    }
  }
  writeJson(p, data) {
    writeFileSync(p, JSON.stringify(data, null, 2), "utf8");
  }
  atomicWriteJson(p, data) {
    const tmp = `${p}.tmp-${shortRand()}`;
    writeFileSync(tmp, JSON.stringify(data, null, 2), "utf8");
    renameSync(tmp, p);
  }
  // — git (single committer, retry + stale-lock recovery) —
  //
  // `gc.autoDetach=false` is what makes this call actually synchronous.
  //
  // A commit runs `gc --auto`, and git detaches that into a BACKGROUND process
  // by default. `spawnSync` returns when `git commit` exits, so the caller
  // believes the hive is quiescent while a gc it cannot see is still writing
  // into `.git/objects/`. Anything that touches the hive directory right after
  // a commit races that process: removing a hive home throws ENOTEMPTY, and a
  // read can catch a half-written pack.
  //
  // It reproduces on its own — create a HiveManager on a fresh temp home, call
  // ensureAgent, then remove the home: ~3.5% of iterations throw ENOTEMPTY,
  // and the leftover is always `.git/objects/`, sometimes still holding a
  // `bitmap-ref-tips_*` temp file that vanishes a fraction of a second later.
  // With this flag, gc runs inline and 200 iterations pass clean.
  //
  // The gc still happens — this only stops it from outliving the command that
  // triggered it, which is what "single committer" was supposed to mean.
  git(args2, cwd) {
    const res = spawnSync("git", ["-c", "commit.gpgsign=false", "-c", "gc.autoDetach=false", "-c", "user.name=Hive", "-c", "user.email=hive@local", ...args2], {
      cwd,
      encoding: "utf8",
      timeout: 8e3
    });
    return { ok: res.status === 0, out: res.stdout ?? "", err: res.stderr ?? "" };
  }
  /** Has the one-time cost-ledger untrack pass run in this process yet? */
  untrackedCostLedger = false;
  /**
   * Stop versioning the cost ledger.
   *
   * `cost-ledger.jsonl` is append-only and gains a row per usage sample, so a
   * repo that tracks it stores a fresh copy of the WHOLE file on every hive
   * commit — and the hive commits constantly. A quarter-gigabyte ledger with a
   * few thousand commits behind it is several hundred gigabytes of blob that
   * git has to walk, which is what turns a routine `gc` into a multi-gigabyte
   * `pack-objects` run. The ignore line in ensureHive keeps new copies out;
   * this drops the one already in the index, because git keeps recording a
   * file it is already tracking no matter what .gitignore says — so the ignore
   * line alone reads as a fix while the repo goes on growing. The ledger stays
   * on disk, so the cost history the app reads is untouched.
   */
  untrackCostLedger(root) {
    if (this.untrackedCostLedger) return;
    this.untrackedCostLedger = true;
    const tracked = this.git(["ls-files", "--", "cost-ledger.jsonl"], root);
    if (!tracked.ok || !tracked.out.trim()) return;
    this.git(["rm", "--cached", "-q", "--ignore-unmatch", "--", "cost-ledger.jsonl"], root);
    console.warn("[hive] untracked the cost ledger from the hive repo");
  }
  /** Has the one-time Codex-home untrack pass run in this process yet? */
  untrackedCodexHomes = false;
  /**
   * Stop versioning Codex worker homes that are ALREADY in the index.
   *
   * Adding `.codex/` to each agent's .gitignore only keeps NEW paths out; git
   * happily keeps recording a file it is already tracking, so a hive that
   * predates that ignore line goes on committing every SQLite and transcript
   * revision exactly as before — the .gitignore reads as a fix while the repo
   * keeps growing. This closes that: once per process, refresh every agent's
   * ignore file (agents that are not running never pass through spawn, and the
   * mine loop only reaches them if mempalace is installed) and drop any tracked
   * `.codex` path from the index. The files stay on disk, so `codex --resume`
   * is unaffected; only their history stops.
   */
  untrackCodexHomes(root) {
    if (this.untrackedCodexHomes) return;
    this.untrackedCodexHomes = true;
    const agentsDir = join2(root, "agents");
    if (!existsSync(agentsDir)) return;
    try {
      for (const id of readdirSync(agentsDir)) ensureMineIgnore(join2(agentsDir, id));
    } catch {
    }
    const tracked = this.git(["ls-files", "--", "agents/*/.codex"], root);
    if (!tracked.ok || !tracked.out.trim()) return;
    this.git(["rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", "agents/*/.codex"], root);
    console.warn("[hive] untracked previously-committed Codex homes from the hive repo");
  }
  /** Commit all hive changes. No-op if there is nothing staged. */
  commit(message) {
    const root = this.root();
    if (!root || !existsSync(join2(root, ".git"))) return;
    this.untrackCostLedger(root);
    this.untrackCodexHomes(root);
    for (let attempt = 0; attempt < 5; attempt++) {
      this.clearStaleLock(root);
      const add = this.git(["add", "-A"], root);
      const commit = this.git(["commit", "-q", "-m", message], root);
      if (commit.ok) return;
      if (/nothing to commit/i.test(commit.out + commit.err)) return;
      if (!add.ok || /index\.lock/i.test(commit.err)) {
        sleepSync(50 * (attempt + 1));
        continue;
      }
      console.warn(`[hive] commit gave up after ${attempt + 1} attempts:`, commit.err || commit.out);
      return;
    }
    console.warn("[hive] commit gave up after 5 attempts");
  }
  clearStaleLock(root) {
    const STALE_THRESHOLD_MS = 1e4;
    try {
      for (const lock of ["index.lock", "HEAD.lock"]) {
        const path = join2(root, ".git", lock);
        if (existsSync(path) && Date.now() - statSync(path).mtimeMs > STALE_THRESHOLD_MS) rmSync(path);
      }
    } catch {
    }
  }
};
function renderCommandsMd() {
  const lines = [
    "# Claude Code commands",
    "",
    "Reference of the Claude Code commands available to you. Two kinds:",
    "- **slash** commands act ONLY on your own session \u2014 you CANNOT run them on another agent's terminal.",
    "- **cli** commands run in your shell (Bash) and can target the fleet, spawn, or query.",
    "",
    'To MONITOR the other agents in this hive, read `fleet.json` in the hive root (live per-agent tokens, cost, status, last tool, breaker level, inbox backlog) plus `registry.json` \u2014 `claude agents` does NOT list your hive siblings. Use `claude -p "..." --output-format json` for a one-off headless query.',
    ""
  ];
  for (const g of COMMAND_GROUPS) {
    lines.push(`## ${g.title}`, "");
    for (const it of g.items) {
      lines.push(`- \`${it.cmd.trim()}\` _(${it.kind})_ \u2014 ${it.desc}${it.usage ? ` e.g. \`${it.usage}\`` : ""}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}
var COMMANDS_MD = renderCommandsMd();
var PROTOCOL_MD = `# Hive protocol

You are one of several Claude agents sharing this hive. Coordination is entirely
file-based; the harness (main process) is the only thing that runs git and the
only thing that moves messages between agents.

## Your workspace \u2014 \`agents/<your-id>/\`
- \`identity.md\`  \u2014 who you are (read-only; the harness writes it).
- \`memory.md\`    \u2014 your long-term memory. Read at the start of a task; append to it as you learn.
- \`inbox/\`       \u2014 messages addressed to you. Read them at the start of a task.
- \`inbox/.done/\` \u2014 move a message here once you've handled it.
- \`outbox/\`      \u2014 drop messages here to send them. The harness delivers them.

**Never write into another agent's folder.** Write to your own \`outbox/\`; the
orchestrator routes it. This keeps every file single-writer.

## Sending a message
Write one JSON file into \`outbox/\` (any filename ending in \`.json\`):

\`\`\`json
{
  "to": "<agent-id> | god | broadcast",
  "act": "request | inform | propose | query | agree | refuse | done",
  "subject": "one-line summary",
  "body": "the details",
  "conversation": "carry this across a thread (optional)",
  "in_reply_to": "<message id you're replying to> (optional)"
}
\`\`\`

The harness fills in \`id\`, \`from\`, \`hops\`, and timestamps.

## Rules of the road
- Only \`request\`, \`query\`, and \`propose\` expect a reply. \`inform\` and \`done\` are terminal \u2014
  don't reply to them, or two agents will loop forever.
- For anything ambiguous, cross-cutting, or needing sign-off, message \`god\` \u2014 the
  god agent clarifies answers for you so you rarely need the human directly.
- There is NO separate human-approval queue. Human-in-the-loop is native to Claude
  Code: a tool you run that needs permission prompts in your own session (the human
  can approve it remotely from their phone via \`/remote-control\`). If you genuinely
  need a human decision, raise it with \`god\` (a message \`"to": "human"\` is routed to
  the god/orchestrator, the human's proxy on the floor).
- \`board.md\` is the shared plan. Don't edit it directly \u2014 \`propose\` changes to \`god\`,
  who is its sole scribe.
- Re-reading a message you already moved to \`.done/\` is a no-op. Don't reprocess.

## The work: board.md vs tasks.json
There are two shared surfaces, both in the hive root:
- \`board.md\` \u2014 the freeform narrative plan. The god agent is its sole scribe; others \`propose\` edits.
- \`tasks.json\` \u2014 the structured task ledger (a kanban: \`todo / doing / blocked / done\`, with title,
  assignee, priority, deps). Keep the task you're working reflected in its status.

## Asking the human (the ASK ME card)
When a card can only move with the human \u2014 a question to answer, or an action only they can do
(create an account, approve a spend, hand over credentials, test on their device) \u2014 the god sets the
card \`"status": "blocked"\` and appends the ask to its \`humanQA\` array:

\`\`\`json
{ "q": "the ask, in markdown", "askedAt": "<iso timestamp>" }
\`\`\`

The harness shows the open ask on the ASK ME board and in the ASK ME tab, and the human's reply lands
in the same entry as \`"a"\` plus an inbox message to god. Every past entry stays on the card \u2014 that
trail is the decision history.

**Write the ask short, and in markdown.** The card renders it, so plain-text asterisks and backticks
show up literally, and a card is not a terminal \u2014 an ask longer than a short paragraph plus its
options (roughly 700 characters) is a report, not a question. Cut the narrative and keep the decision:
- open with ONE **bold** sentence saying exactly what you need from them;
- \`backticks\` for paths, commands, values, and identifiers;
- \`-\` bullets or \`1.\` numbering for every option or step;
- a blank line between paragraphs; a single newline is rendered as a line break, so each option
  stays on its own line.

When the ask originates in another agent's report, REWRITE it into that shape. Never paste the report
body in as the question, and never make the human read the investigation to find the decision. Do NOT park human questions in separate files (no \`HumanQuestion.md\`),
and never sit idle waiting for a reply \u2014 move on to other work and pick the answer up when it arrives.

## Guardrails: circuit breaker & token budgets
A circuit breaker watches every agent for runaway behavior (looping on the same tool, error storms,
overspending). It escalates gently: \`steer\` \u2192 \`constrain\` \u2192 \`stop\`. If a \`Circuit breaker: steer\`
or \`Circuit breaker: constrain\` message lands in your inbox, you ARE the problem it caught \u2014 stop
repeating, summarize what you've tried, and do exactly what the message says (constrain = go read-only
and get god's sign-off before more tool calls). Be **token-frugal**: the floor has a token budget and
each agent can have its own token limit; crossing it trips the breaker. Prefer references over pasted
content, and \`/compact\` your own session when context gets heavy.

## Fleet monitoring (orchestrator)
You (god) are responsible for situational awareness. To see the live state of every agent, read
\`fleet.json\` in the hive root \u2014 it is refreshed continuously with each agent's tokens, cost, status,
breaker level, last tool, last-active time, and inbox backlog. Pair it with \`registry.json\` (the roster)
and \`log.jsonl\` (the event feed). IMPORTANT: \`claude agents\` will NOT show your hive's sibling
sessions (they're spawned independently) \u2014 \`fleet.json\` is your source of truth for them. For a deeper
look at one agent, read its \`agents/<id>/memory.md\` and \`inbox/\`, or send it a \`query\`. A full
Claude Code command reference (slash = your own session only; CLI = your shell, can target the fleet)
is in \`COMMANDS.md\` in the hive root.

## Spawning a worker (orchestrator)
You can start an ephemeral worker yourself. Write ONE JSON file into \`spawn-requests/<id>.json\` in
the hive root:

\`\`\`json
{
  "objective": "what the worker must do (required)",
  "cwd": "/absolute/path/to/the/repo (required)",
  "name": "display name (optional)",
  "command": "engine CLI (optional; defaults to the configured one)",
  "provider": "claude | codex | cursor | antigravity | \u2026 (optional)",
  "model": "model override (optional)",
  "isolate": true,
  "tokenCap": 0,
  "slack": { "channel": "C\u2026", "thread_ts": "\u2026" },
  "character": "meredith",
  "accent": "coral"
}
\`\`\`

The harness polls that directory, spawns \`worker-<id>\`, and moves the request to
\`spawn-requests/.done/\` once it starts or to \`spawn-requests/.failed/\` with a reason. \`isolate\`
defaults to true, giving the worker its own git worktree. \`slack\` routes its failures back to a
thread. This is the ONLY spawn route you can complete on your own: a hire manifest under
\`research/hires/\` needs the human to confirm it in the UI.

\`character\` and \`accent\` set how the worker looks on the office floor, and both are optional.
Naming a worker after a cast member already gets you that avatar, so you only need \`character\` when
the name and the face should differ. An unrecognised value falls back rather than failing the spawn.

**It can be switched off.** The operator controls this under Settings \u2192 Autonomy & Budgets, and it is
OFF by default, because every worker you start spends tokens nobody approved. While it is off your
request is NOT failed or deleted, it waits in \`spawn-requests/\` and runs if the operator turns it on.
If a request of yours has sat there without moving, that is why, and it is a decision to raise with the
human rather than retry. Route work to an agent already on the floor first either way.

## Semantic memory (optional \u2014 when \`mempalace\` is installed)
When \`MEMPALACE_PALACE_PATH\` is set in your environment, the hive shares a
searchable MemPalace and you have the \`mempalace\` CLI:
- \`mempalace search "<query>"\` \u2014 recall relevant past knowledge across the whole
  team by meaning (not just keywords). Add \`--wing <agent-id>\` to scope to one
  agent, \`--results N\` to widen.
- \`mempalace wake-up\` \u2014 a short digest of what matters, good at the start of a task.

Your \`memory.md\` is mined into the palace automatically, so the durable facts you
write there become searchable by every agent. You don't run \`mine\` yourself.
`;
var HOOK_SHIM = `#!/usr/bin/env node
'use strict';
const net = require('net');
const isStatus = process.argv.includes('--status');
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => { data += d; });
process.stdin.on('end', () => {
  let payload = {};
  try { payload = JSON.parse(data || '{}'); } catch (_) {}
  if (!payload.agent_id) payload.agent_id = process.env.AGENT_ID || null;
  const sock = process.env.HIVE_SOCK;
  if (isStatus) {
    // Status-line mode: Claude Code pipes the session status JSON (incl.
    // context_window.total_input_tokens / .context_window_size) after every
    // response. Print the in-terminal gauge IMMEDIATELY (the TUI is waiting),
    // then forward the payload to the harness fire-and-forget so the agent
    // card's context gauge updates push-based, with the EXACT window size.
    payload.hook_event_name = 'Status';
    const cw = payload.context_window || {};
    const used = cw.total_input_tokens, size = cw.context_window_size;
    if (typeof used === 'number' && typeof size === 'number' && size > 0) {
      const pct = Math.round((used / size) * 100);
      process.stdout.write('ctx ' + Math.round(used / 1000) + 'k/' + Math.round(size / 1000) + 'k (' + pct + '%)');
    }
    if (sock) {
      try {
        const c = net.createConnection(sock, () => { c.end(JSON.stringify(payload) + '\\n'); });
        c.on('error', () => {});
        c.on('close', () => process.exit(0));
      } catch (_) { process.exit(0); }
    } else {
      process.exit(0);
    }
    setTimeout(() => process.exit(0), 1500).unref();
    return;
  }
  if (!sock) { process.exit(0); }
  let resp = '';
  const done = (code) => { if (resp) process.stdout.write(resp); process.exit(code); };
  const c = net.createConnection(sock, () => c.write(JSON.stringify(payload) + '\\n'));
  c.setEncoding('utf8');
  c.on('data', (d) => { resp += d; });
  c.on('end', () => done(0));
  c.on('error', () => process.exit(0));
  setTimeout(() => process.exit(0), 5000).unref();
});
`;
var AGY_HOOK_SHIM = `#!/usr/bin/env node
'use strict';
const net = require('net');
const event = process.argv[2] || 'Unknown';
const agentId = process.env.AGENT_ID || null;
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => { data += d; });
process.stdin.on('end', () => {
  const sock = process.env.HIVE_SOCK;
  if (!agentId || !sock) { process.exit(0); } // not a hive worker \u2192 ignore
  let agy = {};
  try { agy = JSON.parse(data || '{}'); } catch (_) {}
  const tc = agy.toolCall || {};
  const payload = {
    hook_event_name: event,
    agent_id: agentId,
    session_id: agy.conversationId,
    transcript_path: agy.transcriptPath,
    cwd: Array.isArray(agy.workspacePaths) ? agy.workspacePaths[0] : undefined,
    tool_name: tc.name,
    tool_input: tc.args
  };
  let resp = '';
  const done = () => {
    // Translate the HookServer's Claude-shaped reply into agy's contract. CRITICAL:
    // agy treats ANY object written to stdout as a decision and FAIL-CLOSES (an
    // empty/decision-less object = DENY). So emit JSON ONLY when there's a real
    // directive (deny/block/steer); otherwise write NOTHING \u2014 no output = allow.
    let out = null;
    try {
      const r = JSON.parse(resp || '{}');
      if (r.decision === 'block') out = { decision: 'block', reason: r.reason, stopReason: r.reason, systemMessage: r.reason };
      else if (r.hookSpecificOutput && r.hookSpecificOutput.permissionDecision === 'deny') out = { decision: 'deny', reason: r.hookSpecificOutput.permissionDecisionReason };
      else if (r.continue === false) out = { decision: 'block', stopReason: r.stopReason };
      else if (r.hookSpecificOutput && r.hookSpecificOutput.additionalContext) out = { systemMessage: r.hookSpecificOutput.additionalContext };
    } catch (_) {}
    if (out) { try { process.stdout.write(JSON.stringify(out)); } catch (_) {} }
    process.exit(0);
  };
  try {
    const c = net.createConnection(sock, () => c.write(JSON.stringify(payload) + '\\n'));
    c.setEncoding('utf8');
    c.on('data', (d) => { resp += d; });
    c.on('end', done);
    c.on('error', () => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  } catch (_) { process.exit(0); }
});
`;
var PI_EXTENSION = `'use strict';
var net = require('node:net');
var SOCK = process.env.HIVE_SOCK;
var AGENT = process.env.AGENT_ID || null;
var AUTO = process.env.HIVE_AUTO_APPROVE === '1';
function post(payload) {
  try {
    if (!SOCK) return;
    payload.agent_id = payload.agent_id || AGENT;
    var c = net.createConnection(SOCK, function () { try { c.end(JSON.stringify(payload) + '\\n'); } catch (e) {} });
    c.on('error', function () {});
  } catch (e) {}
}
function register(pi) {
  if (!pi || typeof pi.on !== 'function') return false;
  try {
    pi.on('tool_call', function (ev) {
      post({ hook_event_name: 'PreToolUse', tool_name: ev && (ev.name || (ev.tool && ev.tool.name)), tool_input: ev && (ev.args || ev.input) });
      if (AUTO) { try { if (ev && typeof ev.approve === 'function') ev.approve(); } catch (e) {} return { approve: true }; }
      return undefined;
    });
    pi.on('tool_result', function (ev) { post({ hook_event_name: 'PostToolUse', tool_name: ev && (ev.name || (ev.tool && ev.tool.name)) }); });
    pi.on('agent_end', function () { post({ hook_event_name: 'Stop' }); });
    return true;
  } catch (e) { return false; }
}
try { if (typeof globalThis !== 'undefined' && globalThis.pi) register(globalThis.pi); } catch (e) {}
module.exports = function (pi) { return register(pi); };
module.exports.activate = function (pi) { return register(pi); };
module.exports.default = module.exports;
`;
var OPENCODE_PLUGIN = `import { createConnection } from 'node:net';
const SOCK = process.env.HIVE_SOCK;
const AGENT = process.env.AGENT_ID || null;
function post(payload) {
  try {
    if (!SOCK) return;
    payload.agent_id = payload.agent_id || AGENT;
    const c = createConnection(SOCK, () => { try { c.end(JSON.stringify(payload) + '\\n'); } catch (e) {} });
    c.on('error', () => {});
  } catch (e) {}
}
export const HiveBridge = async () => {
  return {
    event: async (input) => {
      try { if (input && input.event && input.event.type === 'session.idle') post({ hook_event_name: 'Stop' }); } catch (e) {}
    },
    'tool.execute.before': async (input) => {
      try { post({ hook_event_name: 'PreToolUse', tool_name: input && (input.tool || input.name) }); } catch (e) {}
    },
    'tool.execute.after': async (input) => {
      try { post({ hook_event_name: 'PostToolUse', tool_name: input && (input.tool || input.name) }); } catch (e) {}
    }
  };
};
export default HiveBridge;
`;
var PROXY_BRIDGE_SHIM = `#!/usr/bin/env node
'use strict';
const http = require('http');
const https = require('https');
const net = require('net');
const { URL } = require('url');

const SOCK = process.env.HIVE_SOCK;
const AGENT_ID = process.env.AGENT_ID || null;
const UPSTREAM = process.env.UPSTREAM_BASE_URL || '';
const SESSION = process.env.HIVE_PROXY_SESSION || null;
const API = process.env.HIVE_PROXY_API === 'anthropic' ? 'anthropic' : 'openai';

function trimSlash(s) { while (s.length && s.charAt(s.length - 1) === '/') s = s.slice(0, -1); return s; }

// Per-model context-window size for the Status gauge; fallback 200k.
function ctxSize(model) {
  const m = String(model || '').toLowerCase();
  if (m.indexOf('[1m]') !== -1 || m.indexOf('-1m') !== -1) return 1000000;
  if (m.indexOf('claude') !== -1) return 200000;
  if (m.indexOf('gpt-4o') !== -1 || m.indexOf('gpt-4.1') !== -1 || m.indexOf('o1') !== -1 || m.indexOf('o3') !== -1) return 128000;
  if (m.indexOf('qwen') !== -1) return 262144;
  return 200000;
}

// Fire-and-forget emit of a shim-shaped payload to the hive socket. Never throws.
function emit(payload) {
  if (!SOCK) return;
  try {
    const c = net.createConnection(SOCK, function () { c.end(JSON.stringify(payload) + '\\n'); });
    c.on('error', function () {});
  } catch (e) {}
}

let stopTimer = null;
function armStop() {
  if (stopTimer) clearTimeout(stopTimer);
  stopTimer = setTimeout(function () {
    stopTimer = null;
    emit({ hook_event_name: 'Stop', agent_id: AGENT_ID, session_id: SESSION });
  }, 800);
  if (stopTimer.unref) stopTimer.unref();
}
function cancelStop() { if (stopTimer) { clearTimeout(stopTimer); stopTimer = null; } }

function safeArgs(s) {
  if (s == null) return {};
  if (typeof s === 'object') return s;
  try { return JSON.parse(s); } catch (e) { return { _raw: String(s).slice(0, 500) }; }
}

// Parse a completed response (single JSON or an SSE stream) and synthesize events.
function parseAndEmit(bodyStr, isSse) {
  const objs = [];
  if (isSse) {
    const lines = bodyStr.split('\\n');
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      const idx = ln.indexOf('data:');
      if (idx === -1) continue;
      const data = ln.slice(idx + 5).trim();
      if (!data || data === '[DONE]') continue;
      try { objs.push(JSON.parse(data)); } catch (e) {}
    }
  } else {
    try { objs.push(JSON.parse(bodyStr)); } catch (e) {}
  }
  if (!objs.length) { armStop(); return; }

  let model = null, input = 0, output = 0, cacheRead = 0, cacheCreation = 0, sawUsage = false;
  const toolCalls = [];
  const oaiTools = {}; // accumulate streaming openai tool_calls by index

  for (let i = 0; i < objs.length; i++) {
    const o = objs[i];
    if (!o || typeof o !== 'object') continue;
    if (o.model) model = o.model;
    if (API === 'anthropic') {
      if (o.type === 'message_start' && o.message) {
        if (o.message.model) model = o.message.model;
        const u = o.message.usage || {};
        input += u.input_tokens || 0;
        cacheRead += u.cache_read_input_tokens || 0;
        cacheCreation += u.cache_creation_input_tokens || 0;
        sawUsage = true;
      } else if (o.type === 'message_delta' && o.usage) {
        output += o.usage.output_tokens || 0;
        sawUsage = true;
      } else if (o.type === 'content_block_start' && o.content_block && o.content_block.type === 'tool_use') {
        toolCalls.push({ name: o.content_block.name, input: o.content_block.input || {} });
      } else if (o.usage && !o.type) {
        // non-streaming full message body
        const u = o.usage;
        input += u.input_tokens || 0;
        output += u.output_tokens || 0;
        cacheRead += u.cache_read_input_tokens || 0;
        cacheCreation += u.cache_creation_input_tokens || 0;
        sawUsage = true;
      }
      if (Array.isArray(o.content)) {
        for (let j = 0; j < o.content.length; j++) {
          const blk = o.content[j];
          if (blk && blk.type === 'tool_use') toolCalls.push({ name: blk.name, input: blk.input || {} });
        }
      }
    } else {
      if (o.usage) {
        const u = o.usage;
        input += u.prompt_tokens || 0;
        output += u.completion_tokens || 0;
        if (u.prompt_tokens_details && u.prompt_tokens_details.cached_tokens) cacheRead += u.prompt_tokens_details.cached_tokens;
        sawUsage = true;
      }
      const choices = o.choices || [];
      for (let c = 0; c < choices.length; c++) {
        const ch = choices[c];
        if (!ch) continue;
        if (ch.message && Array.isArray(ch.message.tool_calls)) {
          for (let t = 0; t < ch.message.tool_calls.length; t++) {
            const tc = ch.message.tool_calls[t];
            if (tc && tc.function) toolCalls.push({ name: tc.function.name, input: safeArgs(tc.function.arguments) });
          }
        }
        if (ch.delta && Array.isArray(ch.delta.tool_calls)) {
          for (let t = 0; t < ch.delta.tool_calls.length; t++) {
            const tc = ch.delta.tool_calls[t];
            if (!tc) continue;
            const k = (tc.index != null ? tc.index : t);
            if (!oaiTools[k]) oaiTools[k] = { name: null, args: '' };
            if (tc.function) {
              if (tc.function.name) oaiTools[k].name = tc.function.name;
              if (tc.function.arguments) oaiTools[k].args += tc.function.arguments;
            }
          }
        }
      }
    }
  }
  const keys = Object.keys(oaiTools);
  for (let i = 0; i < keys.length; i++) {
    const t = oaiTools[keys[i]];
    if (t.name) toolCalls.push({ name: t.name, input: safeArgs(t.args) });
  }

  if (sawUsage) {
    emit({ hook_event_name: 'Status', agent_id: AGENT_ID, context_window: { total_input_tokens: input + cacheRead + cacheCreation, context_window_size: ctxSize(model) } });
    emit({ hook_event_name: 'CostSample', agent_id: AGENT_ID, session_id: SESSION, model: model, input: input, output: output, cache_read: cacheRead, cache_creation: cacheCreation });
  }
  if (toolCalls.length) {
    cancelStop(); // a tool call means the turn continues
    for (let i = 0; i < toolCalls.length; i++) {
      emit({ hook_event_name: 'PostToolUse', agent_id: AGENT_ID, session_id: SESSION, tool_name: toolCalls[i].name, tool_input: toolCalls[i].input });
    }
  } else {
    armStop();
  }
}

let upstreamUrl = null;
try { upstreamUrl = new URL(UPSTREAM); } catch (e) {}

const server = http.createServer(function (req, res) {
  cancelStop(); // a new request means the turn is still going
  if (!upstreamUrl) { res.statusCode = 502; res.end('proxy: no upstream'); return; }
  let target;
  try { target = new URL(trimSlash(UPSTREAM) + req.url); } catch (e) { res.statusCode = 502; res.end('proxy: bad url'); return; }
  const isHttps = target.protocol === 'https:';
  const lib = isHttps ? https : http;
  const headers = Object.assign({}, req.headers);
  headers.host = target.host;
  // Ask upstream for plaintext so the tee can parse SSE/JSON reliably; the client
  // gets uncompressed bytes (loopback \u2014 negligible) and no content-encoding to undo.
  delete headers['accept-encoding'];
  const opts = {
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port || (isHttps ? 443 : 80),
    method: req.method,
    path: target.pathname + target.search,
    headers: headers
  };
  const upReq = lib.request(opts, function (upRes) {
    res.writeHead(upRes.statusCode || 502, upRes.headers);
    const ct = String((upRes.headers['content-type'] || ''));
    const wantParse = ct.indexOf('json') !== -1 || ct.indexOf('event-stream') !== -1;
    const isSse = ct.indexOf('event-stream') !== -1;
    const chunks = [];
    let total = 0;
    upRes.on('data', function (chunk) {
      res.write(chunk); // stream straight through to the CLI
      if (wantParse && total < 4194304) { chunks.push(chunk); total += chunk.length; }
    });
    upRes.on('end', function () {
      res.end();
      if (wantParse && chunks.length) {
        try { parseAndEmit(Buffer.concat(chunks).toString('utf8'), isSse); } catch (e) {}
      }
    });
    upRes.on('error', function () { try { res.end(); } catch (e) {} });
  });
  upReq.on('error', function () { try { res.statusCode = 502; res.end('proxy: upstream error'); } catch (e) {} });
  req.pipe(upReq);
});

server.on('error', function () {
  try { process.stdout.write(JSON.stringify({ port: 0 }) + '\\n'); } catch (e) {}
  process.exit(0);
});
server.listen(0, '127.0.0.1', function () {
  const addr = server.address();
  const port = (addr && typeof addr === 'object') ? addr.port : 0;
  try { process.stdout.write(JSON.stringify({ port: port }) + '\\n'); } catch (e) {}
});
`;
var GEMINI_HOOK_SHIM = `#!/usr/bin/env node
'use strict';
const net = require('net');
const agentId = process.env.AGENT_ID || null;
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => { data += d; });
process.stdin.on('end', () => {
  const sock = process.env.HIVE_SOCK;
  if (!agentId || !sock) { process.exit(0); }
  let gemini = {};
  try { gemini = JSON.parse(data || '{}'); } catch (_) {}
  const names = {
    SessionStart: 'SessionStart',
    BeforeAgent: 'UserPromptSubmit',
    BeforeTool: 'PreToolUse',
    AfterTool: 'PostToolUse',
    AfterAgent: 'Stop'
  };
  const payload = {
    ...gemini,
    hook_event_name: names[gemini.hook_event_name] || gemini.hook_event_name || 'Unknown',
    agent_id: agentId
  };
  let resp = '';
  const done = () => {
    let out = null;
    try {
      const r = JSON.parse(resp || '{}');
      if (r.continue === false) out = { continue: false, stopReason: r.stopReason };
      else if (r.decision === 'block') out = { decision: 'deny', reason: r.reason };
      else if (r.hookSpecificOutput && r.hookSpecificOutput.permissionDecision === 'deny') {
        out = { decision: 'deny', reason: r.hookSpecificOutput.permissionDecisionReason };
      } else if (r.hookSpecificOutput && r.hookSpecificOutput.additionalContext) {
        out = { hookSpecificOutput: { additionalContext: r.hookSpecificOutput.additionalContext } };
      }
    } catch (_) {}
    if (out) { try { process.stdout.write(JSON.stringify(out)); } catch (_) {} }
    process.exit(0);
  };
  try {
    const c = net.createConnection(sock, () => c.write(JSON.stringify(payload) + '\\n'));
    c.setEncoding('utf8');
    c.on('data', (d) => { resp += d; });
    c.on('end', done);
    c.on('error', () => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  } catch (_) { process.exit(0); }
});
`;
var GROK_HOOK_SHIM = `#!/usr/bin/env node
'use strict';
const net = require('net');
const agentId = process.env.AGENT_ID || null;
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => { data += d; });
process.stdin.on('end', () => {
  const sock = process.env.HIVE_SOCK;
  if (!agentId || !sock) { process.exit(0); }
  let grok = {};
  try { grok = JSON.parse(data || '{}'); } catch (_) {}
  const names = {
    pre_tool_use: 'PreToolUse',
    post_tool_use: 'PostToolUse',
    post_tool_use_failure: 'PostToolUseFailure',
    permission_denied: 'PermissionDenied',
    stop: 'Stop',
    stop_failure: 'StopFailure',
    session_start: 'SessionStart',
    session_end: 'SessionEnd',
    user_prompt_submit: 'UserPromptSubmit',
    notification: 'Notification',
    subagent_start: 'SubagentStart',
    subagent_stop: 'SubagentStop',
    pre_compact: 'PreCompact',
    post_compact: 'PostCompact'
  };
  const payload = {
    hook_event_name: names[grok.hookEventName] || grok.hookEventName || 'Unknown',
    agent_id: agentId,
    session_id: grok.sessionId,
    cwd: grok.cwd || grok.workspaceRoot,
    tool_name: grok.toolName,
    tool_input: grok.toolInput,
    stop_hook_active: grok.stopHookActive,
    prompt: grok.prompt,
    source: grok.source,
    notification_type: grok.notificationType,
    message: grok.message
  };
  let resp = '';
  const done = () => {
    let out = null;
    try {
      const r = JSON.parse(resp || '{}');
      if (r.continue === false) out = { continue: false, stopReason: r.stopReason };
      else if (r.decision === 'block') out = { decision: 'block', reason: r.reason };
      else if (r.hookSpecificOutput && r.hookSpecificOutput.permissionDecision === 'deny') {
        out = { decision: 'deny', reason: r.hookSpecificOutput.permissionDecisionReason };
      } else if (r.hookSpecificOutput && r.hookSpecificOutput.additionalContext) {
        out = r;
      }
    } catch (_) {}
    if (out) { try { process.stdout.write(JSON.stringify(out)); } catch (_) {} }
    process.exit(0);
  };
  try {
    const c = net.createConnection(sock, () => c.write(JSON.stringify(payload) + '\\n'));
    c.setEncoding('utf8');
    c.on('data', (d) => { resp += d; });
    c.on('end', done);
    c.on('error', () => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  } catch (_) { process.exit(0); }
});
`;

// ../vendor/munder-difflin/src/main/breaker.ts
import { createHash as createHash2 } from "node:crypto";
var LEVELS = ["healthy", "steering", "constrained", "stopped"];
var rank = (l) => LEVELS.indexOf(l);
var actionFor = (l) => l === "steering" ? "steer" : l === "constrained" ? "constrain" : l === "stopped" ? "stop" : "none";
var tokensOf = (s) => s ? s.input + s.output + s.cacheRead + s.cacheCreation : 0;
var workTokensOf = (s) => s ? s.input + s.output + s.cacheCreation : 0;
var DEFAULTS = {
  enabled: true,
  hardStop: false,
  repeatedToolLimit: 8,
  errorStormLimit: 5,
  tokenVelocityPerMin: 6e4
  // output tokens/min — coarse backstop, deliberately high
};
var COMPACT_GRACE_MS = 5 * 6e4;
var POST_COMPACT_GRACE_MS = 9e4;
var PROGRESS_TOOL_WINDOW_MS = 3e5;
var NO_PROGRESS_BEATS = 2;
var CircuitBreaker = class {
  constructor(getConfig) {
    this.getConfig = getConfig;
  }
  getConfig;
  agents = /* @__PURE__ */ new Map();
  cfg() {
    const c = this.getConfig() ?? {};
    return {
      enabled: c.enabled ?? DEFAULTS.enabled,
      hardStop: c.hardStop ?? DEFAULTS.hardStop,
      repeatedToolLimit: c.repeatedToolLimit ?? DEFAULTS.repeatedToolLimit,
      errorStormLimit: c.errorStormLimit ?? DEFAULTS.errorStormLimit,
      tokenVelocityPerMin: c.tokenVelocityPerMin ?? DEFAULTS.tokenVelocityPerMin,
      costCapUsd: c.costCapUsd,
      costCapTokens: c.costCapTokens,
      agentTokenCaps: c.agentTokenCaps
    };
  }
  get(agentId) {
    let s = this.agents.get(agentId);
    if (!s) {
      s = {
        level: "healthy",
        reason: "",
        lastSample: null,
        repeatKey: null,
        repeatCount: 0,
        errorCount: 0,
        compactingUntil: 0,
        lastDistinctToolAt: 0,
        lastUserPromptAt: 0,
        noProgressBeats: 0
      };
      this.agents.set(agentId, s);
    }
    return s;
  }
  /** Drop all state for an agent (call on archive/kill so it can't leak/zombie). */
  forget(agentId) {
    this.agents.delete(agentId);
  }
  /** Current breaker level for an agent (for the live fleet snapshot). */
  levelFor(agentId) {
    return this.agents.get(agentId)?.level ?? "healthy";
  }
  // ── event-driven inputs (fed by HookServer) ──────────────────────────────
  /** A tool call ran. A NEW (name+input) key counts as forward progress (resets
   *  the repeat + error counters and stamps the distinct-tool clock the
   *  no-progress arm reads); the SAME key in a row is the loop signal. */
  recordToolUse(agentId, toolName, toolInput, now = Date.now()) {
    const s = this.get(agentId);
    const key = this.toolKey(toolName, toolInput);
    if (key === s.repeatKey) {
      s.repeatCount += 1;
    } else {
      s.repeatKey = key;
      s.repeatCount = 1;
      s.errorCount = 0;
      s.lastDistinctToolAt = now;
    }
  }
  /** An api_error / retry occurred (no forward progress). */
  recordError(agentId) {
    this.get(agentId).errorCount += 1;
  }
  /** A human submitted a prompt to this agent (UserPromptSubmit hook). Stamps
   *  the conversation progress clock the no-progress arm reads (#376). Only
   *  that arm gains a way to see this work — the loop, error-storm, velocity
   *  and cap arms are unchanged. */
  recordUserPrompt(agentId, now = Date.now()) {
    this.get(agentId).lastUserPromptAt = now;
  }
  /** Compaction started (PreCompact hook). Exempt the Δoutput-based trips —
   *  compaction burns output tokens while touching no coordination file, which
   *  is exactly the false-positive shape of upstream issue #109 (the harness's
   *  own auto-compact mission tripping its own breaker on idle agents). */
  recordCompactStart(agentId, now = Date.now()) {
    this.get(agentId).compactingUntil = now + COMPACT_GRACE_MS;
  }
  /** Compaction finished (PostCompact, or any SessionStart). Shortens the
   *  exemption to a trailing grace — the burst still lands in the next beat's
   *  cumulative diff. A no-op when no compaction is in flight, so a plain
   *  session start never grants an exemption. */
  recordCompactEnd(agentId, now = Date.now()) {
    const s = this.get(agentId);
    if (s.compactingUntil > now) s.compactingUntil = now + POST_COMPACT_GRACE_MS;
  }
  toolKey(toolName, toolInput) {
    let inp = "";
    try {
      inp = JSON.stringify(toolInput, (_k, v) => typeof v === "string" && v.length > 4096 ? v.slice(0, 4096) : v) ?? "";
    } catch {
      inp = String(toolInput);
    }
    return `${toolName ?? "?"}:${createHash2("sha256").update(inp).digest("hex")}`;
  }
  // ── periodic evaluation (called by the heartbeat beat) ────────────────────
  /** Evaluate every agent for this beat and return a decision per agent. The
   *  caller emits each state (keeps the dashboard live) and enforces `action`
   *  when present. */
  tick(inputs, nowMs) {
    const cfg = this.cfg();
    const decisions2 = [];
    if (!cfg.enabled) {
      for (const { agentId } of inputs) {
        const s = this.get(agentId);
        const changed = s.level !== "healthy";
        s.level = "healthy";
        s.reason = "";
        decisions2.push({ state: { agentId, level: "healthy", reason: "", ts: nowMs }, action: "none", changed });
      }
      return decisions2;
    }
    let topSpender = null;
    if (typeof cfg.costCapUsd === "number" && cfg.costCapUsd > 0) {
      let total = 0;
      let max = -1;
      for (const i of inputs) {
        const usd = i.sample?.usd ?? 0;
        total += usd;
        if (usd > max) {
          max = usd;
          topSpender = i.agentId;
        }
      }
      if (total <= cfg.costCapUsd) topSpender = null;
    }
    let topTokenSpender = null;
    if (typeof cfg.costCapTokens === "number" && cfg.costCapTokens > 0) {
      let total = 0;
      let max = -1;
      for (const i of inputs) {
        const tok = tokensOf(i.sample);
        total += tok;
        if (tok > max) {
          max = tok;
          topTokenSpender = i.agentId;
        }
      }
      if (total <= cfg.costCapTokens) topTokenSpender = null;
    }
    for (const input of inputs) {
      const s = this.get(input.agentId);
      const trip = this.evaluate(
        input,
        s,
        cfg,
        nowMs,
        input.agentId === topSpender,
        cfg.costCapUsd,
        input.agentId === topTokenSpender,
        cfg.costCapTokens
      );
      if (input.sample) s.lastSample = input.sample;
      const ceiling = cfg.hardStop ? "stopped" : "constrained";
      let target = s.level;
      if (trip.tripping) {
        target = LEVELS[Math.min(rank(s.level) + 1, rank(ceiling))];
      } else {
        target = LEVELS[Math.max(rank(s.level) - 1, 0)];
      }
      const changed = target !== s.level;
      const escalated = rank(target) > rank(s.level);
      s.level = target;
      s.reason = trip.tripping ? trip.reason : changed ? "recovering \u2014 signals cleared" : s.reason;
      decisions2.push({
        state: { agentId: input.agentId, level: target, reason: s.reason, ts: nowMs },
        action: escalated ? actionFor(target) : "none",
        changed
      });
    }
    return decisions2;
  }
  /** Pure trip evaluation for one agent given its signals + remembered baseline. */
  evaluate(input, s, cfg, nowMs, isTopSpender, costCapUsd, isTopTokenSpender, costCapTokens) {
    if (s.repeatCount >= cfg.repeatedToolLimit) {
      return { tripping: true, reason: `looping: ${s.repeatCount}\xD7 identical tool call (${s.repeatKey?.split(":")[0] ?? "?"})` };
    }
    if (s.errorCount >= cfg.errorStormLimit) {
      return { tripping: true, reason: `error storm: ${s.errorCount} consecutive api errors/retries` };
    }
    const perAgentCap = cfg.agentTokenCaps?.[input.agentId];
    if (typeof perAgentCap === "number" && perAgentCap > 0) {
      const work = workTokensOf(input.sample);
      if (work > perAgentCap) {
        return { tripping: true, reason: `token limit: ${work.toLocaleString()} work tokens over the agent cap of ${perAgentCap.toLocaleString()} (${tokensOf(input.sample).toLocaleString()} total incl. cache reads)` };
      }
    }
    if (isTopSpender && typeof costCapUsd === "number") {
      return { tripping: true, reason: `cost cap: floor total over $${costCapUsd} (top spender $${(input.sample?.usd ?? 0).toFixed(2)})` };
    }
    if (isTopTokenSpender && typeof costCapTokens === "number") {
      return { tripping: true, reason: `token cap: floor total over ${costCapTokens.toLocaleString()} tokens (top spender ${tokensOf(input.sample).toLocaleString()})` };
    }
    if (input.sample && s.lastSample && nowMs >= s.compactingUntil) {
      const dOut = input.sample.output - s.lastSample.output;
      const dMin = (input.sample.ts - s.lastSample.ts) / 6e4;
      if (dOut > 0 && dMin > 0) {
        const velocity = dOut / dMin;
        if (velocity > cfg.tokenVelocityPerMin) {
          return { tripping: true, reason: `token velocity ${Math.round(velocity)}/min > ${cfg.tokenVelocityPerMin}/min` };
        }
        const toolActive = nowMs - s.lastDistinctToolAt < PROGRESS_TOOL_WINDOW_MS;
        const workActive = typeof input.lastWorkAt === "number" && input.lastWorkAt > 0 && nowMs - input.lastWorkAt < PROGRESS_TOOL_WINDOW_MS;
        const humanActive = nowMs - s.lastUserPromptAt < PROGRESS_TOOL_WINDOW_MS;
        if (!input.progressing && !toolActive && !workActive && !humanActive) {
          s.noProgressBeats += 1;
          if (s.noProgressBeats >= NO_PROGRESS_BEATS) {
            return { tripping: true, reason: "no-progress: generating tokens without coordinating (stale log/files)" };
          }
        } else {
          s.noProgressBeats = 0;
        }
      }
    }
    return { tripping: false, reason: "" };
  }
};

// ../vendor/munder-difflin/src/main/control.ts
var MAX_PENDING_STEERS = 20;
var ControlRegistry = class {
  map = /* @__PURE__ */ new Map();
  ensure(id) {
    let c = this.map.get(id);
    if (!c) {
      c = {
        paused: false,
        halted: false,
        autoDeliveryPaused: false,
        gatedTools: /* @__PURE__ */ new Set(),
        steerQueue: []
      };
      this.map.set(id, c);
    }
    return c;
  }
  // ─── Operator actions (wired to IPC) ───────────────────────────────────────
  pause(id, on) {
    this.ensure(id).paused = on;
  }
  pauseAutoDelivery(id, on) {
    this.ensure(id).autoDeliveryPaused = on;
  }
  replaceAutoDeliveryPauses(ids) {
    const paused = new Set(ids);
    for (const [id, control] of this.map) {
      control.autoDeliveryPaused = paused.has(id);
    }
    for (const id of paused) this.ensure(id).autoDeliveryPaused = true;
  }
  gateTool(id, tool, on) {
    const c = this.ensure(id);
    if (on) c.gatedTools.add(tool);
    else c.gatedTools.delete(tool);
  }
  steer(id, text) {
    const t = text.trim();
    if (!t) return;
    const q = this.ensure(id).steerQueue;
    if (q.length >= MAX_PENDING_STEERS) {
      console.warn(`[control] ${id}: steer queue full (${MAX_PENDING_STEERS}) \u2014 dropping oldest note`);
      q.shift();
    }
    q.push(t.slice(0, 1e4));
  }
  /** Request a graceful stop at the next hook boundary. */
  halt(id) {
    this.ensure(id).halted = true;
  }
  /** Drop all queued-but-undelivered steer notes (e.g. closing time cancelled
   *  before a busy agent's next hook boundary consumed the instruction). */
  clearSteers(id) {
    const c = this.map.get(id);
    if (c) c.steerQueue.length = 0;
  }
  /** Clear pause + halt (lets a paused/halted agent run again). Keeps gates. */
  resume(id) {
    const c = this.ensure(id);
    c.paused = false;
    c.halted = false;
  }
  // ─── Reads (used by HookServer) ────────────────────────────────────────────
  shouldHalt(id) {
    return this.map.get(id)?.halted ?? false;
  }
  isAutoDeliveryPaused(id) {
    return this.map.get(id)?.autoDeliveryPaused ?? false;
  }
  /** Whether a tool call should be denied (paused agent, or this tool gated). */
  toolDecision(id, tool) {
    const c = this.map.get(id);
    if (!c) return { deny: false };
    if (c.paused) return { deny: true, reason: "Paused by operator \u2014 resume from the floor to continue." };
    if (tool && c.gatedTools.has(tool)) return { deny: true, reason: `Tool ${tool} is gated by the operator.` };
    return { deny: false };
  }
  /** Dequeue one pending steer note for delivery, or undefined. */
  takeSteer(id) {
    return this.map.get(id)?.steerQueue.shift();
  }
  snapshot(id) {
    const c = this.map.get(id);
    return {
      paused: c?.paused ?? false,
      halted: c?.halted ?? false,
      autoDeliveryPaused: c?.autoDeliveryPaused ?? false,
      gatedTools: c ? Array.from(c.gatedTools) : [],
      pendingSteers: c?.steerQueue.length ?? 0
    };
  }
};

// engine.ts
var body = JSON.parse(readFileSync2(0, "utf8"));
var home = body.home;
if (typeof home !== "string" || !isAbsolute3(home)) throw Error("office_path_invalid");
var hive = new HiveManager(() => home);
var controls = new ControlRegistry();
hive.ensureHive();
var settingsPath = join3(home, "mesh-office.json");
var settings;
try {
  settings = JSON.parse(readFileSync2(settingsPath, "utf8"));
} catch {
  settings = { paused: false, maxIterations: 8, events: [], goals: {} };
}
var save = () => hive.atomicWriteJson(settingsPath, settings);
settings.runtimeBindings ||= {};
var roster = () => Object.values(hive.registry().agents).filter((a) => !a.archived);
var agent = (id) => {
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(id) || !hive.registry().agents[id] || hive.registry().agents[id].archived) throw Error("office_agent_not_found");
  return hive.registry().agents[id];
};
function inboxContext(id) {
  const pending = hive.inbox(id).sort((a, b) => (b.priority || 0) - (a.priority || 0) || String(a.created_at).localeCompare(String(b.created_at)));
  const selected = [];
  let text = "";
  for (const m of pending.slice(0, 8)) {
    const next = (text ? "\n" : "") + m.body;
    if (text.length + next.length > 4e3) break;
    text += next;
    selected.push(m.id);
  }
  return { messages: text, mailboxIds: selected };
}
var log = (event) => hive.appendLog({ ...event, ts: (/* @__PURE__ */ new Date()).toISOString() });
async function hire(name, role, goal, god = false) {
  if (roster().length >= 12) throw Error("office_capacity");
  if (roster().some((a) => a.role === role)) throw Error("office_role_already_exists");
  const id = god ? "orchestrator" : "worker-" + randomUUID().replaceAll("-", "").slice(0, 12);
  await hive.ensureAgent({ id, name, role, provider: "mesh", cwd: home, isGod: god }, { semanticMemory: false, knowledgeGraph: false, mcpDefaults: {} });
  settings.goals[id] = goal;
  save();
  return id;
}
if (!hive.registry().godId) await hire("Director", "Orchestrator", "Delegate, coordinate dependencies and deliver the owner\u2019s mission.", true);
function completeHandoff() {
  if (!settings.handoff) return;
  const { previous, next } = settings.handoff;
  const reg = hive.registry();
  if (!reg.agents[next] || reg.agents[next].archived) throw Error("office_agent_not_found");
  for (const task of hive.tasks().tasks) {
    if (task.assignee === previous && task.status !== "done") hive.patchTask(task.id, { assignee: next });
  }
  for (const message of hive.inbox(previous)) {
    const source = join3(hive.agentDir(previous), "inbox", message.id + ".json");
    const destination = join3(hive.agentDir(next), "inbox", message.id + ".json");
    hive.atomicWriteJson(source, { ...message, to: next });
    renameSync2(source, destination);
  }
  for (const entry of Object.values(reg.agents)) entry.isGod = entry.id === next;
  reg.godId = next;
  hive.atomicWriteJson(join3(hive.root(), "registry.json"), reg);
  log({ kind: "orchestrator.changed", from: previous, to: next });
  delete settings.handoff;
  save();
}
completeHandoff();
var args = body.args || {};
var result = {};
switch (body.operation) {
  case "runtime.sync": {
    for (const [id, runtime] of Object.entries(args.bindings || {})) {
      if (!settings.runtimeBindings[id] && hive.registry().agents[id] && args.agents.some((a) => a.runtime_id === runtime)) {
        settings.runtimeBindings[id] = runtime;
        const row = args.agents.find((a) => a.runtime_id === runtime), reg = hive.registry();
        reg.agents[id].role = row.role || row.name;
        reg.agents[id].name = row.name;
        hive.atomicWriteJson(join3(hive.root(), "registry.json"), reg);
      }
    }
    const initial = hive.registry(), candidate = args.agents.find((a) => a.runtime_id === args.host_runtime);
    if (candidate && !Object.keys(settings.runtimeBindings).length && Object.keys(initial.agents).length === 1 && initial.godId === "orchestrator" && initial.agents.orchestrator.name === "Director" && !hive.tasks().tasks.length && !hive.inboxBacklog("orchestrator")) {
      settings.runtimeBindings.orchestrator = args.host_runtime;
      initial.agents.orchestrator.name = candidate.name;
      initial.agents.orchestrator.role = candidate.role || candidate.name;
      hive.atomicWriteJson(join3(hive.root(), "registry.json"), initial);
    }
    for (const row of args.agents) {
      let id = Object.keys(settings.runtimeBindings).find((id2) => settings.runtimeBindings[id2] === row.runtime_id);
      if (!id) {
        id = "runtime-" + row.runtime_id;
        if (!/^[A-Za-z0-9_-]{1,80}$/.test(id)) throw Error("invalid_runtime_id");
        await hive.ensureAgent({ id, name: row.name, role: row.role || row.name, provider: "mesh", cwd: home, isGod: false }, { semanticMemory: false, knowledgeGraph: false, mcpDefaults: {} });
        settings.runtimeBindings[id] = row.runtime_id;
        settings.goals[id] = row.role || row.name;
      }
      const current = hive.registry().agents[id];
      if (current && current.name !== row.name) {
        const renamed = hive.registry();
        renamed.agents[id].name = row.name;
        hive.atomicWriteJson(join3(hive.root(), "registry.json"), renamed);
      }
      const role = row.role || row.name;
      if (current && current.role !== role) {
        const previousRole = current.role;
        const patched = hive.patchAgentRole(id, role);
        if (!patched.ok) throw Error("office_role_refresh_failed");
        if (settings.goals[id] === previousRole) settings.goals[id] = role;
      }
    }
    save();
    break;
  }
  case "orchestrator.set": {
    const next = agent(args.id), reg = hive.registry(), previous = reg.godId;
    if (previous === next.id) {
      result = { id: next.id, previous };
      break;
    }
    settings.handoff = { previous, next: next.id };
    save();
    completeHandoff();
    result = { id: next.id, previous };
    break;
  }
  case "restore": {
    const entry = hive.registry().agents[args.id];
    if (!entry) throw Error("office_agent_not_found");
    hive.setArchived(args.id, false);
    break;
  }
  case "snapshot":
    break;
  case "hire": {
    const id = await hire(args.name, args.role, args.goal);
    result = { id };
    break;
  }
  case "archive": {
    agent(args.id);
    if (hive.isGod(args.id)) throw Error("director_required");
    if (hive.tasks().tasks.some((t) => t.assignee === args.id && t.status !== "done")) throw Error("agent_has_open_tasks");
    hive.setArchived(args.id, true);
    break;
  }
  case "task.create": {
    if (hive.tasks().tasks.filter((t) => t.status !== "done").length >= 100) throw Error("task_capacity");
    if (args.assignee) agent(args.assignee);
    const tasks = hive.tasks().tasks;
    if (args.dependsOn.some((id2) => !tasks.some((t) => t.id === id2))) throw Error("dependency_not_found");
    const id = "task-" + randomUUID().replaceAll("-", "").slice(0, 12);
    hive.addTask({
      id,
      title: args.title,
      description: args.description,
      assignee: args.assignee || hive.registry().godId,
      status: args.needsApproval ? "blocked" : "todo",
      dependsOn: args.dependsOn,
      priority: 1,
      createdAt: (/* @__PURE__ */ new Date()).toISOString(),
      ...args.needsApproval ? { humanQA: [{ q: "Approve this mission before execution?", askedAt: (/* @__PURE__ */ new Date()).toISOString() }] } : {}
    });
    hive.send({ to: args.assignee || "god", act: "request", subject: args.title, body: args.description || args.title }, "owner");
    result = { id };
    break;
  }
  case "task.priority": {
    const task = hive.tasks().tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "todo") throw Error("task_not_ready");
    hive.patchTask(args.id, { priority: args.priority });
    log({ kind: "task.priority", taskId: args.id, priority: args.priority });
    result = { saved: true };
    break;
  }
  case "task.approve": {
    const task = hive.tasks().tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "blocked") throw Error("approval_not_pending");
    hive.patchTask(args.id, { status: "todo", humanQA: [...(task.humanQA || []).map((qa) => qa.a ? qa : { ...qa, a: args.answer, answeredAt: (/* @__PURE__ */ new Date()).toISOString() })] });
    log({ kind: "approval", taskId: args.id, decision: "approved" });
    break;
  }
  case "mailbox.list": {
    agent(args.agent);
    result = { pending: hive.inbox(args.agent).sort((a, b) => (b.priority || 0) - (a.priority || 0) || String(a.created_at).localeCompare(String(b.created_at))).map((m) => ({ ...m, subject: redactSecrets(m.subject), body: redactSecrets(m.body) })), history: hive.voiceMessages({ agentId: args.agent, limit: 20 }).filter((m) => m.archived) };
    break;
  }
  case "mailbox.edit":
  case "mailbox.remove":
  case "mailbox.priority": {
    agent(args.agent);
    const m = hive.inbox(args.agent).find((m2) => m2.id === args.id);
    if (!m || !/^[A-Za-z0-9_-]{1,160}$/.test(m.id)) throw Error("mailbox_item_not_pending");
    const file = join3(hive.agentDir(args.agent), "inbox", m.id + ".json");
    if (body.operation === "mailbox.remove") unlinkSync2(file);
    else {
      if (body.operation === "mailbox.edit") m.body = args.text;
      else m.priority = args.priority;
      hive.atomicWriteJson(file, m);
    }
    log({ kind: body.operation, agentId: args.agent, id: m.id });
    result = { saved: true };
    break;
  }
  case "message": {
    agent(args.to);
    result = hive.send({ to: args.to, subject: "Owner message", body: args.text, act: "inform" }, "owner");
    break;
  }
  case "pause":
    controls.pause("office", args.paused);
    settings.paused = controls.snapshot("office").paused;
    log({ kind: "office.pause", paused: settings.paused });
    save();
    break;
  case "settings":
    settings.maxIterations = args.maxIterations;
    save();
    break;
  case "memory":
    agent(args.id);
    result = { text: hive.memory(args.id) };
    break;
  case "memory.save":
    agent(args.id);
    writeFileSync2(join3(hive.root(), "agents", args.id, "memory.md"), args.text, { mode: 384 });
    hive.commit("mesh: reviewed office memory");
    break;
  case "begin": {
    if (settings.paused) throw Error("office_paused");
    const tasks = hive.tasks().tasks;
    const task = tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "todo" || task.dependsOn.some((id) => !tasks.some((t) => t.id === id && t.status === "done"))) throw Error("task_not_ready");
    hive.patchTask(args.id, { status: "doing" });
    log({ kind: "mission.start", taskId: args.id });
    result = { task, agents: roster().map((a) => ({
      id: a.id,
      name: a.name,
      role: a.role,
      goal: settings.goals[a.id],
      isDirector: hive.isGod(a.id),
      runtime_id: settings.runtimeBindings[a.id] || null,
      memory: hive.memory(a.id).slice(-4e3),
      ...inboxContext(a.id)
    })), maxIterations: settings.maxIterations };
    for (const a of result.agents) {
      const inbox = join3(hive.agentDir(a.id), "inbox"), done = join3(inbox, ".done");
      mkdirSync2(done, { recursive: true, mode: 448 });
      for (const m of hive.inbox(a.id).filter((m2) => a.mailboxIds.includes(m2.id))) {
        if (/^[A-Za-z0-9_-]{1,160}$/.test(m.id)) renameSync2(join3(inbox, m.id + ".json"), join3(done, m.id + ".json"));
      }
      delete a.mailboxIds;
    }
    break;
  }
  case "event": {
    if (args.agentId) agent(args.agentId);
    log({ kind: args.kind, agentId: args.agentId, to: args.to, taskId: args.taskId, summary: args.summary?.slice(0, 1e3) });
    if (args.to && args.agentId) {
      agent(args.to);
      hive.send({ to: args.to, subject: "Delegation", body: args.summary || "Task delegated", act: "request" }, args.agentId);
    }
    break;
  }
  case "finish": {
    const task = hive.tasks().tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "doing") throw Error("task_not_running");
    hive.patchTask(args.id, {
      status: args.ok ? "done" : "blocked",
      result: args.result?.slice(0, 6e3),
      ...!args.ok ? { humanQA: [{ q: "Mission stopped. Review the failure and approve a retry.", askedAt: (/* @__PURE__ */ new Date()).toISOString() }] } : {}
    });
    hive.send({ to: "god", act: args.ok ? "done" : "refuse", subject: task.title, body: args.result || "Mission stopped" }, "system");
    log({ kind: "mission.finish", taskId: args.id, ok: args.ok });
    break;
  }
  default:
    throw Error("unknown_office_operation");
}
var events = hive.logTail(80);
var breaker = new CircuitBreaker(() => ({ enabled: true, hardStop: true, errorStormLimit: 5 }));
for (const event of events.filter((e) => Date.now() - (typeof e.ts === "number" ? e.ts : Date.parse(e.ts || "")) < 6e4)) {
  if (event.kind === "agent.error" && event.agentId) breaker.recordError(event.agentId);
}
var decisions = breaker.tick(roster().map((a) => ({ agentId: a.id, sample: null, progressing: true })));
if (decisions.some((d) => d.action === "stop")) {
  settings.paused = true;
  save();
}
var snapshot = {
  agents: roster().map((a) => ({
    id: a.id,
    name: a.name,
    role: a.role,
    goal: settings.goals[a.id],
    isDirector: hive.isGod(a.id),
    runtime_id: settings.runtimeBindings[a.id] || null,
    state: settings.paused ? "paused" : events.slice().reverse().find((e) => e.agentId === a.id && ["agent.start", "agent.complete", "agent.error"].includes(e.kind))?.kind === "agent.start" ? "working" : "idle",
    pendingMessages: hive.inboxBacklog(a.id),
    breaker: breaker.levelFor(a.id)
  })),
  orchestratorId: hive.registry().godId,
  archivedAgents: Object.values(hive.registry().agents).filter((a) => a.archived).map((a) => ({ id: a.id, name: a.name, runtime_id: settings.runtimeBindings[a.id] || null })),
  tasks: hive.tasks().tasks,
  messages: hive.voiceMessages({ limit: 30 }),
  events,
  paused: settings.paused,
  maxIterations: settings.maxIterations,
  components: { coordination: "Munder Difflin HiveManager", execution: "CrewAI hierarchical crews" }
};
process.stdout.write(JSON.stringify({ ok: true, result, snapshot }) + "\n");
