#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Snapshot diario de métricas clave de la gestión comercial. Se corre después de
los fetch y antes de los reportes: agrega (o reemplaza) la foto de HOY en
scripts/data/historico.json, que alimenta la sección "Evolución de la gestión"
del dashboard. Solo lee los JSON locales; no toca el CRM."""
import json
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
contacts = json.load(open(DATA / 'contacts.json'))
convos = json.load(open(DATA / 'convos.json'))
opps = json.load(open(DATA / 'opps.json'))

CURSO_PTS = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
STATUS_PTS = {'Negocio abierto': 25, 'En curso': 15, 'Intento de contacto': 8, 'Nuevo': 5, 'En Nutrición': 3}
def _n(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0
def score_of(ct):
    s = CURSO_PTS.get((ct.get('enCursoPor') or '').strip(), 0) + STATUS_PTS.get((ct.get('leadStatus') or '').strip(), 0)
    s += min(20, _n(ct.get('vecesContactado')) + _n(ct.get('salesActivities')))
    la = ct.get('lastActivity') or ct.get('lastEngagement')
    if la:
        try:
            dt = datetime.fromisoformat(str(la).replace('Z', '+00:00'))
            d = (datetime.now(dt.tzinfo) - dt).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)

wait_ids = {c['contactId'] for c in convos if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound'}
NOW_TS = datetime.now().timestamp() * 1000
last_conv = {}
for c in convos:
    if c.get('lastDate'):
        last_conv[c['contactId']] = max(last_conv.get(c['contactId'], 0), c['lastDate'])

m = {'fecha': datetime.now().strftime('%Y-%m-%d'),
     'contactos': len(contacts), 'opps': len(opps),
     'clientes': 0, 'negocio': 0, 'encurso': 0, 'nutricion': 0, 'sinstatus': 0,
     'sinasesor': 0, 'hot': 0, 'warm': 0, 'recompra': 0, 'clifrio': 0}
scores = []
for ct in contacts:
    st = (ct.get('leadStatus') or '').strip() or '(Sin status)'
    sc = score_of(ct); scores.append(sc)
    oport = (ct.get('enCursoPor') or '').startswith('Oportunidad')
    if st == 'Cliente':
        m['clientes'] += 1
        if oport: m['recompra'] += 1
        lc = last_conv.get(ct['id'])
        if lc is None or (NOW_TS - lc) / 86400000 > 180: m['clifrio'] += 1
    if st == 'Negocio abierto': m['negocio'] += 1
    if st == 'En curso': m['encurso'] += 1
    if st == 'En Nutrición': m['nutricion'] += 1
    if st == '(Sin status)': m['sinstatus'] += 1
    if not ct.get('assigned') and st not in ('Descartado', 'Cliente'): m['sinasesor'] += 1
    if sc >= 55: m['hot'] += 1
    elif sc >= 30: m['warm'] += 1
m['score'] = round(sum(scores) / len(scores), 1)
m['esperando'] = sum(1 for c in convos if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound')
cmap = {ct['id']: ct for ct in contacts}
m['esperando30'] = sum(1 for c in convos if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound'
                       and score_of(cmap.get(c['contactId']) or {}) >= 30)

hist_path = DATA / 'historico.json'
try: hist = json.load(open(hist_path))
except Exception: hist = []
hist = [h for h in hist if h.get('fecha') != m['fecha']]
hist.append(m)
hist.sort(key=lambda h: h['fecha'])
json.dump(hist, open(hist_path, 'w'), ensure_ascii=False, indent=1)
print(f"snapshot {m['fecha']} guardado | histórico: {len(hist)} cortes")
print(json.dumps(m, ensure_ascii=False))
