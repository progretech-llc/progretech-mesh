(() => {
  const root=document.querySelector('[data-agent-id]'), id=root.dataset.agentId,$=id=>document.getElementById(id);
  let board=null,busy=false;
  const status=s=>$('boardStatus').textContent=s;
  async function call(action,args={}){const r=await fetch('/api/agents/'+encodeURIComponent(id)+'/management',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,args})});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error==='specklet_revision_conflict'?'The board changed. Refresh and reconcile your edits before saving.':d.error||'Agent host unavailable');return d.result;}
  function controls(){root.querySelectorAll('button,input,select,textarea').forEach(e=>e.disabled=busy||(!board&&e.id!=='refreshBoard'));}
  async function run(fn){if(busy)return;busy=true;controls();try{const b=await fn();if(b){board=b;render();}}catch(e){status(e.message);if(board)$('useSpecklet').checked=board.enabled;}finally{busy=false;controls();}}
  function render(){
    $('useSpecklet').checked=board.enabled;status(board.enabled?'Specklet enabled · revision '+board.revision:'Specklet off · agent updates stopped · owner review and edits available');
    $('workspaceJson').value=JSON.stringify(board.workspace,null,2);$('localFile').textContent='Agent-local file: '+board.localFile;
    $('boardTasks').replaceChildren();
    for(const t of [...board.workspace.tasks].sort((a,b)=>(a.position||0)-(b.position||0))){
      const card=document.createElement('form');card.className='task-card';
      const title=document.createElement('input');title.value=t.title;title.required=true;title.maxLength=240;title.setAttribute('aria-label','Task title');
      const notes=document.createElement('textarea');notes.value=t.notes||'';notes.maxLength=6000;notes.setAttribute('aria-label','Scope and notes');
      const phase=document.createElement('select');phase.setAttribute('aria-label','Task status');for(const name of ['open','doing','blocked','done','cancelled']){const o=document.createElement('option');o.value=name;o.textContent=name;phase.append(o);}phase.value=t.meshStatus||t.status;
      const position=document.createElement('input');position.type='number';position.min=0;position.max=100000;position.value=t.position||0;position.setAttribute('aria-label','Order');
      const priority=document.createElement('select');priority.setAttribute('aria-label','Priority');for(const name of ['low','medium','high']){const o=document.createElement('option');o.value=name;o.textContent=name;priority.append(o);}priority.value=t.priority||'medium';
      const save=document.createElement('button');save.textContent='Save task';for(const [name,field] of [['Title',title],['Scope / notes',notes],['Status',phase],['Priority',priority],['Order',position]]){const label=document.createElement('label');label.append(document.createTextNode(name),field);card.append(label);}card.append(save);
      card.onsubmit=e=>{e.preventDefault();const revision=board.revision;run(()=>call('specklet.task',{revision,task:{id:t.id,title:title.value,notes:notes.value,status:phase.value,priority:priority.value,position:Number(position.value)}}));};$('boardTasks').append(card);
    }
    if(!board.workspace.tasks.length)$('boardTasks').textContent='No tasks yet. Add a task or upload your Specklet workspace.';
    $('boardHistory').replaceChildren();for(const h of [...board.history].reverse()){const li=document.createElement('li');li.textContent=[h.at,h.kind,h.id,h.before,h.after].filter(v=>v!==undefined&&v!==null).join(' · ');$('boardHistory').append(li);}
  }
  $('refreshBoard').onclick=()=>run(()=>call('specklet.get'));
  $('useSpecklet').onchange=()=>{const enabled=$('useSpecklet').checked;run(()=>call('specklet.toggle',{enabled}));};
  $('exportBoard').onclick=()=>{const blob=new Blob([JSON.stringify(board.workspace,null,2)],{type:'application/json'}),u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=id+'-specklet-r'+board.revision+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
  $('saveWorkspace').onclick=()=>{const raw=$('workspaceJson').value,revision=board.revision;run(()=>call('specklet.import',{workspace:JSON.parse(raw),revision}));};
  $('importBoard').onchange=()=>{const file=$('importBoard').files[0],revision=board.revision;if(!file)return;run(async()=>{if(file.size>524288)throw Error('Specklet JSON limit is 512 KiB.');return call('specklet.import',{workspace:JSON.parse(await file.text()),revision});});$('importBoard').value='';};
  $('taskForm').onsubmit=e=>{e.preventDefault();const f=e.target,task={title:f.elements.title.value,notes:f.elements.notes.value},revision=board.revision;run(async()=>{const b=await call('specklet.task',{task,revision});f.reset();return b;});};
  run(()=>call('specklet.get'));
})();
