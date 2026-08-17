#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría individual de desempeño por asesor comercial y por realtor ([empresa]).
Cruza: cartera de contactos (contacts.json), conversaciones WhatsApp/llamadas/email
(convos.json), muestra cualitativa (wa_sample.json) y cola de leads esperando.
Genera auditoria-asesores-pfs-AAAA-MM-DD.html con filtro por asesor y por realtor,
y retroalimentación (fortalezas / a mejorar / recomendaciones) basada en reglas
sobre los datos + notas cualitativas de la muestra leída. Solo lectura del CRM."""
import json, html, re, statistics
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

# ---------- fecha de creación en hora de Miami (el CRM guarda UTC; un lead de las 8 PM
# aparece como "mañana" en UTC). Se muestra y filtra con la fecha que ve el equipo. ----------
try:
    from zoneinfo import ZoneInfo as _ZI
    _TZ_MIA = _ZI('America/New_York')
except Exception:
    _TZ_MIA = None
def fecha_local(iso):
    if not iso: return ''
    try:
        from datetime import datetime as _dt
        d = _dt.fromisoformat(str(iso).replace('Z', '+00:00'))
        if _TZ_MIA is not None and d.tzinfo is not None: d = d.astimezone(_TZ_MIA)
        return d.strftime('%Y-%m-%d')
    except Exception:
        return str(iso)[:10]

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

# ---------- score v2 precalculado (notas, tareas, conversaciones, reciprocidad, recencia real) ----------
try:
    _SC2 = json.load(open(DATA / 'score_v2.json'))
except Exception:
    _SC2 = {}

contacts = json.load(open(DATA / 'contacts.json'))
convos   = json.load(open(DATA / 'convos.json'))
users    = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
sample   = json.load(open(DATA / 'wa_sample.json'))

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
_hoy = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'
NOW_TS = _hoy.timestamp() * 1000
def fmt(n): return f'{n:,}'.replace(',', '.')

# ---------- scoring y fuente (mismas fórmulas de los otros reportes) ----------
CURSO_PTS  = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
STATUS_PTS = {'Negocio abierto': 25, 'En curso': 15, 'Intento de contacto': 8, 'Nuevo': 5, 'En Nutrición': 3}
def _num(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0
def score_of(ct):
    _v2 = _SC2.get(ct.get('id') or '')
    if _v2 is not None: return _v2['s']
    s  = CURSO_PTS.get((ct.get('enCursoPor') or '').strip(), 0)
    s += STATUS_PTS.get((ct.get('leadStatus') or '').strip(), 0)
    s += min(20, _num(ct.get('vecesContactado')) + _num(ct.get('salesActivities')))
    la = ct.get('lastActivity') or ct.get('lastEngagement')
    if la:
        try:
            dt = datetime.fromisoformat(str(la).replace('Z', '+00:00'))
            d = (datetime.now(dt.tzinfo) - dt).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)

def grupo(src):
    s = ' '.join((src or '').split()); sl = s.lower()
    if not sl or sl == '<unspecified>': return '(Sin fuente)'
    if 'google' in sl or sl.startswith('goo ') or sl == 'paid search': return 'Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl: return 'Referidos / Personal'
    if sl.startswith('prensa'): return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'): return 'Sitio Web'
    return s

STATUS_ORDER = ['Cliente','Negocio abierto','En curso','Intento de contacto','Nuevo',
                'En Nutrición','Tenant','Aliado','Relationship','Compra Problematica',
                'Descartado','(Sin status)']

# ---------- agregación por asesor (cartera) + filas lead a lead ----------
cid_by_contact = {}
def acc():
    return {'leads': 0, 'status': Counter(), 'curso': Counter(), 'fuentes': Counter(),
            'hot': 0, 'warm': 0, 'scs': [], 'sindatos': 0}
A = defaultdict(acc)   # asesores (assignedTo del contacto)
R = defaultdict(acc)   # realtors (campo Realtor)

def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi
DASE, giASE = dict_indexer()   # asesores
DRL, giRL = dict_indexer()     # realtors
DFU, giFU = dict_indexer()     # fuentes
DCU, giCU = dict_indexer()     # en curso por
DTG, giTG = dict_indexer()     # etiquetas (tags del CRM)
DOP, giOP = dict_indexer()     # etapa de oportunidad en el pipeline

# ---------- oportunidad en el pipeline (opps.json; match por email/teléfono) ----------
try:
    _OPPS = json.load(open(DATA / 'opps.json'))
    _STG = {s['id']: s['name'] for p in json.load(open(DATA / 'pipelines.json'))['pipelines'] for s in p['stages']}
except Exception:
    _OPPS, _STG = [], {}
_ST_ES = {'open': 'abierta', 'won': 'ganada', 'lost': 'perdida', 'abandoned': 'abandonada'}
def _mejor_opp(nuevo, prev):
    if prev is None: return True
    no, po = nuevo.get('status') == 'open', prev.get('status') == 'open'
    if no != po: return no
    return (nuevo.get('stageChange') or nuevo.get('created') or '') > (prev.get('stageChange') or prev.get('created') or '')
_OPP_BY = {}
for _o in _OPPS:
    for _k in ((_o.get('email') or '').strip().lower(), re.sub(r'\D', '', _o.get('phone') or '')):
        if _k and _mejor_opp(_o, _OPP_BY.get(_k)): _OPP_BY[_k] = _o
def opp_of(c):
    for _k in ((c.get('email') or '').strip().lower(), re.sub(r'\D', '', c.get('phone') or '')):
        if _k and _k in _OPP_BY: return _OPP_BY[_k]
    return None
LEADS = []   # [aIdx, [rIdx...], nombre, email, phone, fuIdx, stIdx, cuIdx, score]

for ct in contacts:
    a = users.get(ct['assigned'], '(Sin asesor asignado)') if ct['assigned'] else '(Sin asesor asignado)'
    st = (ct.get('leadStatus') or '').strip() or '(Sin status)'
    if st not in STATUS_ORDER: st = '(Sin status)'
    ku = (ct.get('enCursoPor') or '').strip() or '(Sin dato)'
    fu = grupo(ct.get('source'))
    sc = score_of(ct)
    cid_by_contact[ct['id']] = (a, sc)
    targets = [A[a]]
    rls = ct.get('realtor') or []
    if isinstance(rls, str): rls = [rls]
    ridxs = []
    for r in rls:
        r = r.strip()
        if r:
            targets.append(R[r])
            ridxs.append(giRL(r))
    LEADS.append([giASE(a), ridxs, (ct.get('name') or '(sin nombre)').strip().title(),
                  ct.get('email') or '', ct.get('phone') or '',
                  giFU(fu), STATUS_ORDER.index(st), giCU(ku), sc,
                  fecha_local(ct.get('created'))])
    for g in targets:
        g['leads'] += 1
        g['status'][st] += 1
        g['curso'][ku] += 1
        g['fuentes'][fu] += 1
        g['scs'].append(sc)
        if sc >= 55: g['hot'] += 1
        elif sc >= 30: g['warm'] += 1
        if not ct.get('email') and not ct.get('phone'): g['sindatos'] += 1

def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]

# ---------- actividad por asesor (conversaciones) ----------
ACT = defaultdict(lambda: {'wa': 0, 'waWait': 0, 'calls': 0, 'emails': 0})
PENDS = defaultdict(list)
for c in convos:
    a = users.get(c['assigned'], '(Sin asesor)') if c['assigned'] else '(Sin asesor)'
    an = '(Sin asesor asignado)' if a == '(Sin asesor)' else a
    t = c['lastType']
    g = ACT[an]
    if t == 'TYPE_WHATSAPP':
        g['wa'] += 1
        if c['lastDir'] == 'inbound':
            g['waWait'] += 1
            ct = next((x for x in [None]), None)
            cinfo = None
    elif t == 'TYPE_CALL': g['calls'] += 1
    elif t in ('TYPE_EMAIL', 'TYPE_CAMPAIGN_EMAIL'): g['emails'] += 1
# cola de espera con detalle
cmap = {ct['id']: ct for ct in contacts}
for c in convos:
    if c['lastType'] != 'TYPE_WHATSAPP' or c['lastDir'] != 'inbound': continue
    a = users.get(c['assigned'], '(Sin asesor asignado)') if c['assigned'] else '(Sin asesor asignado)'
    ct = cmap.get(c['contactId']) or {}
    dias = int((NOW_TS - c['lastDate']) / 86400000) if c.get('lastDate') else -1
    PENDS[a].append([score_of(ct) if ct else 0,
                     (ct.get('name') or '(sin nombre)').strip().title(),
                     grupo(ct.get('source')), dias,
                     ''.join(ch for ch in (ct.get('phone') or '') if ch.isdigit()),
                     ct.get('email') or '', ct.get('phone') or '', ct.get('id'),
                     fecha_local(ct.get('created'))])
for a in PENDS: PENDS[a].sort(key=lambda x: (-x[0], -x[3]))

# ---------- muestra cualitativa ----------
def parse(d):
    try: return datetime.fromisoformat(d.replace('Z', '+00:00'))
    except Exception: return None
SMP = {}
per = defaultdict(lambda: {'rts': [], 'convs': 0, 'mono': 0, 'dial': 0})
for cv in sample:
    p = per[cv['asesor']]; p['convs'] += 1
    inb = sum(1 for m in cv['msgs'] if m['dir'] == 'inbound')
    if inb == 0: p['mono'] += 1
    if inb >= 2: p['dial'] += 1
    for i, m in enumerate(cv['msgs']):
        if m['dir'] != 'inbound': continue
        t0 = parse(m['date'])
        for m2 in cv['msgs'][i + 1:]:
            if m2['dir'] == 'outbound':
                t1 = parse(m2['date'])
                if t0 and t1: p['rts'].append((t1 - t0).total_seconds() / 3600)
                break
for a, p in per.items():
    rt = statistics.median(p['rts']) if p['rts'] else None
    SMP[a] = {'rtH': rt, 'dial': p['dial'], 'mono': p['mono'], 'n': p['convs']}

# ---------- análisis de TODAS las conversaciones de WhatsApp ----------
# (requiere ghl_fetch_wa_all.py; si no existe el archivo, estas métricas quedan vacías)
try:
    wa_all = [cv for cv in json.load(open(DATA / 'wa_all_msgs.json')) if cv.get('msgs')]
except Exception:
    wa_all = []

def norm_sig(b):
    t = re.sub(r'[*_]', '', (b or '').lower())
    t = re.sub(r'\d+', '#', t)
    return t[:60]
_sig_convos = defaultdict(set)
for cv in wa_all:
    for m in cv['msgs']:
        if m[0] == 0:
            _sig_convos[norm_sig(m[2])].add(cv['id'])
TEMPLATES = {s for s, ids in _sig_convos.items() if len(ids) >= 5}

def _ts(x):
    try: return datetime.fromisoformat(str(x).replace('Z', '+00:00')).timestamp()
    except Exception: return None

KW = [
    (('credito', 'crédito', 'cuota', 'financ', 'hipotec', 'prestamo', 'préstamo'), 'financiación',
     'Responder con la ficha de crédito para extranjeros (requisitos y cuota inicial).'),
    (('precio', 'cuánto', 'cuanto', 'costo', 'vale', 'valor'), 'precio',
     'Dar cifras concretas ("desde…") en el mismo mensaje: pedir llamada sin dar precio enfría.'),
    (('renta', 'rentar', 'alquil', 'arrend', 'lease'), 'renta',
     'Enviar requisitos de renta y 2-3 opciones según presupuesto y fechas.'),
    (('visa',), 'visa',
     'Usar el guión de inversión sin visa / crédito sin residencia que promueve la empresa.'),
    (('cita', 'llamada', 'llamar', 'llámame', 'llamame', 'agendar'), 'cita/llamada',
     'Agendar la llamada de inmediato con fecha y hora concretas.'),
    (('informacion', 'información', 'info', 'enviame', 'envíame', 'comparteme', 'compárteme'), 'más información',
     'Enviar la ficha por WhatsApp (lo pidió por este canal) y cerrar con una pregunta de calificación.'),
]
def kw_of(texto):
    t = (texto or '').lower()
    for kws, tema, reco in KW:
        if any(k in t for k in kws): return tema, reco
    return None, None

ACONV = defaultdict(lambda: {'gaps': [], 'in': 0, 'inAns': 0, 'out': 0, 'tpl': 0, 'convs': 0, 'dial': 0})
CONTACT_RT = defaultdict(list)
LEADCONVS = defaultdict(list)   # asesor -> filas de análisis lead a lead
cmap_all = {ct['id']: ct for ct in contacts}
for cv in wa_all:
    a = users.get(cv.get('assigned'), '(Sin asesor asignado)') if cv.get('assigned') else '(Sin asesor asignado)'
    g = ACONV[a]; g['convs'] += 1
    msgs = cv['msgs']
    n_in = sum(1 for m in msgs if m[0] == 1)
    n_out = len(msgs) - n_in
    n_tpl = sum(1 for m in msgs if m[0] == 0 and norm_sig(m[2]) in TEMPLATES)
    g['in'] += n_in; g['out'] += n_out; g['tpl'] += n_tpl
    if n_in >= 2: g['dial'] += 1
    gaps, asked = [], False
    last_in_txt = ''
    for i, m in enumerate(msgs):
        if m[0] == 1:
            last_in_txt = m[2]
            t0 = _ts(m[1])
            for m2 in msgs[i + 1:]:
                if m2[0] == 0:
                    g['inAns'] += 1
                    t1 = _ts(m2[1])
                    if t0 and t1 and t1 > t0: gaps.append((t1 - t0) / 3600)
                    break
        elif norm_sig(m[2]) not in TEMPLATES and '?' in m[2]:
            asked = True
    g['gaps'] += gaps
    if gaps: CONTACT_RT[cv.get('contactId')] += gaps
    if n_in >= 1:
        ct = cmap_all.get(cv.get('contactId')) or {}
        nombre = (ct.get('name') or '(sin nombre)').strip().title()
        sc = score_of(ct) if ct else 0
        rt = statistics.median(gaps) if gaps else None
        tplp = round(n_tpl / n_out * 100) if n_out else 0
        esperando = cv.get('lastDir') == 'inbound'
        tema, reco_kw = kw_of(last_in_txt)
        # análisis + recomendación por lead (reglas sobre lo conversado)
        an = []
        if n_out == 0:
            an.append('El lead escribió y nunca recibió un mensaje: contactar de inmediato.')
        else:
            if tplp >= 90: an.append('Solo recibió plantillas — no hubo gestión personal.')
            elif tplp >= 60: an.append('Gestión mayormente de plantillas, poca conversación propia.')
            elif n_in >= 2 and asked: an.append('Diálogo real con preguntas de calificación: buena conexión.')
            elif n_in >= 2: an.append('Hubo diálogo, pero sin preguntas de calificación registradas.')
            if rt is not None:
                if rt <= 1: an.append('Respuesta ágil (≤1 h).')
                elif rt >= 24: an.append(f'Respuestas tardías (mediana {rt/24:.0f} d): el lead se enfría.')
        if esperando:
            an.append('⏳ Está esperando respuesta' + (f' — preguntó por {tema}.' if tema else '.'))
            if reco_kw: an.append('Recomendación: ' + reco_kw)
            elif n_out > 0: an.append('Recomendación: retomar hoy con respuesta personal, no plantilla.')
        elif tema:
            an.append(f'Último interés del lead: {tema}.')
        if sc >= 30 and esperando: an.insert(0, '🔥 PRIORIDAD: lead tibio/caliente desatendido.')
        LEADCONVS[a].append([nombre, sc, None if rt is None else round(rt, 1), tplp,
                             1 if esperando else 0, ' '.join(an)])
for a in LEADCONVS:
    LEADCONVS[a].sort(key=lambda x: (-x[4], -x[1]))
CONTACT_RTM = {k: round(statistics.median(v), 1) for k, v in CONTACT_RT.items() if v}


# ---------- followers: el asesor cuenta como owner O seguidor (solo lectura) ----------
try:
    _FWMAP = json.load(open(DATA / 'followers.json'))
except Exception:
    _FWMAP = {}
def fols(c):
    """user ids que siguen al contacto (del fetch o del mapa aparte)."""
    return c.get('followers') or _FWMAP.get(c['id'], [])
# gestión por lead (llamadas/TMO, emails, tareas, notas) de carteras humanas — ghl_fetch_gestion.py
try:
    GESTION = json.load(open(DATA / 'gestion.json'))
except Exception:
    GESTION = {}

# tiempo de 1ª atención: primer mensaje SALIENTE de WhatsApp menos creación del lead
FIRST_OUT = {}
for cv in wa_all:
    _cid = cv.get('contactId')
    for m in cv['msgs']:
        if m[0] == 0 and m[1]:
            if _cid not in FIRST_OUT or m[1] < FIRST_OUT[_cid]:
                FIRST_OUT[_cid] = m[1]
            break

def _atn(ct):
    fo = FIRST_OUT.get(ct['id'])
    t1 = _ts(fo) if fo else None
    t0 = _ts(ct.get('created')) if ct.get('created') else None
    if t1 is None or t0 is None: return -1
    h = (t1 - t0) / 3600
    return round(h, 1) if h >= 0 else -1

def conv_stats(a):
    g = ACONV.get(a)
    if not g or (g['in'] == 0 and g['out'] == 0): return None
    return {'rt': round(statistics.median(g['gaps']), 1) if g['gaps'] else None,
            'ans': round(g['inAns'] / g['in'] * 100) if g['in'] else None,
            'tpl': round(g['tpl'] / g['out'] * 100) if g['out'] else None,
            'dial': g['dial'], 'convs': g['convs']}

# anexar resp. mediana y etiquetas por lead a las filas de leads y a la cola de espera
CONTACT_TAGS = {}
for i, ct in enumerate(contacts):
    LEADS[i].append(CONTACT_RTM.get(ct['id']))
    tg = [giTG(t.strip()) for t in (ct.get('tags') or [])[:8] if t and t.strip()]
    LEADS[i].append(tg)
    LEADS[i].append(_num(ct.get('vecesContactado')) + _num(ct.get('salesActivities')))
    LEADS[i].append(_atn(ct))
    _g = GESTION.get(ct['id'])
    if _g:
        LEADS[i].append([_g['c'][0], _g['c'][1], _g['c'][2], _g['c'][3], _g['e'],
                         len(_g['t']), sum(1 for _t in _g['t'] if _t[1]), len(_g['n'])])
        LEADS[i].append(_g['n'][:6] or 0)
        LEADS[i].append(_g['t'][:6] or 0)
        _f = _g.get('f')
        if _f:
            _wc = [_x for _x in _f if _x[1] in ('w', 'c')]
            LEADS[i].append([len(_f), len({_x[0] for _x in _f}),
                             sum(1 for _x in _f if _x[1] == 'w'), sum(1 for _x in _f if _x[1] == 'c'),
                             sum(1 for _x in _f if _x[1] == 'e'), sum(1 for _x in _f if _x[1] == 's'),
                             _f[0][0], _f[-1][0],
                             len(_wc), len({_x[0] for _x in _wc})])
        else:
            LEADS[i].append(0)
    else:
        LEADS[i] += [0, 0, 0, 0]
    LEADS[i].append([giASE(users[u]) for u in fols(ct) if u in users])
    LEADS[i].append((_SC2.get(ct['id']) or {}).get('fl', ''))
    LEADS[i].append((_SC2.get(ct['id']) or {}).get('d', []))
    _op = opp_of(ct)
    LEADS[i].append([giOP(_STG.get(_op['stage'], '(etapa desconocida)')),
                     _ST_ES.get((_op.get('status') or '').lower(), _op.get('status') or ''),
                     (_op.get('stageChange') or _op.get('created') or '')[:10]] if _op else 0)
    CONTACT_TAGS[ct['id']] = tg
for a in PENDS:
    for row in PENDS[a]:
        row.append(CONTACT_TAGS.get(row[7], []))
        row[7] = CONTACT_RTM.get(row[7])

NOTAS = {
 'Sol Angeris': 'Muestra leída: responde en minutos y califica como un manual (presupuesto, fechas, mascotas, crédito) y mueve a llamada. Pero deja preguntas puntuales de cuota inicial y crédito sin cerrar, y 9 conversaciones suyas están en la cola de espera.',
 'Natalia Cardenas': 'Muestra leída: el mejor manejo de objeción económica de toda la muestra (empatía + recontacto con fecha concreta). El resto de su actividad es mayormente plantilla.',
 'Diana Navas': 'Muestra leída: gestión de eventos impecable — confirma, pide cédula y acompañantes y cierra el registro completo en la misma conversación.',
 'Fatima Gouveia': 'Muestra leída: retoma leads de campañas y mantiene abandono bajo (1,4%), pero dejó pasar la objeción de visa sin usar el argumento de crédito sin residencia que la propia empresa promueve.',
 'Valentina Reyes': 'Muestra leída: convocatoria a eventos efectiva. Alerta: mensajes con nombre cruzado (un "Hola Guidion" enviado a Bernardo) y leads pidiendo "hablar con asesor" sin siguiente paso.',
 'Catalina Wills': 'Muestra leída: la respuesta mediana fue ~125 días — los clientes contestan y la respuesta llega meses después o nunca; 12 de 16 convos fueron monólogos de plantilla.',
 'Alexandra Delgado': 'Muestra leída: respuesta mediana ~28 horas; preguntas sobre eventos se contestaron al día siguiente.',
 'Patricia Gomez': 'Muestra leída: 0 esperando en el universo pero 15/16 de su muestra son broadcasts; una clienta reclamó una llamada prometida ("aún no recibo llamadas") y recibió plantillas de marketing como respuesta.',
 'Sandra Osorio': 'Muestra leída: atiende clientes Elite, reactiva con preguntas y mostró conocimiento de mercado (locales comerciales), aunque con errores de digitación; respuesta mediana 13,2 h.',
 'Marilyn Jinete': 'Muestra leída: 0/16 diálogos — actividad casi 100% plantillas. Detectó un lead sin visa y no hubo seguimiento con el guión de inversión sin visa.',
 'Nicolas Gaviria': 'Muestra leída: 15/16 monólogos; casi ninguna interacción entrante registrada.',
 'E. Gisell Sanchez': 'Muestra leída: 13/16 monólogos, pero cuando el cliente escribe responde rápido (0,3 h).',
 'MARKETING PFS': 'No es una persona: es la bolsa de automatización de marketing. Se incluye solo como referencia del embudo automático.',
}

# ---------- benchmarks globales ----------
TOT_LEADS = len(contacts)
TOT_CLI = sum(1 for c in contacts if (c.get('leadStatus') or '').strip() == 'Cliente')
G_CONV = TOT_CLI / TOT_LEADS * 100
wa_all = [c for c in convos if c['lastType'] == 'TYPE_WHATSAPP']
G_WPCT = sum(1 for c in wa_all if c['lastDir'] == 'inbound') / len(wa_all) * 100
G_SC = sum(sc for _, sc in cid_by_contact.values()) / len(cid_by_contact)

_G_CONT = sum(1 for r in LEADS if r[12] > 0) / TOT_LEADS * 100
_G_CXL  = sum(r[12] for r in LEADS) / TOT_LEADS
_atns_g = [r[13] for r in LEADS if r[13] >= 0]
_G_ATN  = sum(_atns_g) / len(_atns_g) if _atns_g else None

def pct(x): return f'{x:.1f}'.replace('.', ',') + '%'

# ---------- feedback por reglas ----------
def feedback(nombre, g, act, smp, pend, es_asesor, cs=None):
    leads, cli = g['leads'], g['status'].get('Cliente', 0)
    neg = g['status'].get('Negocio abierto', 0)
    scp = sum(g['scs']) / len(g['scs']) if g['scs'] else 0
    sin_st = g['status'].get('(Sin status)', 0)
    pasiva = g['status'].get('En Nutrición', 0) + sin_st
    wa, ww = (act['wa'], act['waWait']) if act else (0, 0)
    wpct = ww / wa * 100 if wa >= 20 else None
    conv = cli / leads * 100 if leads >= 30 else None
    hotpend = sum(1 for x in pend if x[0] >= 30)
    # tiempo de respuesta: primero el real (todas sus convos), si no el de la muestra
    rtH = cs['rt'] if cs and cs['rt'] is not None else (smp['rtH'] if smp else None)
    fort, mej, reco = [], [], []
    if conv is not None and conv >= G_CONV * 1.3 and cli >= 5:
        fort.append(f'Convierte por encima de la compañía: {fmt(cli)} clientes en {fmt(leads)} leads ({pct(conv)} vs {pct(G_CONV)} promedio).')
    elif cli >= 20:
        fort.append(f'Cartera con resultados: {fmt(cli)} clientes acumulados.')
    if neg >= 3: fort.append(f'{fmt(neg)} negocios abiertos activos — pipeline vivo cerca del cierre.')
    if wpct is not None and wpct <= 2:
        fort.append(f'Disciplina de respuesta en WhatsApp: solo {fmt(ww)} de {fmt(wa)} conversaciones con el cliente esperando ({pct(wpct)} vs {pct(G_WPCT)} promedio).')
    if rtH is not None and rtH <= 2:
        origen_rt = 'sobre TODAS sus conversaciones' if cs and cs['rt'] is not None else 'en la muestra leída'
        fort.append(f'Velocidad: respuesta mediana de {rtH*60:.0f} min {origen_rt} — el estándar que necesita un lead digital.')
    if cs and cs['ans'] is not None and cs['ans'] >= 95 and cs['convs'] >= 20:
        fort.append(f'Responde el {cs["ans"]}% de los mensajes entrantes de sus leads.')
    if cs and cs['tpl'] is not None and cs['tpl'] <= 50 and cs['convs'] >= 20:
        fort.append(f'Conexión personal: solo {cs["tpl"]}% de sus mensajes son plantillas — conversa con criterio propio.')
    if smp and smp['dial'] >= 6:
        fort.append(f'Conversa de verdad: {smp["dial"]} de {smp["n"]} convos muestreadas con diálogo real (cliente escribió 2+ veces).')
    if g['hot'] > 0 and hotpend == 0 and wa >= 20:
        fort.append(f'Sus {fmt(g["hot"])} leads calientes están atendidos: ninguno en la cola de espera.')
    if scp >= G_SC * 1.3 and leads >= 30:
        fort.append(f'Cartera más caliente que el promedio (score {scp:.0f} vs {G_SC:.0f}).')
    if act and act['calls'] >= 40:
        fort.append(f'Actividad telefónica alta: {fmt(act["calls"])} conversaciones de llamada registradas.')
    if wpct is not None and wpct >= 5:
        mej.append(f'{pct(wpct)} de sus conversaciones de WhatsApp tienen al cliente esperando respuesta (promedio compañía {pct(G_WPCT)}).')
    if hotpend > 0:
        mej.append(f'Tiene {fmt(hotpend)} leads tibios o calientes (score ≥30) esperando respuesta — dinero sobre la mesa.')
    if rtH is not None and rtH >= 24:
        origen_rt = 'sobre todas sus conversaciones' if cs and cs['rt'] is not None else 'en la muestra'
        mej.append(f'Respuesta mediana de {rtH/24:.0f} día(s) {origen_rt}: el lead digital se enfría en horas, no en días.')
    if cs and cs['ans'] is not None and cs['ans'] < 75 and cs['convs'] >= 20:
        mej.append(f'Solo responde el {cs["ans"]}% de los mensajes entrantes de sus leads.')
    if cs and cs['tpl'] is not None and cs['tpl'] >= 85 and cs['convs'] >= 20:
        mej.append(f'El {cs["tpl"]}% de sus mensajes salientes son plantillas masivas: no hay conexión personal con el lead.')
    if smp and smp['mono'] >= 12:
        mej.append(f'{smp["mono"]} de {smp["n"]} convos muestreadas son monólogos de plantillas: mucha automatización, poca gestión personal.')
    if leads >= 50 and sin_st / leads >= .15:
        mej.append(f'{pct(sin_st/leads*100)} de su cartera no tiene Lead Status: sin clasificar no se puede priorizar.')
    if leads >= 100 and pasiva / leads >= .7:
        mej.append(f'{pct(pasiva/leads*100)} de la cartera está pasiva (En Nutrición o sin status).')
    if conv is not None and conv < G_CONV * 0.4 and leads >= 150:
        mej.append(f'Conversión baja para el tamaño de su cartera: {fmt(cli)} clientes en {fmt(leads)} leads ({pct(conv)}).')
    if es_asesor and act and act['calls'] < 10 and leads >= 300:
        mej.append(f'Poca actividad telefónica registrada ({fmt(act["calls"])} llamadas) para una cartera de {fmt(leads)} leads.')
    if hotpend: reco.append(f'HOY: responder los {fmt(hotpend)} leads con score ≥30 de su cola (lista abajo, con enlace directo al WhatsApp).')
    if wpct is not None and wpct >= 3: reco.append('Barrido diario de 20 minutos de la bandeja de WhatsApp al final del día; meta: SLA de respuesta < 1 hora hábil.')
    if smp and smp['mono'] >= 10: reco.append('Pasar de plantilla a pregunta: cerrar cada envío con UNA pregunta de calificación (presupuesto, horizonte, crédito) para provocar diálogo.')
    if leads >= 50 and sin_st / leads >= .15: reco.append('Sesión de limpieza de cartera: diligenciar Lead Status y "En curso por" — son la base del scoring y de la priorización.')
    if rtH is not None and rtH >= 24: reco.append('Activar notificaciones móviles del CRM o acordar un respaldo de primera respuesta cuando no esté disponible.')
    if conv is not None and conv >= G_CONV * 1.3 and cli >= 5: reco.append('Documentar su método y hacer mentoría interna: su proceso es replicable y el equipo lo necesita.')
    if not reco: reco.append('Mantener el estándar actual; auditar su propia cola de espera cada semana y registrar toda gestión en el CRM.')
    # nivel
    pts, has_data = 0, (leads >= 30 or wa >= 20)
    if wpct is not None: pts += 2 if wpct <= 2 else (1 if wpct <= 4 else (-2 if wpct >= 6 else 0))
    if rtH is not None: pts += 2 if rtH <= 2 else (-2 if rtH >= 24 else 0)
    if smp: pts += (1 if smp['dial'] >= 6 else 0) - (1 if smp['mono'] >= 12 else 0)
    if conv is not None: pts += 2 if conv >= G_CONV * 1.3 else (1 if conv >= G_CONV * 0.7 else (-1 if conv < G_CONV * 0.3 else 0))
    pts -= 2 if hotpend > 2 else (1 if hotpend > 0 else 0)
    if nombre in ('MARKETING PFS', '(Sin asesor asignado)'):
        nivel = ['Automatización / sin dueño — no aplica evaluación individual', '#5B6B85']
    elif '(deactivated' in nombre.lower():
        nivel = ['Usuario desactivado — cartera huérfana por reasignar', '#5B6B85']
    elif not has_data:
        nivel = ['Evidencia insuficiente para evaluar', '#8A99A8']
    elif pts >= 3:
        nivel = ['Desempeño sólido', '#1E9E62']
    elif pts >= 0:
        nivel = ['Estable, con oportunidades claras', '#AA9664']
    else:
        nivel = ['Requiere plan de mejora inmediato', '#D64545']
    return fort, mej, reco, nivel

# ---------- payload ----------
def pack(nombre, g, act, smp, pend, es_asesor):
    cs = conv_stats(nombre)
    fort, mej, reco, nivel = feedback(nombre, g, act, smp, pend, es_asesor, cs)
    scp = sum(g['scs']) / len(g['scs']) if g['scs'] else 0
    return {
        'rtAll': cs['rt'] if cs else None, 'ansPct': cs['ans'] if cs else None,
        'tplPct': cs['tpl'] if cs else None, 'dialN': cs['dial'] if cs else 0,
        'convsN': cs['convs'] if cs else 0,
        'lconvs': LEADCONVS.get(nombre, [])[:150],
        'leads': g['leads'], 'cli': g['status'].get('Cliente', 0),
        'neg': g['status'].get('Negocio abierto', 0),
        'hot': g['hot'], 'warm': g['warm'], 'sc': round(scp, 1),
        'status': [[s, g['status'][s]] for s in STATUS_ORDER if g['status'].get(s)],
        'curso': sorted(g['curso'].items(), key=lambda x: -x[1])[:5],
        'oport': sum(n for k2, n in g['curso'].items() if k2.startswith('Oportunidad')),
        'encurso': g['status'].get('En curso', 0),
        'cold': sum(1 for s in g['scs'] if 10 <= s < 30),
        'none': sum(1 for s in g['scs'] if s < 10),
        'fuentes': g['fuentes'].most_common(5),
        'wa': act['wa'] if act else 0, 'waWait': act['waWait'] if act else 0,
        'calls': act['calls'] if act else 0, 'emails': act['emails'] if act else 0,
        'sample': smp, 'pend': pend[:12], 'pendTot': len(pend),
        'fort': fort, 'mej': mej, 'reco': reco, 'nivel': nivel,
        'nota': NOTAS.get(nombre)
    }

PEOPLE = {}
for a, g in A.items():
    if g['leads'] < 10 and ACT.get(a, {}).get('wa', 0) < 10: continue
    PEOPLE['a:' + a] = pack(a, g, ACT.get(a), SMP.get(a), PENDS.get(a, []), True)
for r, g in R.items():
    if g['leads'] < 20: continue
    act = ACT.get(r)      # realtor que también es usuario del CRM (mismo nombre)
    smp = SMP.get(r)
    PEOPLE['r:' + r] = pack(r, g, act, smp, PENDS.get(r, []), False)

orden_a = sorted([k for k in PEOPLE if k.startswith('a:')], key=lambda k: -PEOPLE[k]['leads'])
orden_r = sorted([k for k in PEOPLE if k.startswith('r:')], key=lambda k: -PEOPLE[k]['leads'])
PAYLOAD = json.dumps({'p': PEOPLE, 'ordenA': orden_a, 'ordenR': orden_r,
                      'bench': {'conv': round(G_CONV, 1), 'wpct': round(G_WPCT, 1), 'sc': round(G_SC, 1), 'cont': round(_G_CONT, 1), 'cxl': round(_G_CXL, 1), 'atn': round(_G_ATN, 1) if _G_ATN is not None else None},
                      'leads': LEADS, 'ase': ordered(DASE), 'rl': ordered(DRL),
                      'fu': ordered(DFU), 'cu': ordered(DCU), 'sts': STATUS_ORDER,
                      'tg': ordered(DTG), 'opp': ordered(DOP)},
                     ensure_ascii=False)

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gestión de asesores comerciales</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:14.5px;line-height:1.5}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 20px 50px}}
header{{background:var(--azul-oscuro);color:#fff;padding:20px 0}}
header .wrap{{display:flex;align-items:center;gap:14px;padding-bottom:0;flex-wrap:wrap}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:21px;letter-spacing:1px;padding:11px 13px;border-radius:9px}}
header h1{{font-size:18.5px;font-weight:800}} header p{{color:#C9D6E4;font-size:12.5px;margin-top:2px}}
.navbtn{{background:#ffffff1a;border:1.5px solid #C9D6E455;color:#F2F6FA;text-decoration:none;font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:9px;white-space:nowrap}}
.navbtn:hover{{background:#ffffff2e}}
.navgrp{{margin-left:auto;display:flex;gap:8px}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
h2{{font-size:16.5px;margin:26px 0 8px;border-bottom:2px solid var(--gris-linea);padding-bottom:5px}}
h3{{font-size:14px;margin:16px 0 6px}}
.fbar{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 15px;margin:16px 0 6px;font-size:13px}}
.fbar label{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);font-weight:800;display:block;margin-bottom:3px}}
.fbar select{{border:1.5px solid var(--gris-linea);border-radius:8px;padding:7px 10px;font-size:13px;background:#fff;color:var(--tinta);font-weight:600;min-width:230px}}
.btn{{border:0;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:8px;padding:9px 14px;font-size:12.5px;font-weight:700;cursor:pointer}}
.pies2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;align-items:start}}
.pie-box svg{{width:100%;max-width:380px;height:auto;display:block}}
.pleg{{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12.2px;margin-top:4px}}
.pleg .dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.pslice:hover{{opacity:.85}}
.nivchip{{display:inline-block;border:1.5px solid var(--gris-linea);border-radius:16px;padding:3px 11px;font-size:12px;font-weight:700;cursor:pointer;margin:2px 3px 2px 0;background:#fff}}
.nivchip:hover{{border-color:var(--azul);background:var(--azul-suave)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:14px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:10px 12px}}
.kpi b{{font-size:21px;display:block}} .kpi span{{font-size:11px;color:var(--gris)}}
.kpi[data-lf]{{cursor:pointer}} .kpi[data-lf]:hover{{border-color:var(--azul);background:var(--gris-fondo)}}
tr.clk[data-lf]{{cursor:pointer}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 4px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:7px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:top}}
tr:hover td{{background:var(--gris-fondo)}}
tbody tr.clk{{cursor:pointer}}
.note{{font-size:12px;color:var(--gris);margin:4px 0 10px}}
.tag{{display:inline-block;padding:2px 10px;border-radius:20px;font-weight:700;font-size:11.5px;color:#fff;white-space:nowrap}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
.bar{{background:var(--gris-fondo);border-radius:6px;height:16px;position:relative;min-width:120px}}
.bar>div{{height:100%;border-radius:6px;background:var(--azul)}}
.fb{{border-radius:11px;padding:13px 16px;margin:8px 0}}
.fb.f{{background:#E9F6EF;border:1px solid #BEE3CE}} .fb.m{{background:#FBF3E4;border:1px solid #EAD9B0}}
.fb.r{{background:var(--azul-suave);border:1px solid #C9D9E8}}
.fb b{{display:block;margin-bottom:5px}}
.fb ul{{padding-left:18px}} .fb li{{margin:4px 0}}
.quote{{border-left:3px solid var(--amarillo);background:var(--gris-fondo);padding:8px 12px;border-radius:0 9px 9px 0;margin:8px 0;font-size:13px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:26px}}
.caveat{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.5px;margin:14px 0;color:#3d4c63}}
[data-tip]{{cursor:help}} th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}}
a{{color:var(--azul)}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Gestión de asesores comerciales y realtors</h1>
<p>CRM comercial (solo lectura) · Corte: {CORTE}</p></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html" class="act"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="caveat"><b>Cómo leer este informe.</b> Todo sale de los registros del CRM al corte: cartera asignada, lead scoring, conversaciones de WhatsApp / llamadas / email y una muestra cualitativa leída de 224 conversaciones (16 por asesor con más volumen). Benchmarks de la compañía: conversión a Cliente {pct(G_CONV)} · conversaciones con cliente esperando {pct(G_WPCT)} · score promedio {G_SC:.1f}. <b>Úselo como insumo estructurado, no como veredicto único:</b> la asignación masiva de carteras, los campos sin diligenciar y el tamaño de la muestra afectan las métricas individuales. Antes de decisiones de personal, contraste con el contexto de cada asesor (metas, canal principal, gestión fuera del CRM) y déle la oportunidad de explicar sus números.</div>

<div class="fbar">
<div><label data-tip="La cartera del asesor incluye los contactos donde es OWNER o SEGUIDOR (followers). Solo cambia la consulta del reporte — el CRM no se modifica.">Auditar asesor comercial</label><select id="f-a" autocomplete="off"></select></div>
<div><label>Auditar realtor</label><select id="f-r" autocomplete="off"></select></div>
<div><label data-tip="Filtra la cartera, las tablas de leads y la cola de espera por la fecha de creación del lead en el CRM (dateAdded). La actividad de conversaciones, el análisis lead a lead y la retroalimentación siguen siendo del histórico completo.">Lead creado desde</label><input type="date" id="f-d1" autocomplete="off" style="border:1.5px solid var(--gris-linea);border-radius:8px;padding:6px 9px;font-size:12.5px"></div>
<div><label>Hasta</label><input type="date" id="f-d2" autocomplete="off" style="border:1.5px solid var(--gris-linea);border-radius:8px;padding:6px 9px;font-size:12.5px"></div>
<button class="btn" onclick="verResumen()">↩ Volver al resumen general</button>
</div>

<div id="overview"></div>
<div id="profile" style="display:none"></div>

<div class="warnpii"><b>⚠ Datos personales y laborales:</b> este informe contiene datos de desempeño individual de empleados y datos de contacto de clientes (Habeas Data). Uso exclusivo de la gerencia comercial de [empresa]. No publicar ni circular.</div>
<footer>Generado desde la API de GoHighLevel en modo solo lectura. Cartera = contactos con assignedTo del asesor (o campo Realtor). Actividad = conversaciones por canal del último mensaje. Score y fuentes con las mismas fórmulas del reporte de contactos. Muestra cualitativa: 224 conversaciones leídas al corte {CORTE}. Los umbrales del semáforo: sólido ≥3 pts, estable 0-2, plan de mejora &lt;0 — puntos por velocidad y disciplina de respuesta, diálogo real, conversión vs promedio y leads calientes en espera.</footer>
</div>
<script>
const D = {PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const pc = (a, b) => b ? (a / b * 100).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + '%' : '—';
const scCol = s => s >= 55 ? '#D64545' : s >= 30 ? '#AA9664' : s >= 10 ? '#3A566B' : '#8A99A8';
const SCOL = {{'Cliente':'#2C4356','Negocio abierto':'#1E9E62','En curso':'#3A566B','Intento de contacto':'#AA9664','Nuevo':'#8A6D1A','En Nutrición':'#8A99A8','Descartado':'#D64545','(Sin status)':'#5B6B85'}};

const selA = document.getElementById('f-a'), selR = document.getElementById('f-r');
selA.innerHTML = '<option value="">— Elegir asesor —</option>' + D.ordenA.map(k =>
  `<option value="${{esc(k)}}">${{esc(k.slice(2))}} (${{fN(D.p[k].leads)}} leads)</option>`).join('');
selR.innerHTML = '<option value="">— Elegir realtor —</option>' + D.ordenR.map(k =>
  `<option value="${{esc(k)}}">${{esc(k.slice(2))}} (${{fN(D.p[k].leads)}} leads)</option>`).join('');
selA.addEventListener('change', () => {{ if (selA.value) {{ selR.value = ''; verPerfil(selA.value); }} }});
selR.addEventListener('change', () => {{ if (selR.value) {{ selA.value = ''; verPerfil(selR.value); }} }});

/* rango de fechas de creación del lead */
let CURV = null;
const rangoOn = () => document.getElementById('f-d1').value !== '' || document.getElementById('f-d2').value !== '';
const inR = cr => {{
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  return (d1 === '' || (cr && cr >= d1)) && (d2 === '' || (cr && cr <= d2));
}};
['f-d1', 'f-d2'].forEach(id => document.getElementById(id).addEventListener('change', () => {{
  CURV ? verPerfil(CURV) : verResumen();
}}));
function personRows(k) {{ return leadsDe(k).filter(r => inR(r[9])); }}
function carteraCalc(rs) {{
  const st = new Map(), fu = new Map(), cu = new Map();
  let hot = 0, warm = 0, sum = 0;
  let cold = 0, none = 0;
  let cont = 0, isum = 0, atnS = 0, atnN = 0;
  let gCov = 0, gOut = 0, gIn = 0, gAns = 0, gSecs = 0, gEm = 0, gTT = 0, gTD = 0, gNo = 0, gLN = 0, gLC = 0;
  let iCov = 0, iTot = 0, iDias = 0, iW = 0, iC = 0, iE = 0, iS = 0, iLW = 0, iLC = 0, iLE = 0, iLS = 0, i2 = 0, iMulti = 0, iBurst = 0, iMix = 0;
  rs.forEach(r => {{
    st.set(r[6], (st.get(r[6]) || 0) + 1);
    fu.set(r[5], (fu.get(r[5]) || 0) + 1);
    cu.set(r[7], (cu.get(r[7]) || 0) + 1);
    if (r[8] >= 55) hot++; else if (r[8] >= 30) warm++; else if (r[8] >= 10) cold++; else none++;
    sum += r[8];
    if (r[12] > 0) cont++; isum += (r[12] || 0);
    if (r[13] >= 0) {{ atnS += r[13]; atnN++; }}
    if (r[14]) {{
      gCov++; gOut += r[14][0]; gIn += r[14][1]; gAns += r[14][2]; gSecs += r[14][3];
      gEm += r[14][4]; gTT += r[14][5]; gTD += r[14][6]; gNo += r[14][7];
      if (r[14][7] > 0) gLN++; if (r[14][0] + r[14][1] > 0) gLC++;
    }}
    if (r[17]) {{
      iCov++; iTot += r[17][0]; iDias += r[17][1];
      iW += r[17][2]; iC += r[17][3]; iE += r[17][4]; iS += r[17][5];
      if (r[17][2] > 0) iLW++; if (r[17][3] > 0) iLC++; if (r[17][4] > 0) iLE++; if (r[17][5] > 0) iLS++;
      const canales = (r[17][2] > 0) + (r[17][3] > 0) + (r[17][4] > 0) + (r[17][5] > 0);
      if (canales >= 2) iMix++;
      if ((r[17][8] || 0) >= 2) {{ i2++; if ((r[17][9] || 0) >= 2) iMulti++; else iBurst++; }}
    }}
  }});
  const stArr = [...st.entries()].sort((a, b) => a[0] - b[0]).map(([i, n]) => [D.sts[i], n]);
  const stG = s => (stArr.find(x => x[0] === s) || [0, 0])[1];
  return {{
    leads: rs.length, cli: stG('Cliente'), neg: stG('Negocio abierto'), encurso: stG('En curso'),
    oport: [...cu.entries()].filter(([i]) => D.cu[i].startsWith('Oportunidad')).reduce((t, [, n]) => t + n, 0),
    hot, warm, cold, none, sc: rs.length ? Math.round(sum / rs.length * 10) / 10 : 0,
    contPct: rs.length ? cont / rs.length * 100 : 0,
    cxl: rs.length ? isum / rs.length : 0,
    atnH: atnN ? atnS / atnN : null, atnN,
    gCov, gOut, gIn, gAns, gSecs, gEm, gTT, gTD, gNo, gLN, gLC,
    iCov, iTot, iDias, iW, iC, iE, iS, iLW, iLC, iLE, iLS, i2, iMulti, iBurst, iMix,
    status: stArr,
    fuentes: [...fu.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([i, n]) => [D.fu[i], n]),
    curso: [...cu.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([i, n]) => [D.cu[i], n]),
  }};
}}

function nivelTag(p) {{
  return `<span class="tag" style="background:${{p.nivel[1]}}">${{esc(p.nivel[0])}}</span>`;
}}
const stN = (p, s) => s === 'En curso' ? p.encurso : (p.status.find(x => x[0] === s) || [0, 0])[1];
const oportN = p => p.oport;
const rtT = h => h === null || h === undefined ? '—' : h < 1 ? Math.round(h*60) + ' min' : h < 48 ? h.toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + ' h' : Math.round(h/24) + ' d';
const tmoT = secs => {{ const t = Math.round(secs), m = Math.floor(t / 60), ss = t % 60; return m + ':' + String(ss).padStart(2, '0') + ' min'; }};
function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tg[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas del lead en el CRM: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
function filaRk(k) {{
  const p = D.p[k];
  const rws = personRows(k);
  const c = carteraCalc(rws);
  const iA = k.startsWith('a:') ? D.ase.indexOf(k.slice(2)) : -1;
  const oCnt = iA >= 0 ? rws.filter(r => r[0] === iA).length : c.leads;
  const wp = p.wa >= 20 ? pc(p.waWait, p.wa) : '—';
  return `<tr class="clk" data-k="${{esc(k)}}"><td><b>${{esc(k.slice(2))}}</b></td>
    <td>${{fN(c.leads)}}${{c.leads > oCnt ? ` <small style="color:var(--gris)" data-tip="Desglose: ${{fN(oCnt)}} como owner + ${{fN(c.leads - oCnt)}} como seguidor.">(${{fN(oCnt)}}+${{fN(c.leads - oCnt)}})</small>` : ''}}</td><td>${{fN(c.cli)}}</td><td>${{pc(c.cli, c.leads)}}</td><td>${{fN(c.neg)}}</td>
    <td>${{fN(c.encurso)}}</td><td>${{fN(c.oport)}}</td>
    <td style="white-space:nowrap">${{fN(c.hot)}} / ${{fN(c.warm)}} / ${{fN(c.cold)}}</td><td>${{c.sc.toLocaleString('es-CO')}}</td>
    <td>${{c.leads ? c.contPct.toFixed(0) + '%' : '—'}}</td>
    <td>${{c.leads ? c.cxl.toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</td>
    <td>${{c.atnH === null ? '—' : rtT(c.atnH)}}</td>
    <td>${{c.gCov ? (c.gOut / c.gCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</td>
    <td>${{c.gAns ? tmoT(c.gSecs / c.gAns) : '—'}}</td>
    <td>${{c.gCov ? (c.gEm / c.gCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</td>
    <td>${{c.gCov ? fN(c.gTD) + '/' + fN(c.gTT) : '—'}}</td>
    <td>${{c.gCov ? fN(c.gNo) : '—'}}</td>
    <td>${{c.i2 ? `<b style="color:${{c.iMulti / c.i2 >= .6 ? 'var(--verde)' : c.iMulti / c.i2 < .4 ? 'var(--rojo)' : 'var(--naranja)'}}">${{Math.round(c.iMulti / c.i2 * 100)}}%</b>` : '—'}}</td>
    <td>${{fN(p.wa)}}</td><td>${{fN(p.waWait)}} (${{wp}})</td><td>${{rtT(p.rtAll)}}</td><td>${{fN(p.calls)}}</td>
    <td>${{nivelTag(p)}}</td></tr>`;
}}
const THS_RK = `<tr>
<th>Nombre</th>
<th data-tip="Cartera unificada: contactos donde la persona es OWNER (assignedTo) o SEGUIDOR (followers). El desglose (owner+seguidor) aparece cuando hay leads seguidos. Para realtors: campo Realtor.">Leads</th>
<th data-tip="Contactos de su cartera con Lead Status = Cliente.">Clientes</th>
<th data-tip="% de cierre de ventas: clientes ÷ leads de su cartera. Promedio compañía: ${{D.bench.conv}}%. Con rango de fechas activo mide el cierre de esa camada de leads.">% cierre</th>
<th data-tip="Contactos con Lead Status = Negocio abierto: negociaciones activas.">Neg. abiertos</th>
<th data-tip="Contactos de su cartera con Lead Status = En curso: leads en gestión comercial activa.">En curso</th>
<th data-tip="Contactos con el campo 'En curso por' marcado con una oportunidad vigente (1-3, 3-6 o 6+ meses): el horizonte de compra que registró el equipo.">Con oportunidad</th>
<th data-tip="Temperatura de la cartera por lead scoring: calientes (score ≥55) / tibios (30-54) / fríos (10-29). Los sin señales (<10) son el resto de los leads.">🔥 / 🌤 / ❄</th>
<th data-tip="Score promedio de su cartera. Promedio compañía: ${{D.bench.sc}}.">Score prom.</th>
<th data-tip="% de leads contactados: leads de su cartera con al menos una gestión registrada (nº de veces contactado + actividades de venta > 0). Promedio compañía: ${{D.bench.cont}}%.">% contactados</th>
<th data-tip="Contactos promedio por lead: promedio de gestiones registradas (veces contactado + actividades de venta) sobre TODA su cartera, incluidos los nunca tocados. Promedio compañía: ${{D.bench.cxl}}.">Cont./lead</th>
<th data-tip="Tiempo promedio de 1ª atención: primer mensaje SALIENTE de WhatsApp al lead menos su fecha de creación, promediado sobre los leads con conversación de WhatsApp. Promedio compañía: ${{D.bench.atn === null ? 'sin dato' : rtT(D.bench.atn)}}.">1ª atención</th>
<th data-tip="Llamadas SALIENTES por lead: total de llamadas hechas a los leads de su cartera dividido por sus leads con gestión descargada. Fuente: historial de llamadas del CRM (últimos 100 eventos por conversación).">Llam./lead</th>
<th data-tip="TMO — tiempo medio de operación: duración promedio de sus llamadas CONTESTADAS (minutos:segundos hablados por llamada). No incluye llamadas sin respuesta.">TMO</th>
<th data-tip="Emails SALIENTES por lead de su cartera (incluye correos de automatización enviados a nombre del asesor).">Emails/lead</th>
<th data-tip="Tareas en los leads de su cartera: completadas / creadas. Las tareas son los recordatorios de seguimiento que el asesor programa en el CRM.">Tareas ✓/tot</th>
<th data-tip="Notas dejadas en los leads de su cartera: la bitácora escrita de su gestión comercial. Sin notas no queda memoria de qué se habló con el lead.">Notas</th>
<th data-tip="Persistencia: de sus leads con 2+ intentos PERSONALES (WhatsApp o llamada; el goteo de email no cuenta), % que recibió intentos en 2 o más DÍAS DISTINTOS (seguimiento real). El resto fue ráfaga de un solo día. Verde ≥60%, rojo <40%.">Persist.</th>
<th data-tip="Conversaciones cuyo último mensaje es WhatsApp, asignadas a esta persona.">Convos WA</th>
<th data-tip="De sus conversaciones WA, cuántas tienen al cliente con la última palabra sin respuesta (y % si tiene ≥20 convos). Promedio compañía: ${{D.bench.wpct}}%.">WA sin responder</th>
<th data-tip="Tiempo de respuesta al lead: mediana del tiempo entre cada mensaje del cliente y la siguiente respuesta, medido sobre TODAS sus conversaciones de WhatsApp.">Resp. mediana</th>
<th data-tip="Conversaciones cuyo último evento es una llamada.">Llamadas</th>
<th data-tip="Semáforo calculado por reglas: velocidad y disciplina de respuesta, diálogo real en la muestra, conversión vs promedio (${{D.bench.conv}}%) y leads calientes en espera. Ver metodología en el pie.">Nivel</th></tr>`;

function arcPath2(cx, cy, r0, r1, a0, a1) {{
  const pt = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = pt(r1, a0), [x1, y1] = pt(r1, a1), [x2, y2] = pt(r0, a1), [x3, y3] = pt(r0, a0);
  const big = (a1 - a0) > Math.PI ? 1 : 0;
  return `M${{x0}} ${{y0}} A${{r1}} ${{r1}} 0 ${{big}} 1 ${{x1}} ${{y1}} L${{x2}} ${{y2}} A${{r0}} ${{r0}} 0 ${{big}} 0 ${{x3}} ${{y3}} Z`;
}}
function drawNivelPie() {{
  const NIVCORTO = {{
    'Desempeño sólido': '🟢 Sólido',
    'Estable, con oportunidades claras': '🟡 Estable',
    'Requiere plan de mejora inmediato': '🔴 Deficiente — plan de mejora',
    'Evidencia insuficiente para evaluar': '⚪ Evidencia insuficiente',
    'Usuario desactivado — cartera huérfana por reasignar': '⚫ Desactivado / cartera huérfana'
  }};
  const grupos = new Map();
  D.ordenA.forEach(k => {{
    const nom = k.slice(2);
    if (nom === 'MARKETING PFS' || nom.startsWith('(Sin ')) return;
    const nv = D.p[k].nivel;
    const label = NIVCORTO[nv[0]] || nv[0];
    if (!grupos.has(label)) grupos.set(label, {{color: nv[1], ases: []}});
    grupos.get(label).ases.push(k);
  }});
  const ORDEN = Object.values(NIVCORTO);
  const data = [...grupos.entries()].sort((a, b) => ORDEN.indexOf(a[0]) - ORDEN.indexOf(b[0]));
  const total = data.reduce((t, [, g]) => t + g.ases.length, 0);
  const svg = document.getElementById('pie-niv');
  const cx = 170, cy = 112, r0 = 52, r1 = 96;
  let a = -Math.PI / 2, g2 = '';
  data.forEach(([label, g]) => {{
    const a2 = a + g.ases.length / total * 2 * Math.PI;
    const tip = `${{label}}: ${{g.ases.length}} asesor(es) — ${{g.ases.map(k => k.slice(2)).join(', ')}}. El nivel lo asigna el semáforo por reglas (velocidad de respuesta, diálogo real, conversión vs promedio y calientes en espera).`;
    g2 += `<path class="pslice" data-tip="${{esc(tip)}}" d="${{arcPath2(cx, cy, r0, r1, a, Math.min(a2, a + 6.28318))}}" fill="${{g.color}}" stroke="#fff" stroke-width="2"/>`;
    if (g.ases.length / total >= 0.07) {{
      const am = (a + a2) / 2, rx = cx + (r0 + r1) / 2 * Math.cos(am), ry = cy + (r0 + r1) / 2 * Math.sin(am);
      g2 += `<text x="${{rx}}" y="${{ry + 4}}" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" pointer-events="none">${{(g.ases.length / total * 100).toFixed(0)}}%</text>`;
    }}
    a = a2;
  }});
  g2 += `<text x="${{cx}}" y="${{cy - 2}}" text-anchor="middle" font-size="19" font-weight="900" fill="#152238">${{total}}</text>`;
  g2 += `<text x="${{cx}}" y="${{cy + 15}}" text-anchor="middle" font-size="10.5" fill="#5B6B85">asesores evaluados</text>`;
  svg.innerHTML = g2;
  document.getElementById('leg-niv').innerHTML = data.map(([label, g]) =>
    `<span><span class="dot" style="background:${{g.color}}"></span>${{esc(label)}}: <b>${{g.ases.length}}</b></span>`).join('');
  document.getElementById('niv-lista').innerHTML = data.map(([label, g]) => `
    <div style="margin:7px 0"><b style="font-size:12.5px;color:${{g.color}}">${{esc(label)}} (${{g.ases.length}})</b><br>
    ${{g.ases.map(k => `<span class="nivchip" data-k="${{esc(k)}}" data-tip="Clic para abrir la auditoría individual de ${{esc(k.slice(2))}}.">${{esc(k.slice(2))}}</span>`).join('')}}</div>`).join('');
  document.querySelectorAll('#niv-lista .nivchip').forEach(ch => ch.addEventListener('click', () => {{
    selA.value = ch.dataset.k; selR.value = '';
    verPerfil(ch.dataset.k);
  }}));
}}

function verResumen() {{
  CURV = null;
  selA.value = ''; selR.value = '';
  document.getElementById('profile').style.display = 'none';
  const ov = document.getElementById('overview');
  ov.style.display = 'block';
  const notaRango = rangoOn() ? '<p class="note" style="color:var(--naranja);font-weight:700">📅 Rango de fechas activo: las columnas de cartera (leads, clientes, negocios, en curso, oportunidad, calientes, score) están filtradas por fecha de creación del lead. Las columnas de actividad (WA, resp. mediana, llamadas) y el nivel corresponden al histórico completo.</p>' : '';
  /* KPIs de gestión: promedio simple de los valores de cada asesor comercial
     (excluye MARKETING PFS y '(Sin asesor)'; cada asesor pesa igual, tenga 100 o 2.000 leads) */
  const accum = {{}};
  const met = (k2, val) => {{ if (val !== null && isFinite(val)) (accum[k2] = accum[k2] || []).push(val); }};
  let nAses = 0;
  D.ordenA.forEach(k => {{
    const nom = k.slice(2);
    if (nom === 'MARKETING PFS' || nom.startsWith('(Sin ')) return;
    const c = carteraCalc(personRows(k));
    if (!c.leads) return;
    nAses++;
    const pp = D.p[k];
    if (pp && pp.rtAll !== null && pp.rtAll !== undefined) met('rt', pp.rtAll);
    met('cierre', c.cli / c.leads * 100);
    met('cont', c.contPct);
    met('cxl', c.cxl);
    met('sc', c.sc);
    if (c.atnH !== null) met('atn', c.atnH);
    if (c.gCov) {{
      met('llam', c.gOut / c.gCov);
      met('em', c.gEm / c.gCov);
      met('notas', c.gNo / c.gCov);
    }}
    if (c.gAns) met('tmo', c.gSecs / c.gAns);
    if (c.gTT) met('tareas', c.gTD / c.gTT * 100);
    if (c.iCov) met('int', c.iTot / c.iCov);
    if (c.i2) met('multi', c.iMulti / c.i2 * 100);
  }});
  const avg = k2 => accum[k2] && accum[k2].length ? accum[k2].reduce((a, b) => a + b, 0) / accum[k2].length : null;
  const f1 = v2 => v2 === null ? '—' : v2.toLocaleString('es-CO', {{maximumFractionDigits: 1}});
  const fp = v2 => v2 === null ? '—' : v2.toFixed(1).replace('.', ',') + '%';
  const kpiProm = (val, lbl, tip, color) =>
    `<div class="kpi" data-tip="${{esc(tip)}} Promedio simple entre los ${{nAses}} asesores comerciales con cartera (cada asesor pesa igual; MARKETING PFS y sin-asesor quedan fuera). Respeta el rango de fechas de creación del lead."><b style="color:${{color || 'var(--tinta)'}}">${{val}}</b><span>${{lbl}}</span></div>`;
  const kpisGlobal = `
  <h2>Gestión comercial promedio por asesor</h2>
  <p class="note">La vara de medir: el valor promedio de cada KPI entre los asesores comerciales. Al abrir un asesor (clic en su fila) se ven sus valores propios para compararlos contra estos.</p>
  <div class="kpis">
    ${{kpiProm(fp(avg('cierre')), '% cierre de ventas', 'Clientes ÷ leads de la cartera de cada asesor.', 'var(--rojo)')}}
    ${{kpiProm(fp(avg('cont')), '% de leads contactados', 'Leads con al menos una gestión registrada (veces contactado + actividades de venta > 0).', 'var(--verde)')}}
    ${{kpiProm(f1(avg('cxl')), 'contactos promedio por lead', 'Gestiones registradas del CRM promediadas sobre toda la cartera de cada asesor.')}}
    ${{kpiProm(avg('atn') === null ? '—' : rtT(avg('atn')), '1ª atención promedio (WA)', 'Primer mensaje saliente de WhatsApp menos fecha de creación del lead.', 'var(--azul)')}}
    ${{kpiProm(avg('rt') === null ? '—' : rtT(avg('rt')), 'tiempo de respuesta al lead', 'Cuánto tarda cada asesor en responder los mensajes de sus leads: mediana del tiempo entre cada mensaje del cliente y la siguiente respuesta en WhatsApp, promediada entre asesores. (Es del histórico completo: no cambia con el filtro de fechas.)', 'var(--azul)')}}
    ${{kpiProm(f1(avg('int')), 'intentos por lead tocado', 'Toques salientes (WhatsApp + llamadas + emails + SMS) por lead con al menos un intento.')}}
    ${{kpiProm(fp(avg('multi')), 'seguimiento en varios días', 'De los leads con 2+ intentos personales (WhatsApp/llamada), % con intentos en 2 o más días distintos.', 'var(--verde)')}}
    ${{kpiProm(f1(avg('llam')), 'llamadas por lead', 'Llamadas salientes ÷ leads con gestión descargada.')}}
    ${{kpiProm(avg('tmo') === null ? '—' : tmoT(avg('tmo')), 'TMO (duración prom. llamada)', 'Duración promedio de las llamadas contestadas.')}}
    ${{kpiProm(f1(avg('em')), 'emails por lead', 'Emails salientes por lead (incluye goteo automático a nombre del asesor).')}}
    ${{kpiProm(fp(avg('tareas')), 'tareas completadas', 'De las tareas de seguimiento creadas en el CRM, % completadas.')}}
    ${{kpiProm(f1(avg('notas')), 'notas por lead', 'Notas dejadas en el CRM ÷ leads con gestión descargada: la bitácora escrita.')}}
    ${{kpiProm(f1(avg('sc')), 'score promedio de cartera', 'Lead scoring 0-100 promedio de la cartera de cada asesor.')}}
  </div>`;
  ov.innerHTML = notaRango + kpisGlobal + `
  <h2>Clasificación de los asesores por nivel de gestión</h2>
  <p class="note">Cada asesor comercial clasificado por el semáforo de desempeño (reglas sobre velocidad y disciplina de respuesta, diálogo real, conversión vs promedio de compañía y leads calientes en espera — metodología en el pie de página). Clic en un nombre abre su auditoría individual. MARKETING PFS y "sin asesor" no se evalúan: son automatización.</p>
  <div class="pies2">
    <div class="pie-box"><svg id="pie-niv" viewBox="0 0 340 230"></svg><div class="pleg" id="leg-niv"></div></div>
    <div id="niv-lista"></div>
  </div>
  <h2>Resumen general — asesores comerciales</h2>
  <p class="note">Clic en una fila (o use los selectores de arriba) para abrir la auditoría individual completa, con retroalimentación.</p>
  <div style="overflow-x:auto"><table><thead>${{THS_RK}}</thead><tbody>` +
    D.ordenA.map(filaRk).join('') + `</tbody></table></div>
  <h2>Resumen general — realtors</h2>
  <p class="note">Cartera según el campo "Realtor" del contacto. Si el realtor es además usuario del CRM, se le atribuye también su actividad de conversaciones.</p>
  <div style="overflow-x:auto"><table><thead>${{THS_RK}}</thead><tbody>` +
    D.ordenR.map(filaRk).join('') + `</tbody></table></div>`;
  drawNivelPie();
  ov.querySelectorAll('tr.clk').forEach(tr => tr.addEventListener('click', () => {{
    const k = tr.dataset.k;
    if (k.startsWith('a:')) {{ selA.value = k; selR.value = ''; }} else {{ selR.value = k; selA.value = ''; }}
    verPerfil(k);
  }}));
}}

function barra(items, total, tipo) {{
  return items.map(([s, n]) => `
    <tr class="clk" data-lf="${{esc(tipo + ':' + s)}}||${{esc(s)}}" data-tip="Clic para ver la tabla de estos ${{fN(n)}} leads con su teléfono, email y origen.">
    <td style="white-space:nowrap">${{esc(s)}}</td>
    <td style="width:45%"><div class="bar"><div style="width:${{Math.max(2, n/total*100)}}%;background:${{SCOL[s]||'#5B6B85'}}"></div></div></td>
    <td style="white-space:nowrap">${{fN(n)}} · ${{pc(n, total)}}</td></tr>`).join('');
}}

/* ---------- tabla de leads al hacer clic en una variable ---------- */
let CURK = null, LB = {{list: [], shown: 0, label: ''}};
function leadsDe(k) {{
  const nombre = k.slice(2);
  if (k.startsWith('a:')) {{
    const i = D.ase.indexOf(nombre);
    /* cartera = owner O seguidor (followers) — el CRM no se modifica */
    return D.leads.filter(r => r[0] === i || (r[18] && r[18].indexOf(i) !== -1));
  }}
  const i = D.rl.indexOf(nombre);
  return D.leads.filter(r => r[1].includes(i));
}}
function matchLf(r, f) {{
  if (f === 'all') return true;
  if (f === 'oport') return D.cu[r[7]].startsWith('Oportunidad');
  if (f === 'hotwarm') return r[8] >= 30;
  if (f === 'hot') return r[8] >= 55;
  if (f === 'warm') return r[8] >= 30 && r[8] < 55;
  if (f === 'cold') return r[8] >= 10 && r[8] < 30;
  if (f === 'none') return r[8] < 10;
  if (f.startsWith('st:')) return D.sts[r[6]] === f.slice(3);
  if (f.startsWith('fu:')) return D.fu[r[5]] === f.slice(3);
  if (f.startsWith('cu:')) return D.cu[r[7]] === f.slice(3);
  return false;
}}
// ¿Por qué ese score? — explicación simple para el asesor (r[19]=flags, r[20]=[compra,etapa,respuesta,reciente])
function scDesg(r) {{
  const d = r[20] || [];
  if (d.length !== 4) return '';
  const fl = r[19] || '', sc = r[8];
  const st = D.sts[r[6]] || '(sin status)';
  let e1;
  if (fl.indexOf('Z') !== -1) e1 = 'dijo que quiere comprar' + (fl.indexOf('M') !== -1 ? ' y habló de monto' : '') + ', PERO pidió aplazar la decisión — por eso este punto se limita a 15';
  else if (fl.indexOf('P') !== -1) e1 = 'citó una PROPIEDAD ESPECÍFICA (número MLS o "me interesa esta propiedad"): ya eligió qué quiere — intención máxima';
  else if (d[0] >= 30) e1 = 'habló de un monto de compra en notas o mensajes';
  else if (d[0] >= 22) e1 = 'declaró intención de compra o tiene presupuesto diligenciado';
  else if (d[0] >= 18) e1 = 'tiene horizonte de compra declarado (campo En curso por)';
  else e1 = 'no ha dicho que quiera comprar: sin monto, sin horizonte y sin presupuesto';
  const e3 = d[2] >= 16 ? 'responde y conversa activamente (mensajes o llamadas contestadas)'
           : d[2] >= 8 ? 'sí ha respondido a la gestión al menos una vez'
           : 'casi no ha respondido a la gestión — sin respuesta solo puede sumar hasta 4';
  const e4 = d[3] >= 20 ? 'tuvo actividad esta última semana'
           : d[3] >= 15 ? 'tuvo actividad en el último mes'
           : d[3] >= 8 ? 'su última actividad fue hace 1 a 3 meses'
           : d[3] >= 4 ? 'su última actividad fue hace 3 a 6 meses'
           : 'lleva más de 6 meses sin ninguna actividad';
  return `Este lead tiene ${{sc}} de 100 puntos por estas 4 razones: ` +
    `① GANAS DE COMPRAR: ${{d[0]}} de 35 pts — ${{e1}}. ` +
    `② ETAPA EN EL CRM: ${{d[1]}} de 25 pts — su lead status es «${{st}}». ` +
    `③ RESPUESTAS DEL LEAD: ${{d[2]}} de 20 pts — ${{e3}}. ` +
    `④ ACTIVIDAD RECIENTE: ${{d[3]}} de 20 pts — ${{e4}}.`;
}}
function waBtn(dig) {{
  return dig ? `<a href="https://wa.me/${{dig}}" target="_blank" style="display:inline-block;background:#25D366;color:#fff;border-radius:8px;padding:4px 9px;white-space:nowrap;font-size:.74rem;font-weight:700;text-decoration:none" data-tip="Escribirle directamente por WhatsApp (abre wa.me con su número).">💬 WhatsApp</a>` : '<span style="color:#B9BDCC">—</span>';
}}
// Oportunidad en el pipeline: r[21] = [etapaIdx, estado, fecha último cambio] ó 0 si nunca entró
function opCell(r) {{
  const o = r[21];
  if (!o) return '<span style="color:#B9BDCC" data-tip="Este lead NO tiene oportunidad creada en el pipeline de ventas: nunca ha entrado al embudo comercial.">—</span>';
  const col = o[1] === 'abierta' ? '#1D7A46' : o[1] === 'ganada' ? '#0F6E56' : '#A33B3B';
  return `<span style="white-space:nowrap;cursor:help" data-tip="Tiene OPORTUNIDAD en el pipeline de ventas: etapa «${{esc(D.opp[o[0]])}}» (${{esc(o[1])}}). Último cambio de etapa: ${{esc(o[2] || 'sin fecha')}}.">` +
    `<b>${{esc(D.opp[o[0]])}}</b><small style="display:block;color:${{col}};font-size:.68rem">${{esc(o[1])}} · ${{esc(o[2] || '')}}</small></span>`;
}}
// Próximas tareas del asesor para CONVERTIR el lead, según su diagnóstico
function tareasDe(r) {{
  const d = r[20] || [0, 0, 0, 0], fl = r[19] || '', sc = r[8], t = [];
  const intTot = (r[17] && r[17][0]) || 0;
  if (fl.indexOf('Z') !== -1) t.push(['⏰', 'Agendar recontacto en la fecha aplazada', 'Crear tarea de recontacto para la fecha que él mismo dio ("retomar en…") y, mientras, enviar solo contenido de valor sin presionar.']);
  if (fl.indexOf('P') !== -1) t.push(['🏠', 'Responder YA sobre la propiedad que pidió', 'El lead citó una propiedad concreta (MLS): responder en menos de 1 hora con precio, disponibilidad y ficha de ESA propiedad + 1-2 alternativas similares, y proponer visita o videollamada de inmediato. Es el lead de mayor intención que existe.']);
  if (fl.indexOf('M') !== -1) t.push(['💰', 'Meet 1:1 con opciones en su rango de monto', 'Prioridad alta: agendar meet 1:1 y llegar con 2-3 opciones concretas dentro del rango de monto que declaró.']);
  else if (fl.indexOf('C') !== -1) t.push(['🎯', 'Confirmar presupuesto y forma de pago', 'Ya declaró interés de compra: confirmar presupuesto y forma de pago (cash o crédito) con una pregunta directa.']);
  if (d[2] <= 4) t.push(intTot >= 6
    ? ['🔀', 'Cambiar canal y horario', `Lleva ${{intTot}} intentos sin eco: cambiar canal Y horario (llamada en otra franja + WhatsApp con UNA pregunta corta); si sigue mudo, pasar a nutrición con alerta de reactivación.`]
    : ['📞', 'Insistir multi-canal en días distintos', 'Aún no responde: insistir multi-canal en días distintos (llamada + WhatsApp + email) antes de darlo por frío.']);
  if (d[0] === 0) t.push(['❓', 'Calificar: ¿invertir, vivir o arrendar?', 'Sin intención conocida: hacer la pregunta clave — ¿comprar para invertir, para vivir o arrendar? — y diligenciar "En curso por" y presupuesto en el CRM.']);
  if (d[3] <= 4) t.push(['🧊', 'Reactivar con una novedad concreta', 'Sin actividad reciente: reactivar con una novedad concreta (proyecto, tasa, oportunidad) y llamar al día siguiente del mensaje.']);
  if (d[1] >= 25) t.push(['🏁', 'Cerrar: proforma y fecha de firma', 'Negocio abierto: definir unidad, enviar proforma y proponer fecha de firma — ponerle fecha límite al cierre.']);
  else if (sc >= 55 && d[2] >= 8) t.push(['🔥', 'Videollamada de precalificación en <48 h', 'Caliente y responde: proponer videollamada de precalificación en menos de 48 horas y presentar opciones — no dejarlo enfriar.']);
  if (!t.length) t.push(['🌱', 'Nutrición con toque personal mensual', 'Mantener en nutrición con un toque personal al mes y re-evaluar si abre o responde algo.']);
  return t.slice(0, 3);
}}
function tareasCell(r) {{
  return tareasDe(r).map(x =>
    `<small style="display:block;white-space:nowrap;cursor:help" data-tip="${{esc(x[2])}}">${{x[0]}} ${{esc(x[1])}}</small>`).join('');
}}
function verLeads(f, label) {{
  LB.list = personRows(CURK).filter(r => matchLf(r, f)).sort((x, y) => y[8] - x[8]);
  LB.shown = 0; LB.label = label;
  masLeads();
  document.getElementById('leadbox').scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}
function masLeads() {{
  const curIdx = CURK && CURK.startsWith('a:') ? D.ase.indexOf(CURK.slice(2)) : -1;
  LB.shown = Math.min(LB.list.length, LB.shown + 150);
  const filas = LB.list.slice(0, LB.shown).map(r => {{
    const em = r[3] ? `<a href="mailto:${{esc(r[3])}}">${{esc(r[3])}}</a>` : '—';
    const dig = r[4].replace(/[^0-9]/g, '');
    const ph = r[4] ? `<a href="tel:${{esc(r[4])}}">${{esc(r[4])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank">WA</a>' : ''}}` : '—';
    const sTip = scDesg(r);
    const FLGV = {{P: '🏠', M: '💰', C: '🛒', R: '✋', Z: '⏸'}};
    const flgs = (r[19] || '').split('').map(ch => FLGV[ch] || '').join('');
    return `<tr><td style="white-space:nowrap${{sTip ? ';cursor:help' : ''}}"${{sTip ? ` data-tip="${{sTip}}"` : ''}}><span class="tag" style="background:${{scCol(r[8])}}">${{r[8]}}</span> ${{flgs}}</td>
      <td><b>${{esc(r[2])}}</b>${{(curIdx >= 0 && r[0] !== curIdx) ? ` <span class="tagchip" style="background:#FBF6E7;color:#8A6D1A" data-tip="Este asesor es SEGUIDOR del lead; el owner es ${{esc(D.ase[r[0]])}}.">seguidor · owner: ${{esc(D.ase[r[0]]).slice(0, 16)}}</span>` : ''}}</td><td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
      <td>${{esc(D.fu[r[5]])}}</td><td>${{esc(D.sts[r[6]])}}</td><td>${{esc(D.cu[r[7]])}}</td><td>${{opCell(r)}}</td><td>${{esc(r[9] || '—')}}</td><td>${{rtT(r[10])}}</td><td style="white-space:nowrap"${{r[17] ? ` data-tip="${{r[17][0]}} intentos salientes en ${{r[17][1]}} día${{r[17][1] > 1 ? 's distintos' : ' (ráfaga única)'}} — ${{[r[17][2] ? r[17][2] + ' WhatsApp' : '', r[17][3] ? r[17][3] + ' llamada(s)' : '', r[17][4] ? r[17][4] + ' email(s)' : '', r[17][5] ? r[17][5] + ' SMS' : ''].filter(Boolean).join(' · ')}}. Del ${{esc(r[17][6])}} al ${{esc(r[17][7])}}."` : ''}}>${{r[17] ? `<b>${{r[17][0]}}</b> · ${{r[17][1]}}d ${{(r[17][2] ? '💬' : '') + (r[17][3] ? '📞' : '') + (r[17][4] ? '✉' : '') + (r[17][5] ? '𝗌' : '')}}` : '—'}}</td><td style="white-space:nowrap"${{r[15] ? ` data-tip="Última nota (${{esc(r[15][0][0])}}${{r[15][0][1] ? ', ' + esc(r[15][0][1]) : ''}}): ${{esc(r[15][0][2])}}"` : ''}}>${{r[14] ? `📞 ${{r[14][0]}} · ✉ ${{r[14][4]}} · 🗒 ${{r[14][7]}} · ☑ ${{r[14][6]}}/${{r[14][5]}}` : '—'}}</td><td>${{tareasCell(r)}}</td><td>${{tagsCell(r[11])}}</td><td>${{waBtn((r[4] || '').replace(/[^0-9]/g, ''))}}</td></tr>`;
  }}).join('');
  document.getElementById('leadbox').innerHTML = `
  <h3 style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">📋 Leads de ${{esc(CURK.slice(2))}} — ${{esc(LB.label)}} (${{fN(LB.list.length)}})
  <button class="btn" onclick="document.getElementById('leadbox').innerHTML=''">✕ Cerrar</button></h3>
  <div style="border:1px solid var(--gris-linea);border-radius:12px;overflow:auto;max-height:62vh">
  <table style="margin:0"><thead><tr>
  <th data-tip="Lead scoring v2 0-100 (misma fórmula del reporte de contactos). PASA EL MOUSE sobre el score de cada lead para ver POR QUÉ tiene esos puntos (las 4 variables con su explicación). Flags: 🏠 propiedad específica (MLS) · 💰 monto · 🛒 compra · ✋ respondió · ⏸ aplazado.">Score</th>
  <th data-tip="Nombre del contacto en el CRM.">Contacto</th>
  <th data-tip="Email del lead registrado en el CRM.">Email</th>
  <th data-tip="Teléfono del lead; 'WA' abre su chat de WhatsApp.">Teléfono</th>
  <th data-tip="Origen del lead: campo 'Fuente de contacto' del CRM con las agrupaciones de Paid Search (Google Ads y variantes), Referidos, Prensa y Sitio Web.">Origen</th>
  <th data-tip="Campo Lead Status del CRM.">Lead Status</th>
  <th data-tip="Campo 'En curso por' del CRM (horizonte de oportunidad).">En curso por</th>
  <th data-tip="Si el lead tiene OPORTUNIDAD creada en el pipeline de ventas y en qué etapa del embudo está (Nuevo Lead, WARM, HOT, Cierre…), con su estado (abierta/ganada/perdida/abandonada) y la fecha del último cambio de etapa. Cruce por email/teléfono; si tiene varias, la abierta más reciente. '—' = nunca entró al pipeline.">Etapa de oportunidad</th>
  <th data-tip="Fecha de creación del lead en el CRM (dateAdded).">Creado</th>
  <th data-tip="Tiempo de respuesta que ha recibido este lead: mediana entre sus mensajes y la siguiente respuesta, en sus conversaciones de WhatsApp. '—' = sin conversación medible.">Resp. mediana</th>
  <th data-tip="Intentos de contacto salientes a este lead: total · en cuántos DÍAS DISTINTOS · por qué canales (💬 WhatsApp, 📞 llamada, ✉ email). '1d' con varios intentos = ráfaga de un solo día sin seguimiento posterior. Pasa el mouse para ver el detalle y las fechas.">Intentos</th>
  <th data-tip="Gestión registrada en este lead: 📞 llamadas salientes · ✉ emails salientes · 🗒 notas · ☑ tareas completadas/creadas. Pasa el mouse sobre la celda para leer la última nota. '—' = sin gestión descargada.">Gestión</th>
  <th data-tip="Las principales acciones que el asesor debe ejecutar para CERRAR LA VENTA con este lead, derivadas de su diagnóstico de score (variables débiles, flags y gestión previa). Máx 3 en orden de prioridad; pasa el mouse sobre cada una para la instrucción completa.">Acciones para cerrar venta</th>
  <th data-tip="Etiquetas (tags) del lead tal como están en el CRM — campañas, eventos, listas e importaciones. El chip +N muestra el resto al pasar el mouse.">Etiquetas</th>
  <th data-tip="Escribirle directamente por WhatsApp.">WA</th>
  </tr></thead><tbody>${{filas}}</tbody></table></div>` +
  (LB.shown < LB.list.length ? `<button class="btn" style="margin-top:8px" onclick="masLeads()">Mostrar 150 más (${{fN(LB.list.length - LB.shown)}} restantes)</button>` : '');
}}

function verPerfil(k) {{
  const p = D.p[k], nombre = k.slice(2), esA = k.startsWith('a:');
  document.getElementById('overview').style.display = 'none';
  const el = document.getElementById('profile');
  el.style.display = 'block';
  const smp = p.sample;
  const wp = p.wa >= 20 ? pc(p.waWait, p.wa) : null;
  CURK = k; CURV = k;
  const prows = personRows(k);
  const cart = carteraCalc(prows);
  const notas = [], tareas = [];
  prows.forEach(r => {{
    if (r[15]) r[15].forEach(n2 => notas.push([n2[0], r[2], n2[1], n2[2]]));
    if (r[16]) r[16].forEach(t2 => tareas.push([t2[2], r[2], t2[0], t2[1]]));
  }});
  notas.sort((a, b) => (b[0] || '').localeCompare(a[0] || ''));
  const hoy = new Date().toISOString().slice(0, 10);
  tareas.sort((a, b) => (a[3] - b[3]) || (b[0] || '').localeCompare(a[0] || ''));
  const bitacora = !cart.gCov ? '' : `
  <h3>🗂 Bitácora de gestión: notas y tareas que deja en sus leads <span style="color:var(--gris);font-weight:600;font-size:12px">(${{fN(cart.gNo)}} notas · ${{fN(cart.gTT)}} tareas en su cartera)</span></h3>
  <div class="grid2">
  <div><h3 style="font-size:13px">🗒 Últimas notas (memoria escrita de su gestión)</h3>
  ${{notas.length ? `<table><thead><tr><th>Fecha</th><th>Lead</th><th>Nota</th></tr></thead><tbody>` +
    notas.slice(0, 10).map(x => `<tr><td style="white-space:nowrap">${{esc(x[0] || '—')}}</td><td><b>${{esc(x[1])}}</b></td><td data-tip="${{esc(x[3])}}${{x[2] ? ' — escrita por ' + esc(x[2]) : ''}}">${{esc(x[3].slice(0, 90))}}${{x[3].length > 90 ? '…' : ''}}</td></tr>`).join('') +
    '</tbody></table>' + (notas.length > 10 ? `<p class="note">Mostrando 10 de ${{fN(notas.length)}} notas (las más recientes). El resto se ve lead a lead en la columna Gestión de las tablas.</p>` : '')
    : '<p class="note">⚠ No deja notas en sus leads: no queda memoria escrita de qué se habló con cada uno.</p>'}}</div>
  <div><h3 style="font-size:13px">☑ Tareas de seguimiento programadas</h3>
  ${{tareas.length ? `<table><thead><tr><th>Vence</th><th>Lead</th><th>Tarea</th><th>Estado</th></tr></thead><tbody>` +
    tareas.slice(0, 10).map(x => {{
      const vencida = !x[3] && x[0] && x[0] < hoy;
      return `<tr><td style="white-space:nowrap">${{esc(x[0] || '—')}}</td><td><b>${{esc(x[1])}}</b></td><td>${{esc(x[2].slice(0, 60) || '(sin título)')}}</td><td>${{x[3] ? '<span style="color:var(--verde);font-weight:700">✓ completada</span>' : vencida ? '<span style="color:var(--rojo);font-weight:700">vencida</span>' : '<span style="color:var(--naranja);font-weight:700">pendiente</span>'}}</td></tr>`;
    }}).join('') + '</tbody></table>' + (tareas.length > 10 ? `<p class="note">Mostrando 10 de ${{fN(tareas.length)}} tareas (pendientes primero).</p>` : '')
    : '<p class="note">⚠ No programa tareas de seguimiento en el CRM: su gestión no tiene plan de recontacto visible.</p>'}}</div>
  </div>`;
  const CN = {{w: '💬 WhatsApp', c: '📞 Llamada', e: '✉ Email', s: '✉ SMS'}};
  const intentos = !cart.iCov ? '' : `
  <h3>📆 Intentos de contacto: ¿insiste en varios días o ráfaga de un solo día? <span style="color:var(--gris);font-weight:600;font-size:12px">(${{fN(cart.iTot)}} toques salientes a ${{fN(cart.iCov)}} leads)</span></h3>
  <div class="kpis">
    <div class="kpi" data-tip="Total de toques salientes (llamadas + WhatsApp + emails + SMS) dividido por los leads de su cartera que recibieron al menos uno. Fuente: últimos 100 eventos por conversación."><b>${{(cart.iTot / cart.iCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}</b><span>intentos por lead tocado</span></div>
    <div class="kpi" data-tip="Promedio de DÍAS DISTINTOS en que tocó a cada lead. 1 = todo se intentó en un solo día; más días = seguimiento sostenido en el tiempo."><b>${{(cart.iDias / cart.iCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}</b><span>días distintos de intento por lead</span></div>
    <div class="kpi" data-tip="De sus ${{fN(cart.i2)}} leads con 2+ intentos PERSONALES (WhatsApp o llamada — el goteo automático de email no cuenta aquí), cuántos recibieron intentos en 2 o más días distintos: seguimiento real, no una sola sentada."><b style="color:var(--verde)">${{cart.i2 ? Math.round(cart.iMulti / cart.i2 * 100) + '%' : '—'}}</b><span>seguimiento en varios días</span></div>
    <div class="kpi" data-tip="De sus ${{fN(cart.i2)}} leads con 2+ intentos personales (WhatsApp/llamada), cuántos los recibieron TODOS el mismo día (ráfaga única y nunca más). Alto = se rinde el primer día; los leads que no contestan hoy sí contestan otro día."><b style="color:var(--rojo)">${{cart.i2 ? Math.round(cart.iBurst / cart.i2 * 100) + '%' : '—'}}</b><span>ráfaga de un solo día</span></div>
    <div class="kpi" data-tip="Leads tocados por 2 o más canales distintos (p. ej. WhatsApp + llamada). El multicanal sube la tasa de contacto: quien no contesta el teléfono puede contestar el WhatsApp."><b>${{Math.round(cart.iMix / cart.iCov * 100)}}%</b><span>leads con 2+ canales</span></div>
  </div>
  <div class="grid2">
  <div><h3 style="font-size:13px">Canales que usa para contactar</h3>
  <table><thead><tr><th>Canal</th><th data-tip="Toques salientes por ese canal en su cartera.">Intentos</th><th data-tip="Leads distintos que tocó por ese canal.">Leads tocados</th><th data-tip="% de sus leads tocados que recibieron al menos un intento por ese canal.">% de tocados</th></tr></thead><tbody>
  ${{[['w', cart.iW, cart.iLW], ['c', cart.iC, cart.iLC], ['e', cart.iE, cart.iLE], ['s', cart.iS, cart.iLS]].filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]).map(([k2, n2, l2]) =>
    `<tr><td>${{CN[k2]}}</td><td>${{fN(n2)}}</td><td>${{fN(l2)}}</td><td>${{Math.round(l2 / cart.iCov * 100)}}%</td></tr>`).join('')}}
  </tbody></table></div>
  <div><h3 style="font-size:13px">Cómo leerlo</h3>
  <p class="note" style="margin-top:6px">La columna <b>Intentos</b> de las tablas de leads muestra el detalle por lead: cuántos toques, en cuántos días y por qué canales. Un lead sin respuesta con toda su gestión en un solo día no fue perseguido: fue saludado. La cadencia recomendada es 6-8 intentos repartidos en 2-3 semanas combinando canales.</p></div>
  </div>`;
  el.innerHTML = `
  <h2>${{esc(nombre)}} <span style="color:var(--gris);font-weight:600;font-size:13px">· ${{esA ? 'asesor comercial' : 'realtor'}}</span> &nbsp;${{nivelTag(p)}}</h2>
  <p class="note">Clic en cualquier variable de cartera (tarjetas y barras) para ver la tabla de esos leads con teléfono, email y origen.</p>
  ${{rangoOn() ? '<p class="note" style="color:var(--naranja);font-weight:700">📅 Rango de fechas activo: cartera, tablas de leads y cola de espera filtradas por fecha de creación del lead. La actividad (WA/llamadas), el análisis de conversaciones y la retroalimentación son del histórico completo.</p>' : ''}}
  <div class="kpis">
    <div class="kpi" data-lf="all||Toda la cartera" data-tip="Contactos del CRM asignados a esta persona. Clic para ver la tabla de leads."><b>${{fN(cart.leads)}}</b><span>leads en cartera</span></div>
    <div class="kpi" data-lf="st:Cliente||Clientes" data-tip="Lead Status = Cliente. La conversión se compara con el promedio de la compañía (${{D.bench.conv}}%). Clic para ver la tabla."><b>${{fN(cart.cli)}}</b><span>clientes · conv. ${{pc(cart.cli, cart.leads)}}</span></div>
    <div class="kpi" data-lf="st:Negocio abierto||Negocios abiertos" data-tip="Lead Status = Negocio abierto: lo más cercano al cierre. Clic para ver la tabla."><b>${{fN(cart.neg)}}</b><span>negocios abiertos</span></div>
    <div class="kpi" data-lf="st:En curso||Leads en curso" data-tip="Lead Status = En curso: leads en gestión comercial activa. Clic para ver la tabla."><b>${{fN(cart.encurso)}}</b><span>leads en curso</span></div>
    <div class="kpi" data-lf="oport||Con oportunidad vigente" data-tip="Contactos con 'En curso por' = Oportunidad 1-3 / 3-6 / 6+ meses. Clic para ver la tabla."><b>${{fN(cart.oport)}}</b><span>con oportunidad vigente</span></div>
    <div class="kpi" data-lf="hot||🔥 Leads calientes (score ≥ 55)" data-tip="CALIENTE = score ≥ 55. El score suma: 'En curso por' hasta 35 pts + Lead Status hasta 25 + interacciones hasta 20 + recencia hasta 20. Superar 55 exige combinar oportunidad vigente + estado activo + interacción reciente. Clic para ver la tabla."><b style="color:var(--rojo)">${{fN(cart.hot)}}</b><span>🔥 calientes (≥55)</span></div>
    <div class="kpi" data-lf="warm||🌤 Leads tibios (score 30-54)" data-tip="TIBIO = score 30-54 (misma fórmula: oportunidad hasta 35 + status hasta 25 + interacciones hasta 20 + recencia hasta 20). Tiene UNA señal fuerte pero le falta otra: p. ej. En curso con interacción pero sin oportunidad registrada. Primeros candidatos a calentar. Clic para ver la tabla."><b style="color:var(--naranja)">${{fN(cart.warm)}}</b><span>🌤 tibios (30-54)</span></div>
    <div class="kpi" data-lf="cold||❄ Leads fríos (score 10-29)" data-tip="FRÍO = score 10-29 (misma fórmula). Solo señales débiles: estado inicial (Nutrición=3, Intento=8) y/o interacciones viejas, sin oportunidad vigente. Requieren recalentamiento antes de gestión comercial. Clic para ver la tabla."><b style="color:var(--azul)">${{fN(cart.cold)}}</b><span>❄ fríos (10-29)</span></div>
    <div class="kpi" data-lf="none||Leads sin señales (score <10)" data-tip="SIN SEÑALES = score <10 (misma fórmula). Sin oportunidad registrada, sin estado que sume (vacío, Descartado, Aliado…) y sin interacciones ni actividad reciente: cero evidencia de interés en el CRM. Clic para ver la tabla."><b style="color:#8A99A8">${{fN(cart.none)}}</b><span>sin señales (&lt;10)</span></div>
    <div class="kpi" data-tip="Score promedio de su cartera vs promedio compañía ${{D.bench.sc}}."><b>${{cart.sc.toLocaleString('es-CO')}}</b><span>score promedio</span></div>
    <div class="kpi" data-tip="Tiempo promedio de 1ª atención: primer mensaje SALIENTE de WhatsApp al lead menos su fecha de creación en el CRM, promediado sobre los ${{fN(cart.atnN)}} leads de su cartera con conversación de WhatsApp. Promedio compañía: ${{D.bench.atn === null ? 'sin dato' : rtT(D.bench.atn)}}."><b style="color:var(--azul)">${{cart.atnH === null ? '—' : rtT(cart.atnH)}}</b><span>1ª atención promedio (WA)</span></div>
    <div class="kpi" data-tip="% de leads contactados: leads de su cartera con al menos una gestión registrada (nº de veces contactado + actividades de venta > 0). Promedio compañía: ${{D.bench.cont}}%."><b style="color:var(--verde)">${{cart.leads ? cart.contPct.toFixed(1).replace('.', ',') + '%' : '—'}}</b><span>% de leads contactados</span></div>
    <div class="kpi" data-tip="Contactos promedio por lead: promedio de gestiones registradas sobre TODA su cartera, incluidos los nunca tocados. Promedio compañía: ${{D.bench.cxl}}."><b>${{cart.leads ? cart.cxl.toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</b><span>contactos promedio por lead</span></div>
    <div class="kpi" data-tip="% de cierre de ventas: clientes ÷ leads de su cartera. Promedio compañía: ${{D.bench.conv}}%. Con rango de fechas activo mide el cierre de esa camada."><b style="color:var(--rojo)">${{cart.leads ? pc(cart.cli, cart.leads) : '—'}}</b><span>% cierre de ventas</span></div>
    <div class="kpi" data-tip="Llamadas salientes por lead: ${{fN(cart.gOut)}} llamadas hechas a los ${{fN(cart.gCov)}} leads de su cartera con gestión descargada (${{fN(cart.gLC)}} leads recibieron al menos una llamada). Fuente: historial del CRM, últimos 100 eventos por conversación."><b>${{cart.gCov ? (cart.gOut / cart.gCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</b><span>llamadas por lead</span></div>
    <div class="kpi" data-tip="TMO — tiempo medio de operación: duración promedio de sus ${{fN(cart.gAns)}} llamadas contestadas. Total hablado: ${{Math.round(cart.gSecs / 60)}} minutos. No incluye llamadas sin respuesta."><b>${{cart.gAns ? tmoT(cart.gSecs / cart.gAns) : '—'}}</b><span>TMO (duración prom. llamada)</span></div>
    <div class="kpi" data-tip="Emails salientes por lead de su cartera: ${{fN(cart.gEm)}} correos en total (incluye los de automatización enviados a su nombre)."><b>${{cart.gCov ? (cart.gEm / cart.gCov).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</b><span>emails por lead</span></div>
    <div class="kpi" data-tip="Tareas de seguimiento en sus leads: ${{fN(cart.gTD)}} completadas de ${{fN(cart.gTT)}} creadas. Las tareas son los recordatorios que el asesor se programa en el CRM — pocas tareas = gestión sin plan de seguimiento."><b>${{cart.gTT ? fN(cart.gTD) + '/' + fN(cart.gTT) : '—'}}</b><span>tareas completadas/creadas</span></div>
    <div class="kpi" data-tip="Notas dejadas en sus leads: ${{fN(cart.gNo)}} notas en ${{fN(cart.gLN)}} leads (${{cart.gCov ? Math.round(cart.gLN / cart.gCov * 100) : 0}}% de la cartera con bitácora). La nota es la memoria escrita de la gestión: sin ella, nadie sabe qué se habló."><b>${{cart.gNo ? fN(cart.gNo) : '—'}}</b><span>notas en sus leads</span></div>
    <div class="kpi" data-tip="Tiempo de respuesta al lead: mediana entre cada mensaje del cliente y la siguiente respuesta del asesor, sobre TODAS sus conversaciones de WhatsApp (${{fN(p.convsN)}} convos analizadas)."><b>${{rtT(p.rtAll)}}</b><span>resp. mediana al lead</span></div>
    <div class="kpi" data-tip="Conversaciones de WhatsApp asignadas y cuántas tienen al cliente esperando respuesta (su detalle está en la tabla ⏳ de abajo)."><b>${{fN(p.wa)}}${{wp ? ' · ' + fN(p.waWait) + ' ⏳' : ''}}</b><span>convos WA ${{wp ? '· sin responder ' + wp : ''}}</span></div>
    <div class="kpi" data-tip="Conversaciones de llamada y de email registradas en el CRM."><b>${{fN(p.calls)}} / ${{fN(p.emails)}}</b><span>llamadas / emails</span></div>
  </div>
  ${{smp ? `<p class="note" data-tip="Métricas de la muestra cualitativa: 16 conversaciones de WhatsApp leídas de este asesor.">📖 Muestra leída: respuesta mediana <b>${{smp.rtH === null ? 'sin datos' : smp.rtH < 1 ? (smp.rtH*60).toFixed(0) + ' min' : smp.rtH < 48 ? smp.rtH.toLocaleString('es-CO', {{maximumFractionDigits:1}}) + ' h' : (smp.rtH/24).toFixed(0) + ' días'}}</b> · diálogos reales <b>${{smp.dial}}/${{smp.n}}</b> · monólogos de plantilla <b>${{smp.mono}}/${{smp.n}}</b></p>` : ''}}
  <div class="grid2">
    <div><h3>Cartera por Lead Status</h3><table><tbody>${{barra(cart.status, cart.leads, 'st')}}</tbody></table></div>
    <div><h3>Fuentes principales</h3><table><tbody>${{barra(cart.fuentes, cart.leads, 'fu')}}</tbody></table>
    <h3>En curso por</h3><table><tbody>${{barra(cart.curso, cart.leads, 'cu')}}</tbody></table></div>
  </div>
  <div id="leadbox" style="margin-top:12px"></div>
  ${{intentos}}
  ${{bitacora}}
  ${{p.convsN ? `<h3>🤝 Cómo conecta con sus leads <span style="color:var(--gris);font-weight:600;font-size:12px">(${{fN(p.convsN)}} conversaciones de WhatsApp analizadas)</span></h3>
  <div class="kpis">
    <div class="kpi" data-tip="Mediana del tiempo en responder cada mensaje del cliente, sobre todas sus conversaciones."><b>${{rtT(p.rtAll)}}</b><span>resp. mediana</span></div>
    <div class="kpi" data-tip="Porcentaje de mensajes entrantes de sus leads que en algún momento recibieron una respuesta."><b>${{p.ansPct === null ? '—' : p.ansPct + '%'}}</b><span>mensajes del lead respondidos</span></div>
    <div class="kpi" data-tip="Porcentaje de sus mensajes salientes que son plantillas masivas (el mismo texto aparece en 5+ conversaciones). Alto = gestión automatizada, no personal."><b>${{p.tplPct === null ? '—' : p.tplPct + '%'}}</b><span>mensajes de plantilla</span></div>
    <div class="kpi" data-tip="Conversaciones donde el lead escribió 2 o más veces: diálogo real."><b>${{fN(p.dialN)}}</b><span>diálogos reales</span></div>
  </div>
  <div id="lcbox"></div>` : ''}}
  ${{(p.pend.filter(x => inR(x[8])).length) ? `<h3>⏳ Sus leads esperando respuesta en WhatsApp (${{fN(p.pend.filter(x => inR(x[8])).length)}}${{p.pendTot > 12 ? ' de ' + fN(p.pendTot) + ', top por score' : ''}})</h3>
  <div style="overflow-x:auto"><table><thead><tr><th>Score</th><th>Lead</th><th>Email</th><th>Teléfono</th><th>Origen</th><th data-tip="Mediana histórica de respuesta que ha recibido ESTE lead en sus conversaciones.">Resp. mediana</th><th>Días esperando</th><th data-tip="Etiquetas (tags) del lead en el CRM.">Etiquetas</th></tr></thead><tbody>` +
    p.pend.filter(x => inR(x[8])).map(x => `<tr><td><span class="tag" style="background:${{scCol(x[0])}}">${{x[0]}}</span></td>
      <td><b>${{esc(x[1])}}</b></td>
      <td>${{x[5] ? '<a href="mailto:' + esc(x[5]) + '">' + esc(x[5]) + '</a>' : '—'}}</td>
      <td style="white-space:nowrap">${{x[6] ? '<a href="tel:' + esc(x[6]) + '">' + esc(x[6]) + '</a>' : '—'}}${{x[4] ? ' · <a href="https://wa.me/' + x[4] + '" target="_blank">WA</a>' : ''}}</td>
      <td>${{esc(x[2])}}</td><td>${{rtT(x[7])}}</td><td>${{x[3] >= 0 ? fN(x[3]) : '—'}}</td><td>${{tagsCell(x[9])}}</td></tr>`).join('') +
    '</tbody></table></div>' : ''}}
  <h2>Retroalimentación</h2>
  ${{p.nota ? `<div class="quote">${{esc(p.nota)}}</div>` : ''}}
  <div class="fb f"><b>✅ Lo que hace bien</b><ul>${{p.fort.length ? p.fort.map(x => '<li>' + esc(x) + '</li>').join('') : '<li>Sin fortalezas destacables en los datos del CRM al corte — puede deberse a gestión fuera del sistema.</li>'}}</ul></div>
  <div class="fb m"><b>⚠️ Lo que debe mejorar</b><ul>${{p.mej.length ? p.mej.map(x => '<li>' + esc(x) + '</li>').join('') : '<li>Sin señales de alerta relevantes en los datos del CRM.</li>'}}</ul></div>
  <div class="fb r"><b>🎯 Plan recomendado</b><ul>${{p.reco.map(x => '<li>' + esc(x) + '</li>').join('')}}</ul></div>`;
  el.querySelectorAll('[data-lf]').forEach(x => x.addEventListener('click', () => {{
    const [f, label] = x.dataset.lf.split('||');
    verLeads(f, label);
  }}));
  LC = {{list: p.lconvs, shown: 0}};
  if (p.convsN) masConvs();
  window.scrollTo({{top: 0, behavior: 'smooth'}});
}}

/* análisis lead a lead de las conversaciones */
let LC = {{list: [], shown: 0}};
function masConvs() {{
  LC.shown = Math.min(LC.list.length, LC.shown + 40);
  const filas = LC.list.slice(0, LC.shown).map(x => `
    <tr><td><span class="tag" style="background:${{scCol(x[1])}}">${{x[1]}}</span></td>
    <td><b>${{esc(x[0])}}</b></td><td>${{rtT(x[2])}}</td>
    <td>${{x[3]}}%</td>
    <td>${{x[4] ? '<span style="color:var(--rojo);font-weight:700">⏳ Esperando</span>' : '<span style="color:var(--verde);font-weight:700">Respondida</span>'}}</td>
    <td style="font-size:12.3px">${{esc(x[5])}}</td></tr>`).join('');
  document.getElementById('lcbox').innerHTML = `
  <p class="note">Análisis lead a lead de sus conversaciones con interacción del cliente (ordenadas: primero las que esperan respuesta, luego por score). El análisis y la recomendación se generan por reglas sobre lo conversado: plantillas vs mensajes propios, preguntas de calificación, velocidad y el último interés expresado por el lead.</p>
  <div style="border:1px solid var(--gris-linea);border-radius:12px;overflow:auto;max-height:64vh">
  <table style="margin:0"><thead><tr>
  <th data-tip="Lead scoring 0-100 del contacto.">Score</th>
  <th data-tip="Nombre del lead en el CRM.">Lead</th>
  <th data-tip="Mediana del tiempo de respuesta que recibió ESTE lead en esta conversación.">Resp. mediana</th>
  <th data-tip="Qué % de los mensajes que le envió el asesor a este lead son plantillas masivas.">% plantilla</th>
  <th data-tip="Estado de la conversación: respondida o con el lead esperando.">Estado</th>
  <th data-tip="Análisis de la conversación y recomendación, generados por reglas sobre lo conversado (conexión, asertividad, plantillas, último interés del lead).">Análisis y recomendación</th>
  </tr></thead><tbody>${{filas}}</tbody></table></div>` +
  (LC.shown < LC.list.length ? `<button class="btn" style="margin-top:8px" onclick="masConvs()">Mostrar 40 más (${{fN(LC.list.length - LC.shown)}} restantes)</button>` : '');
}}

/* arranque limpio: el navegador restaura valores de formulario entre visitas */
function arranqueAs() {{
  ['f-a', 'f-r', 'f-d1', 'f-d2'].forEach(id => document.getElementById(id).value = '');
  verResumen();
}}
arranqueAs();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranqueAs(); }});
setTimeout(() => {{
  if (CURV === null && ['f-a', 'f-r', 'f-d1', 'f-d2'].some(id => document.getElementById(id).value !== '')) arranqueAs();
}}, 250);

/* tooltip global */
const vtip = document.createElement('div'); vtip.id = 'vtip'; document.body.appendChild(vtip);
document.addEventListener('mouseover', e => {{
  const t = e.target.closest('[data-tip]');
  if (!t) {{ vtip.style.display = 'none'; return; }}
  vtip.textContent = t.dataset.tip; vtip.style.display = 'block';
}});
document.addEventListener('mousemove', e => {{
  if (vtip.style.display !== 'block') return;
  let x = e.clientX + 14, y = e.clientY + 18;
  if (x + 320 > innerWidth) x = Math.max(8, e.clientX - 324);
  if (y + vtip.offsetHeight + 10 > innerHeight) y = e.clientY - vtip.offsetHeight - 14;
  vtip.style.left = x + 'px'; vtip.style.top = y + 'px';
}});
</script>
</body></html>'''

out = str(ROOT / f'auditoria-asesores-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB)')
print(f'asesores: {len(orden_a)} | realtors: {len(orden_r)}')
print(f'benchmarks: conv {G_CONV:.1f}% | espera {G_WPCT:.1f}% | score {G_SC:.1f}')
