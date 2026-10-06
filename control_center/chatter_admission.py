"""Low-priority chatter admission and bounded shared-project teaching context."""
import os
import sqlite3
from pathlib import Path
import psutil
from control_center.memory_search import database

GiB = 1024**3


def resources(mesh, agents):
    """Fail closed on missing telemetry; never evict models or alter runtime limits."""
    try:
        memory = psutil.virtual_memory()
        if os.getloadavg()[0] / max(1, os.cpu_count() or 1) > .85:
            return False, 'Waiting for CPU capacity'
        if psutil.swap_memory().percent > 20 and memory.available < memory.total*.25:
            return False, 'Waiting for memory pressure to subside'
        resident = {m['name'] for m in mesh.api('ps')['models']}
        installed = {m['name']: m['size'] for m in mesh.api('tags')['models']}
        models = {mesh.model(a) for a in agents}
        if any(m not in installed for m in models):
            return False, 'Waiting for configured local models to be available'
        # Both models can remain resident between serial turns. Reserve weights,
        # conservative context headroom, and RAM for native work/desktop.
        added = sum(installed[m] * 1.3 for m in models if m not in resident)
        if memory.available < added + max(8*GiB, memory.total*.15) + len(models)*2*GiB:
            return False, 'Waiting for RAM headroom'
        for device in Path('/sys/class/drm').glob('card[0-9]*/device'):
            total_file = device/'mem_info_vram_total'
            if not total_file.is_file(): continue
            total = int(total_file.read_text())
            if total < 2*GiB: continue  # Shared-memory GPU is covered by RAM.
            used = int((device/'mem_info_vram_used').read_text())
            # Ollama can split weights between VRAM and system RAM. Requiring
            # every non-resident model file to fit wholly in VRAM permanently
            # blocks otherwise safe serial chatter on smaller GPUs; the RAM
            # check above already reserves the full weights and context budget.
            if total-used < max(GiB, total*.1):
                return False, 'Waiting for GPU memory headroom'
            busy = device/'gpu_busy_percent'
            if busy.is_file() and int(busy.read_text()) > 80:
                return False, 'Waiting for GPU capacity'
        return True, 'Idle agents and hardware headroom confirmed'
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return False, 'Resource telemetry unavailable; chatter deferred'


def teaching(home, author):
    """Service reader: only attributed public project lessons, never role-private rows."""
    path = database(home)
    if not path: return [], 'Shared MemPalace unavailable'
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=3) as db:
            db.execute('PRAGMA query_only=ON')
            rows = db.execute("""SELECT memory_id,title,content,author_id,provenance_ref
                FROM memories WHERE scope='project' AND status='active'
                AND project_id='ProgreTech' AND author_type='agent' AND author_id IN (?, 'codex')
                ORDER BY created_at DESC LIMIT 2""", (author,)).fetchall()
        return [{'id':r[0], 'title':r[1][:160], 'text':r[2][:700], 'author':r[3],
                 'evidence':(r[4] or '')[:160]} for r in rows], 'Shared project lessons retrieved' if rows else 'No shared project lessons found'
    except (sqlite3.Error, OSError, TypeError):
        return [], 'Shared MemPalace retrieval failed'
