# RC2 Live Acceptance — Rend

## Goal

Enroll the current, untouched Rend installation into ProgreTech Mesh using only:
- Mesh in the browser;
- the existing Telegram conversation with Rend.

Edwin must not access Rend's workstation.

## Before sending anything

Confirm:
- Mesh is running from this RC2 candidate.
- The enrollment endpoint produces PTM1 v3.
- OpenClaw adapter package is version `0.7.7`.
- Package SHA-256 is `ffcde913f823ea5986c23a2e445e6cfe4ccb262ae38169ece782db321c7675c3`.
- Bootstrap helper SHA-256 is `7a309839f409cc67199536b28c08e7659c777c9b1b584e76f668db45b9b877d6`.

## Live sequence

1. In Mesh, select Rend and choose Connect.
2. Generate/copy the complete agent-facing enrollment message.
3. Send that message to Rend in the existing Telegram conversation.
4. Do not log into Ubuntu.
5. Let Rend inspect the instruction, discover the Mesh protocol, identify OpenClaw, fetch and verify the adapter, and perform the supported installation using his existing authority.
6. If Rend asks for approval through Telegram because his normal runtime security policy requires it, approve or decline there. Do not switch to workstation access.
7. Observe Mesh for the connected state.
8. While connected, send a normal Telegram message to Rend and confirm its activity appears in Mesh.
9. Send a separate message through Mesh and confirm that reply/session behavior remains independent of Telegram.
10. Start or observe a normal task through Telegram; refresh/disconnect/reconnect Mesh and confirm the Telegram task is not interrupted.
11. If practical, restart only the Mesh browser/PWA session and confirm Rend reconnects without re-enrollment.
12. Record the result.

## PASS

Pass only if the whole enrollment completed without workstation access and:
- Telegram remained healthy;
- no active work was cancelled/reset;
- passive activity appeared in Mesh;
- Mesh conversation remained independent;
- reconnect worked from the stored credential.

## FAIL

Fail if any of these are required:
- workstation login;
- terminal command by Edwin;
- manual plugin copy/install;
- manual OpenClaw restart by Edwin;
- bypassing Rend/OpenClaw permissions;
- Mesh taking over Telegram state;
- active work being interrupted.

## Allowed non-failure outcome

If Rend stops and says through Telegram that his existing policy lacks a necessary permission, that is a valid product finding rather than a security failure. Record the exact missing capability. The hands-off acceptance itself remains incomplete until that capability can be handled through the agent's normal approval path.
