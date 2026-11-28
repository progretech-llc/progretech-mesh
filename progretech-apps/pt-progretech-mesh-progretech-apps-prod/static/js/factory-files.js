/* Files stay on the selected host; requests use the existing owner-scoped relay. */
(() => {
  const request=(agent,action,args)=>MeshRuntime.request(agent,action,args);
  const bytes64=bytes=>{let s='';for(const b of bytes)s+=String.fromCharCode(b);return btoa(s);};
  const decode=text=>Uint8Array.from(atob(text),c=>c.charCodeAt(0));
  async function attach(agent,files,progress=()=>{}) {
    const references=[];
    if(files.length>3)throw Error('Attach up to three files per prompt.');
    for(const file of files) {
      if(!file.size || file.size>10*1024*1024)throw Error('Each attachment must be between 1 byte and 10 MB.');
      let upload;
      try {
        progress('Uploading '+file.name+'…');upload=await request(agent,'files.begin',{name:file.name,size:file.size});
        const bytes=new Uint8Array(await file.arrayBuffer());
        for(let offset=0;offset<bytes.length;offset+=32768) {
          await request(agent,'files.chunk',{upload_id:upload.upload_id,offset,data:bytes64(bytes.subarray(offset,offset+32768))});
          progress(file.name+' · '+Math.round(Math.min(offset+32768,bytes.length)/bytes.length*100)+'%');
        }
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
        const receipt=await request(agent,'files.finish',{upload_id:upload.upload_id,sha256:hash});references.push(receipt.reference);
      } catch(e) {if(upload)try{await request(agent,'files.cancel',{upload_id:upload.upload_id});}catch{}throw e;}
    }
    return references;
  }
  async function download(agent,file,preview=false) {
    if(!file.downloadable)throw Error('This file exceeds the 10 MB download limit.');
    const pieces=[];let offset=0;
    while(true) {
      const r=await request(agent,'files.read',{id:file.id,offset});const bytes=decode(r.data);pieces.push(bytes);offset+=bytes.length;
      if(r.done || (preview==='text' && offset>=32768))break;
      if(!bytes.length)throw Error('File transfer stopped before completion.');
    }
    const blob=new Blob(pieces,{type:'application/octet-stream'});
    if(preview==='image')return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(new Blob(pieces,{type:'image/'+(/\.jpe?g$/i.test(file.name)?'jpeg':file.name.split('.').pop().toLowerCase())}));});
    if(preview)return (await blob.text()).slice(0,32768);
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
  }
  function links(container,agent,files) {
    for(const file of files||[]){const button=document.createElement('button');button.type='button';button.textContent='Download '+file.name;
      button.onclick=async()=>{button.disabled=true;try{await download(agent,file);}catch(e){button.textContent=e.message;}finally{button.disabled=false;}};container.appendChild(button);}
  }
  function brief(text,references) {const value=[text,...references].filter(Boolean).join('\n');if(value.length>4000)throw Error('The prompt plus file references exceeds 4,000 characters. Shorten the prompt.');return value;}
  window.FactoryFiles={attach,download,brief,links};
})();
