#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LEAD SCORING v2 (0-100): enriquece la fórmula clásica con TODA la evidencia
del CRM — notas internas del equipo, tareas, conversaciones de WhatsApp,
reciprocidad real de la interacción, recencia de CUALQUIER actividad y
declaraciones de compra/monto. Escribe scripts/data/score_v2.json:
  {contactId: {"s": score, "d": [intención, etapa, reciprocidad, recencia],
               "fl": "flags"}}
Los reportes lo consumen con prioridad y caen a la fórmula clásica si no existe.

Pilares (misma escala 0-100 de siempre):
 ① INTENCIÓN 0-35 : máx entre propiedad específica citada por el lead (nº MLS o
     "me interesa esta propiedad" = 35, ya eligió qué quiere), horizonte declarado (En curso por: 35/28/18),
     monto de compra detectado en notas/mensajes (30), compra declarada en
     texto (20) o presupuesto diligenciado (22). Si hay APLAZAMIENTO reciente
     ("retomar en octubre", "más adelante"…) se congela a máx 15.
 ② ETAPA 0-25   : Lead Status (Negocio abierto 25, En curso 15, Intento 8,
     Nuevo 5, Nutrición 3).
 ③ RECIPROCIDAD 0-20 : ya no cuenta el esfuerzo del asesor sino el eco del
     lead — respondió (mensaje entrante WA, llamada contestada o nota que
     registra respuesta) = 8 pts + nº de mensajes entrantes (hasta +8) +
     diálogo real (≥2 entrantes) +4. Gestión sin ninguna respuesta: máx 4.
 ④ RECENCIA REAL 0-20 : la fecha más reciente entre lastActivity/Engagement,
     última nota, última tarea, último intento de contacto y última
     conversación en cualquier canal (≤7d=20, ≤30=15, ≤90=8, ≤180=4).
