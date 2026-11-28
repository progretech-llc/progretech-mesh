"""Shared ProgreTech account broker; app ownership identifiers remain compatible."""
import base64,hashlib,json,secrets,time,os
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from flask import abort,redirect,request,session,url_for,jsonify
ISSUER='https://codeseal.progretech.com'
CALLBACK='https://mesh.progretech.com/auth/progretech/callback'

def register_progretech_auth(app):
    app.config.setdefault('PROGRETECH_SECURITY_ENFORCED', os.getenv('PROGRETECH_SECURITY_ENFORCED','0').lower() in ('1','true'))
    app.config.setdefault('PROGRETECH_SECURITY_STATUS_TOKEN', os.getenv('PROGRETECH_SECURITY_STATUS_TOKEN',''))

    @app.before_request
    def enforce_shared_account():
        if not app.config.get('PROGRETECH_SECURITY_ENFORCED'):return
        if request.endpoint == 'static' or request.path in ('/health','/healthz','/startupz','/ready','/readyz','/auth/progretech/login','/auth/progretech/callback','/logout'):return
        if request.path in ('/api/auth/firebase/session','/login/dev'):
            return jsonify(ok=False,error='shared_login_required',login='/auth/progretech/login'),401
        user=session.get('mesh_user')
        if not user:return  # Machine credentials are independently authenticated.
        subject=user.get('progretech_user_id')
        if not subject or type(user.get('session_version')) is not int:
            session.clear()
            return jsonify(ok=False,error='shared_login_required',login='/auth/progretech/login'),401
        from mesh_account_security import account_status
        try:state=account_status(subject)
        except Exception:return jsonify(ok=False,error='account_security_unavailable'),503
        if state['status']=='locked':
            session.clear()
            return jsonify(ok=False,error='account_locked',message='Your ProgreTech account is locked. Contact support@progretech.com for identity verification and recovery. Billing renewal pause has been requested.'),423
        if state['session_version']!=user['session_version']:
            session.clear()
            return jsonify(ok=False,error='shared_login_required',login='/auth/progretech/login'),401

    @app.get('/auth/progretech/login')
    def progretech_login():
        verifier=secrets.token_urlsafe(48);state=secrets.token_urlsafe(32)
        session['progretech_login']={'state':state,'verifier':verifier,'until':time.time()+900}
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        return redirect(ISSUER+'/auth/sso/authorize?'+urlencode({'client_id':'mesh','redirect_uri':CALLBACK,'state':state,'code_challenge':challenge,'code_challenge_method':'S256'}))
    @app.get('/auth/progretech/callback')
    def progretech_callback():
        pending=session.pop('progretech_login',{})
        if pending.get('until',0)<time.time() or not secrets.compare_digest(str(pending.get('state','')),request.args.get('state','')):abort(400)
        body={'client_id':'mesh','redirect_uri':CALLBACK,'code':request.args.get('code',''),'code_verifier':pending['verifier']}
        try:
            with urlopen(Request(ISSUER+'/auth/sso/token',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=15) as r:token=json.load(r)
            with urlopen(Request(ISSUER+'/auth/sso/userinfo',headers={'Authorization':'Bearer '+token['access_token']}),timeout=15) as r:user=json.load(r)
            if user.get('iss')!=ISSUER or user.get('aud')!='mesh' or user.get('email_verified') is not True or not user.get('sub') or not user.get('email'):abort(401)
        except Exception:abort(401)
        # Keep established Firebase ownership IDs for verified legacy emails. The account
        # subject comes from the central CodeSeal record, never a second user database.
        owner_id=user['sub']
        if os.getenv('MESH_FIREBASE_PROJECT_ID'):
            try:
                import firebase_admin
                from firebase_admin import auth
                if not firebase_admin._apps:firebase_admin.initialize_app(options={'projectId':os.environ['MESH_FIREBASE_PROJECT_ID']})
                legacy=auth.get_user_by_email(user['email'])
                if legacy.email_verified and not legacy.disabled:owner_id=legacy.uid
            except Exception as error:
                if type(error).__name__=='UserNotFoundError':
                    pass
                else:
                    abort(503)
        if app.config.get('PROGRETECH_SECURITY_ENFORCED') and type(user.get('session_version')) is not int:abort(401)
        session.clear();session['mesh_user']={'id':owner_id,'progretech_user_id':user['sub'],'email':user['email'],'display_name':user['email'].split('@')[0],'auth_source':'progretech-shared','auth_strength':user['auth_strength']}
        if type(user.get('session_version')) is int:session['mesh_user']['session_version']=user['session_version']
        session.permanent=True
        return redirect(url_for('index'))
