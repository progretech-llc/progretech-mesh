const test=require('node:test'),assert=require('node:assert/strict');
const Motion=require('../static/js/office-floor.js');
test('idle movement is bounded, resumes after hold, and busy agents stay put',()=>{
  const motion=new Motion(()=>.75),points={a:{x:100,y:120},b:{x:500,y:350}},agents=[{id:'a',roaming:true},{id:'b',roaming:false}];
  for(let i=0;i<120;i++)motion.step(points,agents,1/60);
  assert.ok(points.a.x>100);assert.deepEqual(points.b,{x:500,y:350});
  const held={...points.a};motion.step(points,agents,1,new Set(['a']));assert.deepEqual(points.a,held);
  motion.step(points,agents,100);assert.ok(Math.hypot(points.a.x-held.x,points.a.y-held.y)<=3.001);
});
test('proximity does not count a review; previously reviewed ideas are excluded',()=>{
  const motion=new Motion(),agents=[{id:'a',runtime_id:'coder'},{id:'b',runtime_id:'progre'},{id:'c',runtime_id:'imagen'}];
  const points={a:{x:100,y:100},b:{x:130,y:100},c:{x:150,y:100}},idea={id:'idea',x:100,y:100,reviews:[]};
  assert.equal(motion.nearby(agents,points,[idea]).idea.id,'idea');assert.equal(idea.reviews.length,0);
  assert.equal(motion.nearby(agents,points,[],true).agents.length,3);
  assert.equal(motion.nearby(agents,points,[],false).agents.length,2);
  idea.reviews=[{runtime:'coder'}];assert.equal(motion.nearby([agents[0]],points,[idea]),null);
});
test('idle agent steers around a busy anchor instead of getting stuck against it',()=>{
 const motion=new Motion(()=>.5),points={a:{x:250,y:350},b:{x:400,y:350}},agents=[{id:'a',roaming:true},{id:'b',roaming:false}];
 for(let i=0;i<600;i++)motion.step(points,agents,1/60);
 assert.ok(Math.hypot(points.a.x-250,points.a.y-350)>50);assert.deepEqual(points.b,{x:400,y:350});
});
