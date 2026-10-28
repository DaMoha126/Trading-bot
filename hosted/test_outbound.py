import base64,io,json,threading,time,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import build_opener,ProxyHandler
from urllib.error import URLError
from outbound import Agent,NoRedirect,RelayHTTPError,diagnostic

class Local(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*args):pass
    def do_GET(self):
        self.calls.append((self.path,self.headers.get('Authorization'),None))
        self.send_response(303);self.send_header('Location','/login');self.send_header('Set-Cookie','mt5_session=test; Secure; HttpOnly; SameSite=Strict');self.end_headers()
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
        self.calls.append((self.path,self.headers.get('Authorization'),raw))
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"running":false}')

class OutboundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Local)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        Local.calls=[]
        self.a=Agent('https://bot.example','test-key-only'*4,self.server.server_port)
    def job(self,**values):
        return dict(id='example-job',method='GET',path='/login',headers={},body='',deadline=25000,serverTime=0,**values)
    def test_diagnostics_distinguish_key_network_and_hide_secrets(self):
        self.assertIn('401',diagnostic(RelayHTTPError(401)))
        self.assertIn('autre liaison',diagnostic(RelayHTTPError(409)))
        self.assertIn('réseau',diagnostic(URLError('test-only-private-value')))
        self.assertNotIn('test-only-private-value',diagnostic(ValueError('Bearer test-only-private-value')))

    def test_cookie_redirect_and_auth_forwarding(self):
        out=self.a.forward(self.job())
        self.assertEqual(out['status'],303);self.assertIn('HttpOnly',out['headers']['set-cookie'])
        self.assertEqual(len(Local.calls),1);self.assertEqual(Local.calls[0][1],'Bearer '+self.a.key)
    def test_post_origin_body(self):
        j=self.job();j.update(method='POST',path='/api/bridge',headers={'origin':'https://bot.example'},body=base64.b64encode(b'{"action":"stop"}').decode())
        out=self.a.forward(j);self.assertEqual(out['status'],200);self.assertEqual(Local.calls[0][2],b'{"action":"stop"}')
    def test_no_duplicate_dispatch(self):
        j=self.job();self.a.forward(j)
        with self.assertRaises(ValueError):self.a.forward(j)
        self.assertEqual(len(Local.calls),1)
    def test_local_error_is_not_retried(self):
        class Broken:
            count=0
            def open(self,*a,**kw):self.count+=1;raise URLError('simulated connection drop')
        op=Broken();j=self.job()
        with self.assertRaises(URLError):self.a.forward(j,op)
        with self.assertRaises(ValueError):self.a.forward(j,op)
        self.assertEqual(op.count,1)
    def test_no_ssrf_or_private_routes(self):
        for i,path in enumerate(('http://evil.example/','//evil.example/','/hosted/accounts.json','/api/bridge#secret')):
            j=self.job();j.update(id=str(i),path=path)
            with self.assertRaises(ValueError):self.a.forward(j)
        self.assertEqual(Local.calls,[])
    def test_expired_or_cross_origin_requests_rejected(self):
        j=self.job();j['deadline']=1000
        with self.assertRaises(ValueError):self.a.forward(j)
        j=self.job();j.update(id='other',method='POST',headers={'origin':'https://evil.example'})
        with self.assertRaises(ValueError):self.a.forward(j)
        self.assertEqual(Local.calls,[])
    def test_cycle_reports_ambiguous_error_without_replay(self):
        class Cycle(Agent):
            def __init__(self):super().__init__('https://bot.example','k'*40);self.result=None;self.reads=0
            def remote(self,path,body=None):
                if path=='/relay/poll':self.reads+=1;return dict(id='once',path='/hosted/secret',method='GET',headers={},body='',deadline=25000,serverTime=0)
                self.result=body
        a=Cycle();a.cycle();self.assertEqual(a.result['status'],502)
        self.assertIn('Résultat inconnu',json.loads(base64.b64decode(a.result['body']))['error'])

if __name__=='__main__':unittest.main()
