"""Real local HTTP roundtrip across Node relay and Python agent, no MT5."""
import json,os,subprocess,threading,time,unittest
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from outbound import Agent,NoRedirect

class IntegrationTest(unittest.TestCase):
    def test_browser_login_cookie_and_stop_cross_relay_once(self):
        key='integration-test-only-key-not-a-real-secret'
        calls=[]
        class Host(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.assertions=None
                raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
                if self.headers.get('Authorization')!='Bearer '+key:
                    self.send_response(401);self.end_headers();return
                calls.append((self.path,raw,self.headers.get('Cookie')))
                if self.path=='/login':
                    self.send_response(303);self.send_header('Location','/');self.send_header('Set-Cookie','mt5_session=test-only; Secure; HttpOnly; SameSite=Strict');self.end_headers()
                else:
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"running":false,"demo":true}')
        host=ThreadingHTTPServer(('127.0.0.1',0),Host)
        thread=threading.Thread(target=host.serve_forever,daemon=True);thread.start()
        env=dict(os.environ,MT5_HOST_KEY=key)
        root=Path(__file__).parent
        code="import {createRelayServer} from './relay-server.mjs'; const s=createRelayServer({key:process.env.MT5_HOST_KEY,origin:'https://bot.example'}); s.listen(0,'127.0.0.1',()=>console.log(s.address().port));"
        node=subprocess.Popen(['node','--input-type=module','-e',code],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        stop=threading.Event();runner=None
        try:
            port=int(node.stdout.readline().strip());url='http://127.0.0.1:'+str(port)
            op=build_opener(ProxyHandler({}),NoRedirect())
            class Rewrite:
                def open(self,request,**kwargs):
                    if request.full_url.startswith('https://bot.example'):
                        request=Request(request.full_url.replace('https://bot.example',url,1),data=request.data,headers=dict(request.header_items()),method=request.get_method())
                    return op.open(request,**kwargs)
            agent=Agent('https://bot.example',key,host.server_port,Rewrite())
            def loop():
                while not stop.is_set():agent.cycle();stop.wait(.02)
            agent.cycle() # First authenticated registration, no jobs.
            runner=threading.Thread(target=loop,daemon=True);runner.start()
            req=Request(url+'/login',data=b'login=demo-only&password=test-only',headers={'Origin':'https://bot.example','Content-Type':'application/x-www-form-urlencoded'},method='POST')
            try:op.open(req,timeout=4)
            except HTTPError as r:
                self.assertEqual(r.code,303);self.assertIn('HttpOnly',r.headers['Set-Cookie']);r.close()
            req=Request(url+'/api/bridge',data=b'{"action":"stop","id":"test-only-command"}',headers={'Origin':'https://bot.example','Content-Type':'application/json','Cookie':'mt5_session=test-only'},method='POST')
            with op.open(req,timeout=4) as r:self.assertFalse(json.load(r)['running'])
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1][2],'mt5_session=test-only')
        finally:
            stop.set()
            if runner:runner.join(2)
            node.terminate();node.communicate(timeout=5)
            host.shutdown();host.server_close();thread.join()

if __name__=='__main__':unittest.main()
