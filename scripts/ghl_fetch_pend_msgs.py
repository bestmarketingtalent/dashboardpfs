#!/usr/bin/env python3
"""READ-ONLY: baja los mensajes de las conversaciones de WhatsApp donde el cliente
quedó esperando respuesta (lastDir=inbound), para identificar qué plantilla o
automatización fue el último toque saliente. Solo GET. Escribe scripts/data/pend_msgs.json.
También guarda la lista de workflows (GET /workflows) en scripts/data/workflows.json."""
import json, time, urllib.request, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
T, L = ENV['GHL_PIT'], ENV['GHL_LOCATION_ID']
BASE = "https://services.leadconnectorhq.com"

def get(url, version):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {T}", "Version": version, "Accept": "application/json",
        "User-Agent": "curl/8.4.0"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {i+1}: {e}", file=sys.stderr)
            time.sleep(1.5 * (i + 1))
    return None

# workflows (nombres de automatizaciones)
wf = get(f"{BASE}/workflows/?locationId={L}", "2021-07-28") or {}
json.dump(wf.get('workflows', []), open(DATA / 'workflows.json', 'w'), ensure_ascii=False)
print(f"workflows: {len(wf.get('workflows', []))}")

convos = json.load(open(DATA / 'convos.json'))
pend = [c for c in convos if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound']
print(f"conversaciones pendientes: {len(pend)}")

res = []
for i, c in enumerate(pend):
    d = get(f"{BASE}/conversations/{c['id']}/messages?limit=100", "2021-04-15")
    if not d: continue
    ms = d.get('messages', {})
    if isinstance(ms, dict): ms = ms.get('messages', [])
    ms = [m for m in ms if (m.get('body') or '').strip()]
    ms.sort(key=lambda m: m.get('dateAdded') or '')
    # solo mensajes reales al cliente (WhatsApp/SMS), sin actividades ni notas internas
    real = [m for m in ms if m.get('messageType') in ('TYPE_WHATSAPP', 'TYPE_SMS')]
    last_out = next(((m.get('body') or '')[:300] for m in reversed(real)
                     if m.get('direction') == 'outbound'), '')
    n_out = sum(1 for m in real if m.get('direction') == 'outbound')
    n_in = sum(1 for m in real if m.get('direction') == 'inbound')
    res.append({'convoId': c['id'], 'contactId': c['contactId'], 'assigned': c['assigned'],
                'lastOut': last_out, 'nOut': n_out, 'nIn': n_in,
                'lastDate': c.get('lastDate'), 'lastBody': c.get('lastBody')})
    if (i + 1) % 50 == 0: print(f"  {i + 1}/{len(pend)}")
    time.sleep(0.1)

json.dump(res, open(DATA / 'pend_msgs.json', 'w'), ensure_ascii=False)
print(f"LISTO: {len(res)} -> {DATA / 'pend_msgs.json'}")
