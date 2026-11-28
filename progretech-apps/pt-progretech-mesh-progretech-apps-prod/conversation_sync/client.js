import {spawn} from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
export function publish(data){return new Promise((resolve,reject)=>{
 const child=spawn('python3',[path.join(os.homedir(),'.openclaw/extensions/progretech-conversation-sync/store.py')],{stdio:['pipe','pipe','pipe']});let out='';
 const timer=setTimeout(()=>child.kill(),15000);child.stdout.on('data',b=>out+=b);child.stderr.resume();child.on('error',reject);child.on('close',code=>{clearTimeout(timer);if(code!==0)return reject(Error('conversation_sync_unavailable'));try{resolve(JSON.parse(out));}catch{reject(Error('conversation_sync_invalid'));}});child.stdin.end(JSON.stringify({op:'append',...data}));
});}
