import test from 'node:test';
import assert from 'node:assert/strict';
import {forwardFactoryControl} from './factory-control.js';

test('rejects arbitrary commands, malformed args, and missing gateway access', async () => {
  await assert.rejects(forwardFactoryControl({action: 'exec'}, async () => {}));
  await assert.rejects(forwardFactoryControl({action: 'factory.status', args: []}, async () => {}));
  await assert.rejects(forwardFactoryControl({action: 'factory.status'}, null), {message: 'gateway_unavailable'});
});

test('reads the agent roster and model catalog through the connected gateway', async () => {
  const calls = [];
  const result = await forwardFactoryControl({action: 'factory.status'}, async (method, params, options) => {
    calls.push({method, params, options});
    if (method === 'agents.list') return {
      defaultId: 'main',
      agents: [{id: 'main', name: 'Fallback name', identity: {name: 'Rend', role: 'Python architect'}, model: {primary: 'ollama/qwen'}}],
    };
    if (method === 'models.list') return {models: [{id: 'qwen', provider: 'ollama'}]};
    throw new Error(`unexpected method: ${method}`);
  });

  assert.deepEqual(calls.map(({method}) => method), ['agents.list', 'models.list']);
  assert.deepEqual(calls[1].params, {agentId: 'main'});
  assert.deepEqual(calls[0].options, {scopes: ['operator.read']});
  assert.equal(result.agents[0].name, 'Rend');
  assert.equal(result.agents[0].role, 'Python architect');
  assert.deepEqual(result.providers.ollama.models.map(({id}) => id), ['qwen']);
  assert.ok(result.capabilities.includes('models.list'));
});

test('lists models through the default agent gateway scope', async () => {
  const calls = [];
  const result = await forwardFactoryControl({action: 'models.list'}, async (method, params) => {
    calls.push({method, params});
    return method === 'agents.list' ? {defaultId: 'main'} : {models: [{id: 'qwen'}]};
  });

  assert.deepEqual(calls, [{method: 'agents.list', params: {}}, {method: 'models.list', params: {agentId: 'main'}}]);
  assert.deepEqual(result.models, [{id: 'qwen'}]);
});

test('maps read-only host and skill actions to gateway methods', async () => {
  const methods = [];
  const result = await forwardFactoryControl({action: 'skills.list'}, async (method) => {
    methods.push(method);
    return {agentId: 'main', skills: [{name: 'docs', source: 'bundled', path: '/private/plugin/skills/docs', eligible: true}]};
  });

  await forwardFactoryControl({action: 'host.system'}, async (method) => { methods.push(method); return {ok: true}; });
  await forwardFactoryControl({action: 'host.overview'}, async (method) => { methods.push(method); return {ok: true}; });
  assert.deepEqual(methods, ['skills.status', 'health', 'system-presence']);
  assert.deepEqual(result.skills, [{name: 'docs', description: undefined, source: 'bundled', bundled: undefined, eligible: true}]);
});

test('reports controls unavailable when the gateway has no corresponding capability', async () => {
  const result = await forwardFactoryControl({action: 'audio.get'}, async () => { throw new Error('must not call unsupported actions'); });
  assert.deepEqual(result, {ok: false, error: 'gateway_capability_unavailable'});
});
