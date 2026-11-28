import json
import os
import subprocess
import tempfile
import unittest
from functools import wraps
from pathlib import Path
from unittest.mock import patch
from flask import Flask,jsonify,session
from mesh_local_updates import LocalUpdates,register_local_updates,write


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL,text=True).strip()

class LocalGitUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.remote=self.root/'remote.git';self.state=self.root/'state'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['git','clone',str(self.remote),str(self.repo)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        git(self.repo,'config','user.email','fixture@example.invalid');git(self.repo,'config','user.name','Fixture')
        (self.repo/'app.py').write_text('print("first")\n');git(self.repo,'add','app.py');git(self.repo,'commit','-m','First release')
        git(self.repo,'branch','-M','releases/mesh-local');git(self.repo,'push','origin','HEAD')
        self.initial=git(self.repo,'rev-parse','HEAD');self.source=self.root/'installed'
        git(self.repo,'worktree','add','--detach',str(self.source),self.initial)
        write(self.state/'config.json',{'repository':str(self.repo),'remote':'origin','channel':'releases/mesh-local','release_root':str(self.root/'releases')})
        write(self.state/'installed.json',{'commit':self.initial,'source':str(self.source),'python':'fixture','version':'1'})
        self.updater=LocalUpdates(self.state)
    def new_release(self):
        (self.repo/'app.py').write_text('print("second")\n');git(self.repo,'add','app.py');git(self.repo,'commit','-m','Second release');git(self.repo,'push','origin','HEAD');return git(self.repo,'rev-parse','HEAD')
    def test_git_check_reports_actual_remote_update_without_modifying_installed_source(self):
        self.assertFalse(self.updater.check()['offer']['available'])
        target=self.new_release();result=self.updater.check()
        self.assertEqual(result['offer']['target'],target);self.assertTrue(result['offer']['available']);self.assertIn('Second release',result['offer']['commits'][0])
        self.assertEqual(git(self.source,'rev-parse','HEAD'),self.initial);self.assertIn('first',(self.source/'app.py').read_text())
    def test_dirty_install_is_preserved_and_install_requires_checked_pinned_revision(self):
        self.new_release();self.updater.check();(self.source/'app.py').write_text('owner edit')
        with self.assertRaisesRegex(ValueError,'local_changes_preserved'):self.updater.check()
        with self.assertRaisesRegex(ValueError,'check_for_updates_first'):self.updater.apply('f'*40)
        self.assertEqual((self.source/'app.py').read_text(),'owner edit')
    def test_install_launches_fixed_helper_with_exact_checked_target(self):
        target=self.new_release();self.updater.check()
        with patch('mesh_local_updates.subprocess.run',return_value=subprocess.CompletedProcess([],0,'')) as run:
            with patch('mesh_local_updates.git',side_effect=['',self.initial]):
                result=self.updater.apply(target)
        args=run.call_args.args[0];self.assertEqual(args[0],'systemd-run');self.assertEqual(args[-1],target);self.assertEqual(result['job']['phase'],'queued')
    def test_abbreviated_installed_revision_is_resolved_without_false_source_mismatch(self):
        record=json.loads((self.state/'installed.json').read_text());record['commit']=self.initial[:7]
        write(self.state/'installed.json',record)
        target=self.new_release();result=self.updater.check()
        self.assertTrue(result['offer']['available']);self.assertEqual(result['offer']['current'],self.initial)
        self.assertEqual(result['offer']['target'],target)
    def test_actual_source_change_still_blocks_check_and_install(self):
        target=self.new_release();self.updater.check()
        git(self.source,'checkout','--detach',target)
        with self.assertRaisesRegex(ValueError,'installation_source_changed'):self.updater.check()
        with self.assertRaisesRegex(ValueError,'installation_source_changed'):self.updater.apply(target)
    def test_rejects_diverged_remote_instead_of_downgrading(self):
        self.new_release();git(self.repo,'checkout','--orphan','alternate');(self.repo/'app.py').write_text('unrelated');git(self.repo,'add','app.py');git(self.repo,'commit','-m','Unrelated history');git(self.repo,'push','--force','origin','HEAD:releases/mesh-local')
        with self.assertRaisesRegex(ValueError,'diverged'):self.updater.check()
        self.assertEqual(git(self.source,'rev-parse','HEAD'),self.initial)

class LocalUpdateRouteTests(unittest.TestCase):
    def require(self,view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            if not session.get('owner'):return jsonify(ok=False),401
            return view(*args,**kwargs)
        return wrapped
    def make(self,local=True):
        app=Flask(__name__);app.secret_key='fixture';updater=unittest.mock.Mock();updater.status.return_value={'ok':True};updater.check.return_value={'ok':True}
        with patch.dict(os.environ,{'MESH_LOCAL_CONTROL_CENTER':'1' if local else '0','MESH_UPDATE_ENABLED':'1'}):register_local_updates(app,self.require,updater)
        return app.test_client(),updater
    def test_cloud_has_no_update_endpoint(self):
        client,_=self.make(False);self.assertEqual(client.post('/api/local-updates').status_code,404)
    def test_requires_owner_and_same_origin_for_check(self):
        client,updater=self.make();body={'action':'check'}
        self.assertEqual(client.post('/api/local-updates',json=body).status_code,401)
        with client.session_transaction() as s:s['owner']=True
        self.assertEqual(client.post('/api/local-updates',json=body).status_code,400)
        self.assertEqual(client.post('/api/local-updates',json=body,headers={'Origin':'https://evil.invalid'}).status_code,400)
        self.assertEqual(client.post('/api/local-updates',json=body,headers={'Origin':'http://localhost'}).status_code,200)
        updater.check.assert_called_once()
    def test_no_user_supplied_commands_paths_or_remote(self):
        client,updater=self.make()
        with client.session_transaction() as s:s['owner']=True
        for body in [{'action':'check','repository':'/tmp'},{'action':'shell','command':'id'},{'action':'install','target':'a'*40,'remote':'other'}]:
            self.assertEqual(client.post('/api/local-updates',json=body,headers={'Origin':'http://localhost'}).status_code,400)
        updater.check.assert_not_called();updater.apply.assert_not_called()

class ReleaseRollbackTests(unittest.TestCase):
    setUp=LocalGitUpdateTests.setUp
    new_release=LocalGitUpdateTests.new_release
    def test_failed_health_restores_previous_installation_record_and_service(self):
        import importlib.util
        path=Path(__file__).resolve().parents[1]/'install/update-local-mesh.py'
        spec=importlib.util.spec_from_file_location('local_update_worker',path);worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
        (self.repo/'mesh-release.json').write_text('{"version":"2"}');git(self.repo,'add','mesh-release.json');target=self.new_release();self.updater.check()
        actual_run=subprocess.run;calls=[]
        def run(args,**kwargs):
            if args[0]=='git':return actual_run(args,**kwargs)
            calls.append(args);return subprocess.CompletedProcess(args,0,'')
        with patch.object(worker,'host_idle',return_value=True),patch.object(worker,'health',side_effect=[False,True]),patch.object(worker.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(ValueError,'previous_release_restored'):worker.install(self.state,target)
        self.assertEqual(self.updater.installation()['commit'],self.initial)
        self.assertEqual(len([a for a in calls if a[:3]==['systemctl','--user','restart']]),2)
        self.assertEqual(git(self.source,'rev-parse','HEAD'),self.initial)
