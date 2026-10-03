import { registerSpecklet } from './specklet.js';
import { recordInteraction, recordAgentResult } from "./interactions.js";
import { forwardRoleCompletion } from './ide-client.js';
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { createReleaseWatch, closeForRelease, isAuthenticationClose } from "./release-watch.js";
import { saveEnrollment, forgetEnrollment, enrollmentReceipts } from "./gateway-enrollments.js";
import { forwardControlCenter, discoverControlAgents } from "./control-center.js?adapter=0.9.8-chatter-groups.1";

import { definePluginEntry } from "openclaw/plugin-sdk/core";

import { forwardFactoryControl } from "./factory-control.js";
import { resolveMeshTarget, meshConversationBody } from "./routing.js";
import { runGatewayConversation } from "./gateway-client.js";

const PLUGIN_ID = "progretech-mesh";
const ROUTE = "/plugins/progretech-mesh/message";
const MAX_BODY_BYTES = 256 * 1024;
const MAX_EVENT_TEXT = 4000;

const STATE_DIR = process.env.PROGRETECH_MESH_STATE_DIR?.trim()
  || path.join(os.homedir(), ".progretech-mesh");
const PENDING_ENROLLMENT_PATH = path.join(STATE_DIR, "pending-enrollment.json");
const DEVICE_CREDENTIAL_PATH = path.join(STATE_DIR, "device-credential.json");
const CONNECTION_STATUS_PATH = path.join(STATE_DIR, "connection-status.json");
const LIFECYCLE_STATE_PATH = path.join(STATE_DIR, "lifecycle-state.json");
const REVOKED_MARKER_PATH = path.join(STATE_DIR, "revoked.json");
const LOCAL_ACCESS_PATH = path.join(STATE_DIR, "local-access.json");
const FILE_INBOX_DIR = path.join(STATE_DIR, "inbox");
const MAX_MESH_FILE_BYTES = 20 * 1024 * 1024;
const MESH_FILE_CHUNK_BYTES = 64 * 1024;
const inboundMeshTransfers = new Map();
const LOCAL_SIGNAL_PORT = Number.parseInt(process.env.PROGRETECH_MESH_LOCAL_PORT || "18791", 10);

const CONTROL_CENTER_ORIGIN = process.env.PROGRETECH_MESH_CONTROL_CENTER_ORIGIN?.trim()
  || "http://127.0.0.1:8787";
const CONTROL_CENTER_TIMEOUT_MS = Number.parseInt(
  process.env.PROGRETECH_MESH_CONTROL_CENTER_TIMEOUT_MS || "1500",
  10,
);
let capabilityProviderSnapshot = null;



let meshSocket = null;
let meshReconnectTimer = null;
let meshIdentity = null;
let meshReconnectAttempt = 0;
let meshReconnectDisabled = false;
let meshConnectWatchdog = null;

const RECONNECT_BACKOFF_MS = [2000, 5000, 10000, 20000, 30000];
const RECONNECT_CONNECT_TIMEOUT_MS = Number.parseInt(
  process.env.PROGRETECH_MESH_RECONNECT_CONNECT_TIMEOUT_MS || "10000",
  10,
);

let directRtcModule = null;
const directPeers = new Map();
const MAX_DIRECT_MESSAGE_BYTES = 256 * 1024;
let localSignalServer = null;
const localSignalQueues = new Map();


function privateIpv4Addresses() {
  const found = [];
  const nets = os.networkInterfaces();
  for (const entries of Object.values(nets)) {
    for (const item of entries || []) {
      if (item.family !== "IPv4" || item.internal) continue;
      const value = String(item.address || "");
      if (/^10\./.test(value) || /^192\.168\./.test(value) || /^172\.(1[6-9]|2\d|3[01])\./.test(value)) found.push(value);
    }
  }
  return [...new Set(found)];
}

function ensureLocalAccessCredential() {
  const existing = readJsonIfPresent(LOCAL_ACCESS_PATH);
  if (existing?.token && existing?.version === 1) return existing;
  const value = {version:1, token:crypto.randomBytes(32).toString("base64url"), created_at:new Date().toISOString()};
  atomicWriteJson(LOCAL_ACCESS_PATH, value);
  return value;
}

function localRouteMessage() {
  const credential = ensureLocalAccessCredential();
  return {
    type:"mesh_local_route",
    timestamp:new Date().toISOString(),
    agent_id:meshIdentity?.agent_id || null,
    routes:privateIpv4Addresses().map((host)=>({origin:`http://${host}:${LOCAL_SIGNAL_PORT}`,host,port:LOCAL_SIGNAL_PORT,address_space:"local"})),
    local_access_token:credential.token,
    signaling:"local-http-permission-gated",
    data_path:"webrtc-direct",
  };
}

function queueLocalSignal(peerId, signal) {
  const queue=localSignalQueues.get(peerId) || [];
  queue.push(signal);
  if (queue.length > 32) queue.splice(0, queue.length - 32);
  localSignalQueues.set(peerId, queue);
}

function corsLocal(res, origin) {
  if (origin) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Mesh-Local-Token");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Cache-Control", "no-store");
}

async function readLocalJson(req) {
  let total=0; const chunks=[];
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) throw new Error("body_too_large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function probeExistingMeshLocalServer(credential) {
  return new Promise((resolve) => {
    const req=http.request({
      host:"127.0.0.1",
      port:LOCAL_SIGNAL_PORT,
      path:"/mesh-local/status",
      method:"GET",
      headers:{"X-Mesh-Local-Token":credential.token},
      timeout:1500,
    },(res)=>{
      const chunks=[];
      res.on("data",(chunk)=>chunks.push(chunk));
      res.on("end",()=>{
        try {
          const body=JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
          resolve(Boolean(res.statusCode === 200 && body?.ok === true && body?.direct_webrtc === true));
        } catch { resolve(false); }
      });
    });
    req.on("timeout",()=>{ req.destroy(); resolve(false); });
    req.on("error",()=>resolve(false));
    req.end();
  });
}

function startLocalSignalServer(api) {
  if (localSignalServer) return;
  const credential=ensureLocalAccessCredential();
  const candidate=http.createServer((req,res)=>{
    void (async()=>{
      const origin=String(req.headers.origin || "");
      corsLocal(res, origin);
      if (req.method === "OPTIONS") { res.statusCode=204; res.end(); return; }
      if (req.headers["x-mesh-local-token"] !== credential.token) { res.statusCode=401; res.end(JSON.stringify({ok:false,error:"local_auth_required"})); return; }
      const url=new URL(req.url || "/", `http://127.0.0.1:${LOCAL_SIGNAL_PORT}`);
      res.setHeader("content-type","application/json; charset=utf-8");
      if (req.method === "GET" && url.pathname === "/mesh-local/status") {
        res.end(JSON.stringify({ok:true,agent_id:meshIdentity?.agent_id || null,direct_webrtc:true})); return;
      }
      if (req.method === "GET" && url.pathname === "/mesh-local/config") {
        res.end(JSON.stringify({ok:true,ice_servers:[],route_policy:"direct_only",offline_local:true})); return;
      }
      if (req.method === "POST" && url.pathname === "/mesh-local/signal") {
        const body=await readLocalJson(req);
        const signal=body.signal || body;
        const peerId=trimText(signal?.payload?.peer_id || signal?.peer_id || "",120);
        if (!peerId) throw new Error("direct_peer_id_required");
        await handleDirectSignal(api,signal,(outgoing)=>queueLocalSignal(peerId,outgoing));
        res.end(JSON.stringify({ok:true,peer_id:peerId})); return;
      }
      if (req.method === "GET" && url.pathname === "/mesh-local/signals") {
        const peerId=trimText(url.searchParams.get("peer_id") || "",120);
        const queue=localSignalQueues.get(peerId) || [];
        localSignalQueues.set(peerId,[]);
        res.end(JSON.stringify({ok:true,signals:queue})); return;
      }
      res.statusCode=404; res.end(JSON.stringify({ok:false,error:"not_found"}));
    })().catch((error)=>{
      res.statusCode=500; res.setHeader("content-type","application/json; charset=utf-8");
      res.end(JSON.stringify({ok:false,error:trimText(error instanceof Error ? error.message : String(error),500)}));
    });
  });
  candidate.once("error",(error)=>{
    if (error?.code !== "EADDRINUSE") {
      writeLifecycleState({local_signal_state:"error",local_signal_error:trimText(error?.message || String(error),500)});
      return;
    }
    void probeExistingMeshLocalServer(credential).then((owned)=>{
      if (owned) {
        // A previously loaded Mesh adapter already owns the stable local signaling
        // route. Treat it as a compatible handoff target instead of trying to
        // kill/rebind the listener. The newly loaded adapter can still perform
        // activation redemption and outbound Mesh connection independently.
        writeLifecycleState({
          local_signal_state:"reused_existing_mesh_listener",
          local_signal_port:LOCAL_SIGNAL_PORT,
          local_signal_owner_verified:true,
        });
        return;
      }
      writeLifecycleState({
        local_signal_state:"port_conflict",
        local_signal_port:LOCAL_SIGNAL_PORT,
        local_signal_owner_verified:false,
      });
    });
  });
  candidate.once("listening",()=>{
    localSignalServer=candidate;
    writeLifecycleState({
      local_signal_state:"listening",
      local_signal_port:LOCAL_SIGNAL_PORT,
      local_signal_owner_verified:true,
    });
  });
  candidate.listen(LOCAL_SIGNAL_PORT,"0.0.0.0");
}

