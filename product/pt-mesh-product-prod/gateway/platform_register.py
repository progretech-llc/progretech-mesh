"""Owner-run additive native runtime registration; no agent creation or secret transfer."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import shutil
import subprocess
from gateway.platforms import Platform, runtime_key, harness_environment

SUPPORTED = {'hermes', 'opencode', 'codex', 'openclaw', 'harness'}


def candidate(config, platform, native_id, name=None):
    if not isinstance(platform,str) or platform not in SUPPORTED or not isinstance(native_id, str) or not 1 <= len(native_id) <= 128:
        raise ValueError('supported_platform_and_exact_native_id_required')
    updated = dict(config)
    if config['platform'] == 'mixed':
        entries = [dict(e) for e in config['runtimes']]
    else:
        entries = [{k: config[k] for k in ('platform', 'workspace', 'runtime_home', 'endpoint', 'api_key_file') if config.get(k)}]
        entries[0].update(id=config['prime'], native_id=config['prime'])
    for row in entries:
        if row['platform'] == platform and row['native_id'] == native_id:
            return updated, row['id']
    ident = runtime_key(platform + '-' + native_id)
    if any(e['id'] == ident for e in entries):
        raise ValueError('native_identity_collision')
    entries.append({'id': ident, 'platform': platform, 'native_id': native_id,
                    'name': name or platform.title() + ' ' + native_id, 'workspace': config['workspace']})
    updated.update(platform='mixed', runtimes=entries)
    return updated, ident


@contextmanager
def registration_lock(path):
    with path.with_suffix('.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def register(path, platform, native_id, name=None, home=None):
    path = Path(path)
    # Native installation changes serialize independently of the connector's read-only refresh.
    with registration_lock(path):
        config = json.loads(path.read_text())
        updated, ident = candidate(config, platform, native_id, name)
        probe = Platform(updated, home)
        probe.discover()
        if not probe.rows.get(ident, {}).get('enabled'):
            raise ValueError('native_registration_not_ready')
        fd, temporary = tempfile.mkstemp(prefix='.connector-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                if hasattr(os, 'fchmod'): os.fchmod(stream.fileno(), 0o600)
                json.dump(updated, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if Path(temporary).exists(): Path(temporary).unlink()
    return {'ok': True, 'runtime_id': ident, 'platform': platform, 'native_id': native_id}


def harness_control(native_id, grant=False):
    """Native opt-in: only the actual session can grant follow-ups; creation ownership stays intact."""
    exe=shutil.which('harness')
    if not exe: raise ValueError('native_harness_required')
    check=subprocess.run([exe,'followup',native_id,'--check','--json'],env=harness_environment(),capture_output=True,text=True,timeout=20)
    if check.returncode: raise ValueError('update_native_harness_before_registering')
    if json.loads(check.stdout).get('allowed') is True:return 'ready'
    who=subprocess.run([exe,'whoami','--json'],capture_output=True,text=True,timeout=20)
    caller=json.loads(who.stdout).get('context',{}).get('caller',{}) if who.returncode==0 else {}
    if caller.get('inside') is not True or caller.get('id')!=native_id:
        raise ValueError('run_invitation_in_the_exact_native_harness_session')
    if not grant:return 'self-grant-required'
    result=subprocess.run([exe,'delegate-followup',native_id,'--controller','agent:mesh:mesh-native-gateway','--json'],capture_output=True,text=True,timeout=30)
    if result.returncode or json.loads(result.stdout).get('allowed') is not True:
        raise ValueError('native_harness_self_grant_refused')
    return 'granted'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home()/'.progretech-mesh/platform/connector.json')
    parser.add_argument('--platform', required=True, choices=sorted(SUPPORTED))
    parser.add_argument('--native-id', required=True)
    parser.add_argument('--name')
    args = parser.parse_args()
    print(json.dumps(register(args.config, args.platform, args.native_id, args.name)))


if __name__ == '__main__':
    main()
