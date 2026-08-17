#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de análisis de leads DESCARTADOS: por qué se descartan, quién los descarta,
cuánta gestión recibieron antes, cuáles son rescatables y qué aprender para optimizar
el proceso comercial. HTML autocontenido. Lee scripts/data/{contacts,users}.json
(descarga previa de ghl_fetch_contactos.py — solo consulta, cero escritura en el CRM)."""
import json, html, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW   = datetime.now(timezone.utc)
_hoy  = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

# ---------- fuente = campo "Fuente de contacto" del CRM (mismas familias del home) ----------
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
    if 'google' in sl or sl.startswith('goo ') or sl == 'goo disp' or sl == 'paid search':
        return 'Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl or sl in ('rerefido', 'referral', 'pereonal', 'personall'):
        return 'Referidos / Personal'
    if sl.startswith('prensa'):
        return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'):
        return 'Sitio Web'
    return CANON[sl]

# ---------- score (misma fórmula 0-100 del home) ----------
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
    s  = CURSO_PTS.get((c.get('enCursoPor') or '').strip(), 0)
    s += STATUS_PTS.get((c.get('leadStatus') or '').strip(), 0)
    s += min(20, num(c.get('vecesContactado')) + num(c.get('salesActivities')))
    la = c.get('lastActivity') or c.get('lastEngagement')
    if la:
        try:
            d = (NOW - datetime.fromisoformat(str(la).replace('Z','+00:00'))).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)


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
# ---------- filas (mismo formato del home: idx 11 = interacciones, 12 = motivo) ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DA, giA = dict_indexer()
DS, giS = dict_indexer()
DK, giK = dict_indexer()
DR, giR = dict_indexer()
DF, giF = dict_indexer()
DT, giT = dict_indexer()
DMO, giMO = dict_indexer()
for s in STATUS_ORDER: giS(s)
for k in CURSO_ORDER:  giK(k)

DOP, giOP = dict_indexer()  # etapa de oportunidad en el pipeline
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
def opp_row(c):
    _op = None
    for _k in ((c.get('email') or '').strip().lower(), re.sub(r'\D', '', c.get('phone') or '')):
        if _k and _k in _OPP_BY: _op = _OPP_BY[_k]; break
    return ([giOP(_STG.get(_op['stage'], '(etapa desconocida)')),
             _ST_ES.get((_op.get('status') or '').lower(), _op.get('status') or ''),
             (_op.get('stageChange') or _op.get('created') or '')[:10]] if _op else 0)

rows = []
for c in contacts:
    a  = USERS.get(c['assigned'], '(Sin asesor asignado)') if c['assigned'] else '(Sin asesor asignado)'
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    if st not in STATUS_ORDER: st = '(Sin status)'
    ku = (c.get('enCursoPor') or '').strip() or '(Sin dato)'
    if ku not in CURSO_ORDER: ku = '(Sin dato)'
    rl = c.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(r.strip() for r in rl if r and r.strip()) or '(Sin realtor)'
    mo = (c.get('motivoDescarte') or '').strip().replace('No caliifica', 'No califica')
    if not mo or mo == 'N/A': mo = '(Sin motivo registrado)'
    inter = num(c.get('vecesContactado')) + num(c.get('salesActivities'))
    rows.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c['email'] or '', c['phone'] or '',
        giA(a), giS(st), giK(ku), giR(rl), giF(fuente_of(c)),
        fecha_local(c['created']), score_of(c),
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        inter, giMO(mo), intentos_of(c['id']),
        [giA(USERS[u]) for u in fols(c) if u in USERS],
        (_SC2.get(c['id']) or {}).get('fl', ''),
        (_SC2.get(c['id']) or {}).get('d', []),
        opp_row(c)
    ])

TOTAL = len(rows)
ST_D = STATUS_ORDER.index('Descartado')
DESC = [r for r in rows if r[4] == ST_D]
N_DESC = len(DESC)
def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
motivo_vol  = Counter(r[12] for r in DESC)
asesor_vol  = Counter(r[3] for r in DESC)
fuente_vol  = Counter(r[7] for r in rows)
realtor_vol = Counter(r[6] for r in DESC)
curso_vol   = Counter(r[5] for r in DESC)

PAYLOAD = json.dumps({
    'rows': rows,
    'asesores': ordered(DA), 'status': ordered(DS), 'cursos': ordered(DK),
    'realtors': ordered(DR), 'fuentes': ordered(DF), 'tags': ordered(DT),
    'motivos': ordered(DMO), 'opps': ordered(DOP),
    'motivoOrden':  [i for i, _ in motivo_vol.most_common()],
    'asesorOrden':  [i for i, _ in asesor_vol.most_common()],
    'fuenteOrden':  [i for i, _ in fuente_vol.most_common()],
    'realtorOrden': [i for i, _ in realtor_vol.most_common()],
    'cursoOrden':   [i for i, _ in curso_vol.most_common()],
}, ensure_ascii=False)

def fmt(n): return f'{n:,}'.replace(',', '.')

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Análisis de pérdida de leads</title>
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
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
[data-tip]{{cursor:help}}
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
.clkd{{cursor:pointer}} tr.clkd:hover td{{background:var(--azul-suave)}}
.kpi.clkd:hover{{border-color:var(--azul);background:var(--gris-fondo)}}
.kpi.on{{outline:2px solid var(--azul);outline-offset:1px;background:var(--azul-suave)}}
.pies{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
.pie-box h3{{font-size:13.5px;margin:4px 0 2px}}
.pie-box svg{{width:100%;height:auto;display:block}}
.pleg{{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12.2px;margin-top:4px}}
.pleg .li{{cursor:pointer;user-select:none}} .pleg .li:hover{{text-decoration:underline}}
.pleg .dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.pslice{{cursor:pointer}} .pslice:hover{{opacity:.82}}
.chart-sec{{border:1px solid var(--gris-linea);border-radius:13px;padding:16px 16px 12px;margin:4px 0 20px}}
.chart-sec h2{{font-size:15.5px;margin-bottom:2px}}
.chart-sub{{font-size:12px;color:var(--gris);margin-bottom:10px}}
table{{border-collapse:collapse;width:100%;font-size:12.8px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.bar{{background:var(--gris-fondo);border-radius:6px;height:14px;overflow:hidden}}
.bar div{{height:100%;border-radius:6px}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
.mchip{{display:inline-block;background:#D6454515;color:#B03030;border:1px solid #D6454540;border-radius:10px;padding:1px 8px;font-size:10.8px;font-weight:700;white-space:nowrap}}
a{{color:var(--azul)}}
.caveat{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.8px;margin-top:12px}}
.more{{margin:8px 0}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Análisis de pérdida de leads (descartados)</h1>
<p>CRM comercial (solo lectura) · Por qué se descartan, quién los descarta y cuáles rescatar · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(N_DESC)}</b><span>leads descartados ({f'{N_DESC / TOTAL * 100:.0f}'.replace('.', ',')}% de {fmt(TOTAL)})</span></div>
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

<div class="filters">
<div><label data-tip="Filtra por asesor contando OWNER (quien lo tenía al descartarse) o SEGUIDOR (followers). MARKETING PFS = descartado por la automatización. Solo cambia la consulta del reporte.">Quién lo descartó (asesor)</label><select id="f-a" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Motivo de descarte' del CRM. '(Sin motivo registrado)' = descarte sin explicación. Ordenado por volumen.">Motivo de descarte</label><select id="f-m" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el origen del lead: campo 'Fuente de contacto' del CRM, con las variantes de Paid Search (Google Ads), Referidos, Prensa y Sitio Web agrupadas. Ordenado por volumen de toda la base.">Fuente del lead</label><select id="f-f" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'En curso por': el horizonte de oportunidad que registró el equipo. Un descartado con 'Oportunidad …' vigente es una contradicción a revisar.">En curso por</label><select id="f-k" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Realtor' del CRM, ordenado por volumen de descartes.">Realtor</label><select id="f-r" autocomplete="off"></select></div>
<div><label data-tip="Busca texto libre dentro del nombre, el email y el teléfono de los leads descartados.">Buscar (nombre, email, teléfono)</label><input id="f-q" autocomplete="off" placeholder="Escribe para filtrar…"></div>
<div><label data-tip="Filtra por la fecha de creación del lead en el CRM (dateAdded): desde esta fecha inclusive. Afecta KPIs, tablas y la tasa por fuente.">Creado desde</label><input type="date" id="f-d1" autocomplete="off"></div>
<div><label data-tip="Filtra por la fecha de creación del lead en el CRM: hasta esta fecha inclusive.">Creado hasta</label><input type="date" id="f-d2" autocomplete="off"></div>
</div>

<div class="fbar">
<button class="btn sec" onclick="reset()">✕ Limpiar filtros</button>
<span id="resumen" style="font-size:12.5px;color:var(--gris)"></span>
</div>

<div class="kpis" id="dsc-kpis"></div>

<div class="chart-sec">
<h2>🥧 Descartes por fuente y por asesor</h2>
<p class="chart-sub">Cómo se reparten los descartados de la selección actual. Reaccionan a todos los filtros de arriba. Clic en una porción o en su leyenda aplica (o quita) ese filtro.</p>
<div class="pies">
<div class="pie-box"><h3 data-tip="Reparto de los descartados por el medio/fuente del lead (campo 'Fuente de contacto' con las familias agrupadas). Muestra dónde nacen los leads que se botan; compárala con la tabla de tasa por fuente, que mide qué % de cada fuente se descarta. Clic en una porción = filtrar por esa fuente.">📣 Descartados por medio / fuente</h3>
<svg id="pie-fu" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-fu"></div></div>
<div class="pie-box"><h3 data-tip="Reparto de los descartados por el usuario asignado (quién los descartó o los tenía al descartarse). MARKETING PFS = descartes de la automatización, no de una persona. Clic en una porción = filtrar por ese asesor.">👤 Descartados por asesor</h3>
<svg id="pie-asg" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-asg"></div></div>
</div>
</div>

<div class="chart-sec">
<h2>🔎 Radiografía del descarte</h2>
<p class="chart-sub">Todo reacciona a los filtros de arriba. Clic en una fila aplica ese filtro (motivo, asesor o fuente) y baja a la tabla de leads; clic en un KPI activa/desactiva ese recorte especial (sin gestión, rescatables, sin motivo…).</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px">
<div><h3 style="font-size:13.5px;margin:6px 0 4px" data-tip="Campo 'Motivo de descarte' del CRM tal cual. '(Sin motivo registrado)' = descarte sin explicación. Clic en una fila = filtrar por ese motivo.">📋 ¿Por qué se descartan? (motivo registrado)</h3><table><tbody id="dsc-mot"></tbody></table></div>
<div><h3 style="font-size:13.5px;margin:6px 0 4px" data-tip="Usuario asignado al lead descartado. MARKETING PFS = descartado por la automatización, no por una persona. Clic = filtrar por ese asesor.">👤 ¿Quién los descarta?</h3><table><tbody id="dsc-asg"></tbody></table></div>
<div><h3 style="font-size:13.5px;margin:6px 0 4px" data-tip="De cada fuente, qué % de sus leads terminó descartado (solo fuentes con 100+ leads en la selección de fechas). Alto = esa fuente trae leads que no sirven… o que no se gestionan. Clic = filtrar por esa fuente.">📣 Tasa de descarte por fuente</h3><table><tbody id="dsc-fu"></tbody></table></div>
<div><h3 style="font-size:13.5px;margin:6px 0 4px" data-tip="Interacciones registradas (nº de contactos + actividades de venta) ANTES del descarte. 0 = se descartó sin una sola gestión: descarte temprano.">📞 ¿Cuánta gestión recibieron antes del descarte?</h3><table><tbody id="dsc-ges"></tbody></table></div>
</div>
<div id="dsc-learn" class="caveat"></div>
</div>

<div class="chart-sec">
<h2>📄 Leads descartados de la selección</h2>
<p class="chart-sub">Ordenados por score (los descartes más "vivos" primero: son los candidatos a rescate). La columna Interacciones dice cuánta gestión recibió el lead antes de descartarse.</p>
<div id="ltab" style="overflow-x:auto"></div>
</div>

<div class="warnpii"><b>⚠ Datos personales:</b> este archivo contiene nombres, correos y teléfonos de personas de la base del CRM (Habeas Data). No publicarlo ni circularlo fuera del equipo comercial autorizado.</div>
<footer>Universo: los {fmt(N_DESC)} contactos con Lead Status = "Descartado" del CRM ({fmt(TOTAL)} contactos totales al corte). Motivo = campo "Motivo de descarte" tal cual (se unifica el typo "No caliifica" → "No califica"; vacío o N/A = "(Sin motivo registrado)"). Quién descarta = usuario asignado (assignedTo) al momento del corte. Interacciones = nº de veces contactado + actividades de venta registradas en el CRM. Rescatable = descartado con lead score ≥30 (misma fórmula 0-100 del home) o con "En curso por" = Oportunidad vigente. La tasa por fuente usa como denominador TODOS los leads de esa fuente dentro del rango de fechas. Generado desde la API de GHL, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fmtN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
// búsqueda tolerante: texto en nombre/email y, si lo escrito tiene dígitos, compara solo dígitos contra el teléfono
// (así '(786) 932-6512', '786 932 6512' o '7869326512' encuentran +17869326512)
function matchQ(q, nombre, email, tel) {{
  if (!q) return true;
  if ((nombre + ' ' + email + ' ' + tel).toLowerCase().includes(q)) return true;
  const qd = q.replace(/[^0-9]/g, '');
  return qd.length >= 4 && (tel || '').replace(/[^0-9]/g, '').includes(qd);
}}
const scoreCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
const tempTxt = sc => sc >= 55 ? 'Caliente' : sc >= 30 ? 'Tibio' : sc >= 10 ? 'Frío' : 'Sin señales';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';
const ST_D = D.status.indexOf('Descartado');
const PAGE = 200;
let MODE = '', shown = PAGE;

function fill(id, items, labels) {{
  document.getElementById(id).innerHTML = '<option value="">Todos</option>' +
    items.map((v, i) => `<option value="${{v}}">${{esc(labels[i])}}</option>`).join('');
}}
fill('f-a', D.asesorOrden, D.asesorOrden.map(i => D.asesores[i]));
fill('f-m', D.motivoOrden, D.motivoOrden.map(i => D.motivos[i]));
fill('f-f', D.fuenteOrden, D.fuenteOrden.map(i => D.fuentes[i]));
fill('f-k', D.cursoOrden, D.cursoOrden.map(i => D.cursos[i]));
fill('f-r', D.realtorOrden, D.realtorOrden.map(i => D.realtors[i]));

/* tooltip global que sigue al cursor */
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

const inFecha = x => {{
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  return (d1 === '' || (x[8] && x[8] >= d1)) && (d2 === '' || (x[8] && x[8] <= d2));
}};
/* base = TODA la base (cualquier status) con los filtros comunes: denominador de la tasa */
function baseSel() {{
  const g = id => document.getElementById(id).value;
  const a = g('f-a'), f = g('f-f'), k = g('f-k'), r = g('f-r'), q = g('f-q').trim().toLowerCase();
  return D.rows.filter(x =>
    (a === '' || x[3] == a || (x[14] && x[14].indexOf(+a) !== -1)) && (f === '' || x[7] == f) && (k === '' || x[5] == k) &&
    (r === '' || x[6] == r) && inFecha(x) &&
    matchQ(q, x[0], x[1], x[2]));
}}
const esRescatable = x => x[9] >= 30 || D.cursos[x[5]].startsWith('Oportunidad');
const matchMode = x =>
  MODE === '' ? true :
  MODE === 'sg' ? x[11] === 0 :
  MODE === 'resc' ? esRescatable(x) :
  MODE === 'sm' ? D.motivos[x[12]] === '(Sin motivo registrado)' :
  MODE === 'cd' ? (x[1] !== '' || x[2] !== '') : true;

let base = [], desc = [], view = [];
function apply() {{
  base = baseSel();
  const m = document.getElementById('f-m').value;
  desc = base.filter(x => x[4] === ST_D && (m === '' || x[12] == m));
  view = desc.filter(matchMode).slice().sort((x, y) => y[9] - x[9]);
  shown = PAGE;
  renderKpis(); renderPies(); renderDist(); renderLearn(); renderTabla();
  const MN = {{sg: 'sin una sola gestión', resc: 'rescatables', sm: 'sin motivo registrado', cd: 'con email o teléfono'}};
  document.getElementById('resumen').textContent =
    `${{fmtN(view.length)}} descartados en la vista` +
    (MODE ? ` · recorte: ${{MN[MODE]}}` : '') +
    ` · de ${{fmtN(base.length)}} leads de la selección.`;
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
    svg.innerHTML = `<text x="170" y="115" text-anchor="middle" font-size="13" fill="#5B6B85">Sin descartados en la selección actual</text>`;
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
  leg.innerHTML = data.filter(d => d.val).map(d =>
    `<span class="li" data-i="${{data.indexOf(d)}}" data-tip="${{esc(d.tip)}}"><span class="dot" style="background:${{d.color}}"></span>${{esc(d.label)}}: <b>${{fmtN(d.val)}}</b></span>`).join('');
  const act = el => {{ const d = data[+el.dataset.i]; if (d && d.click) d.click(); }};
  svg.querySelectorAll('.pslice').forEach(el => el.addEventListener('click', () => act(el)));
  leg.querySelectorAll('.li').forEach(el => el.addEventListener('click', () => act(el)));
}}
const PIE_COL = ['#D64545', '#3A566B', '#C4B284', '#1E9E62', '#8A6D1A', '#5A6B78', '#C47845', '#8A99A8'];
function pieDe(svgId, legId, col, nombres, selId, titulo) {{
  const cnt = new Map();
  desc.forEach(x => cnt.set(x[col], (cnt.get(x[col]) || 0) + 1));
  const top = [...cnt.entries()].sort((a, b) => b[1] - a[1]);
  const datos = top.slice(0, 7).map(([i, c], j) => ({{
    label: nombres[i], val: c, color: PIE_COL[j],
    tip: `${{nombres[i]}}: ${{fmtN(c)}} descartados (${{(c / desc.length * 100).toFixed(0)}}% de la selección). Clic para aplicar/quitar el filtro de ${{titulo}}.`,
    click: () => {{
      const sel = document.getElementById(selId);
      sel.value = sel.value == i ? '' : i;
      apply();
    }}
  }}));
  const resto = top.slice(7).reduce((t, [, c]) => t + c, 0);
  if (resto) datos.push({{label: 'Otros', val: resto, color: '#C9D6E4',
    tip: `Otros ${{top.length - 7}} valores: ${{fmtN(resto)}} descartados.`, click: null}});
  drawPie(svgId, legId, datos, 'descartados');
}}
function renderPies() {{
  pieDe('pie-fu', 'pleg-fu', 7, D.fuentes, 'f-f', 'fuente');
  pieDe('pie-asg', 'pleg-asg', 3, D.asesores, 'f-a', 'asesor');
}}

function renderKpis() {{
  const n = desc.length;
  const sinGestion = desc.filter(x => x[11] === 0).length;
  const rescat = desc.filter(esRescatable).length;
  const sinMotivo = desc.filter(x => D.motivos[x[12]] === '(Sin motivo registrado)').length;
  const conDatos = desc.filter(x => x[1] !== '' || x[2] !== '').length;
  const kp = (mode, val, lbl, tip, color) =>
    `<div class="kpi ${{mode ? 'clkd' : ''}} ${{mode && MODE === mode ? 'on' : ''}}" ${{mode ? `data-mode="${{mode}}"` : ''}} data-tip="${{esc(tip)}}${{mode ? ' Clic para ver solo esos leads en la tabla (otro clic lo quita).' : ''}}"><b style="color:${{color || 'var(--tinta)'}}">${{val}}</b><span>${{lbl}}</span></div>`;
  document.getElementById('dsc-kpis').innerHTML =
    kp('', fmtN(n), 'descartados en la selección', 'Leads con Lead Status = Descartado dentro de los filtros activos.') +
    kp('', base.length ? (n / base.length * 100).toFixed(0).replace('.', ',') + '%' : '—', 'tasa de descarte', 'Descartados ÷ leads de la selección (todos los status): qué proporción de lo captado se está botando.') +
    kp('sg', fmtN(sinGestion) + ` <small style="font-size:12px">(${{n ? (sinGestion / n * 100).toFixed(0) : 0}}%)</small>`, 'sin UNA sola gestión', 'Descartados con CERO interacciones registradas: descartes tempranos — se botaron sin trabajarlos.', 'var(--rojo)') +
    kp('resc', fmtN(rescat), 'rescatables (señal viva)', 'Descartados con score ≥30 u oportunidad de compra vigente registrada: contradicciones que merecen segunda mirada.', 'var(--verde)') +
    kp('sm', fmtN(sinMotivo) + ` <small style="font-size:12px">(${{n ? (sinMotivo / n * 100).toFixed(0) : 0}}%)</small>`, 'sin motivo registrado', 'Descartes sin explicación en el campo Motivo de descarte: no dejan aprendizaje.', '#8A6D1A') +
    kp('cd', fmtN(conDatos), 'con email o teléfono', 'Descartados contactables: materia prima para una campaña de rescate de bajo costo.');
  document.querySelectorAll('#dsc-kpis .kpi.clkd').forEach(el => el.addEventListener('click', () => {{
    MODE = MODE === el.dataset.mode ? '' : el.dataset.mode;
    apply();
    document.getElementById('ltab').scrollIntoView({{behavior: 'smooth'}});
  }}));
}}

function renderDist() {{
  const n = desc.length;
  const fila = (label, cnt, tot, sel, val, tip, color) =>
    `<tr class="clkd" data-sel="${{sel}}" data-val="${{val}}" data-tip="${{esc(tip)}}"><td style="white-space:nowrap">${{esc(label).slice(0, 36)}}</td>
    <td style="width:42%"><div class="bar"><div style="width:${{Math.max(2, cnt / (tot || 1) * 100)}}%;background:${{color}}"></div></div></td>
    <td style="white-space:nowrap">${{fmtN(cnt)}}${{tot ? ' · ' + (cnt / tot * 100).toFixed(0) + '%' : ''}}</td></tr>`;
  const mm = new Map();
  desc.forEach(x => mm.set(x[12], (mm.get(x[12]) || 0) + 1));
  document.getElementById('dsc-mot').innerHTML = [...mm.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)
    .map(([i, c]) => fila(D.motivos[i], c, n, 'f-m', i, `${{D.motivos[i]}}: ${{fmtN(c)}} descartes (${{n ? (c / n * 100).toFixed(0) : 0}}%). Clic para filtrar por este motivo.`, '#D64545')).join('');
  const am = new Map();
  desc.forEach(x => am.set(x[3], (am.get(x[3]) || 0) + 1));
  document.getElementById('dsc-asg').innerHTML = [...am.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)
    .map(([i, c]) => {{
      const sg = desc.filter(x => x[3] === i && x[11] === 0).length;
      return fila(D.asesores[i], c, n, 'f-a', i, `${{D.asesores[i]}}: ${{fmtN(c)}} descartes, ${{fmtN(sg)}} sin ninguna gestión. Clic para filtrar por este asesor.`, '#3A566B');
    }}).join('');
  const fb = new Map(), fd = new Map();
  base.forEach(x => fb.set(x[7], (fb.get(x[7]) || 0) + 1));
  desc.forEach(x => fd.set(x[7], (fd.get(x[7]) || 0) + 1));
  document.getElementById('dsc-fu').innerHTML = [...fd.entries()]
    .filter(([i]) => (fb.get(i) || 0) >= 100)
    .map(([i, c]) => [i, c, c / fb.get(i) * 100]).sort((a, b) => b[2] - a[2]).slice(0, 10)
    .map(([i, c, r]) => `<tr class="clkd" data-sel="f-f" data-val="${{i}}" data-tip="${{esc(D.fuentes[i])}}: ${{fmtN(c)}} descartados de ${{fmtN(fb.get(i))}} leads de esa fuente (${{r.toFixed(0)}}%). Clic para filtrar por esta fuente."><td style="white-space:nowrap">${{esc(D.fuentes[i]).slice(0, 30)}}</td>
      <td style="width:42%"><div class="bar"><div style="width:${{Math.min(100, Math.max(2, r * 2.2))}}%;background:#AA9664"></div></div></td>
      <td style="white-space:nowrap">${{r.toFixed(0).replace('.', ',')}}% <small style="color:var(--gris)">(${{fmtN(c)}})</small></td></tr>`).join('');
  const buckets = [['0 interacciones', x => x[11] === 0], ['1', x => x[11] === 1], ['2', x => x[11] === 2],
                   ['3-5', x => x[11] >= 3 && x[11] <= 5], ['6 o más', x => x[11] >= 6]];
  document.getElementById('dsc-ges').innerHTML = buckets.map(([l, f]) => {{
    const c = desc.filter(f).length;
    return `<tr data-tip="${{fmtN(c)}} descartados con ${{l}} registradas antes del descarte."><td style="white-space:nowrap">${{l}}</td>
    <td style="width:42%"><div class="bar"><div style="width:${{Math.max(2, c / (n || 1) * 100)}}%;background:#8A99A8"></div></div></td>
    <td style="white-space:nowrap">${{fmtN(c)}}${{n ? ' · ' + (c / n * 100).toFixed(0) + '%' : ''}}</td></tr>`;
  }}).join('');
  document.querySelectorAll('#dsc-mot .clkd, #dsc-asg .clkd, #dsc-fu .clkd').forEach(el =>
    el.addEventListener('click', () => {{
      const sel = document.getElementById(el.dataset.sel);
      sel.value = sel.value === el.dataset.val ? '' : el.dataset.val;
      apply();
      document.getElementById('ltab').scrollIntoView({{behavior: 'smooth'}});
    }}));
}}

function renderLearn() {{
  const n = desc.length;
  if (!n) {{ document.getElementById('dsc-learn').innerHTML = '<b>Sin descartados en la selección actual.</b>'; return; }}
  const sinGestion = desc.filter(x => x[11] === 0).length;
  const rescat = desc.filter(esRescatable).length;
  const sinMotivo = desc.filter(x => D.motivos[x[12]] === '(Sin motivo registrado)').length;
  const mkt = desc.filter(x => D.asesores[x[3]] === 'MARKETING PFS').length;
  const noInt0 = desc.filter(x => D.motivos[x[12]] === 'No interesado' && x[11] === 0).length;
  const nunca = desc.filter(x => D.motivos[x[12]] === 'Nunca contestó').length;
  const invalido = desc.filter(x => D.motivos[x[12]] === 'Numero/email invalido').length;
  const eliminar = desc.filter(x => D.motivos[x[12]] === 'Desea ser eliminado de la base de datos').length;
  document.getElementById('dsc-learn').innerHTML = `<b>🎓 Qué aprender de estos descartes (selección actual):</b><ul style="padding-left:20px;margin:6px 0">
  <li><b>${{(sinGestion / n * 100).toFixed(0)}}% son descartes tempranos:</b> ${{fmtN(sinGestion)}} leads botados con CERO gestión registrada — no fueron rechazados por el cliente, fueron abandonados por el proceso. ${{fmtN(mkt)}} de los descartes (${{(mkt / n * 100).toFixed(0)}}%) los ejecuta la automatización MARKETING PFS, no un asesor que haya hablado con el lead.</li>
  <li><b>El "No interesado" es sospechoso:</b> ${{fmtN(noInt0)}} leads marcados "No interesado" tienen 0 interacciones — ¿no interesado según quién, si nadie habló con ellos? Regla sugerida: ese motivo solo debería poder marcarse con al menos 1 gestión registrada.</li>
  <li><b>"Nunca contestó" (${{fmtN(nunca)}}) + "Número inválido" (${{fmtN(invalido)}}) son problemas de velocidad y datos, no de interés:</b> se atacan con SLA de primera respuesta y validación del teléfono en el formulario — no descartando.</li>
  <li><b>${{fmtN(rescat)}} rescatables:</b> descartados con score ≥30 u oportunidad vigente. Revisión gerencial de una tarde; recuperar 2-3 paga el ejercicio.</li>
  <li><b>${{fmtN(sinMotivo)}} sin motivo (${{(sinMotivo / n * 100).toFixed(0)}}%):</b> hacer obligatorio el motivo al descartar — sin motivo no hay aprendizaje ni mejora del proceso.</li>
  <li><b>${{fmtN(eliminar)}} pidieron ser eliminados:</b> lista de supresión permanente YA (hoy el workflow "Asignar Descartados a MARKETING PFS" puede devolverlos al goteo — riesgo legal de Habeas Data).</li></ul>`;
}}

function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tags[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas del lead en el CRM: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
function scTip(r, d, fl, sc, st) {{
  if (!d || d.length !== 4) return '';
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
  const e4 = d[3] >= 20 ? 'tuvo actividad esta última semana' : d[3] >= 15 ? 'tuvo actividad en el último mes'
           : d[3] >= 8 ? 'su última actividad fue hace 1 a 3 meses' : d[3] >= 4 ? 'su última actividad fue hace 3 a 6 meses'
           : 'lleva más de 6 meses sin ninguna actividad';
  return `Este lead tiene ${{sc}} de 100 puntos por estas 4 razones: ① GANAS DE COMPRAR: ${{d[0]}} de 35 pts — ${{e1}}. ② ETAPA EN EL CRM: ${{d[1]}} de 25 pts — su lead status es «${{st}}». ③ RESPUESTAS DEL LEAD: ${{d[2]}} de 20 pts — ${{e3}}. ④ ACTIVIDAD RECIENTE: ${{d[3]}} de 20 pts — ${{e4}}.`;
}}
const FLGV = {{P: '🏠', M: '💰', C: '🛒', R: '✋', Z: '⏸'}};
function opCellG(o) {{
  if (!o) return '<span style="color:#B9BDCC" data-tip="Este lead NO tiene oportunidad creada en el pipeline de ventas: nunca ha entrado al embudo comercial.">—</span>';
  const col = o[1] === 'abierta' ? '#1D7A46' : o[1] === 'ganada' ? '#0F6E56' : '#A33B3B';
  return `<span style="white-space:nowrap;cursor:help" data-tip="Tiene OPORTUNIDAD en el pipeline de ventas: etapa «${{esc(D.opps[o[0]])}}» (${{esc(o[1])}}). Último cambio de etapa: ${{esc(o[2] || 'sin fecha')}}."><b>${{esc(D.opps[o[0]])}}</b><small style="display:block;color:${{col}};font-size:.68rem">${{esc(o[1])}} · ${{esc(o[2] || '')}}</small></span>`;
}}
function tareasG(d, fl, sc, intTot) {{
  d = d && d.length === 4 ? d : [0, 0, 0, 0]; fl = fl || ''; const t = [];
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
  return t.slice(0, 3).map(x => `<small style="display:block;white-space:nowrap;cursor:help" data-tip="${{esc(x[2])}}">${{x[0]}} ${{esc(x[1])}}</small>`).join('');
}}
function waBtn(dig) {{
  return dig ? `<a href="https://wa.me/${{dig}}" target="_blank" style="display:inline-block;background:#25D366;color:#fff;border-radius:8px;padding:4px 9px;white-space:nowrap;font-size:.74rem;font-weight:700;text-decoration:none" data-tip="Escribirle directamente por WhatsApp (abre wa.me con su número).">💬 WhatsApp</a>` : '<span style="color:#B9BDCC">—</span>';
}}
function renderTabla() {{
  const ls = view.slice(0, shown);
  const filas = ls.map(r => {{
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = (r[2] || '').replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a> · <a href="https://wa.me/${{dig}}" target="_blank">WA</a>` : '—';
    const sTip = scTip(r, r[16], r[15] || '', r[9], D.status[r[4]]);
    const flgs = (r[15] || '').split('').map(ch => FLGV[ch] || '').join('');
    return `<tr><td style="white-space:nowrap${{sTip ? ';cursor:help' : ''}}"${{sTip ? ` data-tip="${{sTip}}"` : ''}}><span class="sc" style="background:${{scoreCol(r[9])}}">${{r[9]}}</span> <small style="color:${{scoreCol(r[9])}};font-weight:700">${{tempTxt(r[9])}}</small> ${{flgs}}</td>
      <td><b>${{esc(r[0])}}</b></td>
      <td><span class="mchip">${{esc(D.motivos[r[12]])}}</span></td>
      <td>${{esc(D.asesores[r[3]])}}</td>
      <td style="text-align:center">${{fmtN(r[11])}}</td>
      <td style="white-space:nowrap" data-tip="${{intTip(r[13])}}">${{intCell(r[13])}}</td><td data-tip="${{intTip(r[13])}}">${{canCell(r[13])}}</td>
      <td>${{em}}</td><td>${{ph}}</td>
      <td>${{esc(D.fuentes[r[7]])}}</td><td>${{esc(D.cursos[r[5]])}}</td>
      <td>${{opCellG(r[17])}}</td>
      <td>${{esc(D.realtors[r[6]])}}</td><td>${{esc(r[8] || '—')}}</td>
      <td>${{tareasG(r[16], r[15], r[9], (r[13] && r[13][0]) || 0)}}</td>
      <td>${{tagsCell(r[10])}}</td><td>${{waBtn(dig)}}</td></tr>`;
  }}).join('');
  document.getElementById('ltab').innerHTML =
    `<table style="min-width:1150px"><thead><tr>
     <th data-tip="Lead scoring v2 0-100 (misma fórmula del home). PASA EL MOUSE sobre el score de cada lead para ver POR QUÉ tiene esos puntos. En descartados, un score alto = señal viva pese al descarte: candidato a rescate. Flags: 🏠 propiedad específica (MLS) · 💰 monto · 🛒 compra · ✋ respondió · ⏸ aplazado.">Score</th>
     <th data-tip="Nombre del contacto tal como está en el CRM.">Contacto</th>
     <th data-tip="Campo 'Motivo de descarte' del CRM. '(Sin motivo registrado)' = descarte sin explicación.">Motivo de descarte</th>
     <th data-tip="Usuario asignado al lead: quien lo descartó o lo tenía al descartarse. MARKETING PFS = automatización.">Quién lo descartó</th>
     <th data-tip="Interacciones registradas antes del descarte (nº de contactos + actividades de venta). 0 = descarte temprano sin gestión.">Interac.</th>
     <th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
     <th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
     <th data-tip="Correo del contacto; el enlace abre tu cliente de correo.">Email</th>
     <th data-tip="Teléfono del contacto; 'WA' abre el chat de WhatsApp.">Teléfono</th>
     <th data-tip="Origen del lead: campo 'Fuente de contacto' del CRM con las familias agrupadas.">Origen</th>
     <th data-tip="Campo 'En curso por': si dice 'Oportunidad …' el lead tenía horizonte de compra vigente — contradicción con el descarte.">En curso por</th>
     <th data-tip="Si el lead tiene OPORTUNIDAD en el pipeline de ventas y en qué etapa quedó, con su estado y fecha del último cambio. '—' = nunca entró al pipeline.">Etapa de oportunidad</th>
     <th data-tip="Realtor vinculado al contacto.">Realtor</th>
     <th data-tip="Fecha de creación del lead en el CRM (dateAdded).">Creado</th>
     <th data-tip="Las principales acciones para RESCATAR/CERRAR este lead, según su diagnóstico de score. Pasa el mouse para el detalle.">Acciones para cerrar venta</th>
     <th data-tip="Etiquetas del contacto en el CRM. Se muestran 2; el chip +N muestra el resto al pasar el mouse.">Etiquetas</th>
     <th data-tip="Escribirle directamente por WhatsApp.">WA</th>
     </tr></thead><tbody>${{filas}}</tbody></table>` +
    (shown < view.length ? `<button class="btn sec more" onclick="masFilas()">Mostrar ${{fmtN(Math.min(PAGE, view.length - shown))}} más (${{fmtN(view.length - shown)}} restantes)</button>` : '') +
    (view.length === 0 ? '<p style="color:var(--gris);margin:14px 0">Sin leads descartados con los filtros actuales.</p>' : '');
}}
function masFilas() {{ shown += PAGE; renderTabla(); }}

/* ---------- generador XLSX nativo (zip STORE + SpreadsheetML) ---------- */
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
  const out = [['Score', 'Temperatura', 'Contacto', 'Motivo de descarte', 'Quien lo descarto', 'Interacciones',
                'Email', 'Telefono', 'Origen', 'En curso por', 'Realtor', 'Creado', 'Intentos', 'Dias de intento', 'Canales', 'Etiquetas']];
  view.forEach(r => out.push([r[9], tempTxt(r[9]), r[0], D.motivos[r[12]], D.asesores[r[3]], r[11],
    r[1], r[2], D.fuentes[r[7]], D.cursos[r[5]], D.realtors[r[6]], r[8],
    r[13] ? r[13][0] : 0, r[13] ? r[13][1] : 0, canTxt(r[13]),
    (r[10] || []).map(i => D.tags[i]).join(' | ')]));
  XL('leads-descartados-filtrado.xlsx', out);
}}

['f-a', 'f-m', 'f-f', 'f-k', 'f-r', 'f-d1', 'f-d2'].forEach(id =>
  document.getElementById(id).addEventListener('change', apply));
document.getElementById('f-q').addEventListener('input', apply);
function reset() {{
  ['f-a', 'f-m', 'f-f', 'f-k', 'f-r', 'f-d1', 'f-d2'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-q').value = '';
  MODE = '';
  apply();
}}
/* arranque limpio: el navegador restaura valores de formulario entre visitas */
function arranque() {{ reset(); }}
arranque();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranque(); }});
setTimeout(() => {{
  const alguno = ['f-a', 'f-m', 'f-f', 'f-k', 'f-r', 'f-q', 'f-d1', 'f-d2'].some(id => document.getElementById(id).value !== '');
  if (alguno) arranque();
}}, 250);
</script>
</body></html>'''

out = str(ROOT / f'descartados-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print(f'descartados: {N_DESC} de {TOTAL} ({N_DESC/TOTAL*100:.1f}%) | sin gestion: {sum(1 for r in DESC if r[11]==0)} | motivos: {len(motivo_vol)}')
