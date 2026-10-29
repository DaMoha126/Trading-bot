"""Windows pilot: MT5 credentials -> isolated demo worker -> opaque browser session.

Operator prepares each terminal. Bind loopback only; expose through authenticated proxy.
No automatic provisioning, no real accounts, no automatic trading at login.
"""
from collections import deque
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'


def identity(login, server):
    if not re.fullmatch(r'[0-9]{1,18}', str(login)):
        raise ValueError('Identifiant MT5 invalide.')
    if not isinstance(server, str) or not re.fullmatch(r'[A-Za-z0-9._ -]{1,100}', server):
        raise ValueError('Serveur invalide.')
    return f'{int(login)}@{server}'


def load_accounts(path):
    rows = json.loads(Path(path).read_text(encoding='utf8'))
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
        raise ValueError('Configurer de 1 a 10 comptes demo pour ce pilote.')
    accounts, terminals = {}, set()
    for row in rows:
        key = identity(row['login'], row['server'])
        terminal = Path(row['terminal']).resolve()
        if terminal.name.lower() != 'terminal64.exe' or not terminal.is_file():
            raise ValueError('Chemin terminal64.exe invalide.')
        normalized = os.path.normcase(str(terminal))
        if key in accounts or normalized in terminals:
            raise ValueError('Chaque compte doit avoir un terminal dedie unique.')
        accounts[key] = dict(login=str(int(row['login'])), server=row['server'], terminal=str(terminal))
        terminals.add(normalized)
    return accounts


def prepare_pool(path, data_root):
    """Prepare capacity once from a clean operator-provided terminal, never copy accounts/EAs."""
    config = json.loads(Path(path).read_text(encoding='utf8'))
    template = Path(config['template']).resolve()
    count = config.get('capacity', 2)
    servers = config.get('servers', [])
    if (not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 10
            or not isinstance(servers, list) or not 1 <= len(servers) <= 30):
        raise ValueError('Configurer 1 a 10 places et les serveurs demo pris en charge.')
    for server in servers:
        identity('1', server)
    source = template / 'terminal64.exe'
    if not source.is_file():
        raise ValueError('Le modele doit contenir terminal64.exe.')
    root = Path(data_root).resolve() / 'terminals'
    if template == root or root in template.parents or template in root.parents:
        raise ValueError('Le modele et les instances doivent etre dans des dossiers distincts.')
    slots = []
    for index in range(count):
        folder = root / f'slot-{index + 1:02}'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'terminal64.exe'
        if not target.exists():
            temp = folder / 'terminal64.exe.tmp'
            shutil.copyfile(source, temp)
            os.replace(temp, target)
        # Only server discovery metadata, not accounts.dat, profiles, logs, or Expert Advisors.
        metadata = template / 'Config' / 'servers.dat'
        if metadata.is_file() and not (folder / 'Config' / 'servers.dat').exists():
            (folder / 'Config').mkdir(exist_ok=True)
            shutil.copyfile(metadata, folder / 'Config' / 'servers.dat')
        slots.append({'terminal': str(target), 'servers': list(servers)})
    return slots


class Actor:
    def __init__(self, config, password, data_root):
        tenant = hashlib.sha256(identity(config['login'], config['server']).encode()).hexdigest()
        self.lock = threading.Lock()
        self.salt = secrets.token_bytes(16)
        self.digest = self.password_digest(password)
        self.process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'hosted' / 'worker.py')],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf8')
        try:
            self.rpc({**config, 'password': password, 'data': str(data_root / tenant)})
        except Exception:
            self.process.kill()
            self.process.wait()
            raise

    def password_digest(self, password):
        return hashlib.scrypt(password.encode(), salt=self.salt, n=16384, r=8, p=1)

    def verify(self, password):
        return hmac.compare_digest(self.digest, self.password_digest(password))

    def rpc(self, request):
        with self.lock:
            if self.process.poll() is not None:
                raise ValueError('Instance MT5 arretee. Contacter l administrateur.')
            self.process.stdin.write(json.dumps(request) + '\n')
            self.process.stdin.flush()
            # Dedicated child can block in native MT5 calls: limit each RPC without retrying orders.
            result = []
            reader = threading.Thread(target=lambda: result.append(self.process.stdout.readline()), daemon=True)
            reader.start()
            reader.join(25)
            if reader.is_alive() or not result or not result[0]:
                self.process.kill()
                self.process.wait()
                raise ValueError('Reponse MT5 incertaine : instance arretee. Verifier MT5 avant toute reprise.')
            reply = json.loads(result[0])
            if not reply.get('ok'):
                raise ValueError(reply.get('error', 'Commande refusee.'))
            return reply.get('data', {})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)


