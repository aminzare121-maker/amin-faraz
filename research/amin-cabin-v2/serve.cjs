// Local static preview only. Explicit allowlist; cannot read files outside this prototype.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const files={'/':'index.html','/index.html':'index.html','/model.js':'model.js','/app.js':'app.js','/style.css':'style.css'};
http.createServer((req,res)=>{const name=files[req.url];if(req.method!=='GET'||!name){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html; charset=utf-8');res.setHeader('Cache-Control','no-store');res.end(fs.readFileSync(path.join(__dirname,name)));}).listen(8769,'127.0.0.1',()=>console.log('Offline preview: http://127.0.0.1:8769 ; Ctrl+C to stop'));
