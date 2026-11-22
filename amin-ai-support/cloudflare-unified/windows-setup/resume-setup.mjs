/** Resume a partially completed owner deployment without changing cloud identities. */
export function resumeWranglerConfig(source,billingId,knowledgeId){
  if(typeof source!=="string")throw Error("Invalid Wrangler configuration");
  const valid=id=>typeof id==="string"&&/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id);
  if(!valid(billingId)||!valid(knowledgeId)||billingId===knowledgeId)
    throw Error("Expected two distinct valid Cloudflare D1 IDs");
  const bill="REPLACE_BILLING_DB_ID", knowledge="REPLACE_KNOWLEDGE_DB_ID";
  if(source.includes(bill)&&source.includes(knowledge))
    return source.replace(bill,billingId).replace(knowledge,knowledgeId);
  if(!source.includes("REPLACE_")&&source.includes('database_id = "'+billingId+'"')&&
     source.includes('database_id = "'+knowledgeId+'"'))return source;
  throw Error("Existing Wrangler configuration uses different D1 IDs; refusing to overwrite.");
}
export function recoverOwnerSecrets(content,endpoint){
  if(typeof content!=="string"||!content.startsWith("PRIVATE AMIN AI OWNER ACCESS"))
    throw Error("Existing private key file is unexpected; refusing to overwrite");
  if(typeof endpoint!=="string"||!/^https:\/\/[a-z0-9.-]+\.workers\.dev$/.test(endpoint)||
      !content.includes("Server HTTPS URL:\n"+endpoint+"\n"))
    throw Error("Private credentials belong to a different Worker; refusing to rotate or overwrite.");
  const get=(label)=>{
    const key=label+"\n";
    const i=content.indexOf(key);
    if(i<0)throw Error("Missing expected key in private credential file");
    return content.slice(i+key.length).split(/\r?\n/,1)[0].trim();
  };
  const owner=get("Owner key for mobile app:");
  const admin=get("Admin key for /owner console (NEVER put in mobile):");
  const enrollment=get("Customer enrollment secret (SERVER ONLY):");
  if(!/^amin_[A-Za-z0-9_-]{40,60}$/.test(owner)||
     !/^[A-Za-z0-9_-]{40,60}$/.test(admin)||
     !/^[A-Za-z0-9_-]{40,60}$/.test(enrollment))
    throw Error("Existing private credentials malformed; refusing to replace them.");
  return {owner,admin,enrollment};
}
