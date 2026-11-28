"""One host-local office identity per runtime; cloud stores only projections."""
import json
from pathlib import Path
from control_center.office import engine, namespace


def synchronize(home, runtime, gateway, rows):
    # Reviewed legacy bindings are explicit, never guessed from display names.
    path = Path(home)/'.progretech-mesh/office-runtime-bindings.json'
    try:
        migrations = json.loads(path.read_text()).get(gateway, {})
    except FileNotFoundError:
        migrations = {}
    return engine(home, namespace(runtime, gateway), 'runtime.sync',
                  {'agents': rows, 'bindings': migrations, 'host_runtime': runtime})['snapshot']


def project(snapshot, rows, gateway, host_runtime):
    by_runtime = {a['runtime_id']: a for a in snapshot['agents'] if a.get('runtime_id')}
    archived = {a['runtime_id'] for a in snapshot.get('archivedAgents', []) if a.get('runtime_id')}
    output = []
    for row in rows:
        runtime = row.get('runtime_id')
        if runtime in archived:
            row = dict(row, office_archived=True)
        office = by_runtime.get(runtime)
        if office:
            row = dict(row, office_agent_id=office['id'], is_orchestrator=office['isDirector'])
        if runtime == host_runtime:
            row = dict(row, id=gateway)
        if not any(r['id'] == row['id'] for r in output): output.append(row)
    for office in snapshot['agents']:
        if office.get('runtime_id'): continue
        output.append({'id':gateway+'--'+office['id'], 'name':office['name'], 'role':office['role'],
                       'office_agent_id':office['id'], 'office_worker':True,
                       'is_orchestrator':office['isDirector'], 'state':office['state']})
    return output
