"""Portable, token-authenticated extension for an agent's local control center.

The host binds enrolled Mesh IDs to runtime IDs in a trusted local file. A cloud
request cannot supply a runtime ID, a URL, a command, or a credential.
"""
import json
import math
import os
import re
import secrets
import threading
from pathlib import Path

from flask import jsonify, request

GRANTS = {'profile', 'inventory', 'speaker', 'workstation', 'microphone', 'camera'}
PROVIDERS = {'kokoro', 'piper'}
VOICES = {'af_alloy', 'af_heart', 'am_adam', 'am_michael', 'am_onyx'}
PROFILE_FIELDS = {'role', 'models', 'workstation', 'stack', 'voice', 'permissions'}
ACTION_GRANTS = {'voice.preview': 'speaker', 'host.system': 'workstation',
                 'models.list': 'inventory', 'audio.get': 'workstation',
                 'audio.set': 'workstation', 'voice.get': 'workstation',
                 'voice.start': 'microphone', 'voice.stop': 'microphone',
                 'vision.get': 'camera', 'vision.analyze': 'camera', 'skills.list': 'inventory',
                 'mail.status': 'inventory', 'orchestration.status': 'inventory',
                 'harness.status': 'inventory', 'grid.status': 'inventory', 'vllm.status': 'inventory',
                 'chatter.get': 'speaker', 'chatter.settings': 'speaker', 'chatter.test': 'speaker'}


def _text(value, limit):
    return isinstance(value, str) and len(value) <= limit and '\x00' not in value


