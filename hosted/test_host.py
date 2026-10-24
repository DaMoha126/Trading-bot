import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).parent))
from host import Hub, handler, identity, load_accounts, dashboard
from worker import authenticate


class FakeActor:
    def __init__(self, config, password, root):
        if password != 'demo-test-password':
            raise ValueError('Identifiants invalides')
        self.config = config
        self.requests = []
        self.process = SimpleNamespace(poll=lambda: None)

    def verify(self, password):
        return password == 'demo-test-password'

    def rpc(self, request):
        self.requests.append(request)
        return {'connected': True, 'running': False, 'account': {'demo': True, 'login': self.config['login']}}

    def close(self):
        pass


class HostTest(unittest.TestCase):
    def setUp(self):
        self.accounts = {f'{n}@Demo': {'login': str(n), 'server': 'Demo', 'terminal': f'{n}/terminal64.exe'} for n in (1, 2)}
        self.hub = Hub(self.accounts, '/unused', FakeActor)

    def test_tenants_are_isolated(self):
        one = self.hub.login('1', 'Demo', 'demo-test-password')
        two = self.hub.login('2', 'Demo', 'demo-test-password')
        self.assertNotEqual(one, two)
        self.hub.actor(one).rpc({'action': 'status'})
        self.assertEqual(self.hub.actor(two).requests, [])
        self.assertIsNone(self.hub.actor('invented-token'))

    def test_login_does_not_start_bot(self):
        token = self.hub.login('1', 'Demo', 'demo-test-password')
        self.assertEqual(self.hub.actor(token).requests, [])

    def test_wrong_password_cannot_reuse_existing_worker(self):
        token = self.hub.login('1', 'Demo', 'demo-test-password')
        with self.assertRaises(ValueError):
            self.hub.login('1', 'Demo', 'wrong')
        self.assertIsNotNone(self.hub.actor(token))

    def test_session_expiry_and_logout(self):
        token = self.hub.login('1', 'Demo', 'demo-test-password')
        self.hub.sessions[token] = ('1@Demo', 0)
        self.assertIsNone(self.hub.actor(token))
        token = self.hub.login('2', 'Demo', 'demo-test-password')
        self.hub.logout(token)
        self.assertIsNone(self.hub.actor(token))

    def test_unprovisioned_account_and_rate_limit(self):
        with self.assertRaises(ValueError):
            self.hub.login('3', 'Demo', 'demo-test-password')
        for _ in range(5):
            with self.assertRaises(ValueError):
                self.hub.login('1', 'Demo', 'wrong')
        with self.assertRaisesRegex(ValueError, 'tentatives'):
            self.hub.login('1', 'Demo', 'demo-test-password')

    def test_account_identity_validation(self):
        self.assertEqual(identity('001', 'Demo'), '1@Demo')
        for login, server in [('a', 'Demo'), ('1', '../Demo'), ('1', '\nDemo')]:
            with self.assertRaises(ValueError):
                identity(login, server)

    def test_duplicate_terminal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            exe = path / 'terminal64.exe'
            exe.touch()
            config = path / 'accounts.json'
            config.write_text(json.dumps([{**v, 'terminal': str(exe)} for v in self.accounts.values()]))
            with self.assertRaisesRegex(ValueError, 'unique'):
                load_accounts(config)

    def test_http_auth_csrf_static_and_isolation(self):
        key = 'x' * 40
        origin = 'https://bot.example'
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.hub, key, origin))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, data=None, **headers):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            conn.request(method, path, data, headers=headers)
            response = conn.getresponse()
            result = (response.status, dict(response.getheaders()), response.read())
            conn.close()
            return result
        auth = {'Authorization': 'Bearer ' + key}
        try:
            self.assertEqual(request('GET', '/login')[0], 401)
            self.assertEqual(request('GET', '/api/bridge', **auth)[0], 401)
            data = urlencode({'login': '1', 'server': 'Demo', 'password': 'demo-test-password'})
            headers = {**auth, 'Content-Type': 'application/x-www-form-urlencoded'}
            self.assertEqual(request('POST', '/login', data, Origin='https://evil.example', **headers)[0], 403)
            status, response_headers, body = request('POST', '/login', data, Origin=origin, **headers)
            self.assertEqual(status, 303)
            cookie = response_headers['Set-Cookie']
            for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'):
                self.assertIn(flag, cookie)
            private = {**auth, 'Cookie': cookie.split(';')[0]}
            status, _, body = request('GET', '/api/bridge', **private)
            self.assertEqual(json.loads(body)['account']['login'], '1')
            self.assertNotIn(b'demo-test-password', body)
            self.assertEqual(request('GET', '/hosted/accounts.json', **private)[0], 404)
            self.assertEqual(request('GET', '/lab/engine.js', **private)[0], 200)
            self.assertEqual(request('POST', '/api/bridge', json.dumps({'action': 'pair', 'login': '2'}), Origin=origin, **{**private, 'Content-Type': 'application/json'})[0], 400)
            self.assertEqual(request('POST', '/logout', b'', Origin=origin, **private)[0], 303)
            self.assertEqual(request('GET', '/api/bridge', **private)[0], 401)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_dashboard_retains_required_ids_without_installation_guide(self):
        html = dashboard().decode()
        self.assertNotIn('Première connexion ? Configure', html)
        self.assertNotIn('section class="rules"', html)
        self.assertIn('Compte MT5 hébergé', html)
        self.assertIn('id="pair-form"', html)  # Hidden compatibility elements.

    def test_worker_rejects_wrong_account_real_and_investor(self):
        config = {'login': '1', 'server': 'Demo', 'terminal': '/fake/client/terminal64.exe'}
        account = SimpleNamespace(login=1, server='Demo', trade_mode=0, currency='USD', trade_allowed=True)
        terminal = SimpleNamespace(connected=True, path='/fake/client', data_path='/fake/client')
        mt = SimpleNamespace(ACCOUNT_TRADE_MODE_DEMO=0, initialize=lambda *a, **kw: True,
                             account_info=lambda: account, terminal_info=lambda: terminal, shutdown=lambda: None)
        authenticate(mt, config, 'secret')
        for attr, value in [('login', 2), ('trade_mode', 2), ('currency', 'EUR'), ('trade_allowed', False)]:
            before = getattr(account, attr)
            setattr(account, attr, value)
            with self.assertRaises(ValueError):
                authenticate(mt, config, 'secret')
            setattr(account, attr, before)
        terminal.path = '/fake/other'
        with self.assertRaises(ValueError):
            authenticate(mt, config, 'secret')


if __name__ == '__main__':
    unittest.main()