function stopLocalSignalServer() {
  if (!localSignalServer) return;
  try { localSignalServer.close(); } catch {}
  localSignalServer=null;
  localSignalQueues.clear();
}

function ensurePrivateStateDir() {
  fs.mkdirSync(STATE_DIR, { recursive: true, mode: 0o700 });
}

function atomicWriteJson(target, value) {
  ensurePrivateStateDir();
  const temp = `${target}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temp, target);
  try { fs.chmodSync(target, 0o600); } catch {}
}

function readJsonIfPresent(target) {
  try {
    return JSON.parse(fs.readFileSync(target, "utf8"));
  } catch {
    return null;
  }
}


function identityMaterialPaths(agentId) {
  const configured = process.env.PROGRETECH_MESH_IDENTITY_DIR?.trim();
  const base = configured
    ? path.resolve(configured.replace(/^~(?=\/|$)/, os.homedir()))
    : path.join(os.homedir(), ".config", "progretech", "mesh", "identity");
  const safeAgent = String(agentId || "").trim().replace(/[^A-Za-z0-9._-]/g, "_");
  return {
    evidence: path.join(base, `${safeAgent}_codeseal_evidence.json`),
    privateKey: path.join(base, `${safeAgent}_identity_private.pem`),
    publicKey: path.join(base, `${safeAgent}_identity_public.pem`),
  };
}

function codeSealAssertionRequired(record) {
  const configured = String(
    process.env.PROGRETECH_MESH_REQUIRE_CODESEAL_ASSERTION || ""
  ).trim().toLowerCase();
  if (["0", "false", "no", "off"].includes(configured)) return false;
  if (["1", "true", "yes", "on"].includes(configured)) return true;

  const paths = identityMaterialPaths(record?.agent_id);
  if (fs.existsSync(paths.evidence) || fs.existsSync(paths.privateKey) || fs.existsSync(paths.publicKey)) {
    return true;
  }

  try {
    return new URL(record?.mesh || "").hostname === "mesh.progretech.com";
  } catch {
    return false;
  }
}

async function postMeshJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"content-type":"application/json", "accept":"application/json"},
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({}));
  return {response, body};
}

async function assertCodeSealIdentity(record) {
  if (!codeSealAssertionRequired(record)) return {required:false, verified:false};

  const paths = identityMaterialPaths(record.agent_id);
  for (const [kind, target] of Object.entries(paths)) {
    if (!fs.existsSync(target)) throw new Error(`codeseal_identity_material_missing:${kind}`);
  }

  const evidence = JSON.parse(fs.readFileSync(paths.evidence, "utf8"));
  const privateKey = fs.readFileSync(paths.privateKey);
  const publicKey = fs.readFileSync(paths.publicKey, "utf8");

  const challenge = await postMeshJson(
    `${record.mesh}/api/agents/${encodeURIComponent(record.agent_id)}/identity/challenge`,
    {device_credential:record.device_credential},
  );
  if (!challenge.response.ok || !challenge.body?.ok) {
    throw new Error(`identity_challenge_rejected:${challenge.body?.error || challenge.response.status}`);
  }

  const signingPayload = String(challenge.body.signing_payload || "");
  if (!signingPayload) throw new Error("identity_challenge_payload_missing");

  const signature = crypto.sign(null, Buffer.from(signingPayload, "utf8"), privateKey).toString("base64");
  const assertion = await postMeshJson(
    `${record.mesh}/api/agents/${encodeURIComponent(record.agent_id)}/identity/assert`,
    {
      device_credential:record.device_credential,
      public_key:publicKey,
      codeseal_evidence:evidence,
      challenge_id:challenge.body.challenge_id,
      signature,
    },
  );
  if (!assertion.response.ok || !assertion.body?.ok || assertion.body?.trust_valid !== true) {
    throw new Error(`identity_assertion_rejected:${assertion.body?.error || assertion.response.status}`);
  }

  writeLifecycleState({
    identity_assertion_state:"verified",
    identity_assertion_provider:assertion.body?.provider || "codeseal",
    identity_assertion_proof:assertion.body?.identity_proof || "ed25519-challenge",
    identity_asserted_at:new Date().toISOString(),
  });
  return {required:true, verified:true};
}

function readLifecycleState() {
  return readJsonIfPresent(LIFECYCLE_STATE_PATH) || {};
}

function writeLifecycleState(patch) {
  const prior = readLifecycleState();
  atomicWriteJson(LIFECYCLE_STATE_PATH, {
    ...prior,
    ...patch,
    updated_at: new Date().toISOString(),
  });
}

function markRevoked(reason, record = null) {
  meshReconnectDisabled = true;
  atomicWriteJson(REVOKED_MARKER_PATH, {
    revoked: true,
    reason: reason || "credential_revoked",
    agent_id: record?.agent_id || meshIdentity?.agent_id || null,
    device_id: record?.device_id || meshIdentity?.device_id || null,
    updated_at: new Date().toISOString(),
  });
  writeLifecycleState({
    enrollment_state: "revoked",
    reconnect_enabled: false,
    revocation_reason: reason || "credential_revoked",
  });
}

function clearRevokedMarker() {
  try { fs.unlinkSync(REVOKED_MARKER_PATH); } catch {}
  meshReconnectDisabled = false;
  writeLifecycleState({
    enrollment_state: "enrolled",
    reconnect_enabled: true,
    revocation_reason: null,
  });
}

function writeConnectionStatus(state, detail = "", extra = {}) {
  atomicWriteJson(CONNECTION_STATUS_PATH, {
    state,
    detail,
    updated_at: new Date().toISOString(),
    ...extra,
  });
}

function isPrivateLanHostname(hostname) {
  const host = String(hostname || "").toLowerCase();
  if (host === "localhost" || host === "::1") return true;
  const parts = host.split(".").map((p) => Number.parseInt(p, 10));
  if (parts.length !== 4 || parts.some((p) => !Number.isInteger(p) || p < 0 || p > 255)) return false;
  if (parts[0] === 127 || parts[0] === 10) return true;
  if (parts[0] === 192 && parts[1] === 168) return true;
  if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
  return false;
}

function parseMeshOrigin(value) {
  const url = new URL(String(value || ""));
  if (!["https:", "http:"].includes(url.protocol)) throw new Error("invalid_mesh_origin");
  if (url.protocol === "http:" && !isPrivateLanHostname(url.hostname)) {
    throw new Error("mesh_https_required");
  }
  return url.origin;
}

async function redeemPendingEnrollment() {
  const pending = readJsonIfPresent(PENDING_ENROLLMENT_PATH);
  if (!pending) return null;

  const meshOrigin = parseMeshOrigin(pending.mesh);
  writeConnectionStatus("redeeming", "Redeeming pending Mesh enrollment");

  const response = await fetch(`${meshOrigin}/api/activation/redeem`, {
    method: "POST",
    headers: { "content-type": "application/json", "accept": "application/json" },
    body: JSON.stringify({
      agent_id: pending.agent_id,
      activation_code: pending.activation_code,
      activation_signature: pending.activation_signature,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body?.ok) {
    throw new Error(`mesh_activation_rejected:${body?.error || response.status}`);
  }

  const record = {
    mesh: meshOrigin,
    agent_id: body.agent_id || pending.agent_id,
    websocket_url: body.websocket_url,
    device_credential: body.device_credential,
    device_id: body.device_id,
    device_credential_expires_at: body.device_credential_expires_at,
    reconnect_mode: body.reconnect_mode,
    enrolled_at: new Date().toISOString(),
  };
  atomicWriteJson(DEVICE_CREDENTIAL_PATH, record);
  clearRevokedMarker();
  writeLifecycleState({
    enrollment_state: "enrolled",
    reconnect_enabled: true,
    agent_id: record.agent_id,
    device_id: record.device_id,
    credential_expires_at: record.device_credential_expires_at || null,
    adapter_version: "0.8.1-cc.1",
  });

  try { fs.unlinkSync(PENDING_ENROLLMENT_PATH); } catch {}

  writeConnectionStatus("credential_ready", "Mesh reconnect credential stored", {
    agent_id: record.agent_id,
    device_id: record.device_id,
  });
  return record;
}

function credentialWebSocketUrl(record, initialPairing = false) {
  if (initialPairing && record.websocket_url) return record.websocket_url;
  const origin = new URL(record.mesh);
  const scheme = origin.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(`${scheme}//${origin.host}/ws/gateway/${encodeURIComponent(record.agent_id)}`);
  url.searchParams.set("credential", record.device_credential);
  return url.toString();
}

