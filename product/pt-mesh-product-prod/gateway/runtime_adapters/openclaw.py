from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import RuntimeAdapter, RuntimeResponse


class OpenClawRuntimeAdapter(RuntimeAdapter):
    name = "openclaw"

    def __init__(self) -> None:
        self.bin = os.path.expanduser(
            os.environ.get("OPENCLAW_BIN", "~/.openclaw/bin/openclaw")
        )
        self.model = os.environ.get("OPENCLAW_MODEL", "").strip()
        self.cwd = os.path.expanduser(
            os.environ.get("OPENCLAW_CWD", "~/Rend")
        )
        self.timeout = int(os.environ.get("OPENCLAW_TIMEOUT", "180"))

    def health(self) -> dict[str, Any]:
        binary_exists = Path(self.bin).exists()
        cwd_exists = Path(self.cwd).exists()
        return {
            "ok": binary_exists and cwd_exists,
            "adapter": self.name,
            "binary": self.bin,
            "binary_exists": binary_exists,
            "cwd": self.cwd,
            "cwd_exists": cwd_exists,
            "model": self.model or None,
            "timeout": self.timeout,
        }

    def _build_prompt(
        self,
        *,
        agent_id: str,
        text: str,
        room: str,
        sender: str,
        attachments: list[dict[str, Any]] | None,
    ) -> str:
        attachment_lines = []
        for item in attachments or []:
            path = item.get("path")
            filename = item.get("filename")
            if path:
                attachment_lines.append(
                    f"- {filename or Path(path).name}: local staged path {path}"
                )

        attachment_block = ""
        if attachment_lines:
            attachment_block = (
                "\n\nFiles supplied with this Mesh message are staged locally:\n"
                + "\n".join(attachment_lines)
                + "\nUse them only as needed for the user's request."
            )

        return (
            f"You are {agent_id}, responding in an independent ProgreTech Mesh conversation.\n"
            f"Conversation mode: {room}.\n"
            f"Sender: {sender}.\n\n"
            f"User message:\n{text}"
            f"{attachment_block}\n\n"
            "Treat this as a Mesh-channel conversation independent from Telegram or any other active channel. "
            "Do not reset, replace, interrupt, or assume ownership of work started from another channel. "
            "Return the useful answer to the user. "
            "Do not describe Mesh transport internals unless they are relevant."
        )

    def _extract_text(self, stdout: str) -> str:
        raw = stdout.strip()
        if not raw:
            return ""

        # OpenClaw --json output has changed across releases, so accept a few
        # common response shapes before falling back to raw stdout.
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key in ("text", "response", "output", "message", "content"):
                    value = parsed.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    if isinstance(value, dict):
                        for nested in ("text", "content"):
                            nested_value = value.get(nested)
                            if isinstance(nested_value, str) and nested_value.strip():
                                return nested_value.strip()

                result = parsed.get("result")
                if isinstance(result, str) and result.strip():
                    return result.strip()
                if isinstance(result, dict):
                    for nested in ("text", "output", "content"):
                        value = result.get(nested)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        except json.JSONDecodeError:
            pass

        # Some builds emit logs before a final JSON object. Try the final line.
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if lines:
            try:
                parsed = json.loads(lines[-1])
                if isinstance(parsed, dict):
                    for key in ("text", "response", "output", "message", "content"):
                        value = parsed.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
            except json.JSONDecodeError:
                pass

        return raw

    def send_message(
        self,
        *,
        agent_id: str,
        text: str,
        room: str,
        sender: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> RuntimeResponse:
        health = self.health()
        if not health["ok"]:
            missing = []
            if not health["binary_exists"]:
                missing.append(f"OpenClaw binary not found: {self.bin}")
            if not health["cwd_exists"]:
                missing.append(f"OpenClaw cwd not found: {self.cwd}")
            return RuntimeResponse(
                ok=False,
                text="",
                metadata=health,
                error="; ".join(missing),
            )

        prompt = self._build_prompt(
            agent_id=agent_id,
            text=text,
            room=room,
            sender=sender,
            attachments=attachments,
        )

        command = [
            self.bin,
            "agent",
            "exec",
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.extend([
            "--cwd",
            self.cwd,
            "--timeout",
            str(self.timeout),
            "--json",
            prompt,
        ])

        started = time.time()
        try:
            completed = subprocess.run(
                command,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 15,
                check=False,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={
                    "adapter": self.name,
                    "duration_seconds": round(time.time() - started, 2),
                },
                error="OpenClaw runtime timed out",
            )
        except OSError as exc:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={"adapter": self.name},
                error=f"OpenClaw execution failed: {exc}",
            )

        duration = round(time.time() - started, 2)
        text_out = self._extract_text(completed.stdout)

        metadata = {
            "adapter": self.name,
            "duration_seconds": duration,
            "returncode": completed.returncode,
            "model": self.model or None,
        }

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            return RuntimeResponse(
                ok=False,
                text=text_out,
                metadata=metadata,
                error=stderr or f"OpenClaw exited with code {completed.returncode}",
            )

        if not text_out:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata=metadata,
                error="OpenClaw returned no response text",
            )

        return RuntimeResponse(
            ok=True,
            text=text_out,
            metadata=metadata,
        )
