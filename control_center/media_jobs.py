"""Local image tasks return checked files, never a model's unsupported completion claim."""
import hashlib
import os
import re
import secrets
import json
import subprocess
import time
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import psutil
from control_center.artifacts import ROLES, MAX_FILE, safe, read_regular, output_directory


def image_request(text):
    # Explicit positive generation requests only. Review/dependency/attachment
    # references are data and must never launch a second generator.
    brief=text.split('\nDependency delivered by ')[0].split('\nAttached file ')[0]
    if re.search(r"\b(?:don't|do not|never|cannot|can't)\s+(?:generate|create|draw|render|make|design|produce|illustrate)\b",brief,re.I):return False
    if re.search(r'\b(?:when|after|once|if)\b.{0,100}\b(?:generated|generates|creates|finished|done)\b',brief,re.I):return False
    return bool(re.search(r'\b(?:generate|create|draw|render|make|design|produce|illustrate)\b\s+(?:(?:me|a|an|the|small|simple|friendly|robot|transparent|new|some|square|cute|cartoon|logo|tiny|1024|pixel|art|of)\b[\s,-]*){0,12}(?:icon|image|picture|illustration|poster|sprite|portrait|banner|artwork|logo)\b',brief,re.I))


def generate(mesh,agent,text,ident):
    import mesh_media_router as router
    import mesh_media_runtime as runtime
    from PIL import Image, ImageStat
    from io import BytesIO
    if len(text)>1200:raise ValueError('mesh_image_brief_too_long')
    route=router.resolve_active_role('image_generation')
    if not route:raise ValueError('mesh_image_provider_unavailable')
    state=safe(mesh.home,mesh.home/'.progretech-mesh');state.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(state/'image-generation.lock',os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('mesh_image_runtime_busy')
        if not mesh.idle():raise ValueError('mesh_image_other_work_active')
        memory=psutil.virtual_memory()
        if memory.available<max(12*1024**3,memory.total*.1):raise ValueError('mesh_image_memory_headroom_required')
        mesh.mark(ident,'generating','Generating image with the approved local '+route.capability_id+' model')
        result=runtime.invoke_intent('generate image',prompt=text,timeout=1000)
        if not result.ok or result.capability_id!=route.capability_id or not result.artifact:raise ValueError('mesh_image_generation_failed')
        # Only the established ComfyUI output tree, fixed by the local runtime.
        source=Path(result.artifact)
        allowed=mesh.home/'.local/share/rend/runtimes/comfyui-rocm/ComfyUI/output'
        if not source.resolve().is_relative_to(allowed.resolve()):raise ValueError('mesh_image_artifact_unavailable')
        if source.is_symlink() or not source.is_file() or not 0<source.stat().st_size<=MAX_FILE:raise ValueError('mesh_image_artifact_unavailable')
        data=source.read_bytes()
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                if image.format!='PNG' or image.size!=(1024,1024):raise ValueError('mesh_image_validation_failed')
                if max(ImageStat.Stat(image.convert('RGB')).var)<=1:raise ValueError('mesh_image_validation_failed')
                dimensions=list(image.size);alpha='A' in image.getbands()
        except (OSError,SyntaxError):raise ValueError('mesh_image_validation_failed')
        role=ROLES[mesh.provider.bindings[agent]]
        directory=safe(mesh.home,output_directory(mesh.home,mesh.provider.bindings[agent]));directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        target=directory/('image-'+ident+'.png');temp=directory/('.image-'+secrets.token_hex(8)+'.tmp')
        out=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(out,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        temp.replace(target);digest=hashlib.sha256(read_regular(mesh.home,target)).hexdigest()
        mesh.mark(ident,'publishing','Image decoded and published; ready for artifact review')
        activity=record_activity(mesh.home,role,ident,target,digest,route.capability_id)
        return {'activity':activity,'reply':'Generated and validated a local PNG artifact: '+str(target)+'\nDimensions: 1024 × 1024. Model: '+route.capability_id+'. SHA-256: '+digest+'\n'+('Contains an alpha channel; visual quality still needs review.' if alpha else 'This provider produced an opaque background. Transparency and visual quality are not verified.')+'\nMemPalace activity: '+activity['status']+'.\nAvailable in Factory Artifacts. A reviewer must inspect the actual file before approving it.', 'role':mesh.provider.bindings[agent],'model':route.capability_id,'artifacts':[{'path':str(target),'sha256':digest,'size':len(data),'dimensions':dimensions,'alpha':alpha,'validated':True}]}
    finally:os.close(fd)


def review_input(mesh, paths):
    """Attach real catalogued image pixels to the exact role's native request."""
    import base64
    from control_center.artifacts import catalog
    from PIL import Image
    from io import BytesIO
    if len(paths)!=1:raise ValueError('mesh_image_review_unavailable')
    row=next((r for r in catalog(mesh.home) if r['path']==str(paths[0]) and r['downloadable']),None)
    if not row:raise ValueError('mesh_image_artifact_unavailable')
    data=read_regular(mesh.home,Path(row['path']))
    with Image.open(BytesIO(data)) as image:
        image.verify();kind=Image.MIME.get(image.format)
    if kind not in {'image/png','image/jpeg','image/webp'}:raise ValueError('mesh_image_review_unavailable')
    installed={m['name'] for m in mesh.api('tags')['models']}
    # Small, already configured vision-capable model; avoid waking the role's
    # large text-only model just to inspect an icon. Never use cloud fallback.
    models=mesh.config(next(iter(mesh.provider.bindings)))[0].get('models',{}).get('providers',{}).get('ollama',{}).get('models',[])
    for name in ['qwen3.5:2b','qwen3.8:27b','moondream:latest']:
        if name in installed and any(m.get('id')==name and 'image' in m.get('input',[]) for m in models):
            caps=mesh.api('show',{'model':name}).get('capabilities',[])
            if 'vision' in caps:return 'ollama/'+name,[{'type':'image_url','image_url':{'url':'data:'+kind+';base64,'+base64.b64encode(data).decode()}}]
    raise ValueError('mesh_image_review_model_unavailable')


def review(mesh,agent,text,ident,paths):
    """Bounded host-mediated visual review, isolated from unrelated native history."""
    chosen,content=review_input(mesh,paths)
    model=chosen.split('/',1)[1];mesh.prepare(agent,ident,model=model)
    role=ROLES[mesh.provider.bindings[agent]]
    schema={'type':'object','properties':{'verdict':{'type':'string','enum':['pass','fail','needs_review']},'observations':{'type':'array','items':{'type':'string'}},'concerns':{'type':'array','items':{'type':'string'}}},'required':['verdict','observations','concerns'],'additionalProperties':False}
    mesh.mark(ident,'processing','Inspecting the actual image pixels with the local vision model')
    response=mesh.api('chat',{'model':model,'stream':False,'think':False,'format':schema,'keep_alive':'15m','options':{'num_ctx':8192,'num_predict':800},'messages':[
        {'role':'system','content':'You are the '+role+' visual reviewer for this owner-authorized artifact. Inspect the provided image. Answer only this visual review in the required JSON format. Report visible evidence and uncertainty; do not infer success from a filename. Do not summarize other work or invent tools or memory access. Background transparency cannot be proved from appearance alone.'},
        {'role':'user','content':text[:6000],'images':[content[0]['image_url']['url'].split(',',1)[1]]}]},timeout=300)
    try:
        result=json.loads(response['message']['content'])
        if set(result)!=set(schema['required']) or result['verdict'] not in ['pass','fail','needs_review']:raise ValueError()
        if not result['observations'] or any(not isinstance(result[k],list) or len(result[k])>12 or any(not isinstance(v,str) or not v.strip() or len(v)>1500 for v in result[k]) for k in ['observations','concerns']):raise ValueError()
    except (KeyError,TypeError,ValueError):raise ValueError('mesh_image_review_incomplete')
    from control_center.artifacts import write
    path=Path(paths[0]);digest=hashlib.sha256(read_regular(mesh.home,path)).hexdigest()
    from PIL import Image
    with Image.open(path) as image:has_alpha='A' in image.getbands()
    result.update(source=str(path),source_sha256=digest,model=model,alpha_channel=has_alpha,scope='host-mediated visual review; model judgments require owner review')
    directory=safe(mesh.home,output_directory(mesh.home,mesh.provider.bindings[agent]));directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=directory/('review-'+ident+'.json');write(target,result)
    activity=record_activity(mesh.home,role,ident,target,hashlib.sha256(read_regular(mesh.home,target)).hexdigest(),model,kind='review')
    return {'role':mesh.provider.bindings[agent],'model':chosen,'activity':activity,'review':result,'reply':'Visual review: '+result['verdict']+'\nObserved: '+ '; '.join(result['observations'])+'\nConcerns: '+('; '.join(result['concerns']) or 'None reported by model')+'\nFile inspection: '+('alpha channel present; transparency coverage requires review' if has_alpha else 'opaque image; no alpha channel')+'\nReview report: '+str(target)+'\nMemPalace activity: '+activity['status']}


def record_activity(home,role,ident,path,digest,model,kind='generation'):
    # The host job is bound to the enrolled logical role, not to its text model.
    # Explicitly identify host-mediated execution rather than LLM authorship.
    body={'what':'Host-mediated local image '+kind+' for the assigned Mesh role.',
          'why':'An owner image request needs an actual inspectable artifact and evidence-based review.',
          'how':('Inspected actual published image bytes using a configured downloaded vision model, validated the structured review and published its report.' if kind=='review' else 'Used the approved local image provider, decoded the PNG, published it atomically and verified its digest.'),
          'technical_steps':['Local provider: '+model,('Structured visual review recorded; model judgments need owner review.' if kind=='review' else 'Validated 1024x1024 PNG; visual brief compliance requires review.'),'Published '+str(path),'SHA-256: '+digest],
          'outcome':'completed','evidence':[str(path),'mesh-image-job:'+ident],'teaching_refs':[]}
    try:
        p=subprocess.run([str(home/'Rend/bin/factory-memory-activity'),'--agent',role,'--project','ProgreTech','--event','mesh-image-job-'+ident],input=json.dumps(body),text=True,capture_output=True,timeout=30)
        receipt=json.loads(p.stdout)
        if p.returncode or not receipt.get('ok') or not receipt.get('recall_verified'):return {'status':'write-failed'}
        result={'status':'saved-and-recalled','memory_id':receipt['memory_id']}
        try:
            audit=safe(home,home/'.local/state/rend/mempalace/completion-audit.jsonl')
            audit.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            row={'agent':role,'project':'ProgreTech','status':'saved','at':datetime.now(timezone.utc).isoformat(),'activity_kind':'host-image-review' if kind=='review' else 'host-image-execution','activity_memory_id':receipt['memory_id'],'activity_recall_verified':True}
            fd=os.open(audit,os.O_WRONLY|os.O_CREAT|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
            try:os.write(fd,(json.dumps(row)+'\n').encode());os.fsync(fd)
            finally:os.close(fd)
        except (OSError,ValueError):result['audit_status']='unavailable'
        return result
    except (OSError,ValueError,subprocess.SubprocessError):return {'status':'write-failed'}
