// Separate Render start command for the hosted pilot; default v4 server is unchanged.
import http from 'node:http';
const target = new URL(process.env.MT5_HOST_URL || 'http://invalid');
const key = process.env.MT5_HOST_KEY || '';
const origin = process.env.PUBLIC_URL || process.env.RENDER_EXTERNAL_URL;
if (target.protocol !== 'https:' || !/^[-a-z0-9]+\.trycloudflare\.com$/.test(target.hostname)
    || target.username || target.password || target.port || target.pathname !== '/' || target.search || target.hash
    || key.length < 32 || !origin || new URL(origin).origin !== origin) {
  throw Error('Configurer MT5_HOST_URL, MT5_HOST_KEY et PUBLIC_URL pour le pilote heberge.');
}
const allowed = new Set(['/','/login','/logout','/health','/control.html','/control.css','/control.js','/guide.css','/api/bridge','/lab/index.html','/lab/app.js','/lab/style.css','/lab/engine.js','/lab/worker.js','/lab/demo.csv']);
http.createServer(async (req, res) => {
  const fail = (status, error) => {res.writeHead(status, {'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({error}));};
  try {
    if (!['GET','POST'].includes(req.method)) return fail(405,'Methode refusee.');
    const url = new URL(req.url, origin);
    if (!allowed.has(url.pathname)) return fail(404,'Introuvable.');
    if (req.method === 'POST' && req.headers.origin !== origin) return fail(403,'Origine refusee.');
    let size = 0; const chunks = [];
    for await (const chunk of req) {size += chunk.length; if (size > 4096) return fail(413,'Requete trop grande.'); chunks.push(chunk);}
    const headers = new Headers({Authorization:'Bearer '+key});
    for (const name of ['cookie','content-type','origin']) if (req.headers[name]) headers.set(name,req.headers[name]);
    const body = Buffer.concat(chunks);
    const response = await fetch(target.origin + url.pathname + url.search, {
      method:req.method, headers, body:req.method === 'POST' ? body : undefined,
      redirect:'manual', signal:AbortSignal.timeout(28000)
    });
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (!location || !['/','/login'].includes(location)) return fail(502,'Redirection refusee.');
    }
    const out = {'Cache-Control':'no-store','Referrer-Policy':'same-origin','X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff'};
    for (const name of ['content-type','set-cookie','location']) if (response.headers.has(name)) out[name] = response.headers.get(name);
    let received = 0; const parts = [];
    if (response.body) for await (const chunk of response.body) {
      received += chunk.length;
      if (received > 3000000) return fail(502,'Reponse trop grande.');
      parts.push(Buffer.from(chunk));
    }
    const data = Buffer.concat(parts);
    res.writeHead(response.status,out);res.end(data);
  } catch {if (!res.headersSent) fail(503,'Serveur MT5 indisponible. Verifie le portable de Ben.'); else res.end();}
}).listen(Number(process.env.PORT || 3000),'0.0.0.0');
