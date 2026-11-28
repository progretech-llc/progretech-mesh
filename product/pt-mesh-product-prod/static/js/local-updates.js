'use strict';
(() => {
  const button=document.getElementById('localUpdateCheck');if(!button)return;
  const dialog=document.createElement('dialog');dialog.className='mesh-update-dialog';
  const title=document.createElement('h2');title.textContent='Local Mesh updates';
  const notice=document.createElement('p');notice.setAttribute('role','status');
  const changes=document.createElement('pre');const apply=document.createElement('button');apply.textContent='Install update';apply.hidden=true;
  const reload=document.createElement('button');reload.textContent='Reload updated Mesh';reload.hidden=true;reload.onclick=()=>location.reload();
  const close=document.createElement('button');close.textContent='Close';close.onclick=()=>dialog.close();
  dialog.append(title,notice,changes,apply,reload,close);document.body.append(dialog);
  let target=null,timer=null;
  const errors={
    installation_source_changed:'The installed files differ from the recorded release. No update was installed. Repair the installation record before updating.',
    local_changes_preserved_update_blocked:'Local edits were found and preserved. No update was installed. Commit or move those edits before trying again.',
    update_channel_diverged_no_downgrade:'This installation and the release channel have different histories. No downgrade was attempted.',
    active_mesh_work_update_deferred:'Active agent work prevented the restart. No update was installed. Try again after that work finishes.'
  };
  async function request(body){const response=await fetch('/api/local-updates',{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(60000)});const data=await response.json();if(!response.ok||data.ok===false)throw Error(errors[data.error]||`${(data.error||'Update unavailable').replaceAll('_',' ')}. No update was installed.`);return data;}
  function render(data){
    target=data.offer?.target;const phase=data.job?.phase;
    const busy=['queued','preparing','installing','waiting_for_idle','restarting'].includes(phase);
    const complete=phase==='complete'&&!data.offer?.available;
    apply.hidden=!data.offer?.available||busy;apply.disabled=false;reload.hidden=!complete;
    notice.textContent=busy?(phase==='waiting_for_idle'?'Update prepared. Waiting for active agent work to finish before restarting…':`Updating: ${phase.replaceAll('_',' ')}…`):data.offer?.available?`Update available for Mesh ${data.version}. Click Install update to download and install it. Checking does not install updates automatically.${phase==='failed'?' Last attempt: '+(errors[data.job.error]||data.job.error||'failed'):''}`:phase==='failed'?(errors[data.job.error]||`Update stopped: ${(data.job.error||'unknown reason').replaceAll('_',' ')}.`):complete?`Mesh ${data.version} was installed successfully. Reload to use the updated app.`:`Mesh ${data.version} is up to date. No update was needed.`;
    changes.textContent=(data.offer?.commits||[]).join('\n');return busy;
  }
  async function poll(){try{if(render(await request()))timer=setTimeout(poll,2000);}catch{notice.textContent='Waiting for Mesh to reconnect…';timer=setTimeout(poll,2000);}}
  button.onclick=async()=>{clearTimeout(timer);dialog.showModal();button.disabled=true;apply.hidden=true;reload.hidden=true;changes.textContent='';notice.textContent='Checking the release channel. This does not install an update…';try{if(render(await request({action:'check'})))timer=setTimeout(poll,2000);}catch(e){notice.textContent=e.message;}finally{button.disabled=false;}};
  apply.onclick=async()=>{apply.disabled=true;try{if(render(await request({action:'install',target})))timer=setTimeout(poll,2000);}catch(e){notice.textContent=e.message;apply.disabled=false;}};
})();