class Hub:
    def __init__(self, accounts, data_root, actor_factory=Actor, pool=None):
        self.accounts = dict(accounts)
        self.data_root = Path(data_root)
        self.pool = pool or []
        self.registry = self.data_root / 'assignments.json'
        if self.pool and self.registry.exists():
            saved = json.loads(self.registry.read_text(encoding='utf8'))
            if not isinstance(saved, dict):
                raise ValueError('Registre invalide : ne pas le supprimer pour liberer des places.')
            known = {slot['terminal']: slot['servers'] for slot in self.pool}
            used = {row['terminal'] for row in self.accounts.values()}
            for key, row in saved.items():
                if (not isinstance(row, dict) or key != identity(row.get('login', ''), row.get('server', ''))
                        or row.get('terminal') not in known or row['server'] not in known[row['terminal']]
                        or row['terminal'] in used or key in self.accounts):
                    raise ValueError('Registre incompatible avec la capacite configuree.')
                self.accounts[key] = {k: row[k] for k in ('login', 'server', 'terminal')}
                used.add(row['terminal'])
        self.actor_factory = actor_factory
        self.actors = {}
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.RLock()
        self.session_lock = threading.RLock()

    def login(self, login, server, password):
        key = identity(login, server)
        if not isinstance(password, str) or not 1 <= len(password) <= 256:
            raise ValueError('Identifiants invalides.')
        with self.lock:
            now = time.time()
            self.attempts = {k: v for k, v in self.attempts.items() if v and v[-1] > now - 300}
            for bucket in ('global', 'account:' + key):
                history = self.attempts.setdefault(bucket, deque())
                while history and history[0] <= now - 300:
                    history.popleft()
                if len(history) >= (30 if bucket == 'global' else 5):
                    raise ValueError('Trop de tentatives. Reessayer dans cinq minutes.')
                history.append(now)
            config = self.accounts.get(key)
            newly_assigned = False
            if not config and self.pool:
                used = {row['terminal'] for row in self.accounts.values()}
                slot = next((s for s in self.pool if s['terminal'] not in used and server in s['servers']), None)
                if slot is None:
                    raise ValueError('Aucune place disponible pour ce serveur. Reessayer plus tard.')
                config = {'login': str(int(login)), 'server': server, 'terminal': slot['terminal']}
                newly_assigned = True
            if not config:
                raise ValueError('Connexion refusee. Verifier les identifiants ou contacter l administrateur.')
            actor = self.actors.get(key)
            if actor:
                if actor.process.poll() is not None:
                    # Do not reset risk or silently retry an uncertain execution.
                    raise ValueError('Instance arretee. Une verification administrateur est requise.')
                if not actor.verify(password):
                    raise ValueError('Identifiants invalides.')
            else:
                actor = self.actor_factory(config, password, self.data_root)
                if newly_assigned:
                    try:
                        self.data_root.mkdir(parents=True, exist_ok=True)
                        updated = {**self.accounts, key: config}
                        temp = self.registry.with_suffix('.tmp')
                        with temp.open('w', encoding='utf8') as file:
                            json.dump(updated, file)
                            file.flush()
                            os.fsync(file.fileno())
                        os.replace(temp, self.registry)
                        self.accounts[key] = config
                    except Exception:
                        actor.close()
                        raise
                with self.session_lock:
                    self.actors[key] = actor
            with self.session_lock:
                self.sessions = {s: v for s, v in self.sessions.items() if v[1] > now}
                if len(self.sessions) >= 256:
                    raise ValueError('Nombre maximal de sessions atteint.')
                token = secrets.token_urlsafe(32)
                self.sessions[token] = (key, now + 12 * 3600)
            return token

    def actor(self, token):
        # A new MT5 login can take seconds; do not block existing accounts' heartbeats.
        with self.session_lock:
            row = self.sessions.get(token)
            if not row or row[1] <= time.time():
                self.sessions.pop(token, None)
                return None
            return self.actors.get(row[0])

    def logout(self, token):
        with self.session_lock:
            self.sessions.pop(token, None)

    def close(self):
        for actor in self.actors.values():
            actor.close()


