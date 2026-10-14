import unittest
from functools import wraps
from flask import Flask, jsonify, session
import mesh_factory_control as factory

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__,template_folder='../templates');self.app.secret_key='test'
        self.registry={'rend':{'owner_id':'owner','trust_state':'verified','name':'Rend'}}
        self.gateways={'rend':object()};self.sent=[]
        self.old=factory.factory_relay;factory.factory_relay=factory.FactoryRelay(timeout=.002)
        def require_session(view):
            @wraps(view)
            def wrapped(*args,**kwargs):
                if not session.get('uid'):return jsonify(ok=False,error='authentication_required'),401
                return view(*args,**kwargs)
            return wrapped
        def send(agent,message):
            self.sent.append(message)
            factory.factory_relay.resolve(agent,{'type':'factory_control_response','request_id':message['request_id'],'payload':{'ok':True,'result':{'agents':[]}}})
            return True,None
        factory.register_factory_routes(self.app,require_session,lambda:session.get('uid',''),self.registry,self.gateways,send)
        self.client=self.app.test_client()
    def tearDown(self):factory.factory_relay=self.old
    def login(self,uid='owner'):
        with self.client.session_transaction() as session_:session_['uid']=uid
    def post(self,body,origin='http://localhost'):
        return self.client.post('/api/agents/rend/factory/control',json=body,headers={'Origin':origin})
    def test_auth(self):self.assertEqual(self.client.get('/api/agents/rend/factory').status_code,401)
    def test_other_owner(self):
        self.login('other');self.assertEqual(self.post({'action':'factory.status'}).status_code,404);self.assertFalse(self.sent)
    def test_unbound(self):
        self.login();self.registry['rend']['owner_id']='';self.assertEqual(self.client.get('/api/agents/rend/factory').status_code,404)
    def test_unverified(self):
        self.login();self.registry['rend']['trust_state']='unsigned';self.assertEqual(self.post({'action':'factory.status'}).status_code,403)
    def test_offline(self):
        self.login();self.gateways.clear();self.assertEqual(self.post({'action':'factory.status'}).status_code,503)
    def test_origin(self):
        self.login();self.assertEqual(self.post({'action':'factory.status'},'https://evil.test').status_code,403)
        self.assertEqual(self.post({'action':'factory.status'},'').status_code,403);self.assertFalse(self.sent)
    def test_actions_and_args(self):
        self.login()
        for body in [{'action':'shell.exec'},{'action':'voice.start','args':{'command':'id'}},{'action':'audio.set','args':[]},{'action':'chatter.settings','args':{'enabled':'yes','quiet':False}},{'action':'voice.preview','args':{'provider':'piper','text':'Hi','pitch':True}}]:
            self.assertEqual(self.post(body).status_code,400)
        self.assertFalse(self.sent)
    def test_mailbox_enum(self):
        self.login()
        for agent in ['rend','lyra','mak']:
            self.assertEqual(self.post({'action':'mail.status','args':{'agent':agent}}).status_code,200)
        self.assertEqual(self.post({'action':'mail.status','args':{'agent':'other'}}).status_code,400)
    def test_proxy_origin(self):
        from werkzeug.middleware.proxy_fix import ProxyFix
        self.login();self.app.wsgi_app=ProxyFix(self.app.wsgi_app,x_proto=1,x_host=1)
        response=self.client.post('/api/agents/rend/factory/control',json={'action':'factory.status'},headers={'Origin':'https://mesh.progretech.com','X-Forwarded-Proto':'https','X-Forwarded-Host':'mesh.progretech.com'})
        self.assertEqual(response.status_code,200)
    def test_roundtrip(self):
        self.login();r=self.post({'action':'factory.status','args':{}});self.assertEqual(r.status_code,200);self.assertTrue(r.json['ok']);self.assertEqual(factory.factory_relay.pending,{})
    def test_mismatched_gateway_and_timeout(self):
        relay=factory.FactoryRelay(timeout=.001)
        def wrong(agent,message):
            self.assertFalse(relay.resolve('other',{'type':'factory_control_response','request_id':message['request_id'],'payload':{'ok':True,'result':{}}}))
            return True,None
        response,status=relay.dispatch('rend','factory.status',{},wrong)
        self.assertEqual(status,504);self.assertEqual(response['error'],'factory_timeout');self.assertEqual(relay.pending,{})
    def test_capacity(self):
        relay=factory.FactoryRelay(capacity=0);self.assertEqual(relay.dispatch('rend','factory.status',{},lambda *_:None)[1],429)
    def test_signed_in_page(self):
        self.login();response=self.client.get('/mission-control');self.assertEqual(response.status_code,200);self.assertIn(b'Mission Control',response.data)
        response=self.client.get('/factory');self.assertEqual(response.status_code,200);self.assertIn(b'The agent factory',response.data)

if __name__=='__main__':unittest.main()
