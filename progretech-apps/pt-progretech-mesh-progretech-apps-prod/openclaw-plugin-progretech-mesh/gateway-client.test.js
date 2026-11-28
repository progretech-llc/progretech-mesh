import assert from "node:assert/strict";
import test from "node:test";
import {runGatewayConversation} from "./gateway-client.js";
const cfg = {gateway:{port:18789,auth:{mode:"token",token:"test-only"}},agents:{defaults:{}}};
const turn = {agentId:"coder",sessionKey:"agent:coder:mesh:test",text:"inspect"};
test("uses loopback, mapped agent, isolated session and bearer auth", async () => {
  const result = await runGatewayConversation(cfg, turn, async (url, options) => {
    assert.equal(url,"http://127.0.0.1:18789/v1/chat/completions");
    assert.equal(options.headers.Authorization,"Bearer test-only");
    assert.equal(options.headers["x-openclaw-session-key"],turn.sessionKey);
    assert.equal(JSON.parse(options.body).model,"openclaw/coder");
    assert.equal(options.redirect,"error");
    return {ok:true,json:async()=>({choices:[{message:{content:"Mak"}}]})};
  });
  assert.equal(result.payloads[0].text,"Mak");
});
test("rejects unsafe auth config before making a request", async () => {
  await assert.rejects(runGatewayConversation({gateway:{auth:{mode:"none"}}},turn,()=>assert.fail()), /token_auth_required/);
});
test("upstream failure is not reported as completion or echoed", async () => {
  await assert.rejects(runGatewayConversation(cfg,turn,async()=>({ok:false,status:503})), /^Error: mesh_gateway_http_503$/);
  await assert.rejects(runGatewayConversation(cfg,turn,async()=>({ok:true,json:async()=>({})})), /empty_response/);
});