LOGIN = '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trading Bot · Connexion MT5</title><style>body{margin:0;background:#050907;color:#e9e7d9;font:15px system-ui;display:grid;min-height:100vh;place-items:center}main{box-sizing:border-box;width:min(430px,92vw);padding:30px;border:1px solid #665730;border-radius:16px}h1{color:#dfc16b}label{display:block;margin:18px 0}input,button{box-sizing:border-box;width:100%;padding:13px;border-radius:6px;margin-top:7px}input{background:#111911;color:white;border:1px solid #46503b}button{background:#41d9ae;border:0;font-weight:bold}p{font-size:13px;line-height:1.7;color:#b6c3af}.error{color:#ffb1ab}</style><main><h1>Trading Bot</h1><p>Relie ton compte MT5 démo. Le moteur fonctionne sur le serveur MT5 : aucune installation sur ton téléphone.</p>ERROR<form action="/login" method="post"><label>Identifiant MT5<input name="login" inputmode="numeric" pattern="[0-9]{1,18}" maxlength="18" autocomplete="username" required></label><label>Serveur du courtier<input name="server" maxlength="100" placeholder="Exemple : Deriv-Demo" required></label><label>Mot de passe de trading MT5<input name="password" type="password" maxlength="256" autocomplete="current-password" required></label><button>Connecter mon compte →</button></form><p>Pilote démo USD uniquement. Ton compte doit être préparé par l’administrateur. Aucun ordre n’est lancé à la connexion.</p></main></html>'''


LOGIN = LOGIN.replace('Ton compte doit être préparé par l’administrateur.', 'Attribution automatique selon les places et serveurs disponibles.')


def dashboard():
    html = (PUBLIC / 'control.html').read_text(encoding='utf8')
    html = html.replace('EUR/USD', 'XAU/USD').replace('EURUSD', 'XAUUSD')
    html = html.replace('<a class="download" href="/lab/index.html?source=mt5">Tester l’historique M3 du compte ↗</a>', '<span class="hint">Backtest XAUUSD non disponible : le laboratoire Forex ne convient pas à l’or.</span>')
    # Retain hidden legacy DOM IDs for control.js, but remove local-connector instructions.
    html = re.sub(r'<details class="first-run-guide".*?(?=<section class="account-status">)', '', html, count=1)
    html = re.sub(r'<section class="rules".*?</section>', '', html, count=1)
    html = html.replace('<section class="panel setup" id="setup">', '<section class="panel setup" id="setup" hidden>')
    html = html.replace('<head>', '<head><style>#setup,#guide,#remove-account,footer a[href="#guide"],a[href="#setup"]{display:none!important}</style>')
    html = html.replace('Le PC et MT5 doivent rester ouverts.', 'Le serveur MT5 doit rester actif.')
    html = html.replace('Le PC, MT5 et le connecteur doivent rester ouverts.', 'Le serveur MT5 doit rester actif.')
    html = html.replace('<main id="dashboard">', '<main id="dashboard"><p class="hint">Compte MT5 hébergé · Démo uniquement · <a href="/logout">Déconnexion</a>. Déconnexion du site : le mode autonome peut continuer sur le serveur.</p>')
    html = html.replace('Recherche de structure M3','Recherche de structure M1').replace('Retest et rejet confirmés','Franchissement de liquidité').replace('Diagnostic du moteur · M3','Diagnostic du moteur · M1').replace('<b>M3</b>','<b>M1</b>')
    html = html.replace('id="risk" type="number" value="0.5"','id="risk" type="number" value="0.5" readonly').replace('id="daily" type="number" value="1"','id="daily" type="number" value="2" readonly').replace('<label>Ratio cible<input id="rr"','<label style="display:none">Ratio cible<input id="rr"')
    html = html.replace('<main id="dashboard">', '<main id="dashboard"><p class="hint">Scalping expérimental XAUUSD M1 · Paramètres personnalisables dans Réglages. Le risque prévu peut être dépassé par les conditions d’exécution.</p>')
    return html.encode()