def validate_args(action, args):
    if not isinstance(args, dict):
        raise ValueError('invalid_args')
    fields = {'profile.save': PROFILE_FIELDS, 'voice.preview': {'text'},
              'audio.set': {'source', 'sink'}, 'vision.analyze': {'prompt'},
              'chatter.settings': {'enabled', 'quiet'}, 'communication.job': {'job_id'}}.get(action, set())
    if set(args) - fields:
        raise ValueError('unknown_fields')
    if action == 'communication.job' and (set(args) != {'job_id'} or not isinstance(args['job_id'], str) or not re.fullmatch('[a-f0-9]{32}', args['job_id'])):
        raise ValueError('invalid_job_id')
    if action == 'profile.save':
        if set(args) != PROFILE_FIELDS or not _text(args['role'], 160):
            raise ValueError('invalid_profile')
        models = args['models']
        if not isinstance(models, list) or len(models) > 32 or not all(_text(m, 160) and m.strip() for m in models):
            raise ValueError('invalid_models')
        if args['workstation'] not in ('yes', 'no', 'unknown') or args['stack'] not in ('custom', 'progretech'):
            raise ValueError('invalid_environment')
        permissions = args['permissions']
        if not isinstance(permissions, list) or len(permissions) > len(GRANTS) or any(not isinstance(p, str) or p not in GRANTS for p in permissions):
            raise ValueError('invalid_permissions')
        voice = args['voice']
        if not isinstance(voice, dict) or set(voice) != {'provider', 'voice', 'pitch'}:
            raise ValueError('invalid_voice')
        if not isinstance(voice['provider'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,47}', voice['provider']) or not _text(voice['voice'], 64) or not voice['voice']:
            raise ValueError('invalid_voice')
        if voice['provider'] == 'kokoro' and voice['voice'] not in VOICES:
            raise ValueError('unsupported_voice')
        if voice['provider'] == 'piper' and voice['voice'] != 'current':
            raise ValueError('unsupported_voice')
        pitch = voice['pitch']
        if type(pitch) not in (int, float) or not math.isfinite(pitch) or not -6 <= pitch <= 6:
            raise ValueError('invalid_pitch')
    if action == 'voice.preview' and (set(args) != {'text'} or not _text(args['text'], 300) or not args['text'].strip()):
        raise ValueError('invalid_preview_text')
    if action == 'audio.set' and (set(args) != {'source', 'sink'} or not all(_text(v, 256) for v in args.values())):
        raise ValueError('invalid_audio_devices')
    if action == 'vision.analyze' and (set(args) != {'prompt'} or not _text(args['prompt'], 500)):
        raise ValueError('invalid_vision_prompt')
    if action == 'chatter.settings' and (set(args) != {'enabled', 'quiet'} or any(type(v) is not bool for v in args.values())):
        raise ValueError('invalid_chatter_settings')


class AgentControlProvider:
    def __init__(self, root, bindings, discover, execute, capabilities=None, voice_providers=('kokoro', 'piper')):
        self.root = Path(root)
        # Only the local administrator controls these enrollment-to-runtime bindings.
        self.bindings = bindings
        self.discover = discover
        self.execute = execute
        self.capabilities = set(capabilities or ())
        self.voice_providers = set(voice_providers)
        self.lock = threading.Lock()

    def _path(self, agent_id):
        if not isinstance(agent_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', agent_id) or agent_id not in self.bindings:
            raise ValueError('agent_binding_required')
        return self.root / f'{agent_id}.json'

    def _read(self, agent_id):
        path = self._path(agent_id)
        if path.exists():
            profile = json.loads(path.read_text())
            validate_args('profile.save', profile)
            return profile
        return {'role': '', 'models': [], 'workstation': 'unknown', 'stack': 'custom',
                'voice': {'provider': 'kokoro', 'voice': 'am_onyx', 'pitch': 4}, 'permissions': []}

    def dispatch(self, agent_id, action, args):
        from control_center.management import ACTIONS, dispatch
        if action in ACTIONS:
            return dispatch(self, agent_id, action, args)
        validate_args(action, args)
        with self.lock:
            path = self._path(agent_id)
            runtime_id = self.bindings[agent_id]
            if action == 'profile.save':
                if 'profile' not in args['permissions']:
                    # Allow revocation without allowing new profile data to be
                    # persisted without consent. Keep previously saved details.
                    previous = self._read(agent_id)
                    if args['permissions'] or any(args[k] != previous[k] for k in PROFILE_FIELDS - {'permissions'}):
                        raise ValueError('profile_permission_required')
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
                temp = path.with_suffix('.tmp')
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    json.dump(args, stream)
                temp.replace(path)
                return {'saved': True, 'agent_id': agent_id, 'scope': 'agent-local',
                        'voice_application': 'Saved for per-agent preview; continuous speech requires a runtime consumer.'}
            profile = self._read(agent_id)
            if action == 'profile.get':
                discovered = self.discover(runtime_id) if 'inventory' in profile['permissions'] else {}
                qualified = self.capabilities.copy()
                if profile['voice']['provider'] not in self.voice_providers:
                    qualified.discard('voice.preview')
                return {'agent_id': agent_id, 'profile': profile, 'discovered': discovered,
                        'capabilities': sorted(qualified), 'voice_providers': sorted(self.voice_providers), 'scope': 'agent-local'}
            if action not in self.capabilities or action not in ACTION_GRANTS:
                raise ValueError('capability_unavailable')
            if ACTION_GRANTS[action] not in profile['permissions']:
                raise ValueError('permission_required')
            if action == 'voice.preview' and profile['voice']['provider'] not in self.voice_providers:
                raise ValueError('voice_provider_unavailable')
            if action not in {'voice.preview', 'models.list', 'skills.list', 'mail.status'}:
                if profile['workstation'] != 'yes' or 'workstation' not in profile['permissions']:
                    raise ValueError('workstation_permission_required')
            # Existing service/audio/vision controls affect the shared host. Runtime
            # voice preferences are never forwarded to global voice.settings.
            result = self.execute(runtime_id, action, args, profile)
            if isinstance(result, dict) and result.get('ok') is False:
                raise ValueError('workstation_action_failed')
            return result


def register_provider_routes(app, provider, token, roster=None):
    @app.post('/api/mesh/specklet')
    def native_specklet():
        expected=token(); actual=request.headers.get('X-ProgreTech-Mesh-Local-Token','')
        if not expected or not secrets.compare_digest(expected,actual):return jsonify(ok=False,error='unauthorized'),401
        if request.content_length and request.content_length>16384:return jsonify(ok=False,error='payload_too_large'),413
        body=request.get_json(silent=True)
        if not isinstance(body,dict) or set(body)!={'runtime','action','args','boardId'}:return jsonify(ok=False,error='invalid_request'),400
        from control_center.specklet import Board
        from control_center.management import preferences
        try:
            with provider.lock:
                ids=[a for a,r in provider.bindings.items() if r==body['runtime'] and preferences(provider,a)['enabled']]
            if body['action']=='get':
                rows=[]
                for a in ids:
                    b=Board(provider,a)
                    with b.guarded():
                        d=b.read()
                        if d['enabled']:rows.append(dict(b.response(d),boardId=a))
                return jsonify(ok=True,result={'boards':rows})
            if body['action']!='task' or body['boardId'] not in ids:raise ValueError('agent_binding_required')
            result=Board(provider,body['boardId']).dispatch('specklet.task',body['args'],agent_write=True)
            return jsonify(ok=True,result=result)
        except (ValueError,TypeError) as exc:return jsonify(ok=False,error=str(exc)),400

    @app.get('/api/mesh/control-center/agents')
    def mesh_control_agents():
        expected = token()
        actual = request.headers.get('X-ProgreTech-Mesh-Local-Token', '')
        if not expected or not secrets.compare_digest(expected, actual):
            return jsonify(ok=False, error='unauthorized'), 401
        try:
            if roster is not None:
                return jsonify(ok=True, agents=roster(request.args.get('gateway_id')))
            agents = []
            for aid, runtime in provider.bindings.items():
                from control_center.management import preferences
                if not preferences(provider, aid)["enabled"]:
                    continue
                item = provider.discover(runtime)
                agents.append({'id': aid, 'name': item.get('name', runtime), 'role': item.get('role', '')})
            return jsonify(ok=True, agents=agents)
        except Exception:
            return jsonify(ok=False, error='role_discovery_failed'), 502

    @app.post('/api/mesh/control-center')
    def mesh_agent_control():
        expected = token()
        actual = request.headers.get('X-ProgreTech-Mesh-Local-Token', '')
        if not expected or not secrets.compare_digest(expected, actual):
            return jsonify(ok=False, error='unauthorized'), 401
        if request.content_length and request.content_length > 550000:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {'agent_id', 'action', 'args'}:
            return jsonify(ok=False, error='invalid_request'), 400
        try:
            result = provider.dispatch(body['agent_id'], body['action'], body['args'])
            return jsonify(ok=True, result=result)
        except (ValueError, TypeError) as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception:
            return jsonify(ok=False, error='local_provider_failed'), 502
