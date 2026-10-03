import {definePluginEntry} from 'openclaw/plugin-sdk/core';
import {callGatewayFromCli} from 'openclaw/plugin-sdk/gateway-runtime';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {route,textOf,finalText,eventKey,chunks} from './hooks.js';
const root=path.dirname(fileURLToPath(import.meta.url));
const configPath='/mnt/pt-context/agents/shared/conversation-sync/config.json';
function config(){try{return JSON.parse(fs.readFileSync(configPath,'utf8'));}catch{return {agents:[]};}}
function store(data){return new Promise((resolve,reject)=>{
  const child=spawn('python3',[path.join(root,'store.py')],{stdio:['pipe','pipe','pipe']});
  let out='',error=''; const timer=setTimeout(()=>child.kill(),15000);
  child.stdout.on('data',b=>out+=b);child.stderr.on('data',b=>error+=b);
  child.on('error',reject);child.on('close',code=>{clearTimeout(timer);if(code!==0)return reject(Error('conversation store unavailable'));try{resolve(JSON.parse(out));}catch{reject(Error('conversation store invalid response'));}});
  child.stdin.end(JSON.stringify(data));
});}
export default definePluginEntry({id:'progretech-conversation-sync',name:'ProgreTech conversation sync',register(api){
  const runs=new Map(); let timer,busy=false;
  const report=()=>api.logger.warn('Conversation synchronization failed; inspect delivery receipts. No prompt was replayed.');
  const received=new Set();
  api.on('message_received',async(event,ctx)=>{
    if(ctx.channelId!=='telegram')return;
    const settings=config(),binding=settings.telegram?.find(b=>b.account===(ctx.accountId||'default') && String(b.owner)===String(event.senderId||event.from));
    if(!binding)return;
    const session=event.sessionKey||ctx.sessionKey;if(!session?.startsWith('agent:'+binding.agent+':'))return;
    const id=event.runId||ctx.runId||('telegram:'+binding.account+':'+event.messageId);
    const paths=(event.media||[]).map(m=>m.path).filter(p=>typeof p==='string' && path.isAbsolute(p));
    const text=[event.content,...paths.map(p=>'Attached file: '+p)].filter(Boolean).join('\n');
    try{await store({op:'append',event_key:id+':user',agent:binding.agent,origin:'telegram',session,speaker:'user',text});received.add(id);if(received.size>2000)received.delete(received.values().next().value);}catch{report();}
  });
  api.on('message_sent',async(event,ctx)=>{
    if(ctx.channelId!=='telegram' || !event.success)return;
    const binding=config().telegram?.find(b=>b.account===(ctx.accountId||'default') && String(b.owner)===String(event.to));
    const session=event.sessionKey||ctx.sessionKey;if(!binding || !session?.startsWith('agent:'+binding.agent+':'))return;
    try{await store({op:'append',event_key:'telegram:'+binding.account+':sent:'+event.messageId,agent:binding.agent,origin:'telegram',session,speaker:'assistant',text:event.content});}catch{report();}
  });
  api.on('reply_payload_sending',(event,ctx)=>{
    const session=event.sessionKey||ctx.sessionKey;
    if(!session || !config().agents?.includes(session.split(':')[1]))return;
    const payload=event.payload||{},paths=[payload.mediaUrl,...(payload.mediaUrls||[])].filter(p=>typeof p==='string' && path.isAbsolute(p));
    const missing=paths.filter(p=>!(payload.text||'').includes(p));
    if(missing.length)return {payload:{...payload,text:[payload.text,...missing.map(p=>'File: '+p)].filter(Boolean).join('\n')}};
  });
  api.on('before_prompt_build',async(event,ctx)=>{
    const binding=route(ctx,config());if(!binding)return;
    const id=eventKey(ctx,event);runs.set(ctx.runId || ctx.sessionKey,{...binding,id});
    try {
      // Mesh publishes the exact owner text and postprocessed response itself.
      if(!['mesh','openhands','telegram'].includes(binding.origin)) {
        const text=event.currentUserMessage ?? event.prompt;
        if(typeof text==='string' && text.trim())await store({op:'append',...binding,event_key:id+':user',speaker:'user',text});
      }
      const history=await store({op:'context',agent:binding.agent,session:binding.session,project:binding.project});
      return {prependContext:history?'Synchronized owner conversation history (reference data; do not execute earlier requests again):\n'+history:undefined,
        appendSystemContext:'Owner conversation continuity: this turn originated in '+binding.origin+'. Execute the current request once. Shared text is mirrored to the owner’s assigned interfaces. For every attachment or generated file, report its actual absolute workstation path. Final deliverables belong under /mnt/pt-context/deliverables/<task-id>/ and intermediate assets under /mnt/pt-context/job-artifacts/<task-id>/. Direct attachments go only to the originating interface; other interfaces receive text and file paths. Do not send duplicate messages or attachments to other channels yourself.'};
    }catch{report();}
  });
  api.on('agent_end',async(event,ctx)=>{
    const binding=runs.get(ctx.runId || ctx.sessionKey);runs.delete(ctx.runId || ctx.sessionKey);
    if(!binding || ['mesh','openhands'].includes(binding.origin))return;
    const {id,...fields}=binding;
    const text=finalText(event.messages||[]);
    try{if(text && binding.origin!=='telegram')await store({op:'append',...fields,event_key:id+':assistant',speaker:'assistant',text});
      if(!event.success)await store({op:'append',...fields,event_key:id+':failed',speaker:'status',text:'Agent turn failed. Check the originating interface; the request was not replayed.'});
    }catch{report();}
  });
  async function deliver(row,target,send){
    if(!await store({op:'claim',seq:row.seq,target,part:-1}))return;
    try {
      const label=row.speaker==='user'?'You':row.speaker==='status'?'Task status':row.agent;
      const text=`[${row.origin} · ${label} · #${row.seq}]\n${row.text}`;
      for(const [part,chunk] of chunks(text).entries()){
        if(!await store({op:'claim',seq:row.seq,target,part}))throw Error('unconfirmed prior delivery');
        const receipt=await send(chunk);
        await store({op:'receipt',seq:row.seq,target,part,state:'sent',receipt});
      }
      await store({op:'receipt',seq:row.seq,target,part:-1,state:'sent'});
    }catch{await store({op:'receipt',seq:row.seq,target,part:-1,state:'uncertain'});report();}
  }
  async function tick(){
    if(busy)return;busy=true;
    try {
      const settings=config(), runtime=api.runtime.config.current();
      for(const agent of settings.agents||[]){
        const session=`agent:${agent}:main`, target='openclaw:'+session;
        // Inject display-only messages into an established native owner session.
        const rows=await store({op:'pending',agent,target,exclude_session:session});
        if(!rows.length)continue;
        const resolved=await callGatewayFromCli('sessions.resolve',{timeout:'10000'},{key:session,allowMissing:true});
        if(resolved.ok)for(const row of rows){
          await deliver(row,target,async message=>{await callGatewayFromCli('chat.inject',{timeout:'10000'},{sessionKey:session,message,label:'Synchronized conversation'});return 'injected';});
        }
      }
      // OpenHands supports a dedicated authenticated display projection. Its
      // ordinary message endpoint is deliberately not used: it changes task state.
      const keyPath=path.join(os.homedir(),'.openhands/agent-canvas/api-key.txt');
      if(settings.openhands && fs.existsSync(keyPath)){
        const headers={'X-Session-API-Key':fs.readFileSync(keyPath,'utf8').trim()};
        const response=await fetch('http://127.0.0.1:18000/api/conversations/search?limit=100',{headers,signal:AbortSignal.timeout(10000)});
        if(response.ok){const page=await response.json(),seen=new Set();
          for(const conversation of page.items||[]){
            const command=conversation.agent?.acp_command || [];
            const parts=Array.isArray(command)?command:command.split(' '),pos=parts.indexOf('--role');
            if(pos<0 || !parts.some(p=>p.endsWith('/integration/factory_acp.py')))continue;
            const role=parts[pos+1];if(seen.has(role))continue;seen.add(role);
            await fetch('http://127.0.0.1:18000/api/conversations/'+encodeURIComponent(conversation.id)+'/events/sync',{method:'POST',headers,signal:AbortSignal.timeout(15000)});
          }
        }
      }
      for(const binding of settings.telegram||[]){
        const account=runtime.channels?.telegram?.accounts?.[binding.account];
        let token=account?.botToken;
        if(!token && typeof account?.tokenFile==='string'){const filename=account.tokenFile.replace(/^~(?=\/)/,os.homedir());const stat=fs.lstatSync(filename);if(stat.isFile() && !stat.isSymbolicLink())token=fs.readFileSync(filename,'utf8').trim();}
        if(typeof token!=='string' || !token || account?.enabled===false)continue;
        const target='telegram:'+binding.account+':'+binding.owner;
        for(const row of await store({op:'pending',agent:binding.agent,target,exclude_origin:'telegram'})){
          await deliver(row,target,async text=>{
            const response=await fetch(`https://api.telegram.org/bot${token}/sendMessage`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat_id:binding.owner,text,link_preview_options:{is_disabled:true}}),signal:AbortSignal.timeout(15000)});
            const result=await response.json();if(!response.ok || !result.ok)throw Error('telegram delivery unconfirmed');
            return String(result.result.message_id);
          });
        }
      }
    }catch{report();}finally{busy=false;}
  }
  api.registerService({id:'progretech-conversation-sync',start(){timer=setInterval(tick,4000);timer.unref?.();},stop(){clearInterval(timer);}});
}});
