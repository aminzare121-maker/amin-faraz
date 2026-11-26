import {readFileSync} from 'node:fs';
import {decide} from './manager.mjs';
try {
  const input=JSON.parse(readFileSync(process.argv[2] ?? 0,'utf8'));
  console.log(JSON.stringify(decide(input),null,2));
} catch(e) {
  console.log(JSON.stringify({mode:'SHADOW_ONLY',action:'NO_TRADE',reason:'INVALID_INPUT_OR_RUNTIME_ERROR',ordersSent:0}));
  process.exitCode=1;
}
