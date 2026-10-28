"""Launch existing MT5 host plus outbound relay. Never starts a trading strategy."""
from getpass import getpass
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from outbound import Agent,configuration,diagnostic

ROOT=Path(__file__).resolve().parents[1]

def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.3):return True
    except OSError:return False

def main():
    os.environ.setdefault('PUBLIC_URL','https://ben-bot-mt5.onrender.com')
    if not os.environ.get('MT5_HOST_KEY'):
        os.environ['MT5_HOST_KEY']=getpass('Clé MT5_HOST_KEY de Render (saisie masquée, ne pas partager) : ').strip()
    origin,key,port=configuration()
    if not (ROOT/'hosted'/'host.py').is_file() or not (ROOT/'hosted'/'pool.json').is_file():
        raise ValueError('Lancer depuis le projet Trading Bot existant avec hosted/pool.json.')
    if listening(port):raise ValueError('Le service MT5 est déjà ouvert. Arrêter sa fenêtre avec Ctrl+C avant ce lancement. Ne pas arrêter de positions automatiquement.')
    child=subprocess.Popen([sys.executable,str(ROOT/'hosted'/'host.py')],cwd=str(ROOT))
    try:
        end=time.monotonic()+60
        while not listening(port):
            if child.poll() is not None:raise ValueError('Le service MT5 n’a pas démarré. Lire son message ci-dessus.')
            if time.monotonic()>end:raise ValueError('Démarrage du service MT5 trop long.')
            time.sleep(.5)
        agent=Agent(origin,key,port)
        print('Service et liaison sortante ouverts. Aucun bot démarré. Garde cette fenêtre ouverte.',flush=True)
        disconnected=False
        while child.poll() is None:
            try:
                agent.cycle()
                if disconnected:print('Liaison rétablie. Aucune ancienne commande rejouée.',flush=True)
                disconnected=False
                time.sleep(1)
            except (OSError,ValueError,URLError) as error:
                if not disconnected:print(diagnostic(error),flush=True)
                disconnected=True;time.sleep(5)
        raise ValueError('Le service MT5 s’est arrêté. Aucun redémarrage automatique du bot.')
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('Service et liaison arrêtés. Les SL/TP restent chez le courtier ; vérifier les positions dans MT5.')
    except (ValueError,OSError) as ex:raise SystemExit(str(ex))
