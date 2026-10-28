"""Outbound-only transport for the existing local MT5 HTTP service.

No MT5 imports, no trading logic, no credentials on disk. Use the same
MT5_HOST_KEY and PUBLIC_URL environment as hosted/host.py. Payloads and keys
are never logged. In-flight browser requests are NEVER retried after errors.
"""
import base64
from collections import deque
import json
import os
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

ALLOWED={'/','/login','/logout','/control.html','/control.css','/control.js','/guide.css','/api/bridge','/lab/index.html','/lab/app.js','/lab/style.css','/lab/engine.js','/lab/worker.js','/lab/demo.csv'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def configuration():
    key=os.environ.get('MT5_HOST_KEY','')
    origin=os.environ.get('PUBLIC_URL','').rstrip('/')
    u=urlsplit(origin)
    if len(key)<32 or u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment:
        raise ValueError('Définir MT5_HOST_KEY (32 caractères minimum) et PUBLIC_URL HTTPS comme pour le service MT5.')
    port=int(os.environ.get('MT5_HOST_PORT','8770'))
    if not 1<=port<=65535:raise ValueError('Port local invalide.')
    return origin,key,port

class Agent:
    def __init__(self, origin, key, port=8770, opener=None):
        self.origin=origin;self.key=key;self.port=port;self.agent=str(uuid.uuid4())
        self.opener=opener or build_opener(ProxyHandler({}),NoRedirect())
        self.seen=set();self.order=deque()

    def remote(self,path,body=None):
        raw=json.dumps(body,separators=(',',':')).encode() if body is not None else None
        headers={'Authorization':'Bearer '+self.key,'X-Relay-Agent':self.agent,'Content-Type':'application/json'}
        request=Request(self.origin+path,data=raw,headers=headers,method='POST' if raw is not None else 'GET')
        started=time.monotonic()
        try:
            with self.opener.open(request,timeout=30) as response:
                if response.status==204:return None
                data=response.read(65537)
                if len(data)>65536:raise ValueError('Réponse de liaison trop grande.')
                if path=='/relay/result':return None
                job=json.loads(data)
                job['_poll_ms']=(time.monotonic()-started)*1000
                job['_received_at']=time.monotonic()
                return job
        except HTTPError as ex:
            # Never follow a remote redirect with the private key.
            raise ValueError('Liaison refusée par Render (HTTP '+str(ex.code)+').') from None

    def forward(self, job, local_opener=None):
        ident=job.get('id')
        if not isinstance(ident,str) or ident in self.seen:raise ValueError('Requête dupliquée ou invalide, aucun renvoi.')
        # Consume before local I/O. Any ambiguity must be inspected, not retried.
        self.seen.add(ident);self.order.append(ident)
        if len(self.order)>1024:self.seen.discard(self.order.popleft())
        path=job.get('path','');parsed=urlsplit(path)
        if (not path.startswith('/') or path.startswith('//') or parsed.scheme or parsed.netloc
            or parsed.fragment or parsed.path not in ALLOWED or len(path)>2048):raise ValueError('Route de liaison refusée.')
        method=job.get('method')
        if method not in ('GET','POST'):raise ValueError('Méthode refusée.')
        if (not isinstance(job.get('deadline'),(int,float)) or not isinstance(job.get('serverTime'),(int,float))
            or job['deadline']-job['serverTime']<2000):raise ValueError('Requête expirée, aucun envoi.')
        remaining=job['deadline']-job['serverTime']-job.get('_poll_ms',0)-(time.monotonic()-job.get('_received_at',time.monotonic()))*1000
        if remaining<2000:raise ValueError('Requête reçue trop tard, aucun envoi.')
        body=base64.b64decode(job.get('body',''),validate=True)
        if len(body)>4096:raise ValueError('Requête trop grande.')
        headers={'Authorization':'Bearer '+self.key}
        for name in ('cookie','content-type','origin'):
            value=job.get('headers',{}).get(name)
            if value is not None:
                if not isinstance(value,str) or len(value)>16000 or '\r' in value or '\n' in value:raise ValueError('En-tête invalide.')
                headers[name]=value
        if method=='POST' and headers.get('origin')!=self.origin:raise ValueError('Origine refusée.')
        request=Request('http://127.0.0.1:'+str(self.port)+path,data=body if method=='POST' else None,headers=headers,method=method)
        op=local_opener or self.opener
        try:
            response=op.open(request,timeout=20)
        except HTTPError as error:response=error
        with response:
            data=response.read(3000001)
            if len(data)>3000000:raise ValueError('Réponse locale trop grande.')
            result_headers={name:response.headers[name] for name in ('content-type','set-cookie','location') if name in response.headers}
            return dict(id=ident,status=response.code,headers=result_headers,body=base64.b64encode(data).decode('ascii'))

    def cycle(self):
        job=self.remote('/relay/poll')
        if job is None:return
        try: result=self.forward(job)
        except (ValueError,OSError,URLError):
            result=dict(id=job.get('id'),status=502,headers={'content-type':'application/json'},
                        body=base64.b64encode(json.dumps({'error':'Réponse du service local non reçue. Résultat inconnu : vérifier MT5 avant toute nouvelle commande.'}).encode()).decode())
        self.remote('/relay/result',result)

def main():
    origin,key,port=configuration()
    agent=Agent(origin,key,port)
    print('Liaison sortante vers Render. Aucun bot démarré. Garde cette fenêtre ouverte.',flush=True)
    interrupted=False
    while True:
        try:
            agent.cycle()
            if interrupted:print('Liaison rétablie. Aucune commande antérieure rejouée.',flush=True)
            interrupted=False
            time.sleep(1)
        except (OSError,ValueError,URLError):
            if not interrupted:print('Liaison indisponible : reconnexion automatique. Vérifier MT5 avant de renvoyer une commande.',flush=True)
            interrupted=True
            time.sleep(5)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('Liaison arrêtée. Le service MT5 conserve son état ; aucun ordre de trading envoyé par cet arrêt.')
    except (ValueError,OSError) as ex:raise SystemExit(str(ex))
