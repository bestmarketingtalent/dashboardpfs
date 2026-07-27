#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY: gestión comercial por lead de las carteras de asesores HUMANOS
(excluye MARKETING PFS y sin asesor): llamadas con duración (TMO), emails,
tareas y notas de cada contacto. Solo GET. Reanudable: guarda avance cada 400
contactos en scripts/data/gestion.json, keyed por contactId.

Por contacto guarda:
  c: [llamadas salientes, entrantes, contestadas, segundos hablados]  (todas sus convos, últimos 100 eventos c/u)
  e: emails salientes
  t: [[título(80), 1 completada/0, fecha límite(10)], ...]
  n: [[fecha(10), autor, texto(240)], ...]
  f: [[fecha(10), canal], ...]  intentos de contacto SALIENTES ordenados por fecha
     (canal: c=llamada, e=email, w=whatsapp, s=sms) — para medir persistencia:
     si el asesor insiste en días distintos o en ráfaga de un solo día.
"""
import json, time, urllib.request, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
OUT = DATA / 'gestion.json'
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
BASE = "https://services.leadconnectorhq.com"
HDR = {"Authorization": f"Bearer {ENV['GHL_PIT']}", "Version": "2021-04-15",
       "Accept": "application/json", "User-Agent": "curl/8.4.0"}

_th = threading.local()
def get(url):
    req = urllib.request.Request(url, headers=HDR)  # GET: solo consulta
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                time.sleep(0.68)   # ~8.8 req/s entre los 6 hilos (límite GHL: 100/10s)
                return json.load(r)
        except Exception as e:
            if '429' in str(e): time.sleep(6)
            else: time.sleep(1.2 * (i + 1))
    return None

contacts = json.load(open(DATA / 'contacts.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
convos = json.load(open(DATA / 'convos.json'))

hum = [c for c in contacts if c['assigned'] and USERS.get(c['assigned'], '') not in ('MARKETING PFS', '')]
convs_by_contact = {}
for cv in convos:
    convs_by_contact.setdefault(cv['contactId'], []).append(cv['id'])

done = {}
if OUT.exists():
    try: done = json.load(open(OUT))
    except Exception: done = {}

# --refresh N: vuelve a bajar la gestión de los contactos con actividad reciente
# (alguna conversación con lastDate en los últimos N días), además de los nuevos.
if '--refresh' in sys.argv:
    import datetime as _dt
    _n = int(sys.argv[sys.argv.index('--refresh') + 1])
    _corte_ms = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=_n)).timestamp() * 1000
    _recientes = {cv['contactId'] for cv in convos if (cv.get('lastDate') or 0) >= _corte_ms}
    _antes = len(done)
    for _cid in _recientes:
        done.pop(_cid, None)
    print(f"refresh {_n}d: se re-bajarán {_antes - len(done)} contactos con actividad reciente", flush=True)

todo = [c for c in hum if c['id'] not in done or 'f' not in done[c['id']]]
print(f"contactos humanos {len(hum)} | ya descargados {len(done)} | pendientes {len(todo)}", flush=True)

lock = threading.Lock()
n_done = 0

def procesa(ct):
    cid = ct['id']
    rec = {'c': [0, 0, 0, 0], 'e': 0, 't': [], 'n': [], 'f': []}
    for convo_id in convs_by_contact.get(cid, []):
        d = get(f"{BASE}/conversations/{convo_id}/messages?limit=100")
        if d is None: continue
        ms = d.get('messages', {})
        if isinstance(ms, dict): ms = ms.get('messages', [])
        CANAL = {'TYPE_CALL': 'c', 'TYPE_EMAIL': 'e', 'TYPE_WHATSAPP': 'w', 'TYPE_SMS': 's'}
        for m in ms:
            mt = m.get('messageType')
            out = m.get('direction') != 'inbound'
            fecha = (m.get('dateAdded') or '')[:10]
            if out and fecha and mt in CANAL:
                rec['f'].append([fecha, CANAL[mt]])
            if mt == 'TYPE_CALL':
                rec['c'][0 if out else 1] += 1
                call = (m.get('meta') or {}).get('call') or {}
                dur = call.get('duration') or 0
                if call.get('status') == 'completed' or dur > 0:
                    rec['c'][2] += 1
                    rec['c'][3] += dur
            elif mt == 'TYPE_EMAIL' and out:
                rec['e'] += 1
    rec['f'] = sorted(rec['f'])[:80]
    d = get(f"{BASE}/contacts/{cid}/tasks")
    for t in (d or {}).get('tasks', []) or []:
        rec['t'].append([(t.get('title') or '')[:80], 1 if t.get('completed') else 0,
                         (t.get('dueDate') or '')[:10]])
    d = get(f"{BASE}/contacts/{cid}/notes")
    for nt in (d or {}).get('notes', []) or []:
        rec['n'].append([(nt.get('dateAdded') or '')[:10],
                         USERS.get(nt.get('userId'), ''),
                         ' '.join((nt.get('bodyText') or nt.get('body') or '').split())[:240]])
    global n_done
    with lock:
        done[cid] = rec
        n_done += 1
        if n_done % 400 == 0:
            json.dump(done, open(OUT, 'w'), ensure_ascii=False)
            print(f"avance: {len(done)}/{len(hum)}", flush=True)

with ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(procesa, todo))

json.dump(done, open(OUT, 'w'), ensure_ascii=False)
tot_calls = sum(r['c'][0] + r['c'][1] for r in done.values())
tot_notes = sum(len(r['n']) for r in done.values())
tot_tasks = sum(len(r['t']) for r in done.values())
print(f"LISTO: {len(done)} contactos | llamadas {tot_calls} | tareas {tot_tasks} | notas {tot_notes} -> {OUT}", flush=True)
