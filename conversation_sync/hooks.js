import crypto from 'node:crypto';
export function route(ctx, config) {
  const key=ctx.sessionKey || '', match=/^agent:([a-z0-9_-]+):(.+)$/.exec(key);
  if (!match || !config.agents?.includes(match[1])) return null;
  if(ctx.inputProvenance && ctx.inputProvenance.kind!=='external_user')return null;
  if (['heartbeat','cron','subagent'].includes(ctx.trigger) || /:(subagent|cron|mesh-chatter|support|mission):/.test(key)) return null;
  const agent=match[1], tail=match[2];
  if (tail.startsWith('mesh-chat:') || tail.startsWith('mesh:')) return {agent, origin:'mesh', session:key, project:'ProgreTech'};
  const factory=/^factory-api:([^:]+):/.exec(tail);
  if (factory) return {agent,origin:ctx.channel==='openhands'?'openhands':'factory-api',session:key,project:factory[1]};
  if (ctx.channel==='telegram' || ctx.messageProvider==='telegram') {
    const binding=config.telegram?.find(b=>b.agent===agent && b.account===(ctx.accountId || 'default'));
    const sender=String(ctx.senderId || ctx.chatId || ctx.channelId || '');
    if (!binding || sender!==String(binding.owner)) return null;
    return {agent,origin:'telegram',session:key,project:'ProgreTech'};
  }
  if ((tail==='main' || tail.startsWith('dashboard:') || tail.startsWith('explicit:')) && (!ctx.channel || ['webchat','openclaw'].includes(ctx.channel)))
    return {agent,origin:'openclaw',session:key,project:'ProgreTech'};
  return null;
}
export function textOf(message) {
  if (typeof message?.content==='string') return message.content;
  return (message?.content || []).filter(x=>x?.type==='text' && typeof x.text==='string').map(x=>x.text).join('\n');
}
export function finalText(messages) {
  let start=-1;
  for(let i=0;i<messages.length;i++)if(messages[i]?.role==='user')start=i;
  return messages.slice(start+1).filter(m=>m?.role==='assistant' && !m.tool_calls?.length && !(m.content||[]).some?.(x=>x.type==='toolCall')).map(textOf).filter(Boolean).join('\n\n');
}
export const eventKey=(ctx,event)=>ctx.runId || event.currentUserMessageId || crypto.createHash('sha256').update(ctx.sessionKey+'\0'+event.prompt).digest('hex');
export function chunks(text, size=3400) {
  const out=[];let chunk='';
  for(const character of text){if(chunk.length+character.length>size){out.push(chunk);chunk='';}chunk+=character;}
  if(chunk)out.push(chunk);
  return out;
}

export function telegramBinding(event,ctx,config,outbound=false){
  if(ctx.channelId!=='telegram')return null;
  const normalize=value=>String(value??'').replace(/^telegram:/,'');
  const target=normalize(outbound?event.to:(ctx.conversationId||event.from));
  const sender=normalize(event.senderId||event.from);
  return config.telegram?.find(b=>config.agents?.includes(b.agent) && b.account===(ctx.accountId||'default') && String(b.owner)===target && (outbound || String(b.owner)===sender)) || null;
}
