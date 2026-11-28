#!/usr/bin/env python3
import argparse, json, os, sys, time
from pathlib import Path
import numpy as np
import soundfile as sf

RUNTIME=Path.home()/".local/share/rend/runtimes/ace-step15-rocm"
SOURCE=RUNTIME/"source/ACE-Step-1.5"
MODEL=Path("/mnt/rend-data/model-cache/music/ace-step-1.5")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--prompt",required=True); ap.add_argument("--output-dir",required=True); a=ap.parse_args()
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    os.environ["ACESTEP_CHECKPOINTS_DIR"]=str(MODEL)
    os.environ["ACESTEP_LM_BACKEND"]="pt"
    os.environ["TOKENIZERS_PARALLELISM"]="false"
    os.environ["MIOPEN_FIND_MODE"]="FAST"

    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    import inspect

    dit=AceStepHandler()
    init={"project_root":str(SOURCE),"config_path":"acestep-v15-turbo","device":"cuda"}
    sig=inspect.signature(dit.initialize_service)
    dit.initialize_service(**{k:v for k,v in init.items() if k in sig.parameters})
    llm=LLMHandler()

    def make(cls,d):
        s=inspect.signature(cls); return cls(**{k:v for k,v in d.items() if k in s.parameters})

    params=make(GenerationParams,{
      "task_type":"text2music","caption":a.prompt,"lyrics":"","duration":10,
      "thinking":False,"inference_steps":8,"shift":3.0,"seed":49103,"guidance_scale":7.0
    })
    config=make(GenerationConfig,{"batch_size":1,"audio_format":"wav","use_random_seed":False})
    result=generate_music(dit_handler=dit,llm_handler=llm,params=params,config=config,save_dir=str(out))
    if not getattr(result,"success",False):
        raise RuntimeError(getattr(result,"error","generation_failed"))
    paths=[]
    for x in getattr(result,"audios",[]) or []:
        if isinstance(x,dict) and x.get("path"): paths.append(Path(x["path"]))
    if not paths:
        paths=list(out.rglob("*.wav"))
    if not paths: raise RuntimeError("music_artifact_missing")
    art=paths[0]
    data,sr=sf.read(art,always_2d=True)
    rms=float(np.sqrt(np.mean(np.square(data,dtype=np.float64)))) if data.size else 0.0
    if sr<8000 or data.shape[0]/sr<3.0 or rms<=1e-5: raise RuntimeError("music_validation_failed")
    resultj={"artifact":str(art),"sample_rate":int(sr),"channels":int(data.shape[1]),"duration":data.shape[0]/sr,"rms":rms}
    (out/"result.json").write_text(json.dumps(resultj,indent=2)); print(json.dumps(resultj))
if __name__=="__main__": main()
