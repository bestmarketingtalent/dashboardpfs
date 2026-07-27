#!/usr/bin/env python3
"""READ-ONLY: baja los mensajes de TODAS las conversaciones de WhatsApp (~4.850)
para medir tiempos de respuesta y calidad de gestión por asesor y por lead.
Solo GET. Reanudable: guarda avance cada 300 convos en scripts/data/wa_all_msgs.json."""
import json, time, urllib.request, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
OUT = DATA / 'wa_all_msgs.json'
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
T = ENV['GHL_PIT']
BASE = "https://services.leadconnectorhq.com"
HDR = {"Authorization": f"Bearer {T}", "Version": "2021-04-15", "Accept": "application/json",
       "User-Agent": "curl/8.4.0"}

def get(url):
    req = urllib.request.Request(url, headers=HDR)  # GET only
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {i+1}: {e}", file=sys.stderr)
            time.sleep(1.2 * (i + 1))
    return None

convos = json.load(open(DATA / 'convos.json'))
wa = [c for c in convos if c['lastType'] == 'TYPE_WHATSAPP']
done = {}
if OUT.exists():
    try: done = {r['id']: r for r in json.load(open(OUT))}
    except Exception: done = {}
print(f"total {len(wa)} | ya descargadas {len(done)}", flush=True)

res = list(done.values())
n_new = 0
for i, c in enumerate(wa):
    if c['id'] in done: continue
    d = get(f"{BASE}/conversations/{c['id']}/messages?limit=100")
    if d is None:
        rec = {'id': c['id'], 'msgs': None}
    else:
        ms = d.get('messages', {})
        if isinstance(ms, dict): ms = ms.get('messages', [])
        msgs = [[m.get('direction') == 'inbound' and 1 or 0, m.get('dateAdded'),
                 ' '.join((m.get('body') or '').split())[:160]]
                for m in sorted(ms, key=lambda m: m.get('dateAdded') or '')
                if m.get('messageType') in ('TYPE_WHATSAPP', 'TYPE_SMS') and (m.get('body') or '').strip()]
        rec = {'id': c['id'], 'contactId': c['contactId'], 'assigned': c['assigned'],
               'lastDir': c['lastDir'], 'msgs': msgs}
    res.append(rec); done[c['id']] = rec; n_new += 1
    if n_new % 300 == 0:
        json.dump(res, open(OUT, 'w'), ensure_ascii=False)
        print(f"avance: {len(done)}/{len(wa)}", flush=True)
    time.sleep(0.07)

json.dump(res, open(OUT, 'w'), ensure_ascii=False)
print(f"LISTO: {len(res)} conversaciones -> {OUT}")
