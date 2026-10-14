/* Fixed analytics document: isolated from normal automatic measurement of the app DOM. */
(() => {
  "use strict";
  if (window === window.top || location.search || location.hash || location.protocol !== "https:" || !["mesh.progretech.com"].includes(location.hostname) || !navigator.onLine) return;
  const ID = "G-7VCZVY3N3Z";
  const safe = {page_location: "https://mesh.progretech.com/", page_title: "ProgreTech Mesh", page_referrer: "", allow_google_signals: false, allow_ad_personalization_signals: false};
  window.dataLayer = [];
  window.gtag = function(){ window.dataLayer.push(arguments); };
  gtag("consent", "default", {analytics_storage:"granted", ad_storage:"denied", ad_user_data:"denied", ad_personalization:"denied"});
  gtag("set", safe);
  gtag("js", new Date());
  // Only the fixed frame document is measured; this trusts Google, not adversarial script isolation.
  gtag("config", ID, {...safe, send_page_view:false, cookie_prefix:"pt_mesh", cookie_domain:"mesh.progretech.com"});
  gtag("event", "page_view", {...safe, send_to:ID});
  const script=document.createElement("script"); script.async=true;
  script.referrerPolicy="no-referrer";
  script.src="https://www.googletagmanager.com/gtag/js?id="+ID;
  document.head.appendChild(script);
})();
