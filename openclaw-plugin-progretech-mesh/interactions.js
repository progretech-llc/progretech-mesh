import {readFileSync,writeFileSync,renameSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
const roles={main:'rend',researcher:'lyra',coder:'mak',progre:'progre',imagen:'imagen',codex:'codex',moxy:'moxy'};
export function recordInteraction(root,event,ctx) {
  if(event?.toolName!=='sessions_send' || event.error || event.result?.isError || ['error','forbidden','timeout'].includes(event.result?.status))return;
  const from=roles[ctx?.agentId || String(ctx?.sessionKey||'').split(':')[1]];
  const to=roles[String(event.params?.sessionKey||'').split(':')[1]];
  if(!from || !to || from===to)return;
  const file=join(root,'agent-interactions.json');let rows=[];
  try{rows=JSON.parse(readFileSync(file,'utf8'));}catch{}
  if(!Array.isArray(rows))rows=[];
  const at=Date.now()/1000;
  rows.push({id:'native-'+Date.now()+'-'+from+'-'+to,kind:'instruction',from,to,at,title:'Agent instruction / handoff attempt',task_id:null,parts:{},source:'sessions_send tool completed; delivery not confirmed'});
  mkdirSync(root,{recursive:true,mode:0o700});
  const tmp=file+'.'+process.pid+'.tmp';writeFileSync(tmp,JSON.stringify(rows.slice(-80)),{mode:0o600});renameSync(tmp,file);
}
export function recordAgentResult(root,event,ctx) {
  const role=ctx?.agentId || String(ctx?.sessionKey||'').split(':')[1];
  if(!roles[role])return;
  const error=Boolean(event?.error || event?.success===false);
  const directory=join(root,'agent-signals');mkdirSync(directory,{recursive:true,mode:0o700});
  const file=join(directory,role+'.json'),tmp=file+'.'+process.pid+'.tmp';
  writeFileSync(tmp,JSON.stringify({severity:error?'error':'success',code:error?'native_agent_failed':'native_turn_complete',at:Date.now()/1000}),{mode:0o600});renameSync(tmp,file);
}
