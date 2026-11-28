import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';

let pending = null;
function listening() {
  return new Promise(resolve => {
    const socket = net.createConnection({host:'127.0.0.1',port:8787});
    socket.setTimeout(500);
    socket.once('connect',()=>{socket.destroy();resolve(true);});
    socket.once('error',()=>{socket.destroy();resolve(false);});
    socket.once('timeout',()=>{socket.destroy();resolve(true);});
  });
}
export async function ensurePortableHost() {
  if (pending) return pending;
  pending = (async()=>{
    // Existing listeners belong to their owner; never stop or replace them.
    if (await listening()) return;
    const state = process.env.PROGRETECH_MESH_STATE_DIR?.trim() || path.join(os.homedir(),'.progretech-mesh');
    const filename = path.join(state,'portable-host.json');
    if (!fs.existsSync(filename)) return;
    const config = JSON.parse(fs.readFileSync(filename,'utf8'));
    if (!path.isAbsolute(config.python || '') || !path.isAbsolute(config.root || '') || !fs.existsSync(config.python)) throw Error('mesh_host_installation_invalid');
    const log = fs.openSync(path.join(state,'portable-host.log'),'a',0o600);
    try {
      const child = spawn(config.python,['-m','control_center.portable_host'],{
        cwd:config.root,detached:true,windowsHide:true,stdio:['ignore',log,log],
        env:{...process.env,PATH:[path.dirname(process.execPath),process.env.PATH].filter(Boolean).join(path.delimiter)}
      });
      await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
      child.unref();
    } finally {fs.closeSync(log);}
    for(let i=0;i<30;i++){
      if(await listening())return;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw Error('mesh_host_start_failed');
  })();
  try {await pending;} finally {pending=null;}
}
