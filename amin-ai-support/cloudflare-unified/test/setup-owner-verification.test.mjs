import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const source=fs.readFileSync(new URL("../windows-setup/Setup-Amin-Cloudflare.mjs",import.meta.url),"utf8");
test("owner setup checks real /api/chat before declaring success",()=>{
 assert.ok(source.includes('endpoint+"/api/chat"'));
 assert.ok(source.includes('liveChat?.model_used!==true'));
 assert.ok(source.includes('external_model_consent:true'));
 assert.ok(source.includes('if(!health?.configured)'));
 assert.ok(source.includes('Keys are in the local PRIVATE file for recovery'));
 assert.ok(!source.includes("your-support-server.example"));
});