function sendMeshGatewayMessage(message) {
  if (!meshSocket || meshSocket.readyState !== WebSocket.OPEN) return false;
  try {
    meshSocket.send(JSON.stringify(message));
    return true;
  } catch {
    return false;
  }
}



function safeTransferName(value) {
  const base = path.basename(String(value || "mesh-file")).replace(/[^A-Za-z0-9._ -]/g, "_").slice(0, 180);
  return base || "mesh-file";
}

function uniqueInboxPath(filename) {
  fs.mkdirSync(FILE_INBOX_DIR, {recursive:true, mode:0o700});
  const safe = safeTransferName(filename);
  let target = path.join(FILE_INBOX_DIR, safe);
  if (!fs.existsSync(target)) return target;
  const ext = path.extname(safe);
  const stem = safe.slice(0, Math.max(1, safe.length - ext.length));
  for (let i = 1; i < 1000; i += 1) {
    target = path.join(FILE_INBOX_DIR, `${stem}-${i}${ext}`);
    if (!fs.existsSync(target)) return target;
  }
  return path.join(FILE_INBOX_DIR, `${stem}-${crypto.randomUUID().slice(0,8)}${ext}`);
}

function cancelInboundTransfer(transferId) {
  const state = inboundMeshTransfers.get(transferId);
  inboundMeshTransfers.delete(transferId);
  if (!state) return;
  try { fs.unlinkSync(state.tempPath); } catch {}
}

function handleInboundFileTransfer(msg) {
  const type = String(msg?.type || "");
  const payload = msg?.payload || {};
  const transferId = trimText(payload.transfer_id || "", 160);
  if (!transferId) throw new Error("file_transfer_id_required");

  if (type === "file_transfer_start") {
    const filename = safeTransferName(payload.filename || "mesh-file");
    const size = Number(payload.size || 0);
    if (!Number.isSafeInteger(size) || size <= 0 || size > MAX_MESH_FILE_BYTES) throw new Error("file_transfer_size_invalid");
    fs.mkdirSync(FILE_INBOX_DIR, {recursive:true, mode:0o700});
    const tempPath = path.join(FILE_INBOX_DIR, `.${transferId}.part`);
    fs.writeFileSync(tempPath, Buffer.alloc(0), {mode:0o600});
    inboundMeshTransfers.set(transferId, {
      filename,
      size,
      sha256:String(payload.sha256 || "").toLowerCase(),
      mime:trimText(payload.mime || "application/octet-stream", 160),
      tempPath,
      received:0,
      nextIndex:0,
      hasher:crypto.createHash("sha256"),
    });
    sendCommandAck("file_transfer_start", {transfer_id:transferId, filename});
    return true;
  }

  const state = inboundMeshTransfers.get(transferId);
  if (!state) throw new Error("file_transfer_unknown");

  if (type === "file_transfer_chunk") {
    const index = Number(payload.index || 0);
    if (index !== state.nextIndex) throw new Error("file_transfer_sequence_mismatch");
    const chunk = Buffer.from(String(payload.content_base64 || ""), "base64");
    if (!chunk.length || chunk.length > MESH_FILE_CHUNK_BYTES) throw new Error("file_transfer_chunk_invalid");
    if (state.received + chunk.length > state.size) throw new Error("file_transfer_overflow");
    fs.appendFileSync(state.tempPath, chunk);
    state.hasher.update(chunk);
    state.received += chunk.length;
    state.nextIndex += 1;
    return true;
  }

  if (type === "file_transfer_end") {
    const digest = state.hasher.digest("hex");
    if (state.received !== state.size) { cancelInboundTransfer(transferId); throw new Error("file_transfer_size_mismatch"); }
    if (state.sha256 && digest !== state.sha256) { cancelInboundTransfer(transferId); throw new Error("file_transfer_sha256_mismatch"); }
    const finalPath = uniqueInboxPath(state.filename);
    fs.renameSync(state.tempPath, finalPath);
    inboundMeshTransfers.delete(transferId);
    sendMeshGatewayMessage({
      type:"agent_activity",
      timestamp:new Date().toISOString(),
      message:`Mesh file received: ${state.filename}`,
      payload:{channel:"mesh",direction:"input",state:"completed",event_class:"file_received",filename:state.filename,size:state.size,sha256:digest,saved_to:finalPath},
    });
    sendCommandAck("file_transfer_end", {transfer_id:transferId, filename:state.filename, sha256:digest});
    return true;
  }

  if (type === "file_transfer_cancel") {
    cancelInboundTransfer(transferId);
    return true;
  }
  return false;
}

function offerBufferToMesh(filename, mime, content) {
  const buffer = Buffer.isBuffer(content) ? content : Buffer.from(String(content), "utf8");
  if (!buffer.length || buffer.length > MAX_MESH_FILE_BYTES) throw new Error("file_offer_size_invalid");
  const offerId = crypto.randomUUID();
  const digest = crypto.createHash("sha256").update(buffer).digest("hex");
  const safeName = safeTransferName(filename);
  sendMeshGatewayMessage({type:"file_offer_start",timestamp:new Date().toISOString(),payload:{offer_id:offerId,filename:safeName,mime,size:buffer.length,sha256:digest}});
  let index = 0;
  for (let offset=0; offset < buffer.length; offset += MESH_FILE_CHUNK_BYTES) {
    const chunk = buffer.subarray(offset, Math.min(buffer.length, offset + MESH_FILE_CHUNK_BYTES));
    sendMeshGatewayMessage({type:"file_offer_chunk",timestamp:new Date().toISOString(),payload:{offer_id:offerId,index,content_base64:chunk.toString("base64")}});
    index += 1;
  }
  sendMeshGatewayMessage({type:"file_offer_end",timestamp:new Date().toISOString(),payload:{offer_id:offerId}});
  return {offer_id:offerId, filename:safeName, size:buffer.length, sha256:digest};
}

function sendCommandAck(commandType, correlation = {}) {
  return sendMeshGatewayMessage({
    type: "command_ack",
    timestamp: new Date().toISOString(),
    message: `Mesh command received: ${commandType}`,
    payload: {
      command_type: commandType,
      ...correlation,
    },
  });
}

function readOnlyTerminalSnapshot() {
  return [
    `host=${os.hostname()}`,
    `platform=${os.platform()} ${os.release()}`,
    `node=${process.version}`,
    `adapter=@progretech/openclaw-mesh 0.7.11`,
    "mode=read-only-snapshot",
    "shell=disabled",
  ];
}

