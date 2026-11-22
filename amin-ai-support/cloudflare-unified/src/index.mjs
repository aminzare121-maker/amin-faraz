
import billing from "../../managed-subscriptions/src/worker.mjs";
import {aiFetch} from "./ai.mjs";
export default {
  fetch(request,env,ctx){
    if(new URL(request.url).pathname.startsWith("/api/"))return aiFetch(request,env);
    return billing.fetch(request,env,ctx);
  },
  scheduled(event,env,ctx){return billing.scheduled(event,env,ctx)}
};
