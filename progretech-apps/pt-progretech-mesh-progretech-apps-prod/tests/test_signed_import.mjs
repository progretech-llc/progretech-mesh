import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {parseIdentities,enrollIdentities} from '../static/js/signed-import.mjs';
import {saveEnrollment,enrollmentReceipts,forgetEnrollment} from '../openclaw-plugin-progretech-mesh/gateway-enrollments.js';

const identity = id => ({agent_id:id,name:'Role',gateway_id:'host',gateway_candidate_id:id,public_key:'public fixture',
  codeseal_evidence:{manifest:{mesh_identity:{agent_id:id,agent_name:'Role',public_key:'public fixture'}},registry_signature:'fixture',registry_public_key:'registry'}});
const reply = (ok,body) => ({ok,json:async()=>body});
test('import rejects private material, duplicate roles and mismatched signed binding',()=>{
  for (const text of ['-----BEGIN PRIVATE KEY-----',JSON.stringify([identity('host--a'),identity('host--a')]),JSON.stringify({...identity('host--a'),agent_id:'host--b'})]) assert.throws(()=>parseIdentities(text));
  assert.equal(parseIdentities(JSON.stringify([identity('host--a'),identity('host--b')])).length,2);
});
test('partial failure stops, surfaces error, and does not claim all roles enrolled',async()=>{
  let mutations=0;const progress=[];
  const request=async (url)=>url==='/api/agents'?reply(true,{agents:[]}):++mutations===1?reply(true,{agent:{trust_state:'verified'}}):reply(false,{error:'signature_invalid'});
  await assert.rejects(enrollIdentities([identity('host--a'),identity('host--b'),identity('host--c')],request,(n)=>progress.push(n)),/signature_invalid/);
  assert.equal(mutations,2);assert.deepEqual(progress,[1]);
});
test('retry skips only exact already owned verified identity',async()=>{
  let mutations=0;const existing={id:'host--a',gateway_enrollment:true,owner_bound:true,trust_state:'verified',control_center_gateway:'host',public_key:'public fixture'};
  const request=async url=>url==='/api/agents'?reply(true,{agents:[existing]}):(mutations++,reply(true,{agent:{trust_state:'verified'}}));
  assert.equal(await enrollIdentities([identity('host--a'),identity('host--b')],request,()=>{}),2);assert.equal(mutations,1);
});
test('gateway receipts persist privately, remain bound to gateway and honor removal',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'mesh-receipt-test-'));
  try {
    saveEnrollment(root,'host','host--a','PTMGE1.fixture.signature');
    assert.deepEqual(enrollmentReceipts(root,'host'),['PTMGE1.fixture.signature']);
    assert.equal(fs.statSync(path.join(root,'gateway-agent-enrollments.json')).mode&0o777,0o600);
    assert.throws(()=>enrollmentReceipts(root,'other'));
    assert.throws(()=>saveEnrollment(root,'host','other--a','PTMGE1.fixture.signature'));
    forgetEnrollment(root,'host','host--a');assert.deepEqual(enrollmentReceipts(root,'host'),[]);
  } finally {fs.rmSync(root,{recursive:true,force:true});}
});
