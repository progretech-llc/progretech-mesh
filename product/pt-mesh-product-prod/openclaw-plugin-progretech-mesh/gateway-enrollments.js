import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const file = root => path.join(root, 'gateway-agent-enrollments.json');
function read(root, gateway) {
  if (!fs.existsSync(file(root))) return {gateway_id: gateway, receipts: {}};
  const data = JSON.parse(fs.readFileSync(file(root), 'utf8'));
  if (data.gateway_id !== gateway || !data.receipts || typeof data.receipts !== 'object' || Array.isArray(data.receipts)) throw Error('gateway_enrollment_cache_binding_mismatch');
  return data;
}
function write(root, data) {
  fs.mkdirSync(root, {recursive: true, mode: 0o700});
  const temporary = file(root) + '.' + crypto.randomUUID();
  try {
    const fd = fs.openSync(temporary, 'wx', 0o600);
    try { fs.writeFileSync(fd, JSON.stringify(data)); fs.fsyncSync(fd); }
    finally { fs.closeSync(fd); }
    fs.renameSync(temporary, file(root));
    const directory = fs.openSync(root, 'r');
    try { fs.fsyncSync(directory); } finally { fs.closeSync(directory); }
  } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
}
export function saveEnrollment(root, gateway, agent, receipt) {
  if (typeof agent !== 'string' || !agent.startsWith(gateway + '--') || !/^[A-Za-z0-9_-]{1,80}$/.test(agent)
      || typeof receipt !== 'string' || !receipt.startsWith('PTMGE1.') || receipt.length > 32768) throw Error('invalid_gateway_enrollment_receipt');
  const data = read(root, gateway);
  if (!Object.hasOwn(data.receipts, agent) && Object.keys(data.receipts).length >= 256) throw Error('gateway_enrollment_cache_full');
  data.receipts[agent] = receipt;
  write(root, data);
}
export function forgetEnrollment(root, gateway, agent) {
  const data = read(root, gateway);
  if (agent === gateway) data.receipts = {};
  else delete data.receipts[agent];
  write(root, data);
}
export function enrollmentReceipts(root, gateway) {
  return Object.values(read(root, gateway).receipts).slice(0, 256);
}
