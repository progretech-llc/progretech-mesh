/* Optional analytics, hosted origins only. No workspace data crosses the frame. */
(() => {
  "use strict";
  if (!["mesh.progretech.com"].includes(location.hostname) || location.protocol !== "https:" || window !== window.top) return;
  const KEY="progretech.analytics.consent.v1";
  let frame=null;
  function read(){try{return localStorage.getItem(KEY);}catch(_){return null;}}
  function apply(){
    if(read()==="accepted" && navigator.onLine){
      if(frame)return;
      frame=document.createElement("iframe");frame.src="/static/analytics/analytics-frame.html";
      frame.setAttribute("sandbox","allow-scripts allow-same-origin");frame.referrerPolicy="no-referrer";
      frame.hidden=true;frame.title="Optional analytics";document.body.appendChild(frame);
    }else {
      if(frame){frame.remove();frame=null;}
      document.cookie.split(";").forEach(cookie=>{
        const name=cookie.split("=")[0].trim();
        if(!name.startsWith("pt_mesh_"))return;
        ["", "; domain=mesh.progretech.com"].forEach(domain=>{document.cookie=name+"=; Max-Age=0; path=/"+domain;});
      });
    }
  }
  function save(value){try{localStorage.setItem(KEY,value);}catch(_){} apply();panel.hidden=true;}
  const settings=document.createElement("button");settings.type="button";settings.className="pt-analytics-settings";settings.textContent="Privacy settings";
  const panel=document.createElement("section");panel.className="pt-analytics-consent";panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Optional analytics");
  const message=document.createElement("p");message.textContent="Allow optional Google Analytics to count visits? Only a generic product page is shared, never workspace content. You can change this choice here.";
  const deny=document.createElement("button");deny.type="button";deny.textContent="Essential only";deny.onclick=()=>save("declined");
  const allow=document.createElement("button");allow.type="button";allow.textContent="Allow analytics";allow.onclick=()=>save("accepted");
  panel.append(message,deny,allow);document.body.append(settings,panel);
  settings.onclick=()=>{panel.hidden=false;deny.focus();};panel.hidden=read()!==null;
  window.addEventListener("offline",apply);window.addEventListener("online",apply);
  window.addEventListener("storage",event=>{if(event.key===KEY||event.key===null)apply();});apply();
})();
