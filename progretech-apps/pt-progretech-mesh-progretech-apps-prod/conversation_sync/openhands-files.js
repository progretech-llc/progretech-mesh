/* Origin-only attachment links. Reuse Agent Canvas's existing local auth. */
(() => {
  let syncing=false;
  setInterval(async()=>{
    const match=/^\/conversations\/([0-9a-f-]{32,36})(?:\/|$)/i.exec(location.pathname);
    const key=window.__AGENT_CANVAS_SESSION_API_KEY__;
    if(!match || !key || syncing || document.hidden)return;
    syncing=true;
    try{await fetch('/api/conversations/'+match[1]+'/events/sync',{method:'POST',headers:{'X-Session-API-Key':key},signal:AbortSignal.timeout(10000)});}catch{/* Preserve the last displayed feed while disconnected. */}
    finally{syncing=false;}
  },5000);
  document.addEventListener('click',async event=>{
    const anchor=event.target.closest?.('a[href^="#progretech-file="]');
    if(!anchor)return;
    event.preventDefault();event.stopImmediatePropagation();
    const label=anchor.textContent;
    try {
      const file=decodeURIComponent(anchor.getAttribute('href').slice('#progretech-file='.length));
      if(!file.startsWith('/mnt/pt-context/deliverables/') || file.split('/').includes('..'))throw Error('Invalid published file path');
      const key=window.__AGENT_CANVAS_SESSION_API_KEY__;
      if(!key)throw Error('Connect to the local OpenHands server to download this file');
      anchor.textContent='Downloading…';
      const response=await fetch('/api/file/download?path='+encodeURIComponent(file),{headers:{'X-Session-API-Key':key},redirect:'error'});
      if(!response.ok)throw Error('File download failed ('+response.status+')');
      const blob=await response.blob(),url=URL.createObjectURL(blob),download=document.createElement('a');
      download.href=url;download.download=file.split('/').pop();download.click();setTimeout(()=>URL.revokeObjectURL(url),30000);anchor.textContent=label;
    }catch(error){anchor.textContent=error.message;}
  },true);
})();
