from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import mesh_media_router as router

ROOT = Path.home() / ".local" / "share" / "rend" / "media-runtime"
OUT_ROOT = Path("/mnt/pt-context/job-artifacts/factory-media")
SCRIPTS = Path(__file__).resolve().parent / "scripts"

def _image_python():
    device=os.environ.get('FACTORY_IMAGE_DEVICE','rocm')
    if device not in {'cuda','rocm'}:
        raise ValueError('Unsupported image backend')
    if device == 'cuda':
        return Path('/mnt/pt-context/factory/runtime/comfyui-cuda/bin/python')
    return Path.home()/'.local/share/rend/runtimes/comfyui-rocm/bin/python'

def _require_output_root():
    if subprocess.check_output(['findmnt','-n','-o','TARGET','-T','/mnt/pt-context'],text=True,timeout=10).strip()!='/mnt/pt-context':
        raise RuntimeError('PT_CONTEXT unavailable; no alternate artifact destination')
    if not OUT_ROOT.resolve().is_relative_to(Path('/mnt/pt-context/job-artifacts')):
        raise ValueError('Invalid artifact destination')

def _image_admission_command(command, timeout):
    helper = Path.home() / 'ptinternal/bin/factory-admission'
    status = json.loads(subprocess.check_output([str(helper), 'status'], text=True, timeout=10))
    ancestors=set(); pid=os.getpid()
    for _ in range(64):
        ancestors.add(pid)
        if pid <= 1: break
        pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
    lease=status.get('lease', {})
    if not status.get('ok'):
        raise RuntimeError('Image admission unavailable')
    if status.get('busy'):
        if lease.get('state') == 'active' and lease.get('pid') in ancestors:
            return command
        raise RuntimeError('Image admission busy; backend not started')
    return [str(Path.home()/'ptinternal/bin/factory-heavy-command'),
            '--role', os.environ.get('FACTORY_ADMISSION_ROLE', 'imagen'),
            '--project', os.environ.get('FACTORY_PROJECT', 'ProgreTech'),
            '--task', 'mesh-image-generation', '--timeout', str(max(1, min(3600, int(timeout)-30))),
            '--admission-timeout', '0', '--owned-backend', '--', *command]

def _run_backend(command, timeout):
    # Every subprocess belongs to this new session, never another factory job.
    with subprocess.Popen(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                # SIGINT lets the supported admission executor run its
                # BaseException cleanup for its separately owned child group.
                os.killpg(proc.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                proc.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                pass
            finally:
                # Also stop descendants if the launcher already exited.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.communicate(timeout=10)
            raise
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)

@dataclass(frozen=True)
class MediaResult:
    ok: bool
    role: str | None
    capability_id: str | None
    artifact: str | None
    elapsed_seconds: float
    returncode: int
    stdout: str
    stderr: str
    metadata: dict[str, Any]

def _validate_prompt(prompt: str) -> str:
    p=str(prompt or "").strip()
    if not p:
        raise ValueError("prompt_required")
    if len(p) > 1200:
        raise ValueError("prompt_too_long")
    return p

def _script_for_role(role: str) -> Path:
    mapping={
      "image_generation": SCRIPTS/"media-image-generate.py",
      "video_generation": SCRIPTS/"media-video-generate.py",
      "music_generation": SCRIPTS/"media-music-generate.py",
    }
    p=mapping.get(role)
    if p is None:
        raise KeyError(f"unsupported_media_role:{role}")
    return p

def invoke_intent(intent: str, *, prompt: str | None=None, timeout: int=1800) -> MediaResult:
    route=router.resolve_media_intent(intent)
    if route is None:
        return MediaResult(False,None,None,None,0.0,2,"","",
                           {"error":"no_unambiguous_active_media_route"})

    # Resolve again through the explicit ACTIVE/owner-approved gate immediately before execution.
    checked=router.resolve_active_role(route.role)
    if checked is None or checked.capability_id != route.capability_id:
        raise PermissionError("media_capability_not_active_or_owner_approved")

    p=_validate_prompt(prompt or intent)
    script=_script_for_role(route.role)
    if not script.is_file():
        raise FileNotFoundError(str(script))

    _require_output_root()
    OUT_ROOT.mkdir(parents=True,exist_ok=True)
    stamp=str(time.time_ns())
    outdir=OUT_ROOT/f"{route.capability_id}-{stamp}"
    outdir.mkdir(parents=True,exist_ok=True)

    cmd=[
      str(_image_python())
      if route.role == "image_generation"
      else str(Path.home()/".local/share/rend/runtimes/comfyui-rocm/bin/python")
      if route.role == "video_generation"
      else str(Path.home()/".local/share/rend/runtimes/ace-step15-rocm/venv/bin/python"),
      str(script),
      "--prompt",p,
      "--output-dir",str(outdir),
    ]

    if route.role == 'image_generation':
        cmd=_image_admission_command(cmd,timeout)

    t0=time.monotonic()
    proc=_run_backend(cmd,timeout)
    elapsed=time.monotonic()-t0

    artifact=None
    meta={}
    result_file=outdir/"result.json"
    if result_file.is_file():
        try:
            meta=json.loads(result_file.read_text())
            artifact=meta.get("artifact")
        except Exception:
            meta={"error":"invalid_result_json"}

    owned=isinstance(artifact,str) and (route.role!='image_generation' or Path(artifact).resolve().is_relative_to(outdir.resolve()))
    ok=proc.returncode==0 and owned and Path(artifact).is_file() and Path(artifact).stat().st_size>0
    if artifact and not owned:
        meta['error']='artifact_outside_owned_job'; meta.pop('artifact',None); artifact=None
    meta['owned_output_dir']=str(outdir.resolve())
    return MediaResult(
      ok=ok,
      role=route.role,
      capability_id=route.capability_id,
      artifact=artifact,
      elapsed_seconds=elapsed,
      returncode=proc.returncode,
      stdout=proc.stdout[-12000:],
      stderr=proc.stderr[-12000:],
      metadata=meta,
    )
