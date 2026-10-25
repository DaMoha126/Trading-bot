"""One private MT5 process per operator-provisioned demo account. JSON over pipes."""
import json
import os
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'connector'))


def authenticate(mt, config, password):
    path = Path(config['terminal']).resolve()
    if not mt.initialize(str(path), login=int(config['login']), password=password,
                         server=config['server'], portable=True, timeout=15000):
        raise ValueError('Connexion MT5 refusee. Verifie les identifiants et le terminal.')
    account = mt.account_info()
    terminal = mt.terminal_info()
    if (account is None or terminal is None or not terminal.connected
            or account.login != int(config['login']) or account.server != config['server']
            or account.trade_mode != mt.ACCOUNT_TRADE_MODE_DEMO or account.currency != 'USD'
            or not account.trade_allowed):
        mt.shutdown()
        raise ValueError('Compte demo USD avec acces trading requis.')
    expected = os.path.normcase(str(path.parent))
    if (os.path.normcase(str(Path(terminal.path).resolve())) != expected
            or os.path.normcase(str(Path(terminal.data_path).resolve())) != expected):
        mt.shutdown()
        raise ValueError('Le terminal MT5 ne correspond pas a cette instance dediee.')


def main():
    import MetaTrader5 as mt
    from bridge import DemoBridge
    setup = json.loads(sys.stdin.readline())
    try:
        password = setup.pop('password')
        try:
            authenticate(mt, setup, password)
        finally:
            password = None
        data = Path(setup['data'])
        data.mkdir(parents=True, exist_ok=True)
        bridge = DemoBridge(mt, state=data / 'risk_state.json', journal=data / 'journal.jsonl', instrument='XAUUSD')
        bridge.pin = (int(setup['login']), setup['server'])
        print(json.dumps({'ok': True}), flush=True)
        done = threading.Event()

        def tick():
            while not done.wait(1):
                with bridge.lock:
                    bridge.step()

        threading.Thread(target=tick, daemon=True).start()
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with bridge.lock:
                    action = request.get('action')
                    if action == 'status':
                        result = bridge.snapshot()
                    elif action == 'candles':
                        result = bridge.candles()
                    elif action in ('start', 'stop'):
                        bridge.command(request)
                        result = bridge.snapshot()
                    else:
                        raise ValueError('Commande inconnue.')
                print(json.dumps({'ok': True, 'data': result}, allow_nan=False), flush=True)
            except ValueError as error:
                print(json.dumps({'ok': False, 'error': str(error)[:300]}), flush=True)
            except (TypeError, KeyError):
                print(json.dumps({'ok': False, 'error': 'Parametres de commande invalides.'}), flush=True)
        done.set()
    except Exception:
        print(json.dumps({'ok': False, 'error': 'Connexion MT5 indisponible ou compte non autorise.'}), flush=True)
    finally:
        mt.shutdown()


if __name__ == '__main__':
    main()
