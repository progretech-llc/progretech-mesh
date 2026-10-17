export const factoryActions = new Set('factory.status host.overview host.system models.list audio.get audio.set voice.get voice.start voice.stop voice.providers voice.preview voice.select voice.settings vision.get vision.analyze chatter.get chatter.settings chatter.test skills.list mail.status orchestration.status harness.status grid.status vllm.status'.split(' '));
const gatewayMethods = {
 'host.overview':'system-presence',
 'host.system':'health',
 'skills.list':'skills.status',
};

// External plugins use an authenticated client; in-process requests are official-only.
export function createGatewayReader(callGatewayFromCli) {
 return (method, params) => callGatewayFromCli(method, {timeout:'15000'}, params, {
  scopes:['operator.read'], progress:false,
 });
}

async function readGatewayFactoryStatus(gatewayRequest) {
 const options = {scopes:['operator.read']};
 const roster = await gatewayRequest('agents.list', {}, options);
 const catalog = await gatewayRequest('models.list', {agentId:roster.defaultId}, options);
 const agents = Array.isArray(roster?.agents) ? roster.agents : [];
 const models = Array.isArray(catalog?.models) ? catalog.models : [];
 return {
  ok:true,
  agents:agents.map(agent=>({
   id:agent.id,
   name:agent.identity?.name || agent.name || agent.id,
   role:agent.identity?.theme || agent.identity?.role || 'OpenClaw agent',
   model:agent.model?.primary || agent.model || 'Not reported',
   hardware_status:'Reported by OpenClaw gateway',
  })),
  providers:Object.fromEntries([...new Set(models.map(model=>model.provider).filter(Boolean))].map(provider=>[
   provider,{models:models.filter(model=>model.provider===provider)},
  ])),
  capabilities:['agents.list','models.list','host.system','host.overview','skills.list'],
  timestamp:new Date().toISOString(),
 };
}

async function readFactoryControl(payload, gatewayRequest) {
 if (!payload || !factoryActions.has(payload.action)) throw new Error('action_not_allowed');
 const args=payload.args ?? {};
 if (typeof args !== 'object' || Array.isArray(args) || !args) throw new Error('invalid_args');
 if (typeof gatewayRequest !== 'function') throw new Error('gateway_unavailable');
 if (payload.action === 'factory.status') return await readGatewayFactoryStatus(gatewayRequest);
 if (payload.action === 'models.list') {
  const roster=await gatewayRequest('agents.list', {}, {scopes:['operator.read']});
  return await gatewayRequest('models.list', {agentId:roster.defaultId}, {scopes:['operator.read']});
 }
 const method=gatewayMethods[payload.action];
 if (!method) return {ok:false,error:'gateway_capability_unavailable'};
 const result=await gatewayRequest(method, args, {scopes:['operator.read']});
 if (payload.action !== 'skills.list') return result;
 return {
  agentId:result.agentId,
  skills:(Array.isArray(result.skills)?result.skills:[]).map(({name,description,source,bundled,eligible})=>({name,description,source,bundled,eligible})),
 };
}

export async function forwardFactoryControl(payload, gatewayRequest) {
 const result = await readFactoryControl(payload, gatewayRequest);
 return result?.ok === false ? result : {ok:true, result};
}