def handler(hub, proxy_key, origin):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def log_message(self, *args):
            pass  # No credential, cookie or request-body logging.

        def reply(self, status, data=b'', content_type='text/html; charset=utf-8', **headers):
            if isinstance(data, dict):
                data = json.dumps(data, allow_nan=False).encode()
                content_type = 'application/json'
            self.send_response(status)
            for k, v in {'Content-Type': content_type, 'Cache-Control': 'no-store',
                         'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                         'Referrer-Policy': 'same-origin', **headers}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def token(self):
            try:
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                return cookie['mt5_session'].value if 'mt5_session' in cookie else ''
            except Exception:
                return ''

        def cookie(self, token, age=43200):
            return f'mt5_session={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={age}'

        def dispatch(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + proxy_key):
                return self.reply(401, {'error': 'Acces refuse.'})
            path = urlsplit(self.path).path
            if self.command == 'POST' and self.headers.get('Origin') != origin:
                return self.reply(403, {'error': 'Origine refusee.'})
            if path == '/health' and self.command == 'GET':
                return self.reply(200, b'ok', 'text/plain')
            body = b''
            if self.command == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 4096 or self.headers.get('Transfer-Encoding'):
                    return self.reply(413, {'error': 'Requete invalide.'})
                body = self.rfile.read(size)
            if path == '/login':
                if self.command == 'GET':
                    return self.reply(200, LOGIN.replace('ERROR', '').encode())
                if not self.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                    return self.reply(415, {'error': 'Formulaire requis.'})
                fields = parse_qs(body.decode(), max_num_fields=3)
                try:
                    token = hub.login(fields.get('login', [''])[0], fields.get('server', [''])[0], fields.get('password', [''])[0])
                    hub.logout(self.token())
                    return self.reply(303, Location='/', **{'Set-Cookie': self.cookie(token)})
                except (ValueError, OSError) as error:
                    message = ('Aucune place disponible pour ce serveur. Réessaie plus tard.'
                               if str(error).startswith('Aucune place disponible') else
                               'Connexion refusée : vérifie tes identifiants et le serveur, ou réessaie dans cinq minutes.')
                    return self.reply(400, LOGIN.replace('ERROR', '<p class="error">' + message + '</p>').encode())
            token = self.token()
            actor = hub.actor(token)
            if not actor:
                if path.startswith('/api/'):
                    return self.reply(401, {'error': 'Connexion requise.'})
                return self.reply(303, Location='/login')
            if path == '/logout':
                if self.command == 'GET':
                    return self.reply(200, b'<form method="post" action="/logout"><button>Confirmer la deconnexion</button></form>')
                hub.logout(token)
                return self.reply(303, Location='/login', **{'Set-Cookie': self.cookie('', 0)})
            if path == '/api/bridge':
                request = {'action': 'status'}
                if self.command == 'POST':
                    if not self.headers.get('Content-Type', '').startswith('application/json'):
                        return self.reply(415, {'error': 'JSON requis.'})
                    request = json.loads(body)
                    if not isinstance(request, dict) or request.get('action') not in ('start', 'stop', 'candles', 'settings'):
                        return self.reply(400, {'error': 'Commande indisponible. Utilise Deconnexion pour quitter ton compte.'})
                    if set(request) - {'action', 'id', 'symbol', 'config', 'supervision'}:
                        return self.reply(400, {'error': 'Parametres inconnus.'})
                try:
                    result = actor.rpc(request)
                    return self.reply(200, {**result, 'paired': True, 'hosted': True})
                except (ValueError, OSError) as error:
                    if self.command == 'GET':
                        return self.reply(200, {'paired': True, 'connected': False, 'running': None,
                                               'error': 'Instance MT5 indisponible. Contacter l’administrateur.'})
                    return self.reply(400, {'error': str(error)[:300] if isinstance(error,ValueError) else 'Instance MT5 indisponible. Verifier le terminal avant de recommencer.'})
            if self.command != 'GET':
                return self.reply(405, {'error': 'Methode refusee.'})
            if path in ('/', '/control.html'):
                return self.reply(200, dashboard())
            allowed = {'/control.css', '/control.js', '/guide.css', '/lab/index.html', '/lab/app.js', '/lab/style.css', '/lab/engine.js', '/lab/worker.js', '/lab/demo.csv'}
            if path not in allowed:
                return self.reply(404, {'error': 'Introuvable.'})
            file = PUBLIC / path.lstrip('/')
            if not file.is_file():
                return self.reply(404, {'error': 'Introuvable.'})
            data = file.read_bytes()
            if path == '/control.js':
                text = data.decode().replace('Le PC, MT5 et le connecteur', 'Le serveur MT5')
                text = text.replace('Garde le PC, MT5 et le connecteur ouverts.', 'Le moteur reste sur le serveur MT5.')
                text = text.replace('Le connecteur doit être actif sur ton PC pour démarrer.', 'Le serveur MT5 doit être disponible pour démarrer.')
                data = text.encode()
            return self.reply(200, data, mimetypes.guess_type(str(file))[0] or 'application/octet-stream')

        def safe_dispatch(self):
            self.connection.settimeout(30)
            try:
                self.dispatch()
            except (ValueError, TypeError, KeyError, OSError):
                self.reply(400, {'error': 'Requete refusee.'})

        do_GET = safe_dispatch
        do_POST = safe_dispatch

    return Handler


def main():
    data_root = ROOT / 'hosted' / 'data'
    pool_file = Path(os.environ.get('MT5_POOL_FILE', str(ROOT / 'hosted' / 'pool.json')))
    if sys.argv[1:] == ['--prepare-only']:
        slots = prepare_pool(pool_file, data_root)
        for slot in slots:
            print(slot['terminal'])
        print('Capacite preparee. Verifier une fois le mode portable et les autorisations API de chaque place.')
        return
    key = os.environ.get('MT5_HOST_KEY', '')
    origin = os.environ.get('PUBLIC_URL', '').rstrip('/')
    parsed = urlsplit(origin)
    if len(key) < 32 or parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise SystemExit('MT5_HOST_KEY (32 caracteres minimum) et PUBLIC_URL HTTPS requis.')
    if pool_file.exists():
        hub = Hub({}, data_root, pool=prepare_pool(pool_file, data_root))
    else:
        accounts = load_accounts(os.environ.get('MT5_ACCOUNTS_FILE', str(ROOT / 'hosted' / 'accounts.json')))
        hub = Hub(accounts, data_root)
    server = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('MT5_HOST_PORT', '8770'))), handler(hub, key, origin))
    try:
        print('Hote MT5 demo pret. Aucun ordre avant Demarrer.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        hub.close()


if __name__ == '__main__':
    main()
