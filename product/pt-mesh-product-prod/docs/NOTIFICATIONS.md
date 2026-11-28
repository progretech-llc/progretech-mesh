# ProgreTech Mesh — Browser/PWA Notification Contract

## User model

Notifications are configured independently for each agent.

Example:

```text
Rend
☑ Notifications   ⚙
```

The setting is local to the browser/PWA installation.

Enabling Rend notifications on one device does not silently enable them on another.

## Default meaningful events

Enabled by default after the user opts into notifications:

- agent reply
- task completed
- approval required
- error/blocker
- file ready
- gateway offline
- gateway reconnected

Disabled by default:

- progress milestones
- routine activity/status

Heartbeat packets never directly generate notifications.

## Privacy

OS/browser notifications deliberately contain only short operational summaries.

Do not include:

- full prompts
- Telegram message contents
- terminal output
- tool arguments
- file contents
- credentials/secrets
- private memory/context

Examples:

```text
Rend · Approval required
Rend needs your approval.
```

```text
Rend · Task completed
Rend completed a task.
```

The user opens Mesh to see authenticated details.

## Active-window suppression

If the user is actively focused on the Mesh browser/PWA window, OS notifications are
suppressed to avoid duplicating information already visible on screen.

## Permission model

The browser permission prompt is requested only after the user explicitly enables
Notifications for an agent.

If permission is denied, Mesh leaves that agent's notification preference disabled.

## Current Phase 2 scope

This build supports browser/PWA notifications while the Mesh application has a live
session.

It does **not** yet implement true closed-PWA background Web Push.

Background Web Push requires a push subscription and server-side push delivery
boundary. That will remain opt-in and must preserve Mesh's no-cloud-history rule.

## Storage

Preferences use browser-local storage under:

```text
progretech.mesh.notifications.v1
```

No notification preference database is required for session notifications.
