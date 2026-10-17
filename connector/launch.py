"""Launch local demo bridge + temporary HTTPS tunnel; secrets stay runtime-only."""
import os,re,secrets,shutil,subprocess,sys,time,webbrowser,json,urllib.request,urllib.error
from pathlib import Path

def main():
    cloud=shutil.which('cloudflared')
    if not cloud:
        candidates=[Path(os.environ.get('ProgramFiles','C:/Program Files'))/'cloudflared'/'cloudflared.exe',Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'cloudflared'/'cloudflared.exe',Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'WinGet'/'Links'/'cloudflared.exe']
        cloud=next((str(p) for p in candidates if p.exists()),None)
    if not cloud:raise SystemExit('cloudflared absent. Installer avec : winget install --id Cloudflare.cloudflared --exact')
    token=secrets.token_urlsafe(32);env=dict(os.environ,BEN_BRIDGE_TOKEN=token,PYTHONUNBUFFERED='1')
    bridge=subprocess.Popen([sys.executable,str(Path(__file__).with_name('bridge.py'))],env=env)
    tunnel=None
    try:
        ready=False
        for _ in range(30):
            if bridge.poll() is not None:raise RuntimeError('Le connecteur MT5 a quitte. Verifie MT5 et Python.')
            try:
                request=urllib.request.Request('http://127.0.0.1:8765/status',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(request,timeout=2) as response:data=json.load(response)
                if not data.get('connected'):raise RuntimeError(data.get('error','Compte MT5 demo non connecte.'))
                ready=True;break
            except urllib.error.HTTPError as ex:
                if ex.code==401:raise RuntimeError('Un autre connecteur occupe le port 8765. Ferme son ancienne fenetre.')
            except urllib.error.URLError:pass
            time.sleep(1)
        if not ready:raise RuntimeError('Le connecteur ne repond pas. Verifie MT5 et relance.')
        tunnel=subprocess.Popen([cloud,'tunnel','--url','http://127.0.0.1:8765','--no-autoupdate'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
        print('\nCreation de la liaison HTTPS... Garde cette fenetre ouverte.',flush=True)
        found=False
        for line in tunnel.stdout:
            match=re.search(r'https://[-a-z0-9]+\.trycloudflare\.com',line)
            if match and not found:
                found=True
                print('\nURL DE LIAISON : '+match.group(0)+'\nCLE DE LIAISON : '+token+'\n\nColle ces deux valeurs dans Connecter mon PC sur ton site prive.\nAucun ordre avant le bouton Demarrer. Ctrl+C pour quitter.\n',flush=True)
                dashboard=os.environ.get('BEN_DASHBOARD_URL','https://ben-bot-mt5.onrender.com')
                if dashboard.startswith('https://'):webbrowser.open(dashboard.rstrip('/')+'/control.html#setup')
                else:print('Ouvre maintenant ton nouveau site externe, rubrique Connexion.',flush=True)
            if bridge.poll() is not None:raise RuntimeError('Le connecteur MT5 a quitte.')
        if tunnel.poll() is not None:print('Tunnel arrete. Relancer ce fichier pour une nouvelle liaison.')
    except (RuntimeError,OSError) as ex:print('Connecteur arrete : '+str(ex),flush=True)
    except KeyboardInterrupt:print('\nArret du connecteur. Les SL/TP chez le courtier restent actifs.')
    finally:
        if tunnel and tunnel.poll() is None:tunnel.terminate()
        if bridge.poll() is None:bridge.terminate()
if __name__=='__main__':main()
