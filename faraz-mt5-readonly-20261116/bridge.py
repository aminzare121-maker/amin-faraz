import json, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>فراز امین - اتصال خواندنی</title><style>body{background:#101f32;color:#eee;font:18px Tahoma,Arial;padding:35px}main{max-width:720px;margin:auto;background:#1c3450;border-radius:14px;padding:25px}button{padding:12px;font:inherit}</style><main><h2>فراز امین | بررسی اتصال MT5</h2><p>این نسخه فقط خواندنی است و هیچ معامله‌ای انجام نمی‌دهد.</p><pre id="s">در حال بررسی...</pre><button onclick="load()">بررسی مجدد</button></main><script>async function load(){try{const r=await fetch('/api/status');const d=await r.json();document.getElementById('s').textContent=d.connected?'وضعیت: متصل\\nنوع حساب: '+d.account_mode+'\\nموجودی: '+d.balance+'\\nمعاملات باز: '+d.positions:'اتصال برقرار نشد: '+d.message}catch(e){document.getElementById('s').textContent='خطای پل محلی: '+e}}load();setInterval(load,5000)</script></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/status":
            data = {"connected":False,"message":"MT5 not connected"}
            try:
                import MetaTrader5 as mt5
                if mt5.initialize(timeout=5000):
                    try:
                        account=mt5.account_info()
                        positions=mt5.positions_get()
                        if account:
                            mode={0:"DEMO",1:"CONTEST",2:"REAL"}.get(account.trade_mode,"UNKNOWN")
                            data={"connected":True,"account_mode":mode,"balance":account.balance,"positions":len(positions) if positions is not None else None}
                        else:
                            data["message"]="Account info unavailable"
                    finally:
                        mt5.shutdown()
                else:
                    data["message"]=str(mt5.last_error())
            except Exception as exc:
                data["message"]=str(exc)
            body=json.dumps(data,ensure_ascii=False).encode("utf-8")
            mime="application/json; charset=utf-8"
        elif self.path in ("/","/index.html"):
            body=PAGE.encode("utf-8")
            mime="text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args): pass

if __name__=="__main__":
    server=ThreadingHTTPServer(("127.0.0.1",8765),Handler)
    print("Faraz read-only bridge: http://127.0.0.1:8765",flush=True)
    webbrowser.open("http://127.0.0.1:8765")
    server.serve_forever()
