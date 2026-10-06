import test from "node:test";
import assert from "node:assert/strict";
import { buildQuickPresenceReply, quickPresenceIntent } from "./quick-reply.js";

test("recognizes exact greeting and status questions", () => {
  assert.equal(quickPresenceIntent("Hi Lyra, are you working on anything?"), "status");
  assert.equal(quickPresenceIntent("hello moxy"), "greeting");
  assert.equal(quickPresenceIntent("Please review the current status implementation"), null);
});

test("reports actual concurrent run count without invoking a model", () => {
  assert.match(buildQuickPresenceReply("are you busy?", { agentId: "researcher", activeRuns: 2 }), /2 other active runs/);
  assert.match(buildQuickPresenceReply("status", { agentId: "moxy", activeRuns: 0 }), /don.t have another active run/);
});
