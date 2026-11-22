import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const source=fs.readFileSync(new URL("../windows-setup/Setup-Amin-Cloudflare.mjs",import.meta.url),"utf8");
test("owner login uses Cloudflare device OAuth without localhost callback",()=>{
  assert.match(source, /run\(\["login","--device"\]\)/);
  assert.doesNotMatch(source, /run\(\["login"\]\)/);
  assert.ok(source.indexOf('run(["login","--device"])')<source.indexOf('const bill=d1('));
  assert.ok(source.includes('run(["whoami"])'));
});
