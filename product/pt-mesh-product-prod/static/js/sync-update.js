(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  let gateways=[],selected=null,pending=false;
  const status=(text,error=false)=>{$('syncStatus').textContent=text;$('syncStatus').dataset.error=String(error);};
  function render(){
    const gateway=gateways.find(g=>g.id===$('syncGateway').value);
    selected=gateway?.id || null;
    $('gatewaySection').hidden=!gateway;$('syncEmpty').hidden=Boolean(gateway);
    if(!gateway)return;
    $('gatewayRuntime').textContent=gateway.runtime;
    const states={current:['Up to date','Your connected gateway reports the current Mesh integration. You can use the prompt to repair or reinstall it if needed.'],update_available:['Update available','This gateway reports different Mesh files. Give its authorized agent the update prompt below, then check again.'],unknown:['Version not reported','This connector does not report its installed files yet. Use the update prompt; the page will verify automatically when a supported connector reconnects. Legacy extensions require the agent’s version and checksum report.'],offline:['Gateway offline','The computer is not connected. You can give its agent these instructions locally, then check again after it reconnects.']};
    const state=states[gateway.state]||states.unknown;
    $('gatewayState').textContent=state[0];$('gatewayExplanation').textContent=state[1];
    $('updatePrompt').value=gateway.prompt;
    $('copyUpdate').textContent=gateway.state==='current'?'Copy repair prompt':'Copy update prompt';
  }
  async function refresh(){
    if(pending)return;pending=true;$('refreshSync').disabled=true;
    status('Checking the current release and gateway reports…');
    try{
      const response=await fetch('/api/sync-updates',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(response.status===401)throw Error('Your session expired. Sign in to Mesh again.');
      const data=await response.json();if(!response.ok||!data.ok)throw Error(data.error||'Update status unavailable. Try Check again.');
      $('latestVersion').textContent=data.version;$('latestBuild').textContent=data.build.slice(0,12);
      gateways=data.gateways;$('syncGateway').replaceChildren(...gateways.map(g=>new Option(g.name+(g.connected?' · connected':' · offline'),g.id)));
      if(gateways.some(g=>g.id===selected))$('syncGateway').value=selected;
      $('syncFiles').replaceChildren(...data.latest.files.map(file=>{const li=document.createElement('li');li.textContent=file;return li;}));
      render();status(gateways.length?'Gateway reports refreshed.':'No verified gateway is linked to your account.');
    }catch(error){status(error.message,true);$('gatewaySection').hidden=true;$('syncEmpty').hidden=true;}
    finally{pending=false;$('refreshSync').disabled=false;}
  }
  $('syncGateway').onchange=render;$('refreshSync').onclick=refresh;
  $('copyUpdate').onclick=async()=>{try{await navigator.clipboard.writeText($('updatePrompt').value);status('Update prompt copied. Give it to your authorized agent on the gateway computer.');}catch{$('updatePrompt').focus();$('updatePrompt').select();status('Clipboard unavailable. Copy the selected instructions.');}};
  $('downloadUpdate').onclick=()=>{const url=URL.createObjectURL(new Blob([$('updatePrompt').value],{type:'text/plain'}));const a=document.createElement('a');a.href=url;a.download='mesh-update-instructions.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  refresh();setInterval(()=>{if(!document.hidden)refresh();},30000);
})();
