#!/usr/bin/env python3
"""Muestreo READ-ONLY de conversaciones de WhatsApp: por asesor toma hasta 16 convos
(prioriza las que el cliente dejó el último mensaje) y baja sus mensajes (solo GET).
Escribe scripts/data/wa_sample.json."""
import json, time, random, urllib.request, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
T, L = ENV['GHL_PIT'], ENV['GHL_LOCATION_ID']
BASE = "https://services.leadconnectorhq.com"
HDR = {"Authorization": f"Bearer {T}", "Version": "2021-04-15", "Accept": "application/json",
       "User-Agent": "curl/8.4.0"}

def get(url):
    req = urllib.request.Request(url, headers=HDR)  # GET only
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {i+1}: {e}", file=sys.stderr)
            time.sleep(1.5 * (i + 1))
    return None

convos = json.load(open(DATA / 'convos.json'))
contacts = {c['id']: c for c in json.load(open(DATA / 'contacts.json'))}
users = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

wa = [c for c in convos if c['lastType'] == 'TYPE_WHATSAPP']
by_asesor = defaultdict(list)
for c in wa:
    by_asesor[users.get(c['assigned'], '(Sin asesor)')].append(c)

top = sorted(by_asesor.items(), key=lambda x: -len(x[1]))[:14]
random.seed(7)
sample = []
for name, cl in top:
    inb = [c for c in cl if c['lastDir'] == 'inbound']
    out = [c for c in cl if c['lastDir'] != 'inbound']
    random.shuffle(inb); random.shuffle(out)
    sample += [(name, c) for c in (inb[:8] + out[:16 - min(8, len(inb))])]

print(f"muestra: {len(sample)} conversaciones de {len(top)} asesores")
res = []
for i, (name, c) in enumerate(sample):
    d = get(f"{BASE}/conversations/{c['id']}/messages?limit=100")
    if not d: continue
    ms = d.get('messages', {})
    if isinstance(ms, dict): ms = ms.get('messages', [])
    msgs = [{'dir': m.get('direction'), 'date': m.get('dateAdded'),
             'type': m.get('messageType'), 'body': (m.get('body') or '')[:500]}
            for m in ms if m.get('messageType') in ('TYPE_WHATSAPP', 'TYPE_SMS') and (m.get('body') or '').strip()]
    if not msgs: continue
    msgs.sort(key=lambda m: m['date'] or '')
    ct = contacts.get(c['contactId'], {})
    res.append({'convoId': c['id'], 'asesor': name,
                'contacto': ct.get('name', ''), 'fuente': (ct.get('source') or '').strip(),
                'leadStatus': ct.get('leadStatus') or '', 'lastDir': c['lastDir'],
                'msgs': msgs[-60:]})
    if (i + 1) % 40 == 0: print(f"  {i + 1}/{len(sample)}")
    time.sleep(0.1)

json.dump(res, open(DATA / 'wa_sample.json', 'w'), ensure_ascii=False)
n_msgs = sum(len(r['msgs']) for r in res)
print(f"LISTO: {len(res)} conversaciones, {n_msgs} mensajes -> {DATA / 'wa_sample.json'}")
