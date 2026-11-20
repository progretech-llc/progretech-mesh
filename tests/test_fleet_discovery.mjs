import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Exercise the shipped pure predicate without importing the operational app.
const source = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');
const declaration = source.match(/  function matchesFleetFilters\(agent, query, connection\) \{[\s\S]*?\n  \}/)[0];
const matches = vm.runInNewContext(`(${declaration.trim()})`);
const live = Object.freeze({name:'Révision <a> 100%_ [ops]',role:'Reviewer',model:'Local/code',runtime:'Hermes',transport:'connected'});

test('literal case-insensitive displayed-field matches combine with connection', () => {
  for (const query of ['RÉVISION',' reviewer ','LOCAL/CODE','hermes','<a>','%_','[ops]','']) assert.equal(matches(live,query,'connected'),true,query);
  for (const query of ['.*','^Révision','Reviewer Local','<script>']) assert.equal(matches(live,query,'all'),false,query);
  assert.equal(matches(live,'reviewer','not-connected'),false);
  assert.equal(matches({...live,transport:'unknown'},'reviewer','not-connected'),true);
  assert.equal(matches({...live,transport:null},'reviewer','connected'),false);
});
test('fallback fields and Scrum Master match exactly what cards display', () => {
  for (const query of ['Unknown','OpenClaw','']) assert.equal(matches({},query,'all'),true);
  assert.equal(matches({is_orchestrator:true,role:'Former role'},'Scrum Master','all'),true);
  assert.equal(matches({is_orchestrator:true,role:'Former role'},'Former role','all'),false);
  assert.equal(matches({name:'日本語の担当者',transport:'connected'},'日本語','connected'),true);
});
test('filtering preserves source records and transport facts', () => {
  const snapshot=JSON.stringify(live);
  assert.equal(matches(live,'Reviewer','all'),true);
  assert.equal(JSON.stringify(live),snapshot);
  assert.equal(matches({...live,state:'working',transport:'not-connected'},'','connected'),false);
  assert.equal(matches({...live,state:'unknown'},'','connected'),true);
});