async function handleApprovedAction(api, msg) {
  const payload = msg?.payload || {};
  const actionId = trimText(payload.action_id || "", 160);
  const actionType = trimText(payload.action_type || "", 120);
  sendCommandAck("approved_action", { action_id: actionId, action_type: actionType });

  if (actionType === "request_terminal_snapshot") {
    sendMeshGatewayMessage({
      type: "terminal",
      timestamp: new Date().toISOString(),
      message: "Read-only terminal snapshot",
      payload: { action_id: actionId, lines: readOnlyTerminalSnapshot(), severity: "info" },
    });
    sendMeshGatewayMessage({
      type: "action_result",
      timestamp: new Date().toISOString(),
      message: "Terminal snapshot completed",
      payload: { action_id: actionId, status: "completed" },
    });
    return;
  }

  if (actionType === "request_task_snapshot") {
    sendMeshGatewayMessage({
      type: "event",
      timestamp: new Date().toISOString(),
      message: "Task snapshot: OpenClaw gateway connected and Mesh adapter responsive",
      payload: { action_id: actionId, severity: "info", event_class: "task" },
    });
    sendMeshGatewayMessage({
      type: "action_result",
      timestamp: new Date().toISOString(),
      message: "Task snapshot completed",
      payload: { action_id: actionId, status: "completed" },
    });
    return;
  }

  if (actionType === "request_status") {
    await refreshCapabilityProviderSnapshot();
    sendMeshGatewayMessage(heartbeatPayload());
    sendMeshGatewayMessage({
      type: "action_result",
      timestamp: new Date().toISOString(),
      message: "Status request completed",
      payload: { action_id: actionId, status: "completed" },
    });
    return;
  }

  sendMeshGatewayMessage({
    type: "action_result",
    timestamp: new Date().toISOString(),
    message: "Unsupported approved action",
    payload: { action_id: actionId, status: "failed", error: "unsupported_action" },
  });
}

const IDE_GATEWAY_ORIGIN = process.env.PROGRETECH_MESH_IDE_GATEWAY_ORIGIN?.trim()
  || "http://127.0.0.1:8766";
const IDE_GATEWAY_TOKEN_PATH = process.env.PROGRETECH_MESH_IDE_GATEWAY_TOKEN_PATH?.trim()
  || path.join(os.homedir(), ".config", "rend", "ide-gateway-token");
const IDE_GATEWAY_TIMEOUT_MS = Number.parseInt(
  process.env.PROGRETECH_MESH_IDE_GATEWAY_TIMEOUT_MS || "145000",
  10,
);

function readIdeGatewayToken() {
  const value = fs.readFileSync(IDE_GATEWAY_TOKEN_PATH, "utf8").trim();
  if (!value) throw new Error("ide_gateway_token_missing");
  return value;
}

async function forwardIdeChat(api, body) {
  return forwardRoleCompletion(api.runtime.config.current(), body);
}

