/* Availability is host-owned; waking never retries an earlier agent task. */
(() => {
  function label(runtime={}) {
    return runtime.sleeping === true ? 'Asleep' : runtime.sleeping === false ? 'Awake' : 'Availability unknown';
  }
  async function request(agent, action, args={}) {
    const response = await fetch(`/api/agents/${encodeURIComponent(agent)}/control-center`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action,args})
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw Error(data.error || 'Host request failed');
    return data.result;
  }
  async function power(agent, sleeping, progress=()=>{}) {
    if (typeof sleeping !== 'boolean') throw Error('Availability is unknown. Refresh the host status first.');
    let job = await request(agent, sleeping ? 'runtime.wake' : 'runtime.sleep');
    const deadline = Date.now() + 21*60*1000;
    while (true) {
      progress(job.detail || 'Updating availability…');
      if (job.done) {
        if (job.error) throw Error(job.error);
        return job.result;
      }
      if (!/^[a-f0-9]{32}$/.test(job.job_id || '')) throw Error('Invalid host progress response');
      if (Date.now() > deadline) throw Error('Still waiting for the host. Check status before trying again.');
      await new Promise(resolve => setTimeout(resolve,1500));
      job = await request(agent,'communication.job',{job_id:job.job_id});
    }
  }
  window.MeshAvailability = {label,power};
})();
