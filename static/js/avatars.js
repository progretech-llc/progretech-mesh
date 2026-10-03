'use strict';
// Match stable runtime IDs, not editable display names. Unknown workers retain initials.
globalThis.MeshAvatar = (() => {
  const images = Object.freeze({"coder": "/static/avatars/coder.jpg", "codex": "/static/avatars/codex.jpg", "imagen": "/static/avatars/imagen.jpg", "main": "/static/avatars/main.jpg", "progre": "/static/avatars/progre.png", "researcher": "/static/avatars/researcher.jpg"});
  const aliases = Object.freeze({rend:'main',mak:'coder',lyra:'researcher',odexi:'codex'});
  function source(agent) {
    const id = agent.runtime_id || agent.id;
    const runtime = Object.hasOwn(aliases, id) ? aliases[id] : id;
    return Object.hasOwn(images, runtime) ? images[runtime] : null;
  }
  return Object.freeze({source});
})();
