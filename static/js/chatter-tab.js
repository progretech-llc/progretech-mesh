/* Chatter consent belongs to one open tab; viewing status never enables it. */
(() => {
  class ChatterTab {
    constructor(runtime, onChange=()=>{}) {
      this.runtime=runtime;this.onChange=onChange;
      this.tabId=crypto.randomUUID().replaceAll('-','');
      this.agent=null;this.epoch=0;this.timer=null;this.startTimer();
      window.addEventListener('pagehide',()=>{this.release();clearInterval(this.timer);this.timer=null;});
      window.addEventListener('pageshow',()=>this.startTimer());
    }
    startTimer() {if(!this.timer)this.timer=setInterval(()=>this.heartbeat(),10000);}
    owns(agent, state) {return this.agent===agent && state?.enabled && state.tab_id===this.tabId;}
    observe(agent,state) {
      if(this.agent===agent && (!state?.enabled || state.tab_id!==this.tabId)) {this.agent=null;this.epoch++;}
    }
    async configure(agent,args) {
      if(this.agent && this.agent!==agent)this.release();
      const epoch=++this.epoch;
      // Track pending enablement so closing during a request also releases consent.
      this.agent=args.enabled?agent:null;
      try {
        const state=await this.runtime.request(agent,'chatter.configure',{...args,tab_id:this.tabId});
        if(epoch!==this.epoch) {
          if(args.enabled)this.releaseRequest(agent);
          return state;
        }
        this.observe(agent,state);return state;
      } catch(error) {if(epoch===this.epoch)this.agent=null;throw error;}
    }
    async heartbeat() {
      const agent=this.agent,epoch=this.epoch;if(!agent)return;
      try {const state=await this.runtime.request(agent,'chatter.configure',{enabled:true,tab_id:this.tabId,renew_only:true});if(epoch===this.epoch){this.observe(agent,state);this.onChange();}}
      catch {if(epoch===this.epoch){this.agent=null;this.epoch++;this.onChange();}}
    }
    releaseRequest(agent) {
      // keepalive works on navigation; the host lease handles crashes or lost requests.
      fetch(`/api/agents/${encodeURIComponent(agent)}/management`,{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'chatter.configure',args:{enabled:false,tab_id:this.tabId}})}).catch(()=>{});
    }
    release() {const agent=this.agent;this.agent=null;this.epoch++;if(agent)this.releaseRequest(agent);}
  }
  window.MeshChatterTab=ChatterTab;
})();