Flags: 🏠 propiedad específica (MLS) · 💰 monto declarado · 🛒 compra declarada · ✋ respondió · ⏸ aplazado."""
import json, re
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
NOW = datetime.now(timezone.utc)
NOW_MS = NOW.timestamp() * 1000

contacts = json.load(open(DATA / 'contacts.json'))
try: GESTION = json.load(open(DATA / 'gestion.json'))
except Exception: GESTION = {}
try: WA = json.load(open(DATA / 'wa_all_msgs.json'))
except Exception: WA = []
try: CONVOS = json.load(open(DATA / 'convos.json'))
except Exception: CONVOS = []

# ---------- evidencia de conversaciones ----------
IN_MSGS, IN_TXT, LAST_WA = {}, {}, {}
for cv in WA:
    cid = cv.get('contactId')
    if not cid: continue
    for m in cv.get('msgs') or []:
        if m[1]: LAST_WA[cid] = max(LAST_WA.get(cid, ''), m[1][:10])
        if m[0] == 1:
            IN_MSGS[cid] = IN_MSGS.get(cid, 0) + 1
            IN_TXT.setdefault(cid, []).append(m[2] or '')
LAST_CONVO = {}
for cv in CONVOS:
    if cv.get('lastDate'):
        LAST_CONVO[cv['contactId']] = max(LAST_CONVO.get(cv['contactId'], 0), cv['lastDate'])

# ---------- detectores de texto (notas + mensajes del lead) ----------
RE_MONTO = re.compile(
    r'(\$|usd\s?)\s?\d[\d.,]*\s*(mil(lones)?|k|m{1,2}\b)?|\b\d{2,3}\s*(mil|k)\s*(de\s*)?(d[oó]lares|usd)|\b\d+\s*millones',
    re.I)
RE_COMPRA = re.compile(
    r'\b(comprar|compra de|invertir|inversi[oó]n en|proforma|apartar|separar|reservar|escritur|cerrar el negocio|firmar|cita (virtual|presencial|de asesor))',
    re.I)
# PROPIEDAD ESPECÍFICA: el lead cita un número MLS (o pide info de "esta propiedad" con
# dirección) — ya eligió qué quiere comprar o arrendar: la intención más concreta posible.
RE_MLS = re.compile(r'\bMLS\s*[:#]?\s*([A-Z]{1,2}\d{6,9})\b|\b([AR]\d{8})\b', re.I)
RE_PROP = re.compile(r'me interesa esta propiedad|interesad[oa] en esta propiedad|informaci[oó]n (de|sobre) (esta|la) propiedad', re.I)
RE_RESP = re.compile(r'\b(responde|contesta|respondi[oó]|contest[oó]|me dice|dice que|confirma)\b', re.I)
RE_NORESP = re.compile(r'\bno (responde|contesta|contest[oó]|respondi[oó])\b', re.I)
RE_APLAZA = re.compile(
    r'retomar en|retomamos en|m[aá]s adelante|para (septiembre|octubre|noviembre|diciembre|enero|febrero|marzo|el otro a[nñ]o|el pr[oó]ximo a[nñ]o|fin de a[nñ]o)|'
    r'no por ahora|ahora no|por ahora no|est[aá] de viaje|fuera de (la )?ciudad|despu[eé]s de', re.I)

# citas de mensajes SALIENTES pegadas en las notas (el asesor transcribe su
# propio WhatsApp: "… PFS REALTY LLC: <pitch>"). Se recortan antes de buscar
# evidencia, para que el pitch del asesor no cuente como declaración del lead.
# Cada cita va desde el remitente hasta la próxima marca "[hh:mm…" o el final.
RE_CITA_OUT = re.compile(r'pfs\s*realty(\s*llc)?\s*:.*?(?=\[|$)', re.I | re.S)
def sin_citas_out(t):
    return RE_CITA_OUT.sub(' ', t or '')

CURSO_PTS = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
STATUS_PTS = {'Negocio abierto': 25, 'En curso': 15, 'Intento de contacto': 8, 'Nuevo': 5, 'En Nutrición': 3}

def num(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0

def dias_desde(fecha_iso):
    if not fecha_iso: return None
    try:
        dt = datetime.fromisoformat(str(fecha_iso).replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = datetime.fromisoformat(str(fecha_iso)[:10] + 'T12:00:00+00:00')
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (NOW - dt).days

OUT = {}
stats = {'monto': 0, 'compra': 0, 'resp': 0, 'aplazado': 0}
for c in contacts:
    cid = c['id']
    g = GESTION.get(cid) or {}
    notas = g.get('n') or []          # [[fecha, autor, texto], ...]
    tareas = g.get('t') or []         # [[titulo, done, due], ...]
    llam = g.get('c') or [0, 0, 0, 0]

    # texto de evidencia: notas del equipo (sin citas salientes) + mensajes ENTRANTES del lead
    txt_notas = ' || '.join(sin_citas_out(n[2]) for n in notas)
    txt_lead = ' || '.join(IN_TXT.get(cid, []))
    todo_txt = txt_notas + ' || ' + txt_lead

    monto = bool(RE_MONTO.search(todo_txt)) or bool(
        (c.get('presupuesto') or '').strip() and 'no espec' not in str(c.get('presupuesto')).lower())
    compra = bool(RE_COMPRA.search(todo_txt))
    presu = (c.get('presupuesto') or '').strip()
    presu_ok = bool(presu and 'no espec' not in presu.lower())

    # respuesta del lead: mensajes entrantes, llamadas contestadas/entrantes,
    # o notas que registran respuesta (excluyendo "no responde")
    notas_resp = sum(1 for n in notas
                     if RE_RESP.search(sin_citas_out(n[2])) and not RE_NORESP.search(sin_citas_out(n[2])))
    respondio = IN_MSGS.get(cid, 0) > 0 or llam[1] > 0 or llam[2] > 0 or notas_resp > 0

    # aplazamiento RECIENTE (nota o mensaje de los últimos 120 días)
    aplazado = False
    for n in notas:
        d = dias_desde(n[0])
        if d is not None and d <= 120 and RE_APLAZA.search(sin_citas_out(n[2])):
            aplazado = True; break

    # propiedad específica: MLS citado por el lead (mensaje entrante) o en nota del asesor,
    # o el lead pidió info de "esta propiedad" (formulario de ficha de inmueble)
    prop = bool(RE_MLS.search(todo_txt)) or bool(RE_PROP.search(txt_lead))

    # ① INTENCIÓN
    p1 = CURSO_PTS.get((c.get('enCursoPor') or '').strip(), 0)
    evid = 0
    if prop: evid = 35                       # eligió la propiedad: intención máxima
    elif RE_MONTO.search(todo_txt): evid = 30
    elif compra: evid = 20
    if presu_ok: evid = max(evid, 22)
    p1 = max(p1, evid)
    if aplazado: p1 = min(p1, 15)

    # ② ETAPA
    p2 = STATUS_PTS.get((c.get('leadStatus') or '').strip(), 0)

    # ③ RECIPROCIDAD
    inb = IN_MSGS.get(cid, 0)
    if respondio:
        p3 = min(20, 8 + min(8, inb) + (4 if inb >= 2 else 0))
    else:
        p3 = min(4, (num(c.get('vecesContactado')) + num(c.get('salesActivities'))) // 5)

    # ④ RECENCIA REAL: la mejor fecha de TODA la evidencia
    fechas = []
    for k in ('lastActivity', 'lastEngagement'):
        d = dias_desde(c.get(k))
        if d is not None and d >= 0: fechas.append(d)
    for n in notas:
        d = dias_desde(n[0])
        if d is not None and d >= 0: fechas.append(d)
    for t in tareas:
        d = dias_desde(t[2])
        if d is not None and d >= 0: fechas.append(d)
    for f_int in (g.get('f') or []):
        d = dias_desde(f_int[0])
        if d is not None and d >= 0: fechas.append(d)
    if cid in LAST_WA:
        d = dias_desde(LAST_WA[cid])
        if d is not None and d >= 0: fechas.append(d)
    if cid in LAST_CONVO:
        fechas.append(max(0, int((NOW_MS - LAST_CONVO[cid]) / 86400000)))
    dmin = min(fechas) if fechas else None
    p4 = 0 if dmin is None else 20 if dmin <= 7 else 15 if dmin <= 30 else 8 if dmin <= 90 else 4 if dmin <= 180 else 0

    s = min(100, p1 + p2 + p3 + p4)
    fl = ''
    if prop: fl += 'P'; stats['prop'] = stats.get('prop', 0) + 1
    if RE_MONTO.search(todo_txt): fl += 'M'; stats['monto'] += 1
    if compra: fl += 'C'; stats['compra'] += 1
    if respondio: fl += 'R'; stats['resp'] += 1
    if aplazado: fl += 'Z'; stats['aplazado'] += 1
    OUT[cid] = {'s': s, 'd': [p1, p2, p3, p4], 'fl': fl}

json.dump(OUT, open(DATA / 'score_v2.json', 'w'))
scs = [v['s'] for v in OUT.values()]
print(f"score_v2: {len(OUT)} leads | prom {sum(scs)/len(scs):.1f} | "
      f"calientes(≥55) {sum(1 for s in scs if s >= 55)} | tibios(30-54) {sum(1 for s in scs if 30 <= s < 55)}")
print(f"flags: propiedad/MLS {stats.get('prop', 0)} | monto {stats['monto']} | compra declarada {stats['compra']} | respondieron {stats['resp']} | aplazados {stats['aplazado']}")
