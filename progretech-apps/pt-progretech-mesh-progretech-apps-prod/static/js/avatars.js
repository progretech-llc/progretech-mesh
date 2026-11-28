'use strict';
// Match stable runtime IDs, not editable display names. Unknown workers retain initials.
globalThis.MeshAvatar = (() => {
  const images = Object.freeze({"coder": "/static/avatars/coder.jpg", "codex": "/static/avatars/codex.jpg", "imagen": "/static/avatars/imagen.jpg", "main": "/static/avatars/main.jpg", "moxy": "/static/avatars/moxy.png?v=teal-20261007", "progre": "/static/avatars/progre.png", "researcher": "/static/avatars/researcher.jpg"});
  const aliases = Object.freeze({rend:'main',mak:'coder',lyra:'researcher',odexi:'codex'});
  function source(agent) {
    const raw = agent?.runtime_id || agent?.native?.runtime_id || agent?.native?.id || agent?.id || agent?.name || '';
    const id = String(raw).toLowerCase().replace(/^factory-/,'').replace(/^runtime-/,'').replace(/^rend--/,'');
    const runtime = Object.hasOwn(aliases, id) ? aliases[id] : id;
    return Object.hasOwn(images, runtime) ? images[runtime] : null;
  }
  return Object.freeze({source});
})();
