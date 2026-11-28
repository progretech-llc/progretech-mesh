/** Follow the public Mesh release without tearing down in-flight relay work. */
export function createReleaseWatch({mesh, idle, reconnect, fetchImpl=fetch, intervalMs=30000}) {
  let build=null, candidate=null, confirmations=0, polling=false, stopped=false, timer=null;
  const valid=value=>typeof value==='string' && /^[A-Za-z0-9._-]{1,128}$/.test(value);
  function paired(value){if(valid(value)){build=value;candidate=null;confirmations=0;}}
  async function poll(){
    if(stopped || polling)return;
    polling=true;
    try{
      const response=await fetchImpl(new URL('/healthz',mesh).href,{redirect:'error',signal:AbortSignal.timeout(5000)});
      if(!response.ok)return;
      const text=await response.text();if(text.length>65536)return;
      const data=JSON.parse(text);
      if(stopped || data.ok!==true || data.service!=='progretech-mesh' || !valid(data.build))return;
      if(!build){build=data.build;return;}
      if(data.build===build){candidate=null;confirmations=0;return;}
      confirmations=candidate===data.build?confirmations+1:1;candidate=data.build;
      if(confirmations>=2 && idle()){
        reconnect({from:build,to:candidate});
        stopped=true;if(timer)clearInterval(timer);
      }
    }catch{/* An unavailable HTTP health endpoint is not proof the socket is stale. */}
    finally{polling=false;}
  }
  return {paired,poll,start(){void poll();timer=setInterval(()=>void poll(),intervalMs);timer.unref?.();},stop(){stopped=true;if(timer)clearInterval(timer);}};
}

export function closeForRelease(socket){socket.close(1000,"mesh_release_changed");}

export function isAuthenticationClose(code){return [4001,4003,4401,4403].includes(Number(code));}
