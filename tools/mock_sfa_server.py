"""A tiny fake SalesPro SFA for testing Hydra without touching the real system.

    python tools/mock_sfa_server.py
Then in the Setup Wizard use:  SFA URL = http://127.0.0.1:8765
                              username = binusha   password = Secret123
"""
import http.server, urllib.parse
PAGES={'/it/reports/outlet_wise_sku_sales':'OUTLET WISE SKU SALES REPORT','/it/reports/callage_summary':'CALLAGE SUMMARY','/it/pre_selling':'VIEW PRE-SELLING','/it/level-six':'VIEW TERRITORY'}
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def authed(self): return 'sess=ok' in (self.headers.get('Cookie') or '')
    def send(self,body,code=200,extra=None):
        self.send_response(code); self.send_header('Content-Type','text/html')
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body.encode())
    def do_GET(self):
        p=urllib.parse.urlparse(self.path).path
        if not self.authed():
            return self.send('<html><body><form method=post action=/login><input name=email type=text><input name=password type=password><button type=submit>Login</button></form></body></html>')
        if p in PAGES: return self.send(f'<html><body><nav>DASHBOARD REPORTS</nav><span>Welcome,</span> <b>Binusha Liyanage</b><h2>{PAGES[p]}</h2></body></html>')
        return self.send('<html><body><nav>DASHBOARD REPORTS SALES</nav><div>Welcome,\nBinusha Liyanage</div></body></html>')
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0)); d=urllib.parse.parse_qs(self.rfile.read(n).decode())
        if d.get('email',[''])[0]=='binusha' and d.get('password',[''])[0]=='Secret123':
            return self.send('',302,{'Location':'/','Set-Cookie':'sess=ok; Path=/'})
        return self.send('<html><body><p>Invalid username or password</p><form method=post action=/login><input name=email type=text><input name=password type=password><button type=submit>Login</button></form></body></html>')
if __name__ == '__main__':
    print('Mock SFA running on http://127.0.0.1:8765  (binusha / Secret123)')
    http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()
