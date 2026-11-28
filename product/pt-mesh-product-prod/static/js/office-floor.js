/* Motion is presentation. Native activity and review receipts remain host-owned. */
(() => {
  class FloorMotion {
    constructor(random=Math.random) {this.random=random;this.targets={};}
    step(positions, agents, seconds, held=new Set()) {
      const live=new Set(agents.map(a=>a.id));
      for(const id of Object.keys(this.targets))if(!live.has(id))delete this.targets[id];
      for(const a of agents) {
        const p=positions[a.id];if(!p || held.has(a.id) || !a.roaming)continue;
        let target=this.targets[a.id];
        if(!target || Math.hypot(target.x-p.x,target.y-p.y)<3)target=this.targets[a.id]={x:100+this.random()*800,y:115+this.random()*470};
        const dx=target.x-p.x,dy=target.y-p.y,d=Math.hypot(dx,dy),step=Math.min(d,30*Math.min(.1,seconds));
        if(d){p.x+=dx/d*step;p.y+=dy/d*step;}
      }
      // Keep idle orbs legible when paths cross. Work and conversation anchors
      // stay fixed; free agents give them space without a teleport on refresh.
      for(let i=0;i<agents.length;i++)for(let j=i+1;j<agents.length;j++) {
        const a=agents[i],b=agents[j],p=positions[a.id],q=positions[b.id];if(!p||!q)continue;
        const dx=q.x-p.x,dy=q.y-p.y,d=Math.hypot(dx,dy);if(d>=150)continue;
        const moveA=a.roaming&&!held.has(a.id),moveB=b.roaming&&!held.has(b.id);
        const push=Math.min(150-d,65*Math.min(.1,seconds)),x=d?dx/d:1,y=d?dy/d:0;
        const steer=(id,point,awayX,awayY)=>{
          const target=this.targets[id];
          if(target && (target.x-point.x)*awayX+(target.y-point.y)*awayY<0)
            this.targets[id]={x:Math.max(100,Math.min(900,point.x+awayX*200-awayY*120)),y:Math.max(115,Math.min(585,point.y+awayY*200+awayX*120))};
        };
        if(moveA)steer(a.id,p,-x,-y);
        if(moveB)steer(b.id,q,x,y);
        if(moveA){p.x=Math.max(90,Math.min(910,p.x-x*push/(moveB?2:1)));p.y=Math.max(105,Math.min(595,p.y-y*push/(moveB?2:1)));}
        if(moveB){q.x=Math.max(90,Math.min(910,q.x+x*push/(moveA?2:1)));q.y=Math.max(105,Math.min(595,q.y+y*push/(moveA?2:1)));}
      }
    }
    nearby(agents,positions,ideas,group=false) {
      const near=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y)<=160;
      for(const a of agents)for(const idea of ideas)if(positions[a.id] && near(positions[a.id],idea) && idea.reviews?.at(-1)?.runtime!==a.runtime_id)return {agents:[a],idea};
      for(let i=0;i<agents.length;i++) {
        const a=agents[i];if(!positions[a.id])continue;
        const peers=agents.slice(i+1).filter(b=>positions[b.id]&&near(positions[a.id],positions[b.id]));
        if(peers.length)return {agents:[a,...peers.slice(0,group?2:1)]};
      }
      return null;
    }
  }
  if(typeof module!=='undefined')module.exports=FloorMotion;
  else window.MeshFloorMotion=FloorMotion;
})();
