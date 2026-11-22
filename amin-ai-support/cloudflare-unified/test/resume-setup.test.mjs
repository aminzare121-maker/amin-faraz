import test from "node:test";
import assert from "node:assert/strict";
import { resumeWranglerConfig, recoverOwnerSecrets } from "../windows-setup/resume-setup.mjs";
import fs from "node:fs";
const script=fs.readFileSync(new URL("../windows-setup/Setup-Amin-Cloudflare.mjs",import.meta.url),"utf8");
const bill="12345678-1234-1234-1234-123456789012";
const knowledge="87654321-4321-4321-4321-210987654321";
test("resume same D1 IDs without rebuilding or resetting existing databases",()=>{
  const first=resumeWranglerConfig('[[d1_databases]]\nbinding = "DB"\ndatabase_id = "REPLACE_BILLING_DB_ID"\n[[d1_databases]]\nbinding = "KNOWLEDGE_DB"\ndatabase_id = "REPLACE_KNOWLEDGE_DB_ID"',bill,knowledge);
  assert.equal(resumeWranglerConfig(first,bill,knowledge),first);
  assert.throws(()=>resumeWranglerConfig(first,knowledge,bill),/different D1 IDs/);
  assert.throws(()=>resumeWranglerConfig(first,bill,bill),/two distinct/);
});
test("resume private owner keys for the same Worker, never a different host",()=>{
  const endpoint="https://amin-ai-unified.example.workers.dev";
  const file="PRIVATE AMIN AI OWNER ACCESS - DO NOT SHARE\nServer HTTPS URL:\n"+endpoint+"\nOwner key for mobile app:\namin_"+ "x".repeat(42)+"\nAdmin key for /owner console (NEVER put in mobile):\n"+ "a".repeat(56)+"\nCustomer enrollment secret (SERVER ONLY):\n"+ "b".repeat(56)+"\n";
  assert.equal(recoverOwnerSecrets(file,endpoint).owner,"amin_"+"x".repeat(42));
  assert.throws(()=>recoverOwnerSecrets(file,"https://wrong.workers.dev"),/different Worker/);
});
test("Windows installer reuses account OAuth and retries failed D1 request",()=>{
  assert.ok(script.includes('run(["whoami"],{capture:true})'));
  assert.ok(script.includes('run(["login","--device"])'));
  assert.ok(script.includes('for(let attempt=1;attempt<=3;attempt++)'));
  assert.ok(script.includes('recoverOwnerSecrets('));
});
