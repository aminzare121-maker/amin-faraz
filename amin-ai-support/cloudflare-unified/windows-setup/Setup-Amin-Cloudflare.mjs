import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import readline from "node:readline/promises";

const root=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,"$1"));
const worker=path.join(root,"amin-ai-support","cloudflare-unified");
const billing=path.join(root,"amin-ai-support","managed-subscriptions");
const privateDir=path.join(process.env.LOCALAPPDATA||os.homedir(),"AminAI");
const privatePath=path.join(privateDir,"OwnerAccess-PRIVATE.txt");
const statusPath=path.join(privateDir,"Cloudflare-Setup-Status.txt");
const npx=process.platform==="win32"?"npx.cmd":"npx";
const log=[];
function report(s){ console.log(s); log.push(s); }
function fail(s){throw Error(s);}
function run(args,{capture=false,input}={}){
  const opts={cwd:worker,encoding:"utf8",shell:process.platform==="win32",
    stdio:input===undefined?["inherit",capture?"pipe":"inherit","inherit"]:["pipe",capture?"pipe":"inherit","inherit"]};
  if(input!==undefined)opts.input=input;
  const r=spawnSync(npx,["--yes","wrangler@4",...args],opts);
  if(r.error)fail("Cannot run Cloudflare Wrangler: "+r.error.message);
  if(r.status!==0)fail("Cloudflare command failed: "+args.join(" ")+" ("+r.status+")");
  return capture?r.stdout:"";
}
function databases(){
  const result=run(["d1","list","--json"],{capture:true});
  const first=result.indexOf("["),last=result.lastIndexOf("]");
  if(first<0||last<first)fail("Cloudflare did not return a D1 JSON list");
  const entries=JSON.parse(result.slice(first,last+1));
  if(!Array.isArray(entries))fail("D1 list was not an array");
  return entries;
}
function d1(name){
  let item=databases().find(x=>x.name===name);
  if(!item){report("Creating database "+name);run(["d1","create",name]);item=databases().find(x=>x.name===name);}
  const id=item?.uuid||item?.id||item?.database_id;
  if(typeof id!=="string"||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id))fail("Cannot verify D1 database id: "+name);
  return id;
}
function randomSecret(){return crypto.randomBytes(42).toString("base64url");}
function notePrivate(text){
  fs.mkdirSync(privateDir,{recursive:true});
  fs.writeFileSync(privatePath,text,{mode:0o600});
  if(process.platform==="win32"){
    const rule=process.env.USERNAME+":(R,W)";
    const x=spawnSync("icacls.exe",[privatePath,"/inheritance:r","/grant:r",rule],{stdio:"ignore",shell:true});
    if(x.status!==0)report("Warning: Windows permissions could not be further restricted.");
  }
}
async function main(){
  report("Amin AI Cloudflare deployment - owner authorization required.");
  report("No card payment, no Google Pay access, no customer sales.");
  const configPath=path.join(worker,"wrangler.toml");
  if(!fs.existsSync(configPath)||!fs.existsSync(path.join(billing,"db","schema.sql")))
    fail("Missing source files. Extract the FULL ZIP first.");
  if(fs.existsSync(privatePath))fail("Existing owner key file found. Refusing to overwrite private access.");
  if(process.platform!=="win32")fail("This installer is intended for Windows 11.");
  const nodeMajor=Number(process.versions.node.split(".")[0]);
  if(nodeMajor<20)fail("Node.js 20+ required. Official installer: https://nodejs.org/en/download");
  report("Cloudflare free signup: https://dash.cloudflare.com/sign-up");
  report("You must have an eligible Cloudflare Free account and allow Wrangler login.");
  const terminal=readline.createInterface({input:process.stdin,output:process.stdout});
  const answer=await terminal.question("Type YES to allow creation of 2 D1 databases and 1 Worker in your Cloudflare account: ");
  terminal.close();
  if(answer!=="YES")fail("Owner did not authorize deployment.");
  run(["--version"]);
  run(["login"]);
  run(["whoami"]);
  const bill=d1("amin-managed-subscriptions");
  const knowledge=d1("amin-ai-knowledge");
  const toml=fs.readFileSync(configPath,"utf8");
  if(!toml.includes("REPLACE_BILLING_DB_ID")||!toml.includes("REPLACE_KNOWLEDGE_DB_ID"))
    fail("Expected original empty Wrangler database placeholders.");
  fs.writeFileSync(configPath,toml.replace("REPLACE_BILLING_DB_ID",bill).replace("REPLACE_KNOWLEDGE_DB_ID",knowledge));
  run(["d1","execute","DB","--remote","--file=../managed-subscriptions/db/schema.sql","--yes"]);
  run(["d1","execute","KNOWLEDGE_DB","--remote","--file=db/ai-schema.sql","--yes"]);
  report("Deploying Worker. Payments are OFF by default.");
  const deployed=run(["deploy"],{capture:true});
  const found=deployed.match(/https:\/\/[a-zA-Z0-9.-]+\.workers\.dev/);
  if(!found)fail("Cloudflare URL not found. Check Cloudflare dashboard; do not guess its value.");
  const endpoint=found[0];
  const owner="amin_"+randomSecret();
  const admin=randomSecret();
  const enrollment=randomSecret();
  // Save keys LOCALLY before uploading, to preserve recovery on partial failures.
  notePrivate("PRIVATE AMIN AI OWNER ACCESS - DO NOT SHARE\n"+
    "STATUS: NOT VERIFIED UNTIL /api/health PASSES\n"+
    "Server HTTPS URL:\n"+endpoint+"\nOwner key for mobile app:\n"+owner+
    "\nAdmin key for /owner console (NEVER put in mobile):\n"+admin+
    "\nCustomer enrollment secret (SERVER ONLY):\n"+enrollment+
    "\nCustomer billing and Google Pay charges: OFF\n");
  for(const [name,secret] of [
    ["AMIN_OWNER_TOKEN",owner],["OWNER_ADMIN_TOKEN",admin],["CUSTOMER_ENROLLMENT_SECRET",enrollment]
  ])run(["secret","put",name],{input:secret+"\n"});
  let health;
  try{
    const resp=await fetch(endpoint+"/api/health",{signal:AbortSignal.timeout(20000)});
    health=resp.ok?await resp.json():null;
  }catch(e){report("Unable to test the live endpoint from this computer: "+e.message);}
  if(!health?.configured)fail("Live Cloudflare AI/D1 bindings unverified. Private key saved locally for recovery; do NOT claim success.");
  notePrivate("PRIVATE AMIN AI OWNER ACCESS - DO NOT SHARE\n"+
    "STATUS: Cloudflare /api/health configured=true (real chat still requires a question)\n"+
    "Server HTTPS URL:\n"+endpoint+"\nOwner key for mobile app:\n"+owner+
    "\nAdmin key for /owner console (NEVER put in mobile):\n"+admin+
    "\nCustomer enrollment secret (SERVER ONLY):\n"+enrollment+
    "\nCustomer billing and Google Pay charges: OFF\n");
  report("Cloudflare AI endpoint configured: "+endpoint);
  report("PRIVATE mobile owner key saved to: "+privatePath);
  report("Paste endpoint and owner key into the 2 fields on your phone.");
  spawnSync("notepad.exe",[privatePath],{stdio:"ignore",shell:false});
}
main().catch(error=>{report("STOP: "+error.message);process.exitCode=1;}).finally(()=>{
  try{fs.mkdirSync(privateDir,{recursive:true});fs.writeFileSync(statusPath,log.join("\r\n")+"\r\n");}
  catch{}
  report("Diagnostic status file (no keys): "+statusPath);
});
