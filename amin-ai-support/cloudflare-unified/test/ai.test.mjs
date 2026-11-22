
import test from "node:test";
import assert from "node:assert/strict";
import unified from "../src/index.mjs";
const owner="amin_"+"A".repeat(44),customer="amin_"+"C".repeat(44);
function env(active=true){
  const activity={inference:0,privateNotesQueried:false};
  const statement=sql=>({bind(...values){
    return {
      first:async()=>{
        if(sql.includes("FROM customers"))return {id:"customer-id",enabled:1};
        if(sql.includes("FROM invoices"))return active?{id:"paid-order"}:null;
      },
      all:async()=>({results:[]}),
      run:async()=>({meta:{changes:1}})
    };
  }});
  return {
    DB:{prepare:statement},KNOWLEDGE_DB:{prepare:statement},
    AMIN_OWNER_TOKEN:owner,CUSTOMER_ENROLLMENT_SECRET:"x".repeat(40),
    AI:{run:async()=>{activity.inference++;return {response:"پاسخ فارسی آزمایشی"};}},
    activity
  };
}
function req(path,token,body){
  return new Request("https://unified.example"+path,{
    method:body?"POST":"GET",
    headers:{Authorization:"Bearer "+token,"Content-Type":"application/json"},
    body:body?JSON.stringify(body):undefined
  });
}
test("one endpoint exposes only support to paying customers, owner has all programs",async()=>{
  const e=env();
  const own=await unified.fetch(req("/api/projects",owner),e);
  assert.equal((await own.json()).projects.length,6);
  const client=await unified.fetch(req("/api/projects",customer),e);
  assert.deepEqual((await client.json()).projects.map(p=>p.id),["support"]);
});
test("model requires explicit consent plus real subscription",async()=>{
  const e=env();
  const v={project:"support",message:"سلام",external_model_consent:false};
  let r=await unified.fetch(req("/api/chat",customer,v),e);assert.equal(r.status,409);
  assert.equal(e.activity.inference,0);
  r=await unified.fetch(req("/api/chat",customer,{...v,external_model_consent:true}),e);
  assert.equal(r.status,200);
  assert.equal((await r.json()).model_used,true);assert.equal(e.activity.inference,1);
});
test("expired subscription, private programs, and owner notes protected",async()=>{
  const inactive=env(false);
  let r=await unified.fetch(req("/api/chat",customer,{project:"support",message:"سلام",external_model_consent:true}),inactive);
  assert.equal(r.status,402);assert.equal(inactive.activity.inference,0);
  const e=env();
  r=await unified.fetch(req("/api/chat",customer,{project:"faraz",message:"سلام",external_model_consent:true}),e);
  assert.equal(r.status,403);
  r=await unified.fetch(req("/api/admin/notes",customer,{project:"support",title:"مدرک",content:"متن آزمایشی کافی"}),e);
  assert.equal(r.status,403);
});
test("owner writes approved note private by default",async()=>{
 const e=env();
 const r=await unified.fetch(req("/api/admin/notes",owner,{
   project:"support",title:"مدرک جدید",content:"نمونه متن مستند برای آزمایش."
 }),e);
 assert.equal(r.status,200);assert.equal((await r.json()).customer_visible,false);
});
test("billing on same host never creates fictional paid status",async()=>{
 const e=env();
 const r=await unified.fetch(req("/health",owner),e);
 assert.equal((await r.json()).automatic_google_pay_charge,false);
});