async function handleGatewayCommand(api, msg) {
  if (msg?.type === "factory_control_request") {
    const requestId = trimText(msg.request_id || "", 160);
    if (!requestId) return true;
    let payload;
    try { payload = await forwardFactoryControl(msg.payload, process.env.PROGRETECH_MESH_LOCAL_TOKEN?.trim() || ensureLocalAccessCredential().token); }
    catch { payload = {ok:false,error:"factory_host_control_failed"}; }
    sendMeshGatewayMessage({type:"factory_control_response",request_id:requestId,payload,timestamp:new Date().toISOString()});
    return true;
  }

  if (["file_transfer_start","file_transfer_chunk","file_transfer_end","file_transfer_cancel"].includes(msg?.type)) {
    try { handleInboundFileTransfer(msg); }
    catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      const transferId = trimText(msg?.payload?.transfer_id || "", 160);
      if (transferId) cancelInboundTransfer(transferId);
      sendMeshGatewayMessage({type:"agent_activity",timestamp:new Date().toISOString(),message:"Mesh file receive failed",payload:{channel:"mesh",direction:"input",state:"error",severity:"error",error:trimText(detail,500),transfer_id:transferId}});
    }
    return true;
  }

  if (msg?.type === "ide_chat_request") {
    const requestId = trimText(msg.request_id || msg?.payload?.request_id || crypto.randomUUID(), 160);
    try {
      const completion = await forwardIdeChat(api, msg?.payload?.openai || {});
      sendMeshGatewayMessage({
        type:"ide_chat_response",
        request_id:requestId,
        timestamp:new Date().toISOString(),
        payload:{request_id:requestId,ok:true,completion},
      });
      appendEvent({
        event_type:"ide_relay",channel:"mesh",state:"completed",direction:null,
        summary:"IDE relay completion returned",
        payload:{request_id:requestId,model:completion?.model || null},
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendMeshGatewayMessage({
        type:"ide_chat_response",
        request_id:requestId,
        timestamp:new Date().toISOString(),
        payload:{request_id:requestId,ok:false,error:trimText(detail,500)},
      });
      appendEvent({
        event_type:"ide_relay",channel:"mesh",state:"error",direction:null,
        summary:"IDE relay request failed",
        payload:{request_id:requestId,error:trimText(detail,500)},
      });
    }
    return true;
  }

  if (msg?.type === "demo_file_offer_request") {
    const status = [
      "ProgreTech Mesh agent file exchange",
      `agent=${meshIdentity?.agent_id || "unknown"}`,
      `adapter=@progretech/openclaw-mesh 0.7.11`,
      `generated_at=${new Date().toISOString()}`,
      "purpose=RC2 file exchange acceptance artifact",
    ].join("\n") + "\n";
    const offered = offerBufferToMesh("mesh-agent-status.txt", "text/plain", status);
    sendCommandAck("demo_file_offer_request", {offer_id:offered.offer_id, filename:offered.filename});
    return true;
  }
  if (msg?.type === "message_request") {
    const requestId = trimText(msg.request_id || crypto.randomUUID(), 160);
    const payload = msg.payload || {};
    sendCommandAck("message_request", { request_id: requestId });
    try {
      const result = await runMeshConversation(api, meshConversationBody(payload, meshIdentity?.agent_id, "mesh-websocket"));
      sendMeshGatewayMessage({
        type: "message_response",
        request_id: requestId,
        timestamp: new Date().toISOString(),
        message: result.text || "",
        payload: {
          request_id: requestId,
          room: payload.room || "direct",
          agent_id: meshIdentity?.agent_id || payload.agent_id || "rend",
          runtime: { adapter: "openclaw-gateway", session_id: result.session_id, session_key: result.session_key, run_id: result.run_id },
        },
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      appendEvent({ event_type: "bridge", channel: "mesh", state: "error", direction: null, summary: "Mesh WebSocket conversation failed", payload: { request_id: requestId, error: trimText(detail, 500) } });
      sendMeshGatewayMessage({
        type: "message_response",
        request_id: requestId,
        timestamp: new Date().toISOString(),
        message: "The agent could not complete the Mesh request through the configured runtime.",
        payload: { request_id: requestId, room: payload.room || "direct", severity: "error", runtime_error: trimText(detail, 500) },
      });
    }
    return true;
  }

  if (msg?.type === "approved_action") {
    await handleApprovedAction(api, msg);
    return true;
  }

  return false;
}

async function fetchLocalJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONTROL_CENTER_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {"accept": "application/json"},
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`http_${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function refreshCapabilityProviderSnapshot() {
  try {
    const [manifest, health] = await Promise.all([
      fetchLocalJson(`${CONTROL_CENTER_ORIGIN}/api/mesh/provider`),
      fetchLocalJson(`${CONTROL_CENTER_ORIGIN}/api/mesh/provider/health`),
    ]);
    capabilityProviderSnapshot = {
      provider_id: manifest.provider_id || "rend-host-control",
      provider_version: manifest.provider_version || null,
      name: manifest.name || "Rend Host Control Provider",
      scope: manifest.scope || "agent-local",
      authority: manifest.authority || {},
      transport: manifest.transport || {},
      capabilities: Array.isArray(manifest.capabilities) ? manifest.capabilities : [],
      health: {
        healthy: Boolean(health.healthy),
        capabilities: Array.isArray(health.capabilities) ? health.capabilities : [],
      },
      reported_at: new Date().toISOString(),
      source: "rend-control-center-local",
    };
  } catch (error) {
    capabilityProviderSnapshot = {
      provider_id: "rend-host-control",
      name: "Rend Host Control Provider",
      scope: "agent-local",
      available: false,
      error: trimText(error instanceof Error ? error.message : String(error), 240),
      reported_at: new Date().toISOString(),
      source: "rend-control-center-local",
    };
  }
  return capabilityProviderSnapshot;
}


function heartbeatPayload() {
  return {
    type: "heartbeat",
    timestamp: new Date().toISOString(),
    payload: {
      state: "online",
      task: "Mesh connected",
      phase: "Passive monitoring active",
      progress: 100,
      model: "OpenClaw agent runtime",
      runtime: "OpenClaw",
      message: `${meshIdentity?.agent_id || "Agent"} connected to Mesh`,
      telemetry: {},
      runtime_adapter: "openclaw-plugin",
      observation_adapter: "openclaw-hooks",
      identity_mode: "enrolled-device",
      capability_provider: capabilityProviderSnapshot,
    },
  };
}

function reconnectDelayMs(attemptNumber) {
  const index = Math.max(0, Math.min(RECONNECT_BACKOFF_MS.length - 1, Number(attemptNumber || 1) - 1));
  return RECONNECT_BACKOFF_MS[index];
}

function clearMeshConnectWatchdog() {
  if (!meshConnectWatchdog) return;
  clearTimeout(meshConnectWatchdog);
  meshConnectWatchdog = null;
}

function scheduleReconnect(api, reason = "connection_closed", explicitDelayMs = null) {
  if (meshReconnectDisabled || meshReconnectTimer) return;

  const nextAttempt = meshReconnectAttempt + 1;
  const delayMs = explicitDelayMs ?? reconnectDelayMs(nextAttempt);
  const nextAttemptAt = new Date(Date.now() + delayMs).toISOString();

  writeConnectionStatus("reconnecting", "Mesh reconnect scheduled", {
    agent_id: meshIdentity?.agent_id || null,
    device_id: meshIdentity?.device_id || null,
    reconnect_attempt: meshReconnectAttempt,
    next_reconnect_attempt: nextAttempt,
    next_reconnect_attempt_at: nextAttemptAt,
    last_reconnect_error: reason,
  });
  writeLifecycleState({
    reconnect_enabled: true,
    reconnect_state: "scheduled",
    reconnect_attempt: meshReconnectAttempt,
    next_reconnect_attempt: nextAttempt,
    next_reconnect_attempt_at: nextAttemptAt,
    last_reconnect_error: reason,
  });

  meshReconnectTimer = setTimeout(async () => {
    meshReconnectTimer = null;
    if (meshReconnectDisabled) return;

    meshReconnectAttempt = nextAttempt;
    const startedAt = new Date().toISOString();
    writeConnectionStatus("reconnecting", "Mesh reconnect attempt started", {
      agent_id: meshIdentity?.agent_id || null,
      device_id: meshIdentity?.device_id || null,
      reconnect_attempt: meshReconnectAttempt,
      last_reconnect_attempt_at: startedAt,
      next_reconnect_attempt_at: null,
      last_reconnect_error: reason,
    });
    writeLifecycleState({
      reconnect_state: "attempting",
      reconnect_attempt: meshReconnectAttempt,
      last_reconnect_attempt_at: startedAt,
      next_reconnect_attempt_at: null,
    });

    try {
      await ensureMeshConnection(api, false);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      if (meshSocket && meshSocket.readyState !== WebSocket.OPEN) meshSocket = null;
      scheduleReconnect(api, `reconnect_exception:${detail}`);
    }
  }, delayMs);
}

async function ensureMeshConnection(api, preferInitialPairing = true) {
  if (meshReconnectDisabled || readJsonIfPresent(REVOKED_MARKER_PATH)?.revoked) {
    writeConnectionStatus("revoked", "Mesh credential revoked; reconnect disabled");
    return;
  }
  if (typeof WebSocket === "undefined") {
    writeConnectionStatus("error", "Node WebSocket API unavailable");
    return;
  }
  if (meshSocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(meshSocket.readyState)) return;

  let record = readJsonIfPresent(DEVICE_CREDENTIAL_PATH);
  let justRedeemed = false;
  if (!record) {
    try {
      record = await redeemPendingEnrollment();
      justRedeemed = Boolean(record);
    } catch (error) {
      writeConnectionStatus("error", error?.message || String(error));
      api.logger?.error?.(`[mesh] enrollment handoff failed: ${error?.message || String(error)}`);
      return;
    }
  }
  if (!record?.agent_id || !record?.device_credential || !record?.mesh) return;

  if (record.device_credential_expires_at) {
    const rawExpiry = record.device_credential_expires_at;
    const expires = typeof rawExpiry === "number" ? rawExpiry * 1000 : Date.parse(rawExpiry);
    if (Number.isFinite(expires) && Date.now() >= expires) {
      writeConnectionStatus("expired", "Mesh reconnect credential expired; re-enrollment required", {
        agent_id: record.agent_id,
        device_id: record.device_id,
      });
      writeLifecycleState({
        enrollment_state: "expired",
        reconnect_enabled: false,
      });
      meshReconnectDisabled = true;
      return;
    }
  }

  meshIdentity = record;

  try {
    const identity = await assertCodeSealIdentity(record);
    if (identity.required) {
      writeConnectionStatus("identity_verified", "CodeSeal identity + Ed25519 proof verified before reconnect", {
        agent_id:record.agent_id,
        device_id:record.device_id,
      });
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    writeConnectionStatus("reconnecting", "Mesh identity assertion failed; reconnect scheduled", {
      agent_id:record.agent_id,
      device_id:record.device_id,
      last_reconnect_error:`identity_assertion:${detail}`,
    });
    scheduleReconnect(api, `identity_assertion:${detail}`);
    return;
  }

  const url = credentialWebSocketUrl(record, preferInitialPairing && justRedeemed);

  writeConnectionStatus("connecting", "Connecting outbound to Mesh", {
    agent_id: record.agent_id,
    device_id: record.device_id,
    reconnect_attempt: meshReconnectAttempt,
    last_reconnect_attempt_at: meshReconnectAttempt > 0 ? new Date().toISOString() : null,
  });

  let socket;
  try {
    socket = new WebSocket(url);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    meshSocket = null;
    writeConnectionStatus("reconnecting", "Mesh WebSocket creation failed; reconnect scheduled", {
      agent_id: record.agent_id,
      device_id: record.device_id,
      reconnect_attempt: meshReconnectAttempt,
      last_reconnect_error: `websocket_construct:${detail}`,
    });
    scheduleReconnect(api, `websocket_construct:${detail}`);
    return;
  }

  meshSocket = socket;
  let opened = false;
  let retryQueued = false;

  const queueRetry = (reason) => {
    if (retryQueued || meshReconnectDisabled) return;
    retryQueued = true;
    clearMeshConnectWatchdog();
    if (meshSocket === socket) meshSocket = null;
    writeConnectionStatus("reconnecting", "Mesh connection unavailable; reconnect scheduled", {
      agent_id: record.agent_id,
      device_id: record.device_id,
      reconnect_attempt: meshReconnectAttempt,
      last_reconnect_error: reason,
    });
    scheduleReconnect(api, reason);
  };

  clearMeshConnectWatchdog();
  meshConnectWatchdog = setTimeout(() => {
    if (opened || socket.readyState === WebSocket.OPEN) return;
    try { socket.close(); } catch {}
    queueRetry("connect_timeout");
  }, RECONNECT_CONNECT_TIMEOUT_MS);

  let rosterTimer=null, rosterBusy=false;
  const syncRoster=async()=>{
    if(rosterBusy || meshSocket!==socket || socket.readyState!==WebSocket.OPEN)return;
    rosterBusy=true;
    try{const agents=await discoverControlAgents(record.agent_id,ensureLocalAccessCredential().token);
      if(meshSocket===socket && socket.readyState===WebSocket.OPEN && Array.isArray(agents))sendMeshGatewayMessage({type:'control_center_roster',payload:{agents,enrollment_restore_version:1,enrollment_receipts:enrollmentReceipts(STATE_DIR,record.agent_id)}});
    }catch{}finally{rosterBusy=false;}
  };
  let activeMeshRequests=0;
  const releaseWatch=createReleaseWatch({mesh:record.mesh,
    idle:()=>meshSocket===socket && socket.readyState===WebSocket.OPEN && activeMeshRequests===0,
    reconnect:()=>closeForRelease(socket)});
  socket.addEventListener("open", () => {
    releaseWatch.start();
    opened = true;
    retryQueued = false;
    clearMeshConnectWatchdog();
    meshReconnectAttempt = 0;
    writeConnectionStatus("connected", "Passive monitoring connected", {
      agent_id: record.agent_id,
      device_id: record.device_id,
      reconnect_attempt: 0,
      last_reconnect_error: null,
      next_reconnect_attempt_at: null,
    });
    writeLifecycleState({
      reconnect_enabled: true,
      reconnect_state: "connected",
      reconnect_attempt: 0,
      last_reconnect_error: null,
      next_reconnect_attempt_at: null,
    });
    void refreshCapabilityProviderSnapshot().finally(() => {
      sendMeshGatewayMessage(heartbeatPayload());
    });
    sendMeshGatewayMessage(localRouteMessage());
    void syncRoster();
    rosterTimer=setInterval(()=>void syncRoster(),10000);
    appendEvent({
      event_type: "gateway",
      channel: "mesh",
      state: "connected",
      direction: null,
      summary: "Mesh passive monitoring connected",
      payload: { device_id: record.device_id },
    });
  });

  socket.addEventListener("message", (event) => {
    void (async () => {
      activeMeshRequests++;
      try {
        const msg = JSON.parse(typeof event.data === "string" ? event.data : String(event.data));
        if(msg?.type === "paired")releaseWatch.paired(msg.build_id);
        if (msg?.type === "control_center_request") {
          if (msg.payload?.action === 'identity.enrollment.save') {
            try {
              saveEnrollment(STATE_DIR, record.agent_id, msg.payload.agent_id, msg.payload.args?.receipt);
              sendMeshGatewayMessage({type:'control_center_response', request_id:msg.request_id, payload:{ok:true,result:{stored:true}}});
            } catch { sendMeshGatewayMessage({type:'control_center_response', request_id:msg.request_id, payload:{ok:false,error:'gateway_enrollment_cache_failed'}}); }
            return;
          }
          let payload;
          try {
            payload = await forwardControlCenter(msg.payload, record.agent_id, ensureLocalAccessCredential().token);
          } catch (error) {
            payload = {ok: false, error: error instanceof Error ? error.message : String(error)};
          }
          sendMeshGatewayMessage({type: "control_center_response", request_id: msg.request_id, payload});
          if (payload.ok && msg.payload?.action === 'enrollment.remove') {
            forgetEnrollment(STATE_DIR, record.agent_id, msg.payload.agent_id);
            if (msg.payload?.agent_id === record.agent_id) {
              markRevoked('owner_removed_from_mesh', record);
            }
            const agents = await discoverControlAgents(record.agent_id, ensureLocalAccessCredential().token);
            if (Array.isArray(agents)) sendMeshGatewayMessage({type:'control_center_roster',payload:{agents, enrollment_restore_version: 1, enrollment_receipts: enrollmentReceipts(STATE_DIR, record.agent_id)}});
          }
          return;
        }
        if (await handleGatewayCommand(api, msg)) return;
        if (msg?.type === "heartbeat_request") {
          sendCommandAck("heartbeat_request", {});
          await refreshCapabilityProviderSnapshot();
          sendMeshGatewayMessage(heartbeatPayload());
          try {
            const agents = await discoverControlAgents(record.agent_id, ensureLocalAccessCredential().token);
            if (Array.isArray(agents)) sendMeshGatewayMessage({type: "control_center_roster", payload: {agents, enrollment_restore_version: 1, enrollment_receipts: enrollmentReceipts(STATE_DIR, record.agent_id)}});
          } catch {}
          return;
        }
        if (msg?.type === "mesh_direct_signal") {
          await handleDirectSignal(api,msg.signal).catch((error)=>{
            const detail=error instanceof Error ? error.message : String(error);
            directSignal({type:"direct_error",payload:{peer_id:msg?.signal?.payload?.peer_id || null,error:trimText(detail,500)}});
          });
          return;
        }
        if (msg?.type === "credential_revoked" || msg?.type === "device_revoked") {
          markRevoked(msg?.reason || "server_revoked", record);
          writeConnectionStatus("revoked", "Mesh credential revoked; reconnect disabled", {
            agent_id: record.agent_id,
            device_id: record.device_id,
          });
          try { socket.close(4003, "revoked"); } catch {}
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        appendEvent({ event_type: "gateway_command", channel: "mesh", state: "error", direction: "input", summary: "Mesh gateway command handling failed", payload: { error: trimText(detail, 500) } });
      } finally {activeMeshRequests--;}
    })();
  });

  socket.addEventListener("close", (event) => {
    releaseWatch.stop();
    clearInterval(rosterTimer);
    clearMeshConnectWatchdog();
    if (meshSocket === socket) meshSocket = null;

    if (isAuthenticationClose(event?.code)) {
      markRevoked(`gateway_auth_${event.code}`, record);
      writeConnectionStatus("revoked", "Mesh authentication rejected; re-enrollment required", {
        agent_id: record.agent_id,
        device_id: record.device_id,
      });
      return;
    }

    const reasonText = event?.reason ? String(event.reason) : "";
    queueRetry(`websocket_close:${event?.code || 0}${reasonText ? `:${reasonText}` : ""}`);
  });

  socket.addEventListener("error", () => {
    // Some WebSocket implementations do not reliably emit close after a failed connect.
    // Queue a bounded retry immediately; the close handler is idempotent via retryQueued.
    if (!opened) {
      try { socket.close(); } catch {}
      queueRetry("websocket_error_before_open");
    }
  });
}

function eventPath() {
  const configured = process.env.PROGRETECH_MESH_EVENT_PATH?.trim();
  if (configured) return configured;

  const runtimeDir = process.env.XDG_RUNTIME_DIR?.trim();
  const base = runtimeDir && path.isAbsolute(runtimeDir)
    ? path.join(runtimeDir, "progretech-mesh")
    : path.join(os.tmpdir(), `progretech-mesh-${process.getuid?.() ?? "user"}`);
  return path.join(base, "openclaw-activity.jsonl");
}

function trimText(value, limit = MAX_EVENT_TEXT) {
  const text = typeof value === "string" ? value : value == null ? "" : String(value);
  return text.length <= limit ? text : `${text.slice(0, limit)}…`;
}

function safeValue(value, depth = 0) {
  if (depth > 3) return "[depth-limited]";
  if (value == null || typeof value === "boolean" || typeof value === "number") return value;
  if (typeof value === "string") return trimText(value, 1000);
  if (Array.isArray(value)) return value.slice(0, 16).map((item) => safeValue(item, depth + 1));
  if (typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value).slice(0, 32)) {
      if (/token|secret|password|credential|authorization|cookie/i.test(key)) {
        out[key] = "<redacted>";
      } else {
        out[key] = safeValue(item, depth + 1);
      }
    }
    return out;
  }
  return trimText(String(value), 500);
}

function appendEvent(event) {
  const target = eventPath();
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o700 });
  const row = {
    timestamp: new Date().toISOString(),
    observer: "openclaw-plugin",
    read_only: true,
    ...event,
  };
  fs.appendFileSync(target, `${JSON.stringify(row)}\n`, { encoding: "utf8", mode: 0o600 });

  if (meshSocket && meshSocket.readyState === WebSocket.OPEN) {
    try {
      meshSocket.send(JSON.stringify({
        type: "agent_activity",
        timestamp: row.timestamp,
        message: row.summary || row.event_type || "Agent activity",
        payload: {
          channel: row.channel || "system",
          direction: row.direction ?? null,
          state: row.state || "active",
          summary: row.summary || "",
          event_type: row.event_type,
          read_only: true,
          observer: row.observer,
          ...safeValue(row.payload || {}),
        },
      }));
    } catch {}
  }
}

function channelFromContext(ctx, fallback = "system") {
  return trimText(ctx?.channelId || ctx?.channel || fallback, 80).toLowerCase();
}

function sessionLooksMesh(ctx) {
  const key = String(ctx?.sessionKey || "");
  return key.includes(":mesh:") || key.startsWith("mesh:");
}

async function readJsonBody(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buf.length;
    if (size > MAX_BODY_BYTES) throw new Error("request_too_large");
    chunks.push(buf);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function isLoopback(req) {
  const address = req?.socket?.remoteAddress || "";
  return address === "127.0.0.1" || address === "::1" || address === "::ffff:127.0.0.1";
}

function localTokenOk(req) {
  const expected = process.env.PROGRETECH_MESH_LOCAL_TOKEN?.trim() || ensureLocalAccessCredential().token;
  if (!expected) return false;
  const actual = String(req.headers?.["x-progretech-mesh-local-token"] || "");
  if (!actual || actual.length !== expected.length) return false;
  try {
    return crypto.timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
  } catch {
    return false;
  }
}

function extractResultText(result) {
  const visible = result?.meta?.finalAssistantVisibleText;
  if (typeof visible === "string" && visible.trim()) return visible.trim();
  const raw = result?.meta?.finalAssistantRawText;
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (Array.isArray(result?.payloads)) {
    const text = result.payloads
      .map((payload) => (typeof payload?.text === "string" ? payload.text : ""))
      .filter(Boolean)
      .join("\n")
      .trim();
    if (text) return text;
  }
  return "";
}

function stableConversationId({ agentId, room, sender }) {
  const digest = crypto
    .createHash("sha256")
    .update(`${agentId}\u0000${room}\u0000${sender}`)
    .digest("hex")
    .slice(0, 24);
  return `mesh-${agentId}-${digest}`;
}

function extractOwnershipClaim(value) {
  const text = String(value || "");
  const match = text.match(/\bPTMOWN1:([A-Za-z0-9_-]{20,200})\b/);
  return match ? match[1] : null;
}

async function redeemOwnershipClaim(api, claimCode) {
  const record = readJsonIfPresent(DEVICE_CREDENTIAL_PATH);
  if (!record?.mesh || !record?.agent_id || !record?.device_credential) {
    throw new Error("ownership_migration_credential_missing");
  }

  writeLifecycleState({
    ownership_state:"redeeming",
    ownership_claim_received_at:new Date().toISOString(),
  });

  const response = await fetch(`${record.mesh}/api/ownership/redeem`, {
    method:"POST",
    headers:{"content-type":"application/json","accept":"application/json"},
    body:JSON.stringify({
      agent_id:record.agent_id,
      device_credential:record.device_credential,
      claim_code:claimCode,
    }),
  });
  const body = await response.json().catch(()=>({}));
  if (!response.ok || !body?.ok) {
    throw new Error(`ownership_redeem_rejected:${body?.error || response.status}`);
  }

  const rotated = {
    ...record,
    device_credential:body.device_credential,
    device_id:body.device_id,
    device_credential_expires_at:body.device_credential_expires_at,
    reconnect_mode:body.reconnect_mode || "signed-device-credential",
    owner_bound:true,
    owner_bound_at:new Date().toISOString(),
  };
  atomicWriteJson(DEVICE_CREDENTIAL_PATH, rotated);
  meshIdentity = rotated;
  clearRevokedMarker();
  writeLifecycleState({
    ownership_state:"bound",
    ownership_bound:true,
    device_id:rotated.device_id,
    credential_expires_at:rotated.device_credential_expires_at || null,
    adapter_version:"0.7.11",
  });
  writeConnectionStatus("ownership_bound","Mesh ownership bound; reconnecting with rotated credential",{
    agent_id:rotated.agent_id,
    device_id:rotated.device_id,
  });

  if (meshSocket) {
    try { meshSocket.close(); } catch {}
    meshSocket = null;
  }
  meshReconnectAttempt = 0;
  scheduleReconnect(api,"ownership_credential_rotated",250);
  return true;
}

function registerObservationHooks(api) {
  api.on("message_received", (event, ctx) => {
    const ownershipClaim = extractOwnershipClaim(event?.content || event?.text || "");
    if (ownershipClaim) {
      void redeemOwnershipClaim(api, ownershipClaim).catch((error) => {
        const detail = error instanceof Error ? error.message : String(error);
        writeLifecycleState({
          ownership_state:"error",
          ownership_error:trimText(detail,500),
        });
        appendEvent({
          event_type:"identity",
          channel:channelFromContext(ctx,event?.channel || "unknown"),
          state:"error",
          direction:"input",
          summary:"Mesh ownership claim failed",
          payload:{error:trimText(detail,500)},
        });
      });
    }
    appendEvent({
      event_type: "message",
      channel: channelFromContext(ctx, event?.channel || "unknown"),
      state: "received",
      direction: "input",
      summary: trimText(event?.content || "Incoming message"),
      payload: {
        session_key: ctx?.sessionKey,
        run_id: ctx?.runId,
        message_id: event?.messageId || ctx?.messageId,
        sender_id: event?.senderId || ctx?.senderId,
      },
    });
  });

  api.on("message_sent", (event, ctx) => {
    appendEvent({
      event_type: "message",
      channel: sessionLooksMesh(ctx) ? "mesh" : channelFromContext(ctx, "unknown"),
      state: "sent",
      direction: "output",
      summary: trimText(event?.content || event?.text || "Outgoing message"),
      payload: {
        session_key: ctx?.sessionKey,
        message_id: event?.messageId || ctx?.messageId,
      },
    });
  });

  api.on("model_call_started", (event, ctx) => {
    appendEvent({
      event_type: "model",
      channel: sessionLooksMesh(ctx) ? "mesh" : channelFromContext(ctx, "system"),
      state: "processing",
      direction: null,
      summary: "Model call started",
      payload: {
        session_key: ctx?.sessionKey,
        run_id: ctx?.runId,
        provider: event?.provider,
        model: event?.model || event?.modelId,
      },
    });
  });

  api.on("model_call_ended", (event, ctx) => {
    appendEvent({
      event_type: "model",
      channel: sessionLooksMesh(ctx) ? "mesh" : channelFromContext(ctx, "system"),
      state: "processing",
      direction: null,
      summary: "Model call completed",
      payload: {
        session_key: ctx?.sessionKey,
        run_id: ctx?.runId,
      },
    });
  });

  api.on("after_tool_call", (event, ctx) => {
    try { recordInteraction(STATE_DIR,event,ctx); } catch {}
    appendEvent({
      event_type: "tool",
      channel: sessionLooksMesh(ctx) ? "mesh" : channelFromContext(ctx, "system"),
      state: "processing",
      direction: null,
      summary: `Tool completed: ${trimText(event?.toolName || "tool", 120)}`,
      payload: {
        session_key: ctx?.sessionKey,
        run_id: ctx?.runId,
        tool_name: event?.toolName,
        // Deliberately do not mirror tool result bodies.
        error: event?.error ? trimText(event.error, 500) : undefined,
      },
    });
  });

  api.on("agent_end", (event, ctx) => {
    try { recordAgentResult(STATE_DIR,event,ctx); } catch {}
    appendEvent({
      event_type: "agent",
      channel: sessionLooksMesh(ctx) ? "mesh" : channelFromContext(ctx, "system"),
      state: event?.error ? "error" : "idle",
      direction: null,
      summary: event?.error ? "Agent turn ended with an error" : "Agent turn completed",
      payload: {
        session_key: ctx?.sessionKey,
        run_id: ctx?.runId,
        error: event?.error ? trimText(event.error, 500) : undefined,
      },
    });
  });
}

async function runMeshConversation(api, body) {
  const cfg = api.runtime.config.current();
  const { agentId, text } = resolveMeshTarget(body, cfg, meshIdentity?.agent_id || "rend");
  const room = trimText(body?.room || "direct", 120);
  const sender = trimText(body?.sender || "Mesh user", 200);
  if (!text.trim()) throw new Error("empty_message");
  const sessionId = stableConversationId({ agentId, room, sender });
  const sessionKey = `agent:${agentId}:mesh:${sessionId}`;
  const runId = crypto.randomUUID();
  appendEvent({event_type:"message",channel:"mesh",state:"received",direction:"input",summary:text,payload:{session_key:sessionKey,run_id:runId,transport:body?.transport || "mesh"}});
  const syncPath=path.join(os.homedir(),'.openclaw/extensions/progretech-conversation-sync/client.js');
  const sync=fs.existsSync(syncPath)?await import(syncPath):null;
  const common={agent:agentId,origin:'mesh',session:sessionKey};
  if(sync)await sync.publish({...common,event_key:'mesh-direct:'+runId+':user',speaker:'user',text});
  const result = await runGatewayConversation(cfg, {agentId, sessionKey, text});
  const responseText = extractResultText(result);
  if(sync)await sync.publish({...common,event_key:'mesh-direct:'+runId+':assistant',speaker:'assistant',text:responseText});
  appendEvent({event_type:"message",channel:"mesh",state:"sent",direction:"output",summary:responseText || "Mesh agent turn completed",payload:{session_key:sessionKey,run_id:runId,transport:body?.transport || "mesh"}});
  return {ok:true,text:responseText,session_id:sessionId,session_key:sessionKey,run_id:runId};
}

async function loadDirectRtc() {
  if (directRtcModule) return directRtcModule;
  const mod = await import("node-datachannel");
  const runtime = mod?.default || mod;
  if (!runtime?.PeerConnection) throw new Error("webrtc_runtime_unavailable");
  directRtcModule = runtime;
  try { runtime.initLogger?.("Warning"); } catch {}
  return runtime;
}

function directSignal(signal) {
  return sendMeshGatewayMessage({type:"mesh_direct_signal",timestamp:new Date().toISOString(),signal});
}

function closeDirectPeer(peerId, reason="closed") {
  const state=directPeers.get(peerId);
  if (!state) return;
  directPeers.delete(peerId);
  try { state.channel?.close?.(); } catch {}
  try { state.peer?.close?.(); } catch {}
  appendEvent({event_type:"direct_transport",channel:"mesh",state:"closed",direction:null,summary:"Direct Mesh peer closed",payload:{peer_id:peerId,reason}});
}

function configureDirectDataChannel(api, peerId, channel) {
  const state=directPeers.get(peerId); if (state) state.channel=channel;
  channel.onOpen(() => {
    appendEvent({event_type:"direct_transport",channel:"mesh",state:"connected",direction:null,summary:"Direct owner-to-agent data channel connected",payload:{peer_id:peerId,path:"direct",cloud_data_path:false,route_policy:state?.routePolicy || "direct_preferred"}});
    try { channel.sendMessage(JSON.stringify({type:"hello_ack",peer_id:peerId,agent_id:meshIdentity?.agent_id || null,path:"direct",cloud_data_path:false})); } catch {}
  });
  channel.onMessage((raw) => { void (async () => {
    try {
      const text=Buffer.isBuffer(raw) ? raw.toString("utf8") : String(raw);
      if (Buffer.byteLength(text,"utf8") > MAX_DIRECT_MESSAGE_BYTES) throw new Error("direct_message_too_large");
      const message=JSON.parse(text);
      if (message?.type === "ping") { channel.sendMessage(JSON.stringify({type:"pong",id:message.id || null,timestamp:new Date().toISOString(),agent_id:meshIdentity?.agent_id || null})); return; }
      if (message?.type === "heartbeat_request") { channel.sendMessage(JSON.stringify(heartbeatPayload())); return; }
      if (message?.type === "message") {
        const requestId=trimText(message.request_id || crypto.randomUUID(),120);
        const result=await runMeshConversation(api,meshConversationBody(message,meshIdentity?.agent_id,"webrtc-direct"));
        channel.sendMessage(JSON.stringify({type:"message_response",request_id:requestId,timestamp:new Date().toISOString(),...result})); return;
      }
      if (message?.type === "hello") channel.sendMessage(JSON.stringify({type:"hello_ack",peer_id:peerId,agent_id:meshIdentity?.agent_id || null,path:"direct",cloud_data_path:false}));
    } catch (error) {
      const detail=error instanceof Error ? error.message : String(error);
      try { channel.sendMessage(JSON.stringify({type:"direct_error",error:trimText(detail,500)})); } catch {}
    }
  })(); });
  channel.onClosed(() => closeDirectPeer(peerId,"data_channel_closed"));
  channel.onError((error) => appendEvent({event_type:"direct_transport",channel:"mesh",state:"error",direction:null,summary:"Direct data channel error",payload:{peer_id:peerId,error:trimText(error,500)}}));
}

async function handleDirectSignal(api, signal, signalSink=directSignal) {
  const peerId=trimText(signal?.payload?.peer_id || signal?.peer_id || "",120);
  const signalType=trimText(signal?.type || "",40);
  const payload=signal?.payload || {};
  if (!peerId) throw new Error("direct_peer_id_required");
  if (signalType === "offer") {
    closeDirectPeer(peerId,"renegotiation");
    const rtc=await loadDirectRtc();
    const routePolicy = ["direct_preferred","direct_only","relay_allowed"].includes(String(payload.route_policy))
      ? String(payload.route_policy)
      : "direct_preferred";
    const providedIceServers = Array.isArray(payload.ice_servers) ? payload.ice_servers : [];
    const iceServers = routePolicy === "direct_only"
      ? providedIceServers.filter((entry) => {
          const urls = Array.isArray(entry?.urls) ? entry.urls : [entry?.urls];
          return !urls.some((url) => String(url || "").startsWith("turn:") || String(url || "").startsWith("turns:"));
        })
      : providedIceServers;
    const peer=new rtc.PeerConnection(`mesh-${peerId}`,{iceServers});
    directPeers.set(peerId,{peer,channel:null,created_at:Date.now(),routePolicy});
    peer.onLocalDescription((sdp,type)=>signalSink({type:"answer",payload:{peer_id:peerId,sdp,description_type:String(type || "answer").toLowerCase()}}));
    peer.onLocalCandidate((candidate,mid)=>signalSink({type:"ice_candidate",payload:{peer_id:peerId,candidate,mid:mid || "0"}}));
    peer.onStateChange((stateName)=>{ signalSink({type:"peer_state",payload:{peer_id:peerId,state:String(stateName)}}); if (["closed","failed","disconnected"].includes(String(stateName).toLowerCase())) closeDirectPeer(peerId,`peer_${String(stateName).toLowerCase()}`); });
    peer.onDataChannel((channel)=>configureDirectDataChannel(api,peerId,channel));
    peer.setRemoteDescription(String(payload.sdp || ""),"Offer");
    return;
  }
  const state=directPeers.get(peerId); if (!state?.peer) throw new Error("direct_peer_not_found");
  if (signalType === "ice_candidate") { state.peer.addRemoteCandidate(String(payload.candidate || ""),String(payload.mid || "0")); return; }
  if (signalType === "close") closeDirectPeer(peerId,"remote_close");
}

function registerConversationBridge(api) {
  api.registerHttpRoute({
    path: ROUTE,
    auth: "plugin",
    handler: async (req, res) => {
      try {
        if (!isLoopback(req)) {
          res.statusCode = 403;
          res.end("loopback_only");
          return true;
        }
        if (!localTokenOk(req)) {
          res.statusCode = 401;
          res.end("unauthorized");
          return true;
        }
        if (String(req.method || "POST").toUpperCase() !== "POST") {
          res.statusCode = 405;
          res.end("method_not_allowed");
          return true;
        }

        const body = await readJsonBody(req);
        const result = await runMeshConversation(api, {...body, transport:"loopback-http"});
        res.statusCode = 200;
        res.setHeader("content-type", "application/json; charset=utf-8");
        res.end(JSON.stringify(result));
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        appendEvent({
          event_type: "bridge",
          channel: "mesh",
          state: "error",
          direction: null,
          summary: "Mesh conversation bridge error",
          payload: { error: trimText(message, 500) },
        });
        res.statusCode = 500;
        res.setHeader("content-type", "application/json; charset=utf-8");
        res.end(JSON.stringify({ ok: false, error: message }));
        return true;
      }
    },
  });
}

export default definePluginEntry({
  id: PLUGIN_ID,
  name: "ProgreTech Mesh",
  description: "Direct-first Mesh transport with offline same-LAN reconnect support.",
  register(api) {
    registerSpecklet(api, () => process.env.PROGRETECH_MESH_LOCAL_TOKEN?.trim() || ensureLocalAccessCredential().token);
    registerObservationHooks(api);
    registerConversationBridge(api);
    startLocalSignalServer(api);
    writeLifecycleState({
      adapter_version: "0.8.1-cc.1",
      runtime: "openclaw",
      observation_mode: "read-only",
      conversation_scope: "mesh-independent",
    });

    queueMicrotask(() => {
      void refreshCapabilityProviderSnapshot().finally(() => {
        void ensureMeshConnection(api, true);
      });
    });

    api.on("gateway_start", () => {
      startLocalSignalServer(api);
      void ensureMeshConnection(api, false);
    });

    api.on("gateway_stop", () => {
      if (meshReconnectTimer) {
        clearTimeout(meshReconnectTimer);
        meshReconnectTimer = null;
      }
      clearMeshConnectWatchdog();
      if (meshSocket) {
        try { meshSocket.close(); } catch {}
        meshSocket = null;
      }
      for (const peerId of [...directPeers.keys()]) closeDirectPeer(peerId,"gateway_stop");
      stopLocalSignalServer();
    });
  },
});
