"""Owner-facing release status and agent-executed Mesh integration updates."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import zipfile
from flask import jsonify, render_template, send_file
from gateway.platform_release import digest
from mesh_host_distribution import host_bundle


def release(root):
    data, sha = host_bundle(root)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()}
    helper = Path(root)/'distribution/mesh-platform-update-v1.py'
    return {'bundle_sha256':sha,'fingerprint':digest(files),
            'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(), 'files':list(sorted(files))}


def update_prompt(origin, host, latest, root):
    gid = host['id']
    platform = host.get('platform', '')
    common = [f'Update this computer’s existing Mesh integration for gateway {gid} to the release at {origin}.',
        'Use your existing owner-authorized installation permissions. Work locally on that gateway computer.',
        'Keep the same signed gateway identity, device credential, prime agent, runtime/model configuration, profiles, skills, API keys, memory and Factory board. Never print or upload secrets or re-enroll the gateway.',
        'Wait for active agent jobs to finish. Identify the existing connector/provider and supervisor before stopping only the Mesh integration for the update. Preserve custom changes; review the changed-file list before applying.',
        f'Target Mesh integration fingerprint: {latest["fingerprint"]}.',
        f'Host bundle: {origin}/api/distribution/host/bundle ; SHA-256 {latest["bundle_sha256"]}.']
    if platform in {'hermes','opencode','openwebui','openai'}:
        common += [f'Download {origin}/api/distribution/platform/update-helper to a private temporary directory as mesh-platform-update-v1.py. Verify SHA-256 {latest["helper_sha256"]} BEFORE executing it.',
            'Locate the existing platform state directory (normally ~/.progretech-mesh/platform) containing connector.json, source and venv. Do not recreate its configuration.',
            f'Run python3 mesh-platform-update-v1.py --state <existing-state-directory> --sha256 {latest["bundle_sha256"]} to review the files. Stop the existing Mesh connector through its actual supervisor, then run the same command with --apply.',
            'The helper stages and checks the downloaded logic, preserves the private connector config and Factory data, and updates Mesh-owned connector/provider/Factory files and dependencies. It does not upgrade the underlying agent runtime or unrelated extensions.',
            'Restart that same Mesh connector with its existing supervisor and configuration. If preflight fails, keep the previous source, restore the existing connector service and report the exact error. Do not call a failed update successful.']
    elif platform == 'openclaw' or 'openclaw' in host.get('runtime','').lower():
        plan = json.loads((Path(root)/'distribution/openclaw-self-bootstrap-plan-v1.json').read_text())
        pkg = plan['package']
        common += [f'OpenClaw Mesh extension: {origin}/api/distribution/openclaw/progretech-mesh/{pkg["version"]}/package ; version {pkg["version"]} ; SHA-256 {pkg["sha256"]}.',
            f'Read {origin}/api/enrollment/adapters/openclaw/install-plan and use its supported managed plugin update procedure for the existing installation. Preserve the plugin config and channels; do not redeem activation or enroll a new identity.',
            f'Fetch {origin}/api/distribution/host/bootstrap ; verify SHA-256 {hashlib.sha256((Path(root)/"distribution/mesh-host-bootstrap-v1.py").read_bytes()).hexdigest()} before execution.',
            f'Using the exact existing native runtime ID, run python3 mesh-host-bootstrap-v1.py --bundle {shlex.quote(origin+"/api/distribution/host/bundle")} --sha256 {latest["bundle_sha256"]} --gateway {shlex.quote(gid)} --runtime <existing-native-runtime-id>.',
            'Reload the Mesh extension/provider using supported runtime controls after active work completes. Upgrade only Mesh-owned extension and provider files.']
    else:
        common += [f'Inspect {origin}/api/enrollment/adapters for the supported Mesh adapter matching the actual installed runtime. Update only that existing integration using its documented procedure and verified published checksums. If no supported adapter matches, report the missing support instead of installing another runtime.']
    common += ['Verify the existing gateway reconnects, all native profiles and their current models/runtime appear in the agent fleet and Mission Control, and Factory retains its agents, chosen Scrum Master and task board.',
        'Refresh Sync & Update. Report the installed fingerprint when supported; for legacy adapters that cannot report one, provide exact installed package versions and checksums and say verification is manual.']
    return '\n\n'.join(common)


def register_sync_routes(app, require_session, user_id, registry, gateways, origin):
    @app.get('/sync-update')
    @require_session
    def sync_update_page():
        return render_template('sync_update.html',build_id=app.config['BUILD_ID'])

    @app.get('/api/distribution/platform/update-helper')
    def platform_update_helper():
        response=send_file(Path(app.root_path)/'distribution/mesh-platform-update-v1.py',mimetype='text/x-python',conditional=True)
        response.headers['Cache-Control']='no-cache'
        return response

    @app.get('/api/sync-updates')
    @require_session
    def sync_update_status():
        from mesh_gateways import visible
        latest=release(app.root_path)
        hosts=[]
        for host in list(registry.values()):
            if (host.get('owner_id') != user_id() or host.get('trust_state')!='verified'
                    or host.get('control_center_gateway') or host.get('office_worker')
                    or host.get('office_archived') or not visible(host,registry)):
                continue
            observed=host.get('gateway_release',{})
            connected=host['id'] in gateways
            fingerprint=observed.get('fingerprint')
            state='offline' if not connected else 'unknown' if not fingerprint else 'current' if fingerprint==latest['fingerprint'] else 'update_available'
            hosts.append({'id':host['id'],'name':host.get('name',host['id']), 'runtime':host.get('runtime','Unknown'),
                'connected':connected,'state':state,'fingerprint':fingerprint,
                'prompt':update_prompt(origin(),host,latest,app.root_path)})
        response=jsonify(ok=True,version=app.config['MESH_VERSION'],build=app.config['BUILD_ID'],latest=latest,gateways=hosts)
        response.headers['Cache-Control']='no-store'
        return response
