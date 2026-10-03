import assert from "node:assert/strict";
import test from "node:test";
import { resolveMeshTarget, meshConversationBody } from "./routing.js";
import { readFileSync } from 'node:fs';
const config = { agents: { entries: { main: {}, coder: {}, researcher: {}, architect: {}, reviewer: {}, fast: {} } } };
test("existing Mesh Rend identity resolves to existing OpenClaw main", () => {
  assert.deepEqual(resolveMeshTarget({agent_id: "rend", text: "hello"}, config), {agentId: "main", text: "hello"});
});
test("console and API text selects a distinct role", () => {
  assert.deepEqual(resolveMeshTarget({agent_id: "rend", text: "/agent mak inspect\ncode"}, config), {agentId: "coder", text: "inspect\ncode"});
  assert.equal(resolveMeshTarget({target_agent: "lyra", text: "brief"}, config).agentId, "researcher");
});
test("unknown and missing roles fail closed", () => {
  for (const id of ["root", "../../etc", "constructor", "__proto__"]) {
    assert.throws(() => resolveMeshTarget({agent_id: id, text: "hello"}, config), /unknown_agent/);
  }
  assert.throws(() => resolveMeshTarget({agent_id: "mak", text: "hello"}, {agents:{entries:{main:{}}}}), /unknown_agent/);
});
test("invalid payloads never start agent work", () => {
  for (const text of ["", " ", 42, null]) assert.throws(() => resolveMeshTarget({text}, config), /empty_message/);
  assert.throws(() => resolveMeshTarget({text: "x".repeat(32001)}, config), /message_too_long/);
  assert.throws(() => resolveMeshTarget({text: "/agent mak"}, config), /usage/);
});
test('authenticated transports preserve explicit role despite enrolled Rend identity', () => {
  for (const transport of ['mesh-websocket', 'webrtc-direct']) {
    for (const [target_agent, agentId] of [['lyra','researcher'], ['mak','coder']]) {
      const body = meshConversationBody({text:'inspect',target_agent, model:'rend-architect'}, 'rend', transport);
      assert.equal(resolveMeshTarget(body, config).agentId, agentId);
      assert.equal(body.transport, transport);
      assert.equal(Object.hasOwn(body, 'model'), false);
    }
    assert.equal(resolveMeshTarget(meshConversationBody({text:'inspect',model:'mak'}, 'rend', transport), config).agentId, 'main');
  }
});
test('explicit invalid or unavailable structured role never falls back to Rend', () => {
  for (const target_agent of ['',null,{},'root','../../etc','constructor','__proto__','qwen3-coder:30b']) {
    const body = meshConversationBody({text:'inspect',target_agent}, 'rend', 'webrtc-direct');
    assert.throws(() => resolveMeshTarget(body, config), /unknown_agent/);
  }
  assert.throws(() => resolveMeshTarget(meshConversationBody({text:'inspect',target_agent:'mak'},'rend','mesh-websocket'), {agents:{entries:{main:{}}}}), /unknown_agent/);
});
test('both transport handlers use the tested normalization path', () => {
  const source=readFileSync(new URL('./index.js',import.meta.url),'utf8');
  assert.match(source, /meshConversationBody\(payload, meshIdentity\?\.agent_id, "mesh-websocket"\)/);
  assert.match(source, /meshConversationBody\(message,meshIdentity\?\.agent_id,"webrtc-direct"\)/);
});

test('consolidated aliases preserve IDs and retired roles fail closed', () => {
  const cfg={agents:{entries:{coder:{},researcher:{},imagen:{},codex:{}}}};
  for (const [name,id] of [['mak','coder'],['lyra','researcher'],['imagen','imagen'],['odexi','codex']]) {
    assert.equal(resolveMeshTarget({target_agent:name,text:'check'},cfg).agentId,id);
  }
  for (const name of ['designer','fast','tec','architect','revie','reviewer']) assert.throws(()=>resolveMeshTarget({target_agent:name,text:'check'},cfg),/unknown_agent/);
});
