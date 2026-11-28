#!/usr/bin/env python3
import argparse, json, subprocess, time, urllib.request, urllib.error, socket
from pathlib import Path

COMFY=Path.home()/".local/share/rend/runtimes/comfyui-rocm/ComfyUI"
PYTHON=Path.home()/".local/share/rend/runtimes/comfyui-rocm/bin/python"

def port():
    for p in range(8351,8400):
        s=socket.socket()
        try:
            s.bind(("127.0.0.1",p)); s.close(); return p
        except OSError: s.close()
    raise RuntimeError("no_free_port")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--prompt",required=True); ap.add_argument("--output-dir",required=True); a=ap.parse_args()
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True); prt=port()
    log=(out/"comfyui.log").open("w")
    proc=subprocess.Popen([str(PYTHON),str(COMFY/"main.py"),"--listen","127.0.0.1","--port",str(prt),"--disable-auto-launch"],
                          cwd=COMFY,stdout=log,stderr=subprocess.STDOUT,text=True)
    try:
        for _ in range(90):
            if proc.poll() is not None: raise RuntimeError("comfyui_exited")
            try:
                info=json.load(urllib.request.urlopen(f"http://127.0.0.1:{prt}/object_info",timeout=2)); break
            except Exception: time.sleep(1)
        else: raise TimeoutError("comfyui_not_ready")
        saver="SaveWEBM" if "SaveWEBM" in info else None
        if not saver: raise RuntimeError("SaveWEBM_missing")
        prefix=f"PT-2026-049B/runtime-video-{int(time.time())}"
        neg="blurry, distorted, text, watermark, camera shake, low quality"
        g={
          "1":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":"Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"}},
          "2":{"class_type":"ModelSamplingSD3","inputs":{"model":["1",0],"shift":8.0}},
          "3":{"class_type":"UnetLoaderGGUF","inputs":{"unet_name":"Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"}},
          "4":{"class_type":"ModelSamplingSD3","inputs":{"model":["3",0],"shift":8.0}},
          "5":{"class_type":"CLIPLoader","inputs":{"clip_name":"umt5_xxl_fp8_e4m3fn_scaled.safetensors","type":"wan","device":"default"}},
          "6":{"class_type":"CLIPTextEncode","inputs":{"text":a.prompt,"clip":["5",0]}},
          "7":{"class_type":"CLIPTextEncode","inputs":{"text":neg,"clip":["5",0]}},
          "8":{"class_type":"VAELoader","inputs":{"vae_name":"wan_2.1_vae.safetensors"}},
          "9":{"class_type":"EmptyHunyuanLatentVideo","inputs":{"width":384,"height":384,"length":9,"batch_size":1}},
          "10":{"class_type":"KSamplerAdvanced","inputs":{"model":["2",0],"add_noise":"enable","noise_seed":49102,"steps":8,"cfg":3.5,"sampler_name":"euler","scheduler":"simple","positive":["6",0],"negative":["7",0],"latent_image":["9",0],"start_at_step":0,"end_at_step":4,"return_with_leftover_noise":"enable"}},
          "11":{"class_type":"KSamplerAdvanced","inputs":{"model":["4",0],"add_noise":"disable","noise_seed":49102,"steps":8,"cfg":3.5,"sampler_name":"euler","scheduler":"simple","positive":["6",0],"negative":["7",0],"latent_image":["10",0],"start_at_step":4,"end_at_step":10000,"return_with_leftover_noise":"disable"}},
          "12":{"class_type":"VAEDecode","inputs":{"samples":["11",0],"vae":["8",0]}},
          "13":{"class_type":"SaveWEBM","inputs":{"images":["12",0],"filename_prefix":prefix,"codec":"vp9","fps":8.0,"crf":24.0}},
        }
        req=urllib.request.Request(f"http://127.0.0.1:{prt}/prompt",data=json.dumps({"prompt":g,"client_id":"pt049b-runtime"}).encode(),headers={"Content-Type":"application/json"})
        pid=json.load(urllib.request.urlopen(req,timeout=30))["prompt_id"]
        deadline=time.time()+1800
        while time.time()<deadline:
            hist=json.load(urllib.request.urlopen(f"http://127.0.0.1:{prt}/history/{pid}",timeout=10))
            st=hist.get(pid,{}).get("status",{})
            if st.get("completed") is True: break
            if st.get("status_str")=="error": raise RuntimeError("generation_error")
            time.sleep(3)
        else: raise TimeoutError("video_timeout")
        folder=COMFY/"output"/"PT-2026-049B"
        files=sorted(folder.glob(Path(prefix).name+"*"),key=lambda p:p.stat().st_mtime,reverse=True)
        if not files or files[0].stat().st_size<=0: raise RuntimeError("video_artifact_missing")
        art=files[0]
        result={"artifact":str(art),"size":art.stat().st_size,"format":art.suffix.lower().lstrip(".")}
        (out/"result.json").write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill()
        log.close()
if __name__=="__main__": main()
