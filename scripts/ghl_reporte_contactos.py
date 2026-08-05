#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reporte drill-down de la BASE COMPLETA de contactos del CRM (con y sin oportunidad):
Asesor → Lead Status → leads ordenados por lead scoring (más caliente a la venta,
calculado por interacción). HTML autocontenido. Lee scripts/data/{contacts,users}.json
(descarga previa de ghl_fetch_contactos.py — solo consulta, cero escritura en el CRM)."""
import json, html, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

# ---------- score v2 precalculado (notas, tareas, conversaciones, reciprocidad, recencia real) ----------
try:
    _SC2 = json.load(open(DATA / 'score_v2.json'))
except Exception:
    _SC2 = {}

contacts = json.load(open(DATA / 'contacts.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW   = datetime.now(timezone.utc)
_hoy  = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

# ---------- fuente = campo "Fuente de contacto" del CRM, tal cual ----------
from collections import defaultdict
_variantes = defaultdict(Counter)
for _c in contacts:
    _s = ' '.join((_c['source'] or '').split())
    if _s and _s.lower() != '<unspecified>':
        _variantes[_s.lower()][_s] += 1
CANON = {k: v.most_common(1)[0][0] for k, v in _variantes.items()}

def fuente_of(c):
    s = ' '.join((c['source'] or '').split())
    if not s or s.lower() == '<unspecified>': return '(Sin fuente)'
    sl = s.lower()
    # Familias que en el CRM vienen dispersas en variantes/typos del mismo medio;
    # se agrupan para que sus resultados no se dispersen en el análisis por fuente.
    if 'google' in sl or sl.startswith('goo ') or sl == 'goo disp' or sl == 'paid search':
        return 'Google / Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl or sl in ('rerefido', 'referral', 'pereonal', 'personall'):
        return 'Referidos / Personal'
    if sl.startswith('prensa'):
        return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'):
        return 'Sitio Web'
    return CANON[sl]

# ---------- lead status (orden de más caliente a más frío) ----------
STATUS_ORDER = ['Negocio abierto','En curso','Intento de contacto','Nuevo','En Nutrición',
                'Cliente','Tenant','Aliado','Relationship','Compra Problematica',
                'Descartado','(Sin status)']
STATUS_PTS = {'Negocio abierto':25,'En curso':15,'Intento de contacto':8,'Nuevo':5,'En Nutrición':3}
CURSO_ORDER = ['Oportunidad 1-3 meses','Oportunidad 3-6 meses','Oportunidad 6+ meses',
               'Sin Oportunidad','No Aplica','_','(Sin dato)']
CURSO_PTS = {'Oportunidad 1-3 meses':35,'Oportunidad 3-6 meses':28,'Oportunidad 6+ meses':18}

def num(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0

def score_of(c):
    _v2 = _SC2.get(c.get('id') or '')
    if _v2 is not None: return _v2['s']
    """Lead scoring 0-100 por interacción y temperatura declarada:
    En curso por (0-35) + Lead Status (0-25) + nº interacciones (0-20) + recencia (0-20)."""
    s  = CURSO_PTS.get((c.get('enCursoPor') or '').strip(), 0)
    s += STATUS_PTS.get((c.get('leadStatus') or '').strip(), 0)
    inter = num(c.get('vecesContactado')) + num(c.get('salesActivities'))
    s += min(20, inter)
    la = c.get('lastActivity') or c.get('lastEngagement')
    if la:
        try:
            d = (NOW - datetime.fromisoformat(str(la).replace('Z','+00:00'))).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)

def temp_of(sc):
    return 'Caliente' if sc >= 55 else 'Tibio' if sc >= 30 else 'Frío' if sc >= 10 else 'Sin señales'

# ---------- tiempo de primera atención (primer msj saliente de WhatsApp) ----------
try:
    _wa_all = json.load(open(DATA / 'wa_all_msgs.json'))
except Exception:
    _wa_all = []
FIRST_OUT = {}
for _cv in _wa_all:
    _cid = _cv.get('contactId')
    for _m in (_cv.get('msgs') or []):
        if _m[0] == 0 and _m[1]:
            if _cid not in FIRST_OUT or _m[1] < FIRST_OUT[_cid]:
                FIRST_OUT[_cid] = _m[1]
            break

def atn_of(c):
    """Horas entre la creación del lead y su primer mensaje saliente de WhatsApp.
    -1 = sin conversación de WhatsApp registrada (otros canales no dejan este dato)."""
    fo = FIRST_OUT.get(c['id'])
    if not fo or not c.get('created'): return -1
    try:
        d = (datetime.fromisoformat(fo.replace('Z', '+00:00')) -
             datetime.fromisoformat(str(c['created']).replace('Z', '+00:00'))).total_seconds() / 3600
    except ValueError:
        return -1
    return round(d, 1) if d >= 0 else -1


# ---------- intentos de contacto por lead (gestion.json + respaldo WhatsApp) ----------
try:
    _GEST_INT = json.load(open(DATA / 'gestion.json'))
except Exception:
    _GEST_INT = {}
try:
    _WA_INT = json.load(open(DATA / 'wa_all_msgs.json'))
except Exception:
    _WA_INT = []
_WA_OUTD = {}
for _cv in _WA_INT:
    _cidw = _cv.get('contactId')
    if not _cidw or not _cv.get('msgs'): continue
    _fs = [(_m[1] or '')[:10] for _m in _cv['msgs'] if _m[0] == 0 and _m[1]]
    if _fs:
        _WA_OUTD.setdefault(_cidw, []).extend(_fs)

def intentos_of(_cid):
    """[total, dias distintos, whatsapp, llamadas, emails, sms] o 0 si no hay datos.
    gestion.json trae todos los canales (carteras de asesores humanos);
    si el lead no esta ahi, se usan solo sus mensajes salientes de WhatsApp."""
    _g = _GEST_INT.get(_cid)
    _f = _g.get('f') if _g else None
    if _f:
        return [len(_f), len({_x[0] for _x in _f}),
                sum(1 for _x in _f if _x[1] == 'w'), sum(1 for _x in _f if _x[1] == 'c'),
                sum(1 for _x in _f if _x[1] == 'e'), sum(1 for _x in _f if _x[1] == 's')]
    _fs = _WA_OUTD.get(_cid)
    if _fs:
        return [len(_fs), len(set(_fs)), len(_fs), 0, 0, 0]
    return 0


# ---------- followers: el asesor cuenta como owner O seguidor (solo lectura) ----------
try:
    _FWMAP = json.load(open(DATA / 'followers.json'))
except Exception:
    _FWMAP = {}
def fols(c):
    """user ids que siguen al contacto (del fetch o del mapa aparte)."""
    return c.get('followers') or _FWMAP.get(c['id'], [])
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
# ---------- construir filas ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DA, giA = dict_indexer()   # asesor
DS, giS = dict_indexer()   # lead status
DK, giK = dict_indexer()   # en curso por
DR, giR = dict_indexer()   # realtor
DF, giF = dict_indexer()   # fuente
DT, giT = dict_indexer()   # etiquetas (tags del CRM)
DMO, giMO = dict_indexer()  # motivo de descarte
DOP, giOP = dict_indexer()  # etapa de oportunidad en el pipeline

for s in STATUS_ORDER: giS(s)
for k in CURSO_ORDER:  giK(k)

rows = []
scnt = Counter()
for c in contacts:
    a  = USERS.get(c['assigned'], '(Sin asesor asignado)') if c['assigned'] else '(Sin asesor asignado)'
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    if st not in STATUS_ORDER: st = '(Sin status)'
    ku = (c.get('enCursoPor') or '').strip() or '(Sin dato)'
    if ku not in CURSO_ORDER: ku = '(Sin dato)'
    rl = c.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(r.strip() for r in rl if r and r.strip()) or '(Sin realtor)'
    sc = score_of(c)
    mo = (c.get('motivoDescarte') or '').strip().replace('No caliifica', 'No califica')
    if not mo or mo == 'N/A': mo = '(Sin motivo registrado)'
    inter = 0
    for _k in ('vecesContactado', 'salesActivities'):
        try: inter += max(0, int(float(c.get(_k) or 0)))
        except (TypeError, ValueError): pass
    rows.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c['email'] or '', c['phone'] or '',
        giA(a), giS(st), giK(ku), giR(rl), giF(fuente_of(c)),
        (c['created'] or '')[:10], sc,
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        inter, giMO(mo), atn_of(c), intentos_of(c['id']),
        [giA(USERS[u]) for u in fols(c) if u in USERS],
        (_SC2.get(c['id']) or {}).get('fl', ''),
        (_SC2.get(c['id']) or {}).get('d', []),
        ([giOP(_STG.get(_op['stage'], '(etapa desconocida)')),
          _ST_ES.get((_op.get('status') or '').lower(), _op.get('status') or ''),
          (_op.get('stageChange') or _op.get('created') or '')[:10]]
         if (_op := opp_of(c)) else 0)
    ])
    scnt[st] += 1

TOTAL = len(rows)
def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
realtor_vol = Counter(r[6] for r in rows)

fuente_vol = Counter(r[7] for r in rows)
PAYLOAD = json.dumps({
    'rows': rows,
    'asesores': ordered(DA), 'status': ordered(DS), 'cursos': ordered(DK),
    'realtors': ordered(DR), 'fuentes': ordered(DF),
    'realtorOrden': [i for i, _ in realtor_vol.most_common()],
    'fuenteOrden': [i for i, _ in fuente_vol.most_common()],
    'tags': ordered(DT),
    'motivos': ordered(DMO),
    'opps': ordered(DOP),
}, ensure_ascii=False)

def fmt(n): return f'{n:,}'.replace(',', '.')

# ---------- evolución de la gestión (histórico de snapshots) ----------
try:
    HIST = json.load(open(DATA / 'historico.json'))
except Exception:
    HIST = []

def _evol_html():
    if len(HIST) < 1: return ''
    V, R = '#1E9E62', '#D64545'
    def f_es(d):
        y, mo, da = d.split('-')
        return f'{int(da)} {MESES[int(mo)-1][:3]}'
    bullets = ''
    if len(HIST) >= 2:
        a, b = HIST[-2], HIST[-1]
        dd = lambda k: b.get(k, 0) - a.get(k, 0)
        LB = []
        if dd('clientes') > 0: LB.append((V, f'🎉 <b>+{fmt(dd("clientes"))} ventas</b>: nuevos clientes cerrados.'))
        if dd('negocio') != 0: LB.append((V if dd('negocio') > 0 else R, f'🤝 Negocios abiertos: {fmt(b["negocio"])} ({dd("negocio"):+d}).'))
        if dd('sinstatus') < 0: LB.append((V, f'✅ Se clasificaron <b>{fmt(-dd("sinstatus"))}</b> leads (bajó "Sin status").'))
        elif dd('sinstatus') > 0: LB.append((R, f'⚠ Entraron {fmt(dd("sinstatus"))} leads sin clasificar.'))
        if dd('sinasesor') < 0: LB.append((V, f'✅ Se asignaron <b>{fmt(-dd("sinasesor"))}</b> leads que estaban sin asesor.'))
        elif dd('sinasesor') > 0: LB.append((R, f'⚠ La cartera sin asesor creció en {fmt(dd("sinasesor"))}.'))
        if dd('esperando') < 0: LB.append((V, f'✅ Se atendieron <b>{fmt(-dd("esperando"))}</b> conversaciones de la cola de WhatsApp (quedan {fmt(b["esperando"])}).'))
        elif dd('esperando') > 0: LB.append((R, f'⚠ La cola de WhatsApp creció en {fmt(dd("esperando"))} (van {fmt(b["esperando"])}).'))
        if dd('esperando30') != 0: LB.append((V if dd('esperando30') < 0 else R, f'{"✅" if dd("esperando30") < 0 else "⚠"} Tibios/calientes esperando respuesta: {fmt(b["esperando30"])} ({dd("esperando30"):+d}).'))
        if dd('clifrio') < 0: LB.append((V, f'✅ Se reactivaron <b>{fmt(-dd("clifrio"))}</b> clientes que estaban fríos.'))
        if dd('hot') != 0: LB.append((V if dd('hot') > 0 else R, f'🔥 Leads calientes: {fmt(b["hot"])} ({dd("hot"):+d}).'))
        if dd('warm') != 0: LB.append(('#8A6D1A', f'🌤 Tibios: {fmt(b["warm"])} ({dd("warm"):+d}).'))
        if dd('recompra') != 0: LB.append((V if dd('recompra') > 0 else '#8A6D1A', f'🔁 Clientes con recompra declarada: {fmt(b["recompra"])} ({dd("recompra"):+d}).'))
        if dd('contactos') != 0: LB.append(('#5B6B85', f'📥 Leads en el CRM: {fmt(b["contactos"])} ({dd("contactos"):+d}).'))
        if dd('opps') > 0: LB.append(('#5B6B85', f'📈 Oportunidades en pipeline: {fmt(b["opps"])} (+{fmt(dd("opps"))}).'))
        if dd('nutricion') > 0: LB.append(('#8A6D1A', f'🌱 El goteo de nutrición absorbió {fmt(dd("nutricion"))} leads más (van {fmt(b["nutricion"])}).'))
        if abs(b.get('score', 0) - a.get('score', 0)) >= 0.1:
            LB.append((V if b['score'] > a['score'] else R, f'🌡 Score promedio de la base: {str(b["score"]).replace(".", ",")} ({b["score"]-a["score"]:+.1f}).'))
        if not LB: LB = [('#5B6B85', 'Sin cambios relevantes entre los dos últimos cortes.')]
        bullets = (f'<h3 style="font-size:13.5px;margin:8px 0 4px">Impacto del último corte · {f_es(a["fecha"])} → {f_es(b["fecha"])}</h3><ul style="padding-left:20px;margin:4px 0">' +
                   ''.join(f'<li style="margin:4px 0;color:{c}">{t}</li>' for c, t in LB) + '</ul>')
    # tabla histórica (últimos 14 cortes, el más reciente arriba)
    cols = [('contactos', 'Leads'), ('opps', 'Oportun.'), ('clientes', 'Clientes'), ('negocio', 'Neg. ab.'),
            ('hot', '🔥'), ('warm', '🌤'), ('esperando', 'Esperando WA'), ('sinstatus', 'Sin status'),
            ('sinasesor', 'Sin asesor'), ('score', 'Score prom.')]
    filas = ''
    hh = HIST[-14:]
    for i in range(len(hh) - 1, -1, -1):
        h = hh[i]; prev = hh[i - 1] if i > 0 else None
        tds = ''
        for k, _ in cols:
            v = h.get(k, 0)
            vtxt = str(v).replace('.', ',') if k == 'score' else fmt(v)
            delta = ''
            if prev is not None:
                d = round(v - prev.get(k, 0), 1)
                if d:
                    malo_sube = k in ('esperando', 'sinstatus', 'sinasesor', 'nutricion')
                    col = (R if malo_sube else V) if d > 0 else (V if malo_sube else R)
                    delta = f' <small style="color:{col};font-weight:700">{"▲" if d > 0 else "▼"}{str(abs(d)).replace(".0", "").replace(".", ",")}</small>'
            tds += f'<td style="white-space:nowrap">{vtxt}{delta}</td>'
        filas += f'<tr><td><b>{f_es(h["fecha"])}</b></td>{tds}</tr>'
    ths = '<th data-tip="Fecha del corte (snapshot tomado al actualizar los datos).">Corte</th>' + ''.join(
        f'<th>{t}</th>' for _, t in cols)
    return f'''<div class="chart-sec">
<h2>📅 Evolución de la gestión comercial</h2>
<p class="chart-sub">Cada vez que se actualizan los datos se guarda una foto de las métricas clave; esta sección compara los cortes y resume el impacto de la gestión: qué mejoró, qué se movió y qué se está descuidando. Las flechas de la tabla comparan cada corte con el anterior (verde = mejora, rojo = deterioro; para colas y pendientes, bajar es mejorar).</p>
{bullets}
<div style="overflow-x:auto"><table style="min-width:820px"><thead><tr>{ths}</tr></thead><tbody>{filas}</tbody></table></div>
</div>'''
EVOL_HTML = _evol_html()

SCOL = {'Negocio abierto':'#1E9E62','En curso':'#3A566B','Intento de contacto':'#AA9664',
        'Nuevo':'#8A6D1A','En Nutrición':'#8A99A8','Cliente':'#2C4356','Descartado':'#D64545',
        '(Sin status)':'#5B6B85'}
hot_n  = sum(1 for r in rows if r[9] >= 55)
warm_n = sum(1 for r in rows if 30 <= r[9] < 55)
cold_n = sum(1 for r in rows if 10 <= r[9] < 30)
none_n = sum(1 for r in rows if r[9] < 10)
TIPS = {
 'En Nutrición': 'Leads en campañas de nutrición (emails/contenidos automáticos), sin gestión comercial activa en este momento.',
 'En curso': 'Leads en gestión comercial activa por un asesor.',
 'Descartado': 'Leads que el equipo marcó como descartados (no continúan en el proceso).',
 '(Sin status)': 'Contactos cuyo campo Lead Status está vacío en el CRM: nadie los ha clasificado aún.',
 'Intento de contacto': 'Leads a los que se les ha intentado contactar pero aún no responden.',
 'Cliente': 'Contactos que ya compraron: son clientes de la compañía.',
 'Aliado': 'Aliados comerciales o de referidos, no son compradores.',
 'Nuevo': 'Leads recién ingresados que todavía no inician gestión.',
 'Negocio abierto': 'Leads con una negociación activa: los más cercanos a la venta.',
 'Tenant': 'Arrendatarios de propiedades administradas.',
 'Relationship': 'Contactos de relacionamiento personal del equipo.',
 'Compra Problematica': 'Compras que presentaron algún problema.',
}
def _tip(s, n):
    return (f'{TIPS.get(s, "")} Cómo se calcula: cuenta los {fmt(n)} contactos cuyo campo '
            f'“Lead Status” del CRM es “{s}”. Clic: filtra la tabla y los muestra clasificados por asesor.')
FORMULA = ('El score v2 (0-100) suma 4 pilares con TODA la evidencia del CRM: ① INTENCIÓN hasta 35 pts — horizonte '
           'declarado (En curso por), monto de compra detectado en notas/conversaciones (30), compra declarada en texto (20) '
           'o presupuesto diligenciado (22); un aplazamiento reciente ("retomar en octubre…") la congela a máx 15 · '
           '② ETAPA hasta 25 pts (Lead Status: Negocio abierto=25, En curso=15…) · ③ RECIPROCIDAD hasta 20 pts — cuenta el eco '
           'del lead (respondió +8, nº de mensajes entrantes hasta +8, diálogo real +4); gestión sin respuesta vale máx 4 · '
           '④ RECENCIA REAL hasta 20 pts — la fecha más reciente entre actividad, notas, tareas, intentos y conversaciones '
           '(≤7 días=20, ≤30=15, ≤90=8, ≤180=4). Flags: 💰 monto · 🛒 compra declarada · ✋ respondió · ⏸ aplazado.')
hot_tip = (f'CALIENTE = score ≥ 55. {FORMULA} Para superar 55 el lead necesita combinar al menos dos señales fuertes: '
           'oportunidad vigente + estado activo + interacción reciente. Son los más cercanos a la venta. '
           'Clic: filtra la tabla y muestra de cada lead su asesor, etapa y “En curso por”.')
warm_tip = (f'TIBIO = score entre 30 y 54. {FORMULA} Perfil típico: tiene UNA señal fuerte pero le falta otra — '
            'p. ej. está “En curso” con interacciones recientes pero sin oportunidad registrada, o tiene oportunidad '
            'a 6+ meses con poca interacción. Con una buena gestión son los primeros candidatos a volverse calientes. '
            'Clic: filtra la tabla a solo tibios.')
cold_tip = (f'FRÍO = score entre 10 y 29. {FORMULA} Perfil típico: apenas una o dos señales débiles — '
            'solo el estado (En Nutrición=3, Intento de contacto=8) más algunas interacciones viejas, sin oportunidad '
            'vigente ni actividad reciente. Requieren recalentamiento (campaña o contacto) antes de gestión comercial. '
            'Clic: filtra la tabla a solo fríos.')
none_tip = (f'SIN SEÑALES = score menor a 10. {FORMULA} Significa que el lead no tiene oportunidad registrada, '
            'su Lead Status no suma (vacío, Descartado, Aliado…), no hay interacciones registradas y no hay actividad '
            'reciente: cero evidencia de interés en el CRM. Clic: filtra la tabla.')
leyenda = (f'<span class="pill click hotp" data-temp="hot" data-tip="{html.escape(hot_tip)}" '
           f'style="background:#D6454518;color:#D64545;border:1.5px solid #D6454555">🔥 Leads calientes (score ≥ 55): <b id="pill-hot">{fmt(hot_n)}</b> · ver asesor, etapa y en curso por</span> '
           f'<span class="pill click" data-temp="warm" data-tip="{html.escape(warm_tip)}" '
           f'style="background:#AA966422;color:#8A6D1A">🌤 Tibios (30-54): <b id="pill-warm">{fmt(warm_n)}</b></span> '
           f'<span class="pill click" data-temp="cold" data-tip="{html.escape(cold_tip)}" '
           f'style="background:#3A566B22;color:#3A566B">❄ Fríos (10-29): <b id="pill-cold">{fmt(cold_n)}</b></span> '
           f'<span class="pill click" data-temp="none" data-tip="{html.escape(none_tip)}" '
           f'style="background:#8A99A822;color:#5B6B85">Sin señales (&lt;10): <b id="pill-none">{fmt(none_n)}</b></span> ')
leyenda += ' '.join(
    f'<span class="pill click" data-s="{STATUS_ORDER.index(s)}" data-tip="{html.escape(_tip(s, n))}" '
    f'style="background:{SCOL.get(s,"#5B6B85")}22;color:{SCOL.get(s,"#5B6B85")}">{html.escape(s)}: <b data-cs="{STATUS_ORDER.index(s)}">{fmt(n)}</b></span>'
    for s, n in scnt.most_common())

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gestión comercial</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:14.5px;line-height:1.45}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 20px 50px}}
header{{background:var(--azul-oscuro);color:#fff;padding:20px 0}}
header .wrap{{display:flex;align-items:center;gap:16px;padding-bottom:0}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:21px;letter-spacing:1px;padding:11px 13px;border-radius:9px}}
header h1{{font-size:18.5px;font-weight:800}}
header p{{color:#C9D6E4;font-size:12.5px;margin-top:2px}}
.hstats{{margin-left:auto;text-align:right}} .hstats b{{font-size:26px;display:block}} .hstats span{{font-size:12px;color:#C9D6E4}}
.navgrp{{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}}
.navbtn{{background:#ffffff1a;border:1.5px solid #C9D6E455;color:#F2F6FA;text-decoration:none;
font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:9px;white-space:nowrap}}
.navbtn:hover{{background:#ffffff2e}}
.navgrp + .hstats{{margin-left:14px}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
.leyenda{{margin:16px 0 4px;display:flex;flex-wrap:wrap;gap:7px}}
.pill{{display:inline-block;padding:3px 10px;border-radius:20px;font-weight:600;font-size:12px}}
.pill.click{{cursor:pointer;user-select:none}}
.pill.click:hover{{text-decoration:underline}}
.pill.on{{outline:2px solid currentColor;outline-offset:1px}}
[data-tip]{{cursor:help}} .pill.click[data-tip]{{cursor:pointer}}
th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.filters{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:13px;padding:14px;margin-top:14px;
display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}}
.filters label{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);font-weight:800;display:block;margin-bottom:3px}}
.filters select,.filters input{{width:100%;border:1.5px solid var(--gris-linea);border-radius:8px;padding:7px 9px;font-size:13px;background:#fff;color:var(--tinta)}}
.fbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 16px}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:11px 13px;background:#fff}}
.kpi b{{font-size:22px;display:block}} .kpi span{{font-size:11.5px;color:var(--gris)}}
.pies{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
.pie-box h3{{font-size:13.5px;margin:4px 0 2px}}
.pie-box svg{{width:100%;height:auto;display:block}}
.pleg{{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12.2px;margin-top:4px}}
.pleg .li{{cursor:pointer;user-select:none}} .pleg .li:hover{{text-decoration:underline}}
.pleg .dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.pslice{{cursor:pointer}} .pslice:hover{{opacity:.82}}
.chart-sec{{border:1px solid var(--gris-linea);border-radius:13px;padding:16px 16px 10px;margin:4px 0 20px}}
.chart-sec h2{{font-size:15.5px;margin-bottom:2px}}
.chart-sub{{font-size:12px;color:var(--gris);margin-bottom:10px}}
.chart-ctrl{{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:6px;font-size:12px}}
.chart-ctrl b{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris)}}
.chart-ctrl select{{border:1.5px solid var(--gris-linea);border-radius:8px;padding:4px 8px;font-size:12px;background:#fff;color:var(--tinta)}}
.grp{{border:1px solid var(--gris-linea);border-radius:12px;margin-bottom:10px;overflow:hidden}}
.grp>summary{{list-style:none;cursor:pointer;display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:12px 16px;background:var(--gris-fondo);font-weight:800}}
.grp>summary::-webkit-details-marker{{display:none}}
.grp>summary .car{{transition:transform .15s;color:var(--gris)}}
.grp[open]>summary .car{{transform:rotate(90deg)}}
.grp>summary small{{font-weight:600;color:var(--gris)}}
.sub{{border-top:1px solid var(--gris-linea)}}
.sub>summary{{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;padding:9px 16px 9px 34px;font-weight:700;font-size:13px}}
.sub>summary::-webkit-details-marker{{display:none}}
.sub>summary .car{{transition:transform .15s;color:var(--gris)}}
.sub[open]>summary .car{{transform:rotate(90deg)}}
table{{border-collapse:collapse;width:100%;font-size:12.8px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.twrap{{overflow-x:auto;padding:0 10px 8px 34px}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
.stag{{display:inline-block;padding:2px 9px;border-radius:20px;font-weight:700;font-size:11px;white-space:nowrap}}
a{{color:var(--azul)}}
.more{{margin:6px 0 10px 34px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Gestión comercial</h1>
<p>CRM comercial (solo lectura) · Base completa del CRM · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(TOTAL)}</b><span>contactos en el reporte</span></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html" class="act"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="filters">
<div><label data-tip="Filtra por asesor contando OWNER (assignedTo) Y SEGUIDOR (followers): muestra todo contacto que el asesor toca, sea o no su dueño. Las filas donde solo es seguidor llevan el chip 'seguidor' con el owner real. '(Sin asesor asignado)' = contactos sin dueño.">Asesor</label><select id="f-a" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Lead Status' del CRM: la clasificación comercial del contacto (Nuevo, En curso, En Nutrición, Cliente, Descartado, etc.), ordenada de más caliente a más fría.">Lead status</label><select id="f-s" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'En curso por' del CRM: el horizonte de oportunidad que registró el equipo (Oportunidad 1-3 / 3-6 / 6+ meses, Sin Oportunidad). '(Sin dato)' = campo vacío.">En curso por</label><select id="f-k" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Realtor' del CRM: el realtor vinculado al contacto, ordenado por volumen.">Realtor</label><select id="f-r" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el origen del lead: campo 'Fuente de contacto' del CRM tal cual, con las variantes de Google, Referidos, Prensa y Sitio Web agrupadas. Ordenado por volumen.">Fuente del lead</label><select id="f-f" autocomplete="off"></select></div>
<div><label data-tip="Filtra por la temperatura del lead scoring (0-100): Caliente ≥55, Tibio 30-54, Frío 10-29, Sin señales <10. Misma clasificación de las píldoras — se sincronizan entre sí.">Scoring (temperatura)</label><select id="f-t" autocomplete="off">
<option value="">Todos</option>
<option value="hot">🔥 Calientes (≥55)</option>
<option value="warm">🌤 Tibios (30-54)</option>
<option value="cold">❄ Fríos (10-29)</option>
<option value="none">Sin señales (&lt;10)</option></select></div>
<div><label data-tip="Busca texto libre dentro del nombre, el email y el teléfono de los contactos de la vista.">Buscar (nombre, email, teléfono)</label><input id="f-q" autocomplete="off" placeholder="Escribe para filtrar…"></div>
<div><label data-tip="Filtra por la fecha de creación del lead en el CRM (campo dateAdded): desde esta fecha inclusive. Aplica a la tabla Y al gráfico de fuentes.">Creado desde</label><input type="date" id="f-d1" autocomplete="off"></div>
<div><label data-tip="Filtra por la fecha de creación del lead en el CRM: hasta esta fecha inclusive. Aplica a la tabla Y al gráfico de fuentes.">Creado hasta</label><input type="date" id="f-d2" autocomplete="off"></div>
</div>

<div class="fbar">
<button class="btn sec" onclick="reset()">✕ Limpiar filtros</button>
<button class="btn sec" onclick="toggleAll(true)">Expandir todo</button>
<button class="btn sec" onclick="toggleAll(false)">Colapsar todo</button>
<span id="resumen" style="font-size:12.5px;color:var(--gris)"></span>
</div>

<div class="leyenda">{leyenda}</div>

<div class="kpis">
<div class="kpi" data-tip="Qué es: cuántos contactos cumplen los filtros activos (asesor, lead status, en curso por, realtor, búsqueda). Sin filtros = la base completa del CRM."><b id="k-n">—</b><span>contactos en la vista</span></div>
<div class="kpi" data-tip="Qué es: los contactos más cercanos a la venta. Cómo se calcula: lead score ≥ 55, donde el score 0-100 suma 'En curso por' (hasta 35), Lead Status (hasta 25), interacciones registradas (hasta 20) y recencia de última actividad (hasta 20)."><b id="k-hot" style="color:var(--rojo)">—</b><span>calientes (score ≥ 55)</span></div>
<div class="kpi" data-tip="{html.escape(warm_tip.replace(' Clic: filtra la tabla a solo tibios.', ''))}"><b id="k-warm" style="color:var(--naranja)">—</b><span>tibios (score 30-54)</span></div>
<div class="kpi" data-tip="{html.escape(cold_tip.replace(' Clic: filtra la tabla a solo fríos.', ''))}"><b id="k-cold" style="color:var(--azul)">—</b><span>fríos (score 10-29)</span></div>
<div class="kpi" data-tip="{html.escape(none_tip.replace(' Clic: filtra la tabla.', ''))}"><b id="k-none" style="color:#8A99A8">—</b><span>sin señales (score &lt;10)</span></div>
<div class="kpi" data-tip="Qué es: la temperatura promedio de la vista actual. Cómo se calcula: promedio simple del lead score de todos los contactos filtrados."><b id="k-avg">—</b><span>score promedio</span></div>
<div class="kpi" data-tip="Qué es: contactos que no tienen usuario responsable en el CRM. Cómo se calcula: campo assignedTo vacío."><b id="k-sina" style="color:#8A6D1A">—</b><span>sin asesor asignado</span></div>
<div class="kpi" id="kc-atn" data-tip="Qué es: cuánto tarda el equipo en atender por primera vez a un lead. Cómo se calcula: fecha del primer mensaje SALIENTE de WhatsApp al lead menos su fecha de creación en el CRM, promediado sobre los leads de la vista que tienen conversación de WhatsApp registrada (los demás canales no dejan este dato)."><b id="k-atn" style="color:var(--azul)">—</b><span>1ª atención promedio (WA)</span></div>
<div class="kpi" data-tip="Qué es: qué % de los leads de la vista ha recibido al menos una gestión. Cómo se calcula: leads con (nº de veces contactado + actividades de venta) mayor que 0, dividido por los leads de la vista."><b id="k-cont" style="color:var(--verde)">—</b><span>% de leads contactados</span></div>
<div class="kpi" data-tip="Qué es: cuántas gestiones recibe en promedio cada lead. Cómo se calcula: promedio de (nº de veces contactado + actividades de venta) sobre todos los leads de la vista, incluidos los nunca contactados."><b id="k-cxl">—</b><span>contactos promedio por lead</span></div>
<div class="kpi" data-tip="Qué es: qué % de los leads de la vista terminó comprando. Cómo se calcula: leads con Lead Status = Cliente dividido por los leads de la vista. Con filtros de fecha mide el cierre de esa camada de leads."><b id="k-win" style="color:var(--rojo)">—</b><span>% cierre de ventas</span></div>
</div>

{EVOL_HTML}

<div class="chart-sec">
<h2>Distribución del scoring</h2>
<p class="chart-sub">Las dos tortas reaccionan a todos los filtros de arriba (fuente, asesor, status, fechas…). Clic en una porción o en su leyenda para aplicar o quitar ese filtro; pasa el mouse para ver el detalle.</p>
<div class="pies">
<div class="pie-box"><h3 data-tip="Cómo se reparte la selección actual entre calientes (score ≥55), tibios (30-54), fríos (10-29) y sin señales (<10). Respeta todos los filtros excepto el propio filtro de temperatura. Clic en una porción = filtrar la tabla a esa temperatura.">🌡 Temperatura de la vista <small style="color:var(--gris)">(por fuente u otro filtro activo)</small></h3>
<svg id="pie-temp" viewBox="0 0 340 230"></svg><div class="pleg" id="leg-temp"></div></div>
<div class="pie-box"><h3 data-tip="Qué asesores concentran los leads con score ≥30 (calientes + tibios) de la selección actual. Respeta todos los filtros excepto el de asesor y el de temperatura. Clic en una porción = filtrar por ese asesor.">👤 Scoring por asesor <small style="color:var(--gris)">(leads calientes + tibios: quién los tiene)</small></h3>
<svg id="pie-ase" viewBox="0 0 340 230"></svg><div class="pleg" id="leg-ase"></div></div>
<div class="pie-box"><h3 data-tip="Torta libre: elige la dimensión y muestra cómo se reparte la selección actual por ella (top 7 + Otros). Respeta todos los filtros excepto el de su propia dimensión. Clic en una porción = aplicar ese filtro; otro clic lo quita.">🧭 Distribución por…</h3>
<div class="chart-ctrl" style="margin:2px 0 4px"><select id="pie-dim" autocomplete="off">
<option value="s" selected>Lead Status</option>
<option value="f">Medio / fuente</option>
<option value="a">Asesor</option>
<option value="r">Realtor</option>
<option value="k">En curso por</option>
</select></div>
<svg id="pie-lib" viewBox="0 0 340 230"></svg><div class="pleg" id="leg-lib"></div></div>
</div>
</div>

<div class="chart-sec">
<h2>⏳ Maduración: temperatura según la antigüedad del lead</h2>
<p class="chart-sub">Muestra de qué temperatura son HOY los leads, agrupados por antigüedad (tiempo desde su creación), por medio/fuente o por asesor. La barra es la composición de cada grupo; las celdas se colorean con más intensidad cuanto mayor es el porcentaje. <b>Cómo leerla por antigüedad:</b> si la franja 🔥+🌤 crece en las cohortes más antiguas, los leads se van calentando con la gestión; si crece la gris, envejecen sin calentarse. Reacciona a todos los filtros de arriba excepto el de temperatura — puedes combinar: p. ej. agrupar por asesor Y filtrar la fuente Google arriba. Es una foto al corte, no un seguimiento del mismo lead.</p>
<div class="chart-ctrl"><b data-tip="Cambia la dimensión de las filas de la tabla: cohortes de antigüedad, medios/fuentes (top 12 por volumen) o asesores (top 15 por volumen).">Agrupar filas por:</b>
<select id="ed-mode" autocomplete="off">
<option value="edad" selected>Antigüedad del lead</option>
<option value="fuente">Medio / fuente</option>
<option value="asesor">Asesor</option></select></div>
<div id="edades" style="overflow-x:auto"></div>
</div>

<div class="chart-sec">
<h2>📈 Llegada de leads nuevos</h2>
<p class="chart-sub">Cuántos leads nuevos entraron al CRM en cada período, según su fecha de creación (dateAdded). <b>Respeta todos los filtros de arriba</b> — incluidos fuente, asesor, temperatura y el rango de fechas — así que puedes ver, por ejemplo, la llegada mensual de leads de Google o la llegada diaria de un asesor. Pasa el mouse sobre una barra para ver el detalle.</p>
<div class="chart-ctrl"><b data-tip="Granularidad del eje de tiempo: por mes (todo el histórico), por semana (últimas 26, cada barra inicia el lunes) o por día (últimos 60 días).">Ver por:</b>
<select id="bar-gran" autocomplete="off">
<option value="mes" selected>Mes</option>
<option value="semana">Semana (últimas 26)</option>
<option value="dia">Día (últimos 60)</option>
</select></div>
<div style="overflow-x:auto"><svg id="bar-leads" viewBox="0 0 1240 300" preserveAspectRatio="xMidYMid meet" style="width:100%;min-width:700px;height:auto;display:block"></svg></div>
</div>

<div id="tree"></div>

<div class="warnpii"><b>⚠ Datos personales:</b> este archivo contiene nombres, correos y teléfonos de {fmt(TOTAL)} personas — es la base de datos misma (Habeas Data). No publicarlo ni circularlo fuera del equipo comercial autorizado.</div>
<footer>Drill-down: Asesor → Lead Status → leads ordenados por score (más caliente primero). Lead scoring 0-100 calculado por interacción y temperatura declarada en el CRM: "En curso por" (hasta 35 pts: 1-3 meses=35, 3-6=28, 6+=18) + Lead Status (hasta 25 pts: Negocio abierto=25, En curso=15, Intento de contacto=8, Nuevo=5, En Nutrición=3) + nº de interacciones registradas (contactos + actividades de venta, hasta 20 pts) + recencia de última actividad (hasta 20 pts: ≤7 días=20, ≤30=15, ≤90=8, ≤180=4). Caliente ≥55 · Tibio 30-54 · Frío 10-29 · Sin señales &lt;10. Origen = campo "Fuente de contacto" del CRM tal cual, con cuatro agrupaciones de variantes del mismo medio: "Google / Paid Search" (Google Ads, GOOGLE, GOO DISP, paid search), "Referidos / Personal" (Personal, PERSONAL, PG Personal, Referido/a, REFERIDO y typos), "Prensa" (PRENSA, PRENSA ELECTRONICA) y "Sitio Web" (web site, Sitio web, Web Blog, dominios del sitio corporativo). Base completa de contactos (con y sin oportunidad). Generado desde la API de GHL, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fmtN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const STATUS_ORDER = {json.dumps(STATUS_ORDER, ensure_ascii=False)};
const SCOL = {json.dumps(SCOL, ensure_ascii=False)};
const scol = s => SCOL[s] || '#5B6B85';
const scoreCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
const tempTxt = sc => sc >= 55 ? 'Caliente' : sc >= 30 ? 'Tibio' : sc >= 10 ? 'Frío' : 'Sin señales';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';
const atnT = h => h < 1 ? Math.round(h * 60) + ' min' : h < 48 ? h.toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + ' h' : (h / 24).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + ' días';
const PAGE = 200;
/* el filtro de asesor cuenta owner O seguidor (followers) del contacto */
const matchA = (x, a) => a === '' || x[3] == a || (x[15] && x[15].indexOf(+a) !== -1);

function fill(id, items, labels) {{
  const s = document.getElementById(id);
  s.innerHTML = '<option value="">Todos</option>' + items.map((v, i) =>
    `<option value="${{v}}">${{esc(labels ? labels[i] : v)}}</option>`).join('');
}}
fill('f-a', D.asesores.map((_, i) => i).sort((x,y)=>D.asesores[x].localeCompare(D.asesores[y],'es')).map(i=>i),
     D.asesores.map((_, i) => i).sort((x,y)=>D.asesores[x].localeCompare(D.asesores[y],'es')).map(i => D.asesores[i]));
fill('f-s', STATUS_ORDER.map(s => D.status.indexOf(s)).filter(i => i >= 0),
     STATUS_ORDER.filter(s => D.status.indexOf(s) >= 0));
fill('f-k', D.cursos.map((_, i) => i), D.cursos);
fill('f-r', D.realtorOrden, D.realtorOrden.map(i => D.realtors[i]));
fill('f-f', D.fuenteOrden, D.fuenteOrden.map(i => D.fuentes[i]));

let view = [], TEMP = '';
['f-a','f-s','f-k','f-r','f-f'].forEach(id => document.getElementById(id).addEventListener('change', apply));
document.getElementById('f-q').addEventListener('input', apply);
const inFecha = x => {{
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  return (d1 === '' || (x[8] && x[8] >= d1)) && (d2 === '' || (x[8] && x[8] <= d2));
}};
/* las píldoras de la leyenda (calientes, En Nutrición, En curso…) se recalculan con
   TODOS los filtros activos excepto el de Lead Status (así siguen funcionando como
   conteos por estado de la selección actual) */
function pillsUpdate() {{
  const g = id => document.getElementById(id).value;
  const a = g('f-a'), k = g('f-k'), r = g('f-r'), f = g('f-f'), q = g('f-q').trim().toLowerCase();
  const rows = D.rows.filter(x =>
    matchA(x, a) && (k === '' || x[5] == k) && (r === '' || x[6] == r) &&
    (f === '' || x[7] == f) && inFecha(x) &&
    (q === '' || (x[0] + ' ' + x[1] + ' ' + x[2]).toLowerCase().includes(q)));
  document.getElementById('pill-hot').textContent = fmtN(rows.filter(r2 => r2[9] >= 55).length);
  document.getElementById('pill-warm').textContent = fmtN(rows.filter(r2 => r2[9] >= 30 && r2[9] < 55).length);
  document.getElementById('pill-cold').textContent = fmtN(rows.filter(r2 => r2[9] >= 10 && r2[9] < 30).length);
  document.getElementById('pill-none').textContent = fmtN(rows.filter(r2 => r2[9] < 10).length);
  document.querySelectorAll('[data-cs]').forEach(b => {{
    const i = +b.dataset.cs;
    b.textContent = fmtN(rows.filter(r2 => r2[4] === i).length);
  }});
}}
['f-d1','f-d2'].forEach(id => document.getElementById(id).addEventListener('change', apply));

/* tooltip global: sigue al cursor y no se recorta */
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

/* pildoras de la leyenda: filtran la tabla y bajan a ella */
document.getElementById('f-t').addEventListener('change', () => {{
  TEMP = document.getElementById('f-t').value;
  apply();
}});
document.querySelectorAll('.pill.click').forEach(p => p.addEventListener('click', () => {{
  if (p.dataset.temp) {{
    TEMP = TEMP === p.dataset.temp ? '' : p.dataset.temp;
    document.getElementById('f-t').value = TEMP;
  }} else {{
    const sel = document.getElementById('f-s');
    sel.value = sel.value === p.dataset.s ? '' : p.dataset.s;
  }}
  apply();
  document.getElementById('tree').scrollIntoView({{behavior: 'smooth'}});
}}));
function paintPills() {{
  const s = document.getElementById('f-s').value;
  document.querySelectorAll('.pill.click').forEach(p =>
    p.classList.toggle('on', p.dataset.temp ? TEMP === p.dataset.temp : (s !== '' && p.dataset.s === s)));
}}
const matchTemp = sc => TEMP === '' || (TEMP === 'hot' ? sc >= 55 : TEMP === 'warm' ? sc >= 30 && sc < 55
  : TEMP === 'cold' ? sc >= 10 && sc < 30 : sc < 10);

function apply() {{
  const g = id => document.getElementById(id).value;
  const a = g('f-a'), s = g('f-s'), k = g('f-k'), r = g('f-r'), f = g('f-f'), q = g('f-q').trim().toLowerCase();
  view = D.rows.filter(x =>
    matchA(x, a) && (s === '' || x[4] == s) && (k === '' || x[5] == k) &&
    (r === '' || x[6] == r) && (f === '' || x[7] == f) && matchTemp(x[9]) &&
    inFecha(x) &&
    (q === '' || (x[0] + ' ' + x[1] + ' ' + x[2]).toLowerCase().includes(q)));
  paintPills();
  pillsUpdate();
  renderPies();
  renderEdades();
  renderBarras();
  render();
  if (TEMP === 'hot' && view.length <= 600) toggleAll(true);
}}
const TEMPN = {{hot: 'calientes (score ≥ 55)', warm: 'tibios (30-54)', cold: 'fríos (10-29)', none: 'sin señales (<10)'}};

function render() {{
  const n = view.length;
  let hot = 0, warm = 0, cold = 0, none = 0, sum = 0, sina = 0;
  let cont = 0, isum = 0, cli = 0, atnS = 0, atnN = 0;
  const atns = [];
  const sinA = D.asesores.indexOf('(Sin asesor asignado)');
  const cliI = D.status.indexOf('Cliente');
  view.forEach(r => {{
    if (r[9] >= 55) hot++; else if (r[9] >= 30) warm++; else if (r[9] >= 10) cold++; else none++;
    sum += r[9]; if (r[3] === sinA) sina++;
    if (r[11] > 0) cont++; isum += r[11]; if (r[4] === cliI) cli++;
    if (r[13] >= 0) {{ atnS += r[13]; atnN++; atns.push(r[13]); }}
  }});
  document.getElementById('k-n').textContent = fmtN(n);
  document.getElementById('k-hot').textContent = fmtN(hot);
  document.getElementById('k-warm').textContent = fmtN(warm);
  document.getElementById('k-cold').textContent = fmtN(cold);
  document.getElementById('k-none').textContent = fmtN(none);
  document.getElementById('k-avg').textContent = n ? (sum / n).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—';
  document.getElementById('k-sina').textContent = fmtN(sina);
  document.getElementById('k-atn').textContent = atnN ? atnT(atnS / atnN) : '—';
  atns.sort((a, b) => a - b);
  const atnMed = atnN ? atns[Math.floor(atnN / 2)] : 0;
  const atn1h = atnN ? Math.round(atns.filter(h => h <= 1).length / atnN * 100) : 0;
  document.getElementById('kc-atn').dataset.tip = 'Qué es: cuánto tarda el equipo en atender por primera vez a un lead. Cómo se calcula: fecha del primer mensaje SALIENTE de WhatsApp al lead menos su fecha de creación en el CRM, sobre los ' + fmtN(atnN) + ' leads de la vista con conversación de WhatsApp (los demás canales no dejan este dato). Ojo: el promedio mezcla dos realidades — el ' + atn1h + '% se atiende en la primera hora (saludo automático) y el resto son leads viejos tocados por primera vez mucho después (mediana: ' + (atnN ? atnT(atnMed) : '—') + '). Si el promedio es alto, el problema suele ser la reactivación tardía, no el saludo inicial.';
  document.getElementById('k-cont').textContent = n ? (cont / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  document.getElementById('k-cxl').textContent = n ? (isum / n).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—';
  document.getElementById('k-win').textContent = n ? (cli / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  document.getElementById('resumen').textContent =
    n === D.rows.length ? `Mostrando la base completa (${{fmtN(n)}} contactos).`
    : `Filtro activo${{TEMP !== '' ? ' · solo leads ' + TEMPN[TEMP] : ''}}: ${{fmtN(n)}} de ${{fmtN(D.rows.length)}} contactos.`;

  /* agrupar: asesor -> status */
  const byA = new Map();
  view.forEach(r => {{
    if (!byA.has(r[3])) byA.set(r[3], []);
    byA.get(r[3]).push(r);
  }});
  const aOrder = [...byA.keys()].sort((x, y) => byA.get(y).length - byA.get(x).length);
  const sinAIdx = D.asesores.indexOf('(Sin asesor asignado)');
  if (aOrder.includes(sinAIdx)) {{ aOrder.splice(aOrder.indexOf(sinAIdx), 1); aOrder.push(sinAIdx); }}

  document.getElementById('tree').innerHTML = aOrder.map(ai => {{
    const leads = byA.get(ai);
    const hotA = leads.filter(r => r[9] >= 55).length;
    const avgA = leads.reduce((t, r) => t + r[9], 0) / leads.length;
    const byS = new Map();
    leads.forEach(r => {{
      if (!byS.has(r[4])) byS.set(r[4], []);
      byS.get(r[4]).push(r);
    }});
    const sOrder = STATUS_ORDER.map(s => D.status.indexOf(s)).filter(si => byS.has(si));
    const subs = sOrder.map(si => {{
      const ls = byS.get(si).slice().sort((x, y) => y[9] - x[9]);
      const st = D.status[si];
      return `<details class="sub" data-a="${{ai}}" data-s="${{si}}">
        <summary><span class="car">▸</span>
        <span class="stag" style="background:${{scol(st)}}22;color:${{scol(st)}}">${{esc(st)}}</span>
        <small style="color:var(--gris)">${{fmtN(ls.length)}} leads · score prom. ${{(ls.reduce((t,r)=>t+r[9],0)/ls.length).toLocaleString('es-CO',{{maximumFractionDigits:1}})}}</small>
        </summary><div class="twrap" data-holder></div></details>`;
    }}).join('');
    return `<details class="grp" data-a="${{ai}}">
      <summary><span class="car">▸</span> ${{esc(D.asesores[ai])}}
      <small>${{fmtN(leads.length)}} leads · ${{fmtN(hotA)}} calientes · score prom. ${{avgA.toLocaleString('es-CO',{{maximumFractionDigits:1}})}}</small>
      </summary>${{subs}}</details>`;
  }}).join('') || '<p style="color:var(--gris);margin:20px 0">Sin resultados con los filtros actuales.</p>';

  /* carga perezosa de tablas al expandir el status */
  document.querySelectorAll('.sub').forEach(d => d.addEventListener('toggle', () => {{
    if (d.open && !d.dataset.done) {{ d.dataset.done = 1; d.dataset.shown = 0; renderLeads(d); }}
  }}));
}}

function leadsOf(d) {{
  return view.filter(r => r[3] == d.dataset.a && r[4] == d.dataset.s).sort((x, y) => y[9] - x[9]);
}}
function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tags[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas del lead en el CRM: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
// ¿Por qué ese score? — explicación en lenguaje simple para el asesor:
// "tiene X de 100 puntos por estas razones", con las 4 variables y su porqué
function scDesg(r) {{
  const d = r[17] || [];
  if (d.length !== 4) return '';
  const fl = r[16] || '', sc = r[9];
  const st = D.status[r[4]] || '(sin status)';
  let e1;
  if (fl.indexOf('Z') !== -1) e1 = 'dijo que quiere comprar' + (fl.indexOf('M') !== -1 ? ' y habló de monto' : '') + ', PERO pidió aplazar la decisión — por eso este punto se limita a 15';
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
  const tip = `Este lead tiene ${{sc}} de 100 puntos por estas 4 razones: ` +
    `① GANAS DE COMPRAR: ${{d[0]}} de 35 pts — ${{e1}}. ` +
    `② ETAPA EN EL CRM: ${{d[1]}} de 25 pts — su lead status es «${{st}}». ` +
    `③ RESPUESTAS DEL LEAD: ${{d[2]}} de 20 pts — ${{e3}}. ` +
    `④ ACTIVIDAD RECIENTE: ${{d[3]}} de 20 pts — ${{e4}}.`;
  return `<small class="dsg" style="display:block;white-space:nowrap;color:#8A8FA3;font-size:.68rem;cursor:help;margin-top:2px" data-tip="${{tip}}">` +
    `compra ${{d[0]}} · etapa ${{d[1]}} · resp ${{d[2]}} · rec ${{d[3]}} <span style="border-bottom:1px dotted #8A8FA3">¿por qué?</span></small>`;
}}
// Oportunidad en el pipeline: r[18] = [etapaIdx, estado, fecha último cambio] ó 0 si nunca entró
function opCell(r) {{
  const o = r[18];
  if (!o) return '<span style="color:#B9BDCC" data-tip="Este lead NO tiene oportunidad creada en el pipeline de ventas: nunca ha entrado al embudo comercial.">—</span>';
  const col = o[1] === 'abierta' ? '#1D7A46' : o[1] === 'ganada' ? '#0F6E56' : '#A33B3B';
  return `<span style="white-space:nowrap;cursor:help" data-tip="Tiene OPORTUNIDAD en el pipeline de ventas: etapa «${{esc(D.opps[o[0]])}}» (${{esc(o[1])}}). Último cambio de etapa: ${{esc(o[2] || 'sin fecha')}}.">` +
    `<b>${{esc(D.opps[o[0]])}}</b><small style="display:block;color:${{col}};font-size:.68rem">${{esc(o[1])}} · ${{esc(o[2] || '')}}</small></span>`;
}}
// Próximas tareas del asesor para CONVERTIR el lead, derivadas del diagnóstico (pilares + flags + gestión)
function tareasDe(r) {{
  const d = r[17] || [0, 0, 0, 0], fl = r[16] || '', sc = r[9], t = [];
  const intTot = (r[14] && r[14][0]) || 0;
  if (fl.indexOf('Z') !== -1) t.push(['⏰', 'Agendar recontacto en la fecha aplazada', 'Crear tarea de recontacto para la fecha que él mismo dio ("retomar en…") y, mientras, enviar solo contenido de valor sin presionar.']);
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
function renderLeads(d) {{
  const aFsel = document.getElementById('f-a').value;
  const ls = leadsOf(d);
  const shown = Math.min(ls.length, (+d.dataset.shown || 0) + PAGE);
  d.dataset.shown = shown;
  const rows = ls.slice(0, shown).map(r => {{
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a> · <a href="https://wa.me/${{esc(r[2].replace(/[^0-9]/g, ''))}}" target="_blank">WA</a>` : '—';
    const FLG = {{M: ['💰', 'Monto de compra detectado en notas o mensajes del lead.'], C: ['🛒', 'Declaración de compra/inversión detectada en notas o conversaciones.'], R: ['✋', 'El lead HA RESPONDIDO (mensaje entrante, llamada contestada o respuesta registrada en notas).'], Z: ['⏸', 'Aplazamiento reciente detectado en notas ("retomar en…", "más adelante") — la intención está congelada.']}};
    const flg = (r[16] || '').split('').map(ch => FLG[ch] ? `<span data-tip="${{FLG[ch][1]}}" style="cursor:help">${{FLG[ch][0]}}</span>` : '').join('');
    return `<tr><td style="white-space:nowrap"><span class="sc" style="background:${{scoreCol(r[9])}}">${{r[9]}}</span> <small style="color:${{scoreCol(r[9])}};font-weight:700">${{tempTxt(r[9])}}</small> ${{flg}}${{scDesg(r)}}</td>
      <td><b>${{esc(r[0])}}</b>${{(aFsel !== '' && r[3] != aFsel && r[15] && r[15].indexOf(+aFsel) !== -1) ? ` <span class="tagchip" style="background:#FBF6E7;color:#8A6D1A" data-tip="El asesor filtrado es SEGUIDOR de este lead; el owner es ${{esc(D.asesores[r[3]])}} (grupo donde aparece).">seguidor</span>` : ''}}</td><td>${{em}}</td><td>${{ph}}</td>
      <td>${{esc(D.fuentes[r[7]])}}</td><td>${{esc(D.cursos[r[5]])}}</td><td>${{opCell(r)}}</td>
      <td>${{esc(D.realtors[r[6]])}}</td><td>${{esc(r[8] || '—')}}</td><td style="white-space:nowrap" data-tip="${{intTip(r[14])}}">${{intCell(r[14])}}</td><td data-tip="${{intTip(r[14])}}">${{canCell(r[14])}}</td><td>${{tareasCell(r)}}</td><td>${{tagsCell(r[10])}}</td></tr>`;
  }}).join('');
  d.querySelector('[data-holder]').innerHTML =
    `<table><thead><tr>
     <th data-tip="Qué es: lead scoring v2 0-100 y su temperatura, con el DESGLOSE de por qué debajo (int=intención, eta=etapa, eco=reciprocidad, rec=recencia; pasa el mouse para el detalle). Cómo se calcula: ① Intención 0-35 (horizonte declarado, monto o compra detectados en notas y mensajes; un aplazamiento reciente la congela a 15) + ② Etapa 0-25 (lead status) + ③ Reciprocidad 0-20 (cuánto responde EL LEAD) + ④ Recencia real 0-20 (última actividad en notas, tareas, intentos o conversaciones). Flags: 💰 monto · 🛒 compra · ✋ respondió · ⏸ aplazado. Caliente ≥55, Tibio 30-54, Frío 10-29.">Score</th>
     <th data-tip="Qué es: el nombre del contacto tal como está registrado en el CRM.">Contacto</th>
     <th data-tip="Qué es: el correo del contacto en el CRM; el enlace abre tu cliente de correo.">Email</th>
     <th data-tip="Qué es: el teléfono del contacto; 'WA' abre el chat de WhatsApp (wa.me + número).">Teléfono</th>
     <th data-tip="Qué es: de dónde llegó el lead. Cómo se calcula: campo 'Fuente de contacto' del CRM tal cual, con las variantes de Google, Referidos, Prensa y Sitio Web agrupadas.">Origen</th>
     <th data-tip="Qué es: el horizonte de oportunidad que el equipo registró. Cómo se calcula: campo 'En curso por' del CRM (Oportunidad 1-3 / 3-6 / 6+ meses, Sin Oportunidad).">En curso por</th>
     <th data-tip="Qué es: si el lead tiene OPORTUNIDAD creada en el pipeline de ventas y en qué etapa del embudo está (Nuevo Lead, Intento de Contacto, WARM, HOT, Cierre…), con su estado: abierta, ganada, perdida o abandonada, y la fecha del último cambio de etapa. Cómo se calcula: cruce por email/teléfono contra las oportunidades del PIPELINE; si tiene varias se muestra la abierta más reciente. '—' = nunca ha entrado al pipeline.">Oportunidad</th>
     <th data-tip="Qué es: el realtor vinculado al contacto. Cómo se calcula: campo 'Realtor' del CRM.">Realtor</th>
     <th data-tip="Qué es: cuándo entró el contacto a la base. Cómo se calcula: fecha de creación del contacto en el CRM (dateAdded).">Creado</th>
     <th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
     <th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
     <th data-tip="Qué es: las principales acciones que el asesor debe ejecutar para CONVERTIR este lead, derivadas de su diagnóstico de score (pilares débiles, flags y gestión previa). Máx 3 en orden de prioridad; pasa el mouse sobre cada una para el detalle completo.">Para convertir</th>
     <th data-tip="Qué es: las etiquetas (tags) del contacto tal como están en el CRM — campañas, eventos, listas e importaciones. Se muestran las 2 primeras; el chip +N muestra el resto al pasar el mouse.">Etiquetas</th>
     </tr></thead>
     <tbody>${{rows}}</tbody></table>` +
    (shown < ls.length ? `<button class="btn sec more" onclick="moreLeads(this)">Mostrar ${{fmtN(Math.min(PAGE, ls.length - shown))}} más (${{fmtN(ls.length - shown)}} restantes)</button>` : '');
}}
function moreLeads(btn) {{ renderLeads(btn.closest('.sub')); }}
function toggleAll(open) {{
  document.querySelectorAll('.grp').forEach(d => d.open = open);
  if (open) document.querySelectorAll('.sub').forEach(d => {{ if (!d.open) d.open = true; }});
  else document.querySelectorAll('.sub').forEach(d => d.open = false);
}}
function reset() {{
  ['f-a','f-s','f-k','f-r','f-f','f-t','f-d1','f-d2'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-q').value = '';
  TEMP = '';
  apply();
}}

/* ---------- generador XLSX nativo (sin librerias): zip STORE + SpreadsheetML ---------- */
const XL = (() => {{
  const CRC = (() => {{ const t = new Uint32Array(256); for (let n = 0; n < 256; n++) {{ let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c; }} return t; }})();
  const crc32 = b => {{ let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }};
  const enc = new TextEncoder();
  const escX = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  function sheetXml(rows) {{
    let out = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>';
    for (let ri = 0; ri < rows.length; ri++) {{
      out += '<row r="' + (ri + 1) + '">';
      const r = rows[ri];
      for (let ci = 0; ci < r.length; ci++) {{
        const v = r[ci];
        if (typeof v === 'number' && isFinite(v)) out += '<c t="n"><v>' + v + '</v></c>';
        else out += '<c t="inlineStr"><is><t xml:space="preserve">' + escX(v === null || v === undefined ? '' : v) + '</t></is></c>';
      }}
      out += '</row>';
    }}
    return out + '</sheetData></worksheet>';
  }}
  function zip(files) {{
    const parts = [], cd = [];
    let off = 0, cdLen = 0;
    for (const [name, str] of files) {{
      const nb = enc.encode(name), db = enc.encode(str), crc = crc32(db);
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, db.length, true); lh.setUint32(22, db.length, true);
      lh.setUint16(26, nb.length, true);
      parts.push(new Uint8Array(lh.buffer), nb, db);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true);
      ch.setUint32(16, crc, true); ch.setUint32(20, db.length, true); ch.setUint32(24, db.length, true);
      ch.setUint16(28, nb.length, true); ch.setUint32(42, off, true);
      cd.push(new Uint8Array(ch.buffer), nb);
      cdLen += 46 + nb.length;
      off += 30 + nb.length + db.length;
    }}
    const eo = new DataView(new ArrayBuffer(22));
    eo.setUint32(0, 0x06054b50, true);
    eo.setUint16(8, files.length, true); eo.setUint16(10, files.length, true);
    eo.setUint32(12, cdLen, true); eo.setUint32(16, off, true);
    return new Blob([...parts, ...cd, new Uint8Array(eo.buffer)],
      {{type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}});
  }}
  return function (filename, rows) {{
    const files = [
      ['[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
      ['_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
      ['xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Datos" sheetId="1" r:id="rId1"/></sheets></workbook>'],
      ['xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'],
      ['xl/worksheets/sheet1.xml', sheetXml(rows)]
    ];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(zip(files));
    a.download = filename; a.click(); URL.revokeObjectURL(a.href);
  }};
}})();

function csv() {{
  const rows = [['Asesor','Lead Status','Score','Temperatura','Contacto','Email','Telefono','Origen','En curso por','Realtor','Creado','Intentos','Dias de intento','Canales','Etiquetas']];
  view.slice().sort((x, y) => (x[3] - y[3]) || (y[9] - x[9])).forEach(r =>
    rows.push([D.asesores[r[3]], D.status[r[4]], r[9], tempTxt(r[9]), r[0], r[1], r[2],
               D.fuentes[r[7]], D.cursos[r[5]], D.realtors[r[6]], r[8],
               r[14] ? r[14][0] : 0, r[14] ? r[14][1] : 0, canTxt(r[14]),
               (r[10] || []).map(i => D.tags[i]).join(' | ')]));
  XL('gestion-comercial-filtrado.xlsx', rows);
}}/* ---------- tortas interactivas: temperatura y scoring por asesor ---------- */
function filtroBase(exceptos) {{
  const g = id => document.getElementById(id).value;
  const a = g('f-a'), s = g('f-s'), k = g('f-k'), r = g('f-r'), f = g('f-f'), q = g('f-q').trim().toLowerCase();
  return D.rows.filter(x =>
    (exceptos.includes('a') || matchA(x, a)) &&
    (exceptos.includes('s') || s === '' || x[4] == s) &&
    (exceptos.includes('k') || k === '' || x[5] == k) &&
    (exceptos.includes('r') || r === '' || x[6] == r) &&
    (exceptos.includes('f') || f === '' || x[7] == f) &&
    (exceptos.includes('t') || matchTemp(x[9])) && inFecha(x) &&
    (q === '' || (x[0] + ' ' + x[1] + ' ' + x[2]).toLowerCase().includes(q)));
}}
function arcPath(cx, cy, r0, r1, a0, a1) {{
  const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(r1, a0), [x1, y1] = p(r1, a1), [x2, y2] = p(r0, a1), [x3, y3] = p(r0, a0);
  const big = (a1 - a0) > Math.PI ? 1 : 0;
  return `M${{x0}} ${{y0}} A${{r1}} ${{r1}} 0 ${{big}} 1 ${{x1}} ${{y1}} L${{x2}} ${{y2}} A${{r0}} ${{r0}} 0 ${{big}} 0 ${{x3}} ${{y3}} Z`;
}}
function drawPie(svgId, legId, data, centro) {{
  const svg = document.getElementById(svgId), leg = document.getElementById(legId);
  const total = data.reduce((t, d) => t + d.val, 0);
  if (!total) {{
    svg.innerHTML = `<text x="170" y="115" text-anchor="middle" font-size="13" fill="#5B6B85">Sin leads en la selección actual</text>`;
    leg.innerHTML = ''; return;
  }}
  const cx = 170, cy = 112, r0 = 52, r1 = 96;
  let a = -Math.PI / 2, g = '';
  data.forEach((d, i) => {{
    if (!d.val) return;
    const a2 = a + d.val / total * 2 * Math.PI;
    g += `<path class="pslice" data-i="${{i}}" data-tip="${{esc(d.tip)}}" d="${{arcPath(cx, cy, r0, r1, a, Math.min(a2, a + 6.28318))}}" fill="${{d.color}}" stroke="#fff" stroke-width="2"/>`;
    if (d.val / total >= 0.06) {{
      const am = (a + a2) / 2, rx = cx + (r0 + r1) / 2 * Math.cos(am), ry = cy + (r0 + r1) / 2 * Math.sin(am);
      g += `<text x="${{rx}}" y="${{ry + 4}}" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" pointer-events="none">${{(d.val / total * 100).toFixed(0)}}%</text>`;
    }}
    a = a2;
  }});
  g += `<text x="${{cx}}" y="${{cy - 2}}" text-anchor="middle" font-size="19" font-weight="900" fill="#152238">${{fmtN(total)}}</text>`;
  g += `<text x="${{cx}}" y="${{cy + 15}}" text-anchor="middle" font-size="10.5" fill="#5B6B85">${{esc(centro)}}</text>`;
  svg.innerHTML = g;
  leg.innerHTML = data.filter(d => d.val).map((d, i) =>
    `<span class="li" data-i="${{data.indexOf(d)}}" data-tip="${{esc(d.tip)}}"><span class="dot" style="background:${{d.color}}"></span>${{esc(d.label)}}: <b>${{fmtN(d.val)}}</b></span>`).join('');
  const act = el => {{ const d = data[+el.dataset.i]; if (d && d.click) d.click(); }};
  svg.querySelectorAll('.pslice').forEach(el => el.addEventListener('click', () => act(el)));
  leg.querySelectorAll('.li').forEach(el => el.addEventListener('click', () => act(el)));
}}
const PIE_ASE_COL = ['#3A566B', '#C4B284', '#1E9E62', '#8A6D1A', '#5A6B78', '#2C4356', '#C47845', '#8A99A8'];
function renderPies() {{
  /* torta 1: temperatura de la vista (todos los filtros menos temperatura) */
  const r1 = filtroBase(['t']);
  const cnt = {{hot: 0, warm: 0, cold: 0, none: 0}};
  r1.forEach(x => {{ if (x[9] >= 55) cnt.hot++; else if (x[9] >= 30) cnt.warm++; else if (x[9] >= 10) cnt.cold++; else cnt.none++; }});
  const TCRIT = {{
    hot: 'Criterio: score ≥55 — combina al menos dos señales fuertes: oportunidad vigente (hasta 35 pts) + estado activo (hasta 25) + interacción reciente (hasta 40 entre volumen y recencia).',
    warm: 'Criterio: score 30-54 — tiene UNA señal fuerte pero le falta otra (p. ej. En curso con interacción pero sin oportunidad registrada, u oportunidad 6+ meses con poca interacción).',
    cold: 'Criterio: score 10-29 — solo señales débiles: estado inicial (Nutrición/Intento) y/o interacciones viejas, sin oportunidad vigente.',
    none: 'Criterio: score <10 — sin oportunidad registrada, sin estado que sume y sin interacciones: cero evidencia de interés en el CRM.'}};
  const tdef = [
    ['hot', '🔥 Calientes (≥55)', '#D64545'], ['warm', '🌤 Tibios (30-54)', '#AA9664'],
    ['cold', '❄ Fríos (10-29)', '#3A566B'], ['none', 'Sin señales (<10)', '#8A99A8']];
  drawPie('pie-temp', 'leg-temp', tdef.map(([k2, l, c]) => ({{
    label: l, val: cnt[k2], color: c,
    tip: `${{l}}: ${{fmtN(cnt[k2])}} leads (${{r1.length ? (cnt[k2] / r1.length * 100).toFixed(1) : 0}}% de la selección). ${{TCRIT[k2]}} Clic para filtrar la tabla a esta temperatura.`,
    click: () => {{ TEMP = TEMP === k2 ? '' : k2; apply(); renderPies(); }}
  }})), 'leads en la selección');
  /* torta 2: leads score ≥30 por asesor (todos los filtros menos asesor y temperatura) */
  const r2 = filtroBase(['a', 't']).filter(x => x[9] >= 30);
  const porA = new Map();
  r2.forEach(x => porA.set(x[3], (porA.get(x[3]) || 0) + 1));
  const top = [...porA.entries()].sort((x, y) => y[1] - x[1]);
  const datos = top.slice(0, 7).map(([ai, n], i) => ({{
    label: D.asesores[ai], val: n, color: PIE_ASE_COL[i],
    tip: `${{D.asesores[ai]}}: ${{fmtN(n)}} leads calientes/tibios (${{(n / r2.length * 100).toFixed(1)}}% de los calificados de la selección). Clic para filtrar por este asesor.`,
    click: () => {{ const s = document.getElementById('f-a'); s.value = s.value == ai ? '' : ai; apply(); renderPies(); }}
  }}));
  const resto = top.slice(7).reduce((t, [, n]) => t + n, 0);
  if (resto) datos.push({{label: 'Otros asesores', val: resto, color: '#C9D6E4',
    tip: `Otros ${{top.length - 7}} asesores: ${{fmtN(resto)}} leads calientes/tibios.`, click: null}});
  drawPie('pie-ase', 'leg-ase', datos, 'calientes + tibios');
  /* torta 3: dimensión libre */
  const DIMS = {{
    s: {{col: 4, nombres: D.status, sel: 'f-s', titulo: 'Lead Status'}},
    f: {{col: 7, nombres: D.fuentes, sel: 'f-f', titulo: 'medio / fuente'}},
    a: {{col: 3, nombres: D.asesores, sel: 'f-a', titulo: 'asesor'}},
    r: {{col: 6, nombres: D.realtors, sel: 'f-r', titulo: 'realtor'}},
    k: {{col: 5, nombres: D.cursos, sel: 'f-k', titulo: 'en curso por'}},
  }};
  const dv = document.getElementById('pie-dim').value;
  const dim = DIMS[dv];
  const r3 = filtroBase([dv]);
  const cnt3 = new Map();
  r3.forEach(x => cnt3.set(x[dim.col], (cnt3.get(x[dim.col]) || 0) + 1));
  const top3 = [...cnt3.entries()].sort((x, y) => y[1] - x[1]);
  const datos3 = top3.slice(0, 7).map(([vi, n], i) => ({{
    label: dim.nombres[vi], val: n,
    color: dv === 's' ? (SCOL[dim.nombres[vi]] || PIE_ASE_COL[i]) : PIE_ASE_COL[i],
    tip: `${{dim.nombres[vi]}}: ${{fmtN(n)}} leads (${{(n / r3.length * 100).toFixed(1)}}% de la selección por ${{dim.titulo}}). Clic para aplicar/quitar este filtro.`,
    click: () => {{ const s = document.getElementById(dim.sel); s.value = s.value == vi ? '' : vi; apply(); }}
  }}));
  const resto3 = top3.slice(7).reduce((t, [, n]) => t + n, 0);
  if (resto3) datos3.push({{label: 'Otros', val: resto3, color: '#C9D6E4',
    tip: `Otros ${{top3.length - 7}} valores de ${{dim.titulo}}: ${{fmtN(resto3)}} leads.`, click: null}});
  drawPie('pie-lib', 'leg-lib', datos3, 'por ' + dim.titulo);
}}

/* ---------- maduración: temperatura según antigüedad ---------- */
const EDADES = [
  ['0-30 días', 0, 30], ['1-3 meses', 31, 90], ['3-6 meses', 91, 180],
  ['6-12 meses', 181, 365], ['1-2 años', 366, 730], ['+2 años', 731, 99999]];
const TCOL2 = {{hot: '#D64545', warm: '#AA9664', cold: '#3A566B', none: '#8A99A8'}};
const hexA = (hex, a) => hex + Math.round(a * 255).toString(16).padStart(2, '0');
function renderEdades() {{
  const hoy = Date.now();
  const modo = document.getElementById('ed-mode').value;
  const rows = filtroBase(['t']);
  const nuevo = () => ({{hot: 0, warm: 0, cold: 0, none: 0, n: 0, sum: 0}});
  const meter = (b, x) => {{
    b.n++; b.sum += x[9];
    if (x[9] >= 55) b.hot++; else if (x[9] >= 30) b.warm++; else if (x[9] >= 10) b.cold++; else b.none++;
  }};
  let labels = [], B = [];
  if (modo === 'edad') {{
    labels = EDADES.map(e => e[0]);
    B = EDADES.map(nuevo);
    rows.forEach(x => {{
      if (!x[8]) return;
      const dias = Math.floor((hoy - new Date(x[8] + 'T12:00:00').getTime()) / 86400000);
      const bi = EDADES.findIndex(([, d0, d1]) => dias >= d0 && dias <= d1);
      if (bi >= 0) meter(B[bi], x);
    }});
  }} else {{
    const dim = modo === 'fuente' ? 7 : 3;
    const nombres = modo === 'fuente' ? D.fuentes : D.asesores;
    const topN = modo === 'fuente' ? 12 : 15;
    const cnt = new Map();
    rows.forEach(x => cnt.set(x[dim], (cnt.get(x[dim]) || 0) + 1));
    const top = [...cnt.entries()].sort((a, b) => b[1] - a[1]).slice(0, topN).map(e => e[0]);
    labels = top.map(i => nombres[i]).concat(cnt.size > topN ? ['Otros'] : []);
    B = labels.map(nuevo);
    const pos = new Map(top.map((i, j) => [i, j]));
    rows.forEach(x => meter(B[pos.has(x[dim]) ? pos.get(x[dim]) : B.length - 1] || B[B.length - 1], x));
  }}
  const TL = {{hot: '🔥 Calientes', warm: '🌤 Tibios', cold: '❄ Fríos', none: 'Sin señales'}};
  const celda = (b, k) => {{
    if (!b.n) return '<td>—</td>';
    const p = b[k] / b.n * 100;
    return `<td style="background:${{hexA(TCOL2[k], Math.min(.5, p / 100 * .85))}};font-weight:700" ` +
      `data-tip="${{TL[k]}} en esta cohorte: ${{fmtN(b[k])}} leads = ${{p.toFixed(1)}}% de los ${{fmtN(b.n)}} de esa antigüedad.">${{fmtN(b[k])}} <small style="font-weight:600;opacity:.75">(${{p.toFixed(0)}}%)</small></td>`;
  }};
  const barra2 = b => {{
    if (!b.n) return '';
    return '<div style="display:flex;height:18px;border-radius:6px;overflow:hidden;min-width:180px">' +
      ['hot', 'warm', 'cold', 'none'].map(k => b[k] ? `<div data-tip="${{TL[k]}}: ${{(b[k]/b.n*100).toFixed(1)}}% de la cohorte" style="width:${{b[k]/b.n*100}}%;background:${{TCOL2[k]}}"></div>` : '').join('') + '</div>';
  }};
  const tot = B.reduce((t, b) => ({{hot: t.hot + b.hot, warm: t.warm + b.warm, cold: t.cold + b.cold, none: t.none + b.none, n: t.n + b.n, sum: t.sum + b.sum}}), {{hot: 0, warm: 0, cold: 0, none: 0, n: 0, sum: 0}});
  const col1 = modo === 'edad' ? 'Antigüedad del lead' : modo === 'fuente' ? 'Medio / fuente' : 'Asesor';
  const tip1 = modo === 'edad'
    ? 'Cohorte por antigüedad: días transcurridos desde la fecha de creación del lead en el CRM (dateAdded) hasta hoy.'
    : modo === 'fuente' ? 'Medio/fuente del lead (campo Fuente de contacto agrupado), top 12 por volumen de la selección.'
    : 'Asesor asignado al lead (assignedTo), top 15 por volumen de la selección.';
  document.getElementById('edades').innerHTML = `<table style="min-width:860px"><thead><tr>
    <th data-tip="${{esc(tip1)}}">${{col1}}</th>
    <th data-tip="Total de leads de la selección actual en ese grupo.">Leads</th>
    <th data-tip="Composición de temperatura del grupo: proporción de calientes, tibios, fríos y sin señales.">Composición de temperatura</th>
    <th data-tip="Leads con score ≥55 en el grupo (nº y % del grupo).">🔥</th>
    <th data-tip="Leads con score 30-54 en el grupo.">🌤</th>
    <th data-tip="Leads con score 10-29 en el grupo.">❄</th>
    <th data-tip="Leads con score <10 en el grupo: sin evidencia de interés.">Sin señales</th>
    <th data-tip="Score promedio del grupo: su 'temperatura media'.">Score prom.</th></tr></thead><tbody>` +
    B.map((b, i) => `<tr><td><b>${{esc(labels[i])}}</b></td><td>${{fmtN(b.n)}}</td><td>${{barra2(b)}}</td>` +
      celda(b, 'hot') + celda(b, 'warm') + celda(b, 'cold') + celda(b, 'none') +
      `<td><b>${{b.n ? (b.sum / b.n).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</b></td></tr>`).join('') +
    `<tr style="border-top:2px solid var(--gris-linea)"><td><b>Toda la selección</b></td><td><b>${{fmtN(tot.n)}}</b></td><td>${{barra2(tot)}}</td>` +
    celda(tot, 'hot') + celda(tot, 'warm') + celda(tot, 'cold') + celda(tot, 'none') +
    `<td><b>${{tot.n ? (tot.sum / tot.n).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—'}}</b></td></tr></tbody></table>`;
}}

/* ---------- barras: llegada de leads nuevos ---------- */
const MES_N = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function renderBarras() {{
  const gran = document.getElementById('bar-gran').value;
  const rows = filtroBase([]).filter(x => x[8]);
  const cnt = new Map();
  const lunes = ds => {{
    const d = new Date(ds + 'T12:00:00');
    d.setDate(d.getDate() - (d.getDay() + 6) % 7);
    return d.toISOString().slice(0, 10);
  }};
  rows.forEach(x => {{
    const k = gran === 'mes' ? x[8].slice(0, 7) : gran === 'semana' ? lunes(x[8]) : x[8];
    cnt.set(k, (cnt.get(k) || 0) + 1);
  }});
  let keys = [...cnt.keys()].sort();
  if (gran === 'semana') keys = keys.slice(-26);
  if (gran === 'dia') keys = keys.slice(-60);
  if (gran === 'mes') keys = keys.slice(-24);
  const svg = document.getElementById('bar-leads');
  if (!keys.length) {{ svg.innerHTML = '<text x="620" y="150" text-anchor="middle" font-size="13" fill="#5B6B85">Sin leads en la selección actual</text>'; return; }}
  const et = k => {{
    if (gran === 'mes') return MES_N[+k.slice(5, 7) - 1] + ' ' + k.slice(2, 4);
    const d = new Date(k + 'T12:00:00');
    return (gran === 'semana' ? 'sem ' : '') + d.getDate() + ' ' + MES_N[d.getMonth()];
  }};
  const W = 1240, H = 300, L = 46, R = 14, T = 18, B2 = 42;
  const max = Math.max(...keys.map(k => cnt.get(k)));
  const bw = (W - L - R) / keys.length;
  const Y = v => T + (1 - v / (max * 1.12)) * (H - T - B2);
  let g = '';
  const paso = max > 40 ? Math.ceil(max / 4 / 10) * 10 : Math.max(1, Math.ceil(max / 4));
  for (let v = 0; v <= max * 1.05; v += paso) {{
    g += `<line x1="${{L}}" y1="${{Y(v)}}" x2="${{W - R}}" y2="${{Y(v)}}" stroke="#F0F3F8"/>` +
         `<text x="${{L - 6}}" y="${{Y(v) + 3.5}}" text-anchor="end" font-size="10.5" fill="#5B6B85">${{fmtN(v)}}</text>`;
  }}
  keys.forEach((k, i) => {{
    const v = cnt.get(k);
    const x = L + i * bw + bw * 0.12, w = bw * 0.76;
    g += `<rect x="${{x}}" y="${{Y(v)}}" width="${{w}}" height="${{H - B2 - Y(v)}}" rx="3" fill="#3A566B" ` +
      `data-tip="${{esc(et(k))}}: ${{fmtN(v)}} leads nuevos en la selección actual." style="cursor:help"></rect>`;
    if (keys.length <= 32) g += `<text x="${{x + w / 2}}" y="${{Y(v) - 5}}" text-anchor="middle" font-size="${{keys.length > 24 ? 9 : 11}}" font-weight="700" fill="#2C4356">${{fmtN(v)}}</text>`;
    const cada = keys.length > 40 ? 7 : keys.length > 20 ? 2 : 1;
    if (i % cada === 0) g += `<text x="${{x + w / 2}}" y="${{H - B2 + 16}}" text-anchor="middle" font-size="10" fill="#5B6B85">${{esc(et(k))}}</text>`;
  }});
  g += `<line x1="${{L}}" y1="${{H - B2}}" x2="${{W - R}}" y2="${{H - B2}}" stroke="#E4E9F2"/>`;
  svg.innerHTML = g;
}}
document.getElementById('bar-gran').addEventListener('change', renderBarras);

/* arranque limpio: el navegador restaura valores de formulario entre visitas
   (incluso con autocomplete=off), así que reseteamos filtros al cargar */
document.getElementById('ed-mode').addEventListener('change', renderEdades);
document.getElementById('pie-dim').addEventListener('change', renderPies);
function arranque() {{
  document.getElementById('ed-mode').value = 'edad';
  document.getElementById('pie-dim').value = 's';
  document.getElementById('bar-gran').value = 'mes';
  reset();
}}
arranque();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranque(); }});
setTimeout(() => {{
  const alguno = ['f-a','f-s','f-k','f-r','f-f','f-t','f-q','f-d1','f-d2'].some(id => document.getElementById(id).value !== '');
  if (alguno) arranque();
}}, 250);
</script>
</body></html>'''

out = str(ROOT / f'reporte-contactos-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
sc_all = [r[9] for r in rows]
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print('status:', dict(scnt.most_common()))
print(f'scores: prom {sum(sc_all)/len(sc_all):.1f} | calientes(>=55) {sum(1 for s in sc_all if s>=55)} | tibios(30-54) {sum(1 for s in sc_all if 30<=s<55)}')
