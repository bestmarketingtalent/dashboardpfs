#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de ADQUISICIÓN DE LEADS: análisis completo por medio/fuente — volumen y
momentum de llegada, calidad (conversión a cliente, descarte, temperatura, gestión
recibida), campañas detectadas por etiqueta, atribución digital (UTM/gclid) y
mercados por país. HTML autocontenido, misma lógica del resto del dashboard.
Lee scripts/data/{contacts,users,gestion,wa_all_msgs}.json (solo consulta)."""
import json, html
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

contacts = json.load(open(DATA / 'contacts.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW   = datetime.now(timezone.utc)
_hoy  = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

# ---------- fuente (mismas familias de todo el dashboard) ----------
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
        return 'Google / Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl or sl in ('rerefido', 'referral', 'pereonal', 'personall'):
        return 'Referidos / Personal'
    if sl.startswith('prensa'):
        return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'):
        return 'Sitio Web'
    return CANON[sl]

# ---------- score (misma fórmula 0-100) ----------
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

# ---------- país por prefijo del móvil ----------
PA = sorted([('57','Colombia'),('52','México'),('51','Perú'),('593','Ecuador'),('58','Venezuela'),
             ('34','España'),('56','Chile'),('54','Argentina'),('507','Panamá'),('506','Costa Rica'),
             ('502','Guatemala'),('55','Brasil'),('598','Uruguay'),('591','Bolivia'),('53','Cuba'),
             ('504','Honduras'),('503','El Salvador'),('595','Paraguay'),('1','EE.UU. / Canadá')],
            key=lambda x: -len(x[0]))
def pais_of(ph):
    if not ph or not ph.startswith('+'): return 'Sin teléfono'
    for pre, nm in PA:
        if ph[1:].startswith(pre): return nm
    return 'Otros países'

# ---------- 1ª atención (primer msj saliente de WhatsApp) ----------
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
_WA_OUTD = {}
for _cv in _wa_all:
    _cidw = _cv.get('contactId')
    if not _cidw or not _cv.get('msgs'): continue
    _fs = [(_m[1] or '')[:10] for _m in _cv['msgs'] if _m[0] == 0 and _m[1]]
    if _fs:
        _WA_OUTD.setdefault(_cidw, []).extend(_fs)

def intentos_of(_cid):
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

# ---------- contactabilidad: el lead RESPONDIÓ (msj entrante WA o llamada contestada) ----------
INB_WA = set()
for _cv in _wa_all:
    if _cv.get('contactId') and any(_m[0] == 1 for _m in (_cv.get('msgs') or [])):
        INB_WA.add(_cv['contactId'])

def respondio(c):
    if c['id'] in INB_WA: return 1
    _g = _GEST_INT.get(c['id'])
    if _g and (_g['c'][1] > 0 or _g['c'][2] > 0): return 1
    return 0

# ---------- categoría de medios (drill-down de la tabla maestra) ----------
CAT_ORDER = ['Pauta digital', 'Orgánico digital', 'Eventos', 'Referidos y aliados',
             'Equipo comercial', 'Importaciones / listas', 'Otros medios', 'Sin fuente registrada']
def categoria_of(f):
    fl = f.lower()
    if f == '(Sin fuente)': return 'Sin fuente registrada'
    if 'hubspot' in fl or 'migration' in fl or 'importa' in fl: return 'Importaciones / listas'
    if 'referid' in fl or 'personal' in fl or 'aliado' in fl: return 'Referidos y aliados'
    if fl in ('antonio aguirre', 'pfs guardia'): return 'Equipo comercial'
    if any(k in fl for k in ('evento', 'celebra', 'simposio', 'torneo', 'master class', 'mundial',
                             'concurso', 'cóctel', 'coctel', 'c�ctel', 'ágora', 'agora', 'amcham',
                             'cotelco', 'club lagos', 'campestre', 'salto', 'webinar', 'jornada', 'feria')):
        return 'Eventos'
    if any(k in fl for k in ('facebook', 'google', 'paid', 'instagram', 'tiktok', 'digital',
                             'zillow', 'ihomefinder', 'wivboost', 'meta', 'markdpa')):
        return 'Pauta digital'
    if any(k in fl for k in ('sitio web', 'web', 'blog', 'email', 'linkedin', 'linked in', 'prensa',
                             'whatsapp', 'organic', 'orgánic', 'form', 'pfsmain', 'medios alternos', 'miami', 'brickell', 'kendall')):
        return 'Orgánico digital'
    return 'Otros medios'

# ---------- filas ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DF, giF = dict_indexer()
DP, giP = dict_indexer()
DS, giS = dict_indexer()
DK, giK = dict_indexer()
DA, giA = dict_indexer()
DR, giR = dict_indexer()
DT, giT = dict_indexer()
DAT, giAT = dict_indexer()
DC, giC = dict_indexer()
for _c2 in CAT_ORDER: giC(_c2)
for s in STATUS_ORDER: giS(s)
for k in CURSO_ORDER:  giK(k)

rows = []
for c in contacts:
    a = USERS.get(c['assigned'], '(Sin asesor asignado)') if c['assigned'] else '(Sin asesor asignado)'
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    if st not in STATUS_ORDER: st = '(Sin status)'
    ku = (c.get('enCursoPor') or '').strip() or '(Sin dato)'
    if ku not in CURSO_ORDER: ku = '(Sin dato)'
    rl = c.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(r.strip() for r in rl if r and r.strip()) or '(Sin realtor)'
    at = c.get('attr') or {}
    at_lbl = (f"{at.get('sessionSource', '(sin sesión)')} · {at.get('medium', 'sin medio')}"
              if at else '(Sin atribución digital)')
    rows.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c['email'] or '', c['phone'] or '',
        giF(fuente_of(c)), giP(pais_of(c.get('phone') or '')),
        giS(st), giK(ku), score_of(c), (c['created'] or '')[:10],
        giA(a),
        num(c.get('vecesContactado')) + num(c.get('salesActivities')),
        atn_of(c),
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        intentos_of(c['id']),
        giR(rl), giAT(at_lbl),
        respondio(c), giC(categoria_of(fuente_of(c)))
    ])

TOTAL = len(rows)
def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
fuente_vol = Counter(r[3] for r in rows)
pais_vol   = Counter(r[4] for r in rows)

ATTR_COV = {
    'conAttr': sum(1 for c in contacts if c.get('attr')),
    'gclid':   sum(1 for c in contacts if (c.get('attr') or {}).get('gclid')),
    'fbclid':  sum(1 for c in contacts if (c.get('attr') or {}).get('fbclid')),
    'utm':     sum(1 for c in contacts if (c.get('attr') or {}).get('utmCampaign')),
    'adName':  sum(1 for c in contacts if (c.get('attr') or {}).get('adName')),
}

PAYLOAD = json.dumps({
    'rows': rows,
    'fuentes': ordered(DF), 'paises': ordered(DP), 'status': ordered(DS),
    'cursos': ordered(DK), 'asesores': ordered(DA), 'realtors': ordered(DR),
    'tags': ordered(DT), 'attrs': ordered(DAT), 'cats': ordered(DC),
    'fuenteOrden': [i for i, _ in fuente_vol.most_common()],
    'paisOrden':   [i for i, _ in pais_vol.most_common()],
    'attrCov': ATTR_COV,
}, ensure_ascii=False)

def fmt(n): return f'{n:,}'.replace(',', '.')

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adquisición de leads</title>
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
.pies{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
.pie-box h3{{font-size:13.5px;margin:4px 0 2px}}
.pie-box svg{{width:100%;height:auto;display:block}}
.pleg{{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12.2px;margin-top:4px}}
.pleg .li{{cursor:pointer;user-select:none}} .pleg .li:hover{{text-decoration:underline}}
.pleg .dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.pslice{{cursor:pointer}} .pslice:hover{{opacity:.82}}
#scat-wrap{{position:relative}}
#scat{{width:100%;height:auto;display:block}}
#scat-tip{{position:absolute;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:9px 11px;border-radius:8px;font-size:11.8px;line-height:1.5;max-width:280px;pointer-events:none;z-index:40;box-shadow:0 6px 18px rgba(7,32,49,.28)}}
#scat-interp{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.9px;margin:12px 0 12px;line-height:1.55}}
#scat-interp h3{{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);margin-bottom:6px}}
#scat-interp ul{{margin:0;padding-left:18px}}
#scat-interp li{{margin:4px 0}}
#scat-top{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:3px 22px;font-size:12.3px;margin:10px 2px 6px}}
#scat-top div{{display:flex;gap:8px;align-items:baseline;border-bottom:1px dashed var(--gris-linea);padding:3px 0}}
#scat-top .rk{{color:var(--gris);font-weight:700;min-width:18px}}
#scat-top .pc{{margin-left:auto;font-weight:800;color:var(--azul)}}
.dot{{fill:#3A566B;fill-opacity:.45;stroke:#3A566B;stroke-width:1.5;cursor:pointer}}
.dot:hover{{fill-opacity:.85}}
.ckp{{display:inline-flex;align-items:center;gap:5px;border:1.5px solid var(--gris-linea);border-radius:18px;padding:4px 10px;cursor:pointer;user-select:none;font-weight:600;color:var(--gris);background:#fff}}
.ckp input{{accent-color:var(--azul);margin:0}}
.ckp.on{{border-color:var(--azul);color:var(--azul);background:var(--azul-suave)}}
.chart-ctrl{{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:6px;font-size:12px}}
.chart-ctrl b{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris)}}
.chart-ctrl select{{border:1.5px solid var(--gris-linea);border-radius:8px;padding:4px 8px;font-size:12px;background:#fff;color:var(--tinta)}}
.chart-sec{{border:1px solid var(--gris-linea);border-radius:13px;padding:16px 16px 12px;margin:4px 0 20px}}
.chart-sec h2{{font-size:15.5px;margin-bottom:2px}}
.chart-sub{{font-size:12px;color:var(--gris);margin-bottom:10px}}
table{{border-collapse:collapse;width:100%;font-size:12.8px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.clkd{{cursor:pointer}} tr.clkd:hover td{{background:var(--azul-suave)}}
.bar{{background:var(--gris-fondo);border-radius:6px;height:14px;overflow:hidden}}
.bar div{{height:100%;border-radius:6px}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
a{{color:var(--azul)}}
.caveat{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.8px;margin-top:12px}}
.alerta{{background:#FBF6E7;border:1px solid #E4D5A9;border-radius:11px;padding:12px 16px;font-size:12.8px;margin-top:12px}}
.more{{margin:8px 0}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Adquisición de leads</h1>
<p>CRM comercial (solo lectura) · Qué medios traen leads, cuáles convierten y cuáles se botan · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(TOTAL)}</b><span>leads adquiridos en el CRM</span></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html" class="act"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="filters">
<div><label data-tip="Filtra por la categoría de medios: pauta digital, orgánico digital, eventos, referidos y aliados, equipo comercial, importaciones. Cada fuente pertenece a una categoría (ver la tabla maestra).">Categoría de medios</label><select id="f-c" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el medio/fuente del lead: campo 'Fuente de contacto' del CRM con las variantes de Google, Referidos, Prensa y Sitio Web agrupadas. Ordenado por volumen.">Medio / fuente</label><select id="f-f" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el país del lead, determinado por el prefijo internacional de su número móvil.">País (prefijo del móvil)</label><select id="f-p" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Lead Status' del CRM: en qué quedó el lead adquirido (Cliente, Descartado, En curso…).">Lead status</label><select id="f-s" autocomplete="off"></select></div>
<div><label data-tip="Filtra por temperatura del lead scoring 0-100: Caliente ≥55, Tibio 30-54, Frío 10-29, Sin señales <10.">Scoring (temperatura)</label><select id="f-t" autocomplete="off">
<option value="">Todos</option>
<option value="hot">🔥 Calientes (≥55)</option>
<option value="warm">🌤 Tibios (30-54)</option>
<option value="cold">❄ Fríos (10-29)</option>
<option value="none">Sin señales (&lt;10)</option></select></div>
<div><label data-tip="Busca texto libre dentro del nombre, el email y el teléfono.">Buscar (nombre, email, teléfono)</label><input id="f-q" autocomplete="off" placeholder="Escribe para filtrar…"></div>
<div><label data-tip="Fecha de creación del lead (dateAdded) desde, inclusive. Afecta TODO: KPIs, tortas, llegada, tabla por fuente y campañas.">Adquirido desde</label><input type="date" id="f-d1" autocomplete="off"></div>
<div><label data-tip="Fecha de creación del lead hasta, inclusive.">Adquirido hasta</label><input type="date" id="f-d2" autocomplete="off"></div>
</div>

<div class="fbar">
<button class="btn sec" onclick="reset()">✕ Limpiar filtros</button>
<span id="resumen" style="font-size:12.5px;color:var(--gris)"></span>
</div>

<div class="kpis" id="adq-kpis"></div>

<div class="chart-sec">
<h2>🥧 De dónde vienen los leads</h2>
<p class="chart-sub">Reparto de la selección actual por medio y por país. Clic en una porción aplica (o quita) ese filtro.</p>
<div class="pies">
<div class="pie-box"><h3 data-tip="Reparto de los leads de la selección por medio/fuente (top 7 + Otros). Clic = filtrar por esa fuente.">📣 Por medio / fuente</h3>
<svg id="pie-fu" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-fu"></div></div>
<div class="pie-box"><h3 data-tip="Reparto de los leads de la selección por país (prefijo del móvil, top 7 + Otros). Clic = filtrar por ese país.">🌎 Por país del lead</h3>
<svg id="pie-pa" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-pa"></div></div>
</div>
</div>

<div class="chart-sec">
<h2>📈 Llegada mensual por medio</h2>
<p class="chart-sub">Cuántos leads entraron cada mes (últimos 18 meses de la selección), apilados por las 6 fuentes principales. Respeta todos los filtros. Pasa el mouse sobre un segmento para el detalle.</p>
<div style="overflow-x:auto"><svg id="stack" viewBox="0 0 1240 320" preserveAspectRatio="xMidYMid meet" style="width:100%;min-width:700px;height:auto;display:block"></svg></div>
<div class="pleg" id="stack-leg"></div>
</div>

<div class="chart-sec">
<h2>¿Qué fuentes producen los leads mejor calificados para la venta?</h2>
<p class="chart-sub">Cada punto es una fuente ("Fuente de contacto" del CRM). Eje horizontal: cuántos leads trajo (escala logarítmica). Eje vertical: qué % de ellos está calificado para venta según los estados que marques abajo. Tamaño del punto: nº de leads calificados. Las fuentes más eficientes quedan arriba; las líneas punteadas son las medianas — el cuadrante superior derecho combina volumen y calificación. Pasa el mouse sobre un punto para ver su detalle. Respeta todos los filtros de arriba excepto los de categoría y fuente (que son las dimensiones analizadas).</p>
<div class="chart-ctrl"><b data-tip="Define qué estados cuentan como 'lead calificado para venta' en el gráfico. El % de cada fuente = leads en los estados marcados ÷ total de leads de la fuente. Un lead caliente que además tiene un estado marcado se cuenta una sola vez.">Cuenta como calificado:</b><span id="sc-cks"></span>
<b style="margin-left:8px" data-tip="Excluye del gráfico las fuentes con menos leads que este mínimo, para que los porcentajes de fuentes diminutas no distorsionen la lectura.">Fuentes con al menos</b>
<select id="sc-min" autocomplete="off"><option value="5">5 leads</option><option value="10" selected>10 leads</option>
<option value="30">30 leads</option><option value="100">100 leads</option></select></div>
<div id="scat-wrap"><svg id="scat" viewBox="0 0 1240 430" preserveAspectRatio="xMidYMid meet"></svg><div id="scat-tip"></div></div>
<div id="scat-interp"></div>
<div id="scat-top"></div>
</div>

<div class="chart-sec">
<h2>🏆 Calidad de cada medio: la tabla maestra de adquisición</h2>
<p class="chart-sub">Agrupada por <b>categoría de medios</b> (pauta digital, orgánico, eventos, referidos…) con drill-down: clic en la fila de una categoría la expande a sus fuentes. Cada nivel muestra volumen, momentum, contactabilidad, MQL, SQL, conversión y descarte. <b>Respeta todos los filtros excepto categoría y fuente.</b> Clic en una fuente = filtrarla y ver sus leads abajo.</p>
<div style="overflow-x:auto"><table style="min-width:1150px"><thead><tr>
<th data-tip="Categoría de medios (clic para expandir sus fuentes) o fuente individual (clic para filtrar). Fuentes con <30 leads se agrupan en 'Otras' dentro de su categoría.">Categoría / fuente</th>
<th data-tip="Leads adquiridos en la selección.">Leads</th>
<th data-tip="% del total de la selección.">%</th>
<th data-tip="Leads llegados en los últimos 90 días.">Últ. 90d</th>
<th data-tip="Momentum: variación de los últimos 90 días vs los 90 anteriores. ▲ crece, ▼ cae. Estable = ±15%.">Momentum</th>
<th data-tip="% contactabilidad: leads que RESPONDIERON (mensaje entrante de WhatsApp o llamada contestada). Mide si el dato sirve y el canal conecta. Cobertura: WA descargado + llamadas de carteras humanas.">Contactab.</th>
<th data-tip="% MQL: leads con señal de calificación de marketing — score ≥30 u oportunidad declarada (En curso por = Oportunidad…) o ya en Negocio abierto/Cliente.">MQL%</th>
<th data-tip="% SQL: leads aceptados por ventas — Negocio abierto o Cliente, o En curso CON oportunidad vigente. Todo SQL es MQL.">SQL%</th>
<th data-tip="Leads que hoy son clientes.">Clientes</th>
<th data-tip="Tasa de conversión: clientes ÷ leads. La métrica reina de adquisición.">Conv%</th>
<th data-tip="% de leads que terminó descartado.">Desc%</th>
<th data-tip="Score promedio (0-100).">Score</th>
<th data-tip="Tiempo promedio de 1ª atención (primer mensaje saliente de WhatsApp) de los leads con conversación.">1ª atención</th>
</tr></thead><tbody id="tb-fu"></tbody></table></div>
</div>

<div class="chart-sec">
<h2>🎪 Campañas detectadas (por etiqueta)</h2>
<p class="chart-sub">El CRM no registra la campaña en un campo propio, así que se detecta con la primera etiqueta no genérica de cada lead (mismo criterio del dashboard gerencial). Top 15 de la selección con su conversión y descarte. Respeta todos los filtros.</p>
<div style="overflow-x:auto"><table style="min-width:760px"><thead><tr>
<th data-tip="Primera etiqueta no genérica del lead: eventos, webinars, activaciones con nombre propio, listas.">Campaña / etiqueta</th>
<th data-tip="Leads de la selección con esa etiqueta como primera etiqueta no genérica.">Leads</th>
<th data-tip="De esos leads, cuántos son hoy clientes.">Clientes</th>
<th data-tip="Conversión de la campaña: clientes ÷ leads.">Conv%</th>
<th data-tip="% de los leads de la campaña que terminó descartado.">Desc%</th>
<th data-tip="Score promedio de los leads de la campaña.">Score</th>
<th data-tip="Fuente principal por la que entraron los leads de esa campaña.">Fuente principal</th>
</tr></thead><tbody id="tb-camp"></tbody></table></div>
</div>

<div class="chart-sec">
<h2>🧬 Atribución digital (sesión de origen)</h2>
<p class="chart-sub">Lo que la plataforma alcanzó a registrar de la sesión que creó cada contacto (sessionSource · medium). Respeta todos los filtros.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px">
<div><table><thead><tr>
<th data-tip="Combinación sessionSource · medium del registro de atribución del contacto. '(Sin atribución digital)' = el contacto no trae registro de sesión.">Atribución</th>
<th>Leads</th><th data-tip="Clientes que salieron de esa vía de atribución.">Clientes</th><th>Conv%</th>
</tr></thead><tbody id="tb-attr"></tbody></table></div>
<div class="alerta"><b>⚠ El embudo de WhatsApp rompe la atribución de pauta:</b> de {fmt(TOTAL)} leads, solo <b>{fmt(ATTR_COV['gclid'])}</b> traen gclid (Google), <b>{fmt(ATTR_COV['fbclid'])}</b> fbclid y <b>{fmt(ATTR_COV['utm'])}</b> utmCampaign — porque el lead de pauta aterriza en la landing y salta a WhatsApp, donde nace el contacto sin herencia de UTMs (queda solo "Social media · whatsapp"). Meta sí conserva "Paid Social" porque usa formularios nativos. <b>Solución:</b> mini-formulario antes del botón de WhatsApp o código de campaña en el texto prellenado del mensaje. Mientras tanto, la fuente confiable es el campo "Fuente de contacto" (esta hoja) y las etiquetas de campaña.</div>
</div>
</div>

<div id="adq-learn" class="caveat"></div>

<div class="chart-sec" style="margin-top:20px">
<h2>📄 Leads de la selección</h2>
<p class="chart-sub">Ordenados por score. Con un filtro de fuente activo, esta es la lista de leads que trajo ese medio.</p>
<div id="ltab" style="overflow-x:auto"></div>
</div>

<div class="warnpii"><b>⚠ Datos personales:</b> este archivo contiene nombres, correos y teléfonos de {fmt(TOTAL)} personas — es la base de datos misma (Habeas Data). No publicarlo ni circularlo fuera del equipo comercial autorizado.</div>
<footer>Universo: los {fmt(TOTAL)} contactos del CRM. Fuente = campo "Fuente de contacto" con las familias de Google, Referidos, Prensa y Sitio Web agrupadas; vacío = "(Sin fuente)". País por prefijo internacional del móvil. Conversión = Lead Status "Cliente" ÷ leads (con rango de fechas mide el cierre de esa camada). Descarte = Lead Status "Descartado". Score 0-100 con la fórmula de todo el dashboard. 1ª atención = primer mensaje saliente de WhatsApp menos creación del lead (solo leads con conversación). Campaña = primera etiqueta no genérica. Atribución = registro attributionSource de la plataforma. Generado desde la API de GHL, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fmtN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scoreCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
const tempTxt = sc => sc >= 55 ? 'Caliente' : sc >= 30 ? 'Tibio' : sc >= 10 ? 'Frío' : 'Sin señales';
const atnT = h => h < 1 ? Math.round(h * 60) + ' min' : h < 48 ? h.toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + ' h' : (h / 24).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + ' días';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';
const CLI_I = D.status.indexOf('Cliente'), DESC_I = D.status.indexOf('Descartado');
const NEG_I = D.status.indexOf('Negocio abierto'), ENC_I = D.status.indexOf('En curso');
const esOport = x => D.cursos[x[6]].startsWith('Oportunidad');
const esMQL = x => x[7] >= 30 || esOport(x) || x[5] === NEG_I || x[5] === CLI_I;
const esSQL = x => x[5] === NEG_I || x[5] === CLI_I || (x[5] === ENC_I && esOport(x));
const PAGE = 200;
let shown = PAGE;

function fill(id, items, labels) {{
  document.getElementById(id).innerHTML = '<option value="">Todos</option>' +
    items.map((v, i) => `<option value="${{v}}">${{esc(labels[i])}}</option>`).join('');
}}
fill('f-c', D.cats.map((_, i) => i), D.cats);
fill('f-f', D.fuenteOrden, D.fuenteOrden.map(i => D.fuentes[i]));
fill('f-p', D.paisOrden, D.paisOrden.map(i => D.paises[i]));
fill('f-s', D.status.map((_, i) => i), D.status);

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

const inFecha = x => {{
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  return (d1 === '' || (x[8] && x[8] >= d1)) && (d2 === '' || (x[8] && x[8] <= d2));
}};
const matchTemp = sc => {{
  const t = document.getElementById('f-t').value;
  return t === '' || (t === 'hot' ? sc >= 55 : t === 'warm' ? sc >= 30 && sc < 55
    : t === 'cold' ? sc >= 10 && sc < 30 : sc < 10);
}};
function filtro(exceptos) {{
  const g = id => document.getElementById(id).value;
  const f = g('f-f'), p = g('f-p'), s = g('f-s'), cc = g('f-c'), q = g('f-q').trim().toLowerCase();
  return D.rows.filter(x =>
    (exceptos.includes('c') || cc === '' || x[17] == cc) &&
    (exceptos.includes('f') || f === '' || x[3] == f) &&
    (exceptos.includes('p') || p === '' || x[4] == p) &&
    (exceptos.includes('s') || s === '' || x[5] == s) &&
    (exceptos.includes('t') || matchTemp(x[7])) && inFecha(x) &&
    (q === '' || (x[0] + ' ' + x[1] + ' ' + x[2]).toLowerCase().includes(q)));
}}

let view = [];
function apply() {{
  view = filtro([]).slice().sort((a, b) => b[7] - a[7]);
  shown = PAGE;
  renderKpis(); renderPies(); renderStack(); renderScat(); renderFuentes(); renderCampanas(); renderAttr(); renderLearn(); renderTabla();
  document.getElementById('resumen').textContent =
    `${{fmtN(view.length)}} leads en la vista de ${{fmtN(D.rows.length)}} adquiridos.`;
}}

function renderKpis() {{
  const n = view.length;
  let cli = 0, desc = 0, cal = 0, sum = 0, cont = 0, sinF = 0, atnS = 0, atnN = 0, d90 = 0;
  let resp = 0, mql = 0, sql = 0;
  const hoy = Date.now(), sinFI = D.fuentes.indexOf('(Sin fuente)');
  const corte90 = new Date(hoy - 90 * 86400000).toISOString().slice(0, 10);
  view.forEach(x => {{
    if (x[5] === CLI_I) cli++;
    if (x[5] === DESC_I) desc++;
    if (x[7] >= 30) cal++;
    sum += x[7]; if (x[10] > 0) cont++;
    if (x[3] === sinFI) sinF++;
    if (x[11] >= 0) {{ atnS += x[11]; atnN++; }}
    if (x[8] >= corte90) d90++;
    if (x[16]) resp++;
    if (esMQL(x)) mql++;
    if (esSQL(x)) sql++;
  }});
  const kp = (val, lbl, tip, color) =>
    `<div class="kpi" data-tip="${{esc(tip)}}"><b style="color:${{color || 'var(--tinta)'}}">${{val}}</b><span>${{lbl}}</span></div>`;
  const pc = v => n ? (v / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  document.getElementById('adq-kpis').innerHTML =
    kp(fmtN(n), 'leads adquiridos (vista)', 'Leads de la selección actual según los filtros.') +
    kp(fmtN(d90), 'llegados últimos 90 días', 'Leads de la vista creados en los últimos 90 días: el ritmo de adquisición reciente.') +
    kp(fmtN(cli) + ` <small style="font-size:12px">(${{pc(cli)}})</small>`, 'clientes · conversión', 'Leads de la vista que hoy son clientes, y la tasa de conversión de la selección. Con rango de fechas mide el cierre de esa camada.', 'var(--verde)') +
    kp(fmtN(desc) + ` <small style="font-size:12px">(${{pc(desc)}})</small>`, 'descartados · tasa', 'Leads de la vista que terminaron descartados: adquisición que se botó.', 'var(--rojo)') +
    kp(fmtN(cal), 'calificados (🔥+🌤 score ≥30)', 'Leads calientes + tibios de la vista: el inventario con señales de compra vigentes.', 'var(--naranja)') +
    kp(n ? (sum / n).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) : '—', 'score promedio', 'Temperatura promedio de la selección (lead scoring 0-100).') +
    kp(pc(cont), '% contactados', 'Leads de la vista con al menos una gestión registrada (veces contactado + actividades de venta > 0). Mide el esfuerzo del equipo.') +
    kp(pc(resp), '% contactabilidad', 'Leads que RESPONDIERON: al menos un mensaje entrante de WhatsApp o una llamada contestada. Mide si el dato del lead sirve y si el canal conecta. Cobertura: conversaciones de WhatsApp descargadas + llamadas de carteras humanas.', 'var(--verde)') +
    kp(fmtN(mql) + ` <small style="font-size:12px">(${{pc(mql)}})</small>`, 'MQL (calificados marketing)', 'MQL = lead con señal de calificación: score ≥30 (tibio/caliente) u oportunidad de compra declarada (En curso por = Oportunidad 1-3/3-6/6+ meses) o que ya avanzó a Negocio abierto/Cliente.', 'var(--naranja)') +
    kp(fmtN(sql) + ` <small style="font-size:12px">(${{pc(sql)}})</small>`, 'SQL (calificados ventas)', 'SQL = lead aceptado y trabajado por ventas: Lead Status = Negocio abierto o Cliente, o En curso CON oportunidad vigente declarada. Todo SQL es también MQL.', 'var(--rojo)') +
    kp(atnN ? atnT(atnS / atnN) : '—', '1ª atención promedio (WA)', 'Primer mensaje saliente de WhatsApp menos creación del lead, promediado sobre los ' + fmtN(atnN) + ' leads de la vista con conversación.', 'var(--azul)') +
    kp(pc(sinF), 'sin fuente registrada', 'Leads de la vista sin campo Fuente de contacto: adquisición ciega — no se sabe qué medio pagó por ellos.', '#8A6D1A');
}}

/* ---------- tortas ---------- */
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
    svg.innerHTML = `<text x="170" y="115" text-anchor="middle" font-size="13" fill="#5B6B85">Sin leads en la selección</text>`;
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
const PIE_COL = ['#3A566B', '#C4B284', '#1E9E62', '#D64545', '#8A6D1A', '#5A6B78', '#C47845', '#8A99A8'];
function pieDe(svgId, legId, col, nombres, selId, titulo, exc) {{
  const base = filtro([exc]);
  const cnt = new Map();
  base.forEach(x => cnt.set(x[col], (cnt.get(x[col]) || 0) + 1));
  const top = [...cnt.entries()].sort((a, b) => b[1] - a[1]);
  const datos = top.slice(0, 7).map(([i, c], j) => ({{
    label: nombres[i], val: c, color: PIE_COL[j],
    tip: `${{nombres[i]}}: ${{fmtN(c)}} leads (${{(c / base.length * 100).toFixed(1)}}% de la selección). Clic para aplicar/quitar el filtro de ${{titulo}}.`,
    click: () => {{
      const sel = document.getElementById(selId);
      sel.value = sel.value == i ? '' : i;
      apply();
    }}
  }}));
  const resto = top.slice(7).reduce((t, [, c]) => t + c, 0);
  if (resto) datos.push({{label: 'Otros', val: resto, color: '#C9D6E4',
    tip: `Otros ${{top.length - 7}} valores: ${{fmtN(resto)}} leads.`, click: null}});
  drawPie(svgId, legId, datos, 'leads');
}}
function renderPies() {{
  pieDe('pie-fu', 'pleg-fu', 3, D.fuentes, 'f-f', 'fuente', 'f');
  pieDe('pie-pa', 'pleg-pa', 4, D.paises, 'f-p', 'país', 'p');
}}

/* ---------- llegada mensual apilada por fuente ---------- */
const MES_N = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function renderStack() {{
  const rows = view.filter(x => x[8]);
  const svg = document.getElementById('stack'), leg = document.getElementById('stack-leg');
  if (!rows.length) {{ svg.innerHTML = '<text x="620" y="150" text-anchor="middle" font-size="13" fill="#5B6B85">Sin leads en la selección</text>'; leg.innerHTML = ''; return; }}
  const fcnt = new Map();
  rows.forEach(x => fcnt.set(x[3], (fcnt.get(x[3]) || 0) + 1));
  const top = [...fcnt.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(e => e[0]);
  const pos = new Map(top.map((f, i) => [f, i]));
  const meses = [...new Set(rows.map(x => x[8].slice(0, 7)))].sort().slice(-18);
  const mIdx = new Map(meses.map((m, i) => [m, i]));
  const serie = meses.map(() => new Array(top.length + 1).fill(0));
  rows.forEach(x => {{
    const mi = mIdx.get(x[8].slice(0, 7));
    if (mi === undefined) return;
    serie[mi][pos.has(x[3]) ? pos.get(x[3]) : top.length]++;
  }});
  const W = 1240, H = 320, L = 46, R = 14, T = 16, B = 40;
  const tot = serie.map(s => s.reduce((a, b) => a + b, 0));
  const max = Math.max(...tot, 1);
  const bw = (W - L - R) / meses.length;
  const Y = v => T + (1 - v / (max * 1.1)) * (H - T - B);
  let g = '';
  const paso = max > 40 ? Math.ceil(max / 4 / 10) * 10 : Math.max(1, Math.ceil(max / 4));
  for (let v = 0; v <= max * 1.02; v += paso) {{
    g += `<line x1="${{L}}" y1="${{Y(v)}}" x2="${{W - R}}" y2="${{Y(v)}}" stroke="#F0F3F8"/>` +
         `<text x="${{L - 6}}" y="${{Y(v) + 3.5}}" text-anchor="end" font-size="10.5" fill="#5B6B85">${{fmtN(v)}}</text>`;
  }}
  const et = m => MES_N[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4);
  meses.forEach((m, i) => {{
    let acc = 0;
    const x = L + i * bw + bw * 0.14, w = bw * 0.72;
    serie[i].forEach((v, si) => {{
      if (!v) return;
      const y1 = Y(acc), y2 = Y(acc + v);
      const nom = si < top.length ? D.fuentes[top[si]] : 'Otras fuentes';
      g += `<rect x="${{x}}" y="${{y2}}" width="${{w}}" height="${{y1 - y2}}" fill="${{si < top.length ? PIE_COL[si] : '#C9D6E4'}}" ` +
        `data-tip="${{esc(nom)}} — ${{esc(et(m))}}: ${{fmtN(v)}} leads (mes total: ${{fmtN(tot[i])}})." style="cursor:help"></rect>`;
      acc += v;
    }});
    if (meses.length <= 20) g += `<text x="${{x + w / 2}}" y="${{Y(tot[i]) - 5}}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#2C4356">${{fmtN(tot[i])}}</text>`;
    g += `<text x="${{x + w / 2}}" y="${{H - B + 16}}" text-anchor="middle" font-size="10" fill="#5B6B85">${{esc(et(m))}}</text>`;
  }});
  g += `<line x1="${{L}}" y1="${{H - B}}" x2="${{W - R}}" y2="${{H - B}}" stroke="#E4E9F2"/>`;
  svg.innerHTML = g;
  leg.innerHTML = top.map((f, i) =>
    `<span><span class="dot" style="background:${{PIE_COL[i]}}"></span>${{esc(D.fuentes[f])}}</span>`).join('') +
    (serie.some(s => s[top.length]) ? '<span><span class="dot" style="background:#C9D6E4"></span>Otras fuentes</span>' : '');
}}

/* ---------- dispersión: eficiencia por fuente ---------- */
const SC_DEFAULT = ['hot', 'Negocio abierto', 'Cliente'];
(function initScatCtrl() {{
  const holder = document.getElementById('sc-cks');
  const opts = [['hot', '🔥 Calientes (score ≥ 55)']]
    .concat(D.status.map((s, i) => [String(i), s]));
  holder.innerHTML = opts.map(([v, l]) => {{
    const on = SC_DEFAULT.includes(v === 'hot' ? 'hot' : D.status[+v]);
    return `<label class="ckp ${{on ? 'on' : ''}}"><input type="checkbox" autocomplete="off" value="${{v}}" ${{on ? 'checked' : ''}}>${{esc(l)}}</label>`;
  }}).join('');
  holder.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {{
    i.parentElement.classList.toggle('on', i.checked); renderScat();
  }}));
  document.getElementById('sc-min').addEventListener('change', renderScat);
}})();

function scatData() {{
  const minN = +document.getElementById('sc-min').value;
  const checked = [...document.querySelectorAll('#sc-cks input:checked')].map(i => i.value);
  const hotOn = checked.includes('hot');
  const sSet = new Set(checked.filter(v => v !== 'hot').map(Number));
  const F = new Map();
  filtro(['c', 'f']).forEach(r => {{
    let o = F.get(r[3]);
    if (!o) {{ o = {{ t: 0, st: {{}}, hotSt: {{}} }}; F.set(r[3], o); }}
    o.t++;
    o.st[r[5]] = (o.st[r[5]] || 0) + 1;
    if (r[7] >= 55) o.hotSt[r[5]] = (o.hotSt[r[5]] || 0) + 1;
  }});
  const pts = [];
  F.forEach((o, fi) => {{
    if (o.t < minN) return;
    let q = 0;
    for (const [s, c] of Object.entries(o.st)) if (sSet.has(+s)) q += c;
    if (hotOn) for (const [s, c] of Object.entries(o.hotSt)) if (!sSet.has(+s)) q += c;
    pts.push({{ fi, t: o.t, q, p: q / o.t * 100, st: o.st,
                hot: Object.values(o.hotSt).reduce((a, b) => a + b, 0) }});
  }});
  return pts;
}}

function median(a) {{
  if (!a.length) return 0;
  const s = a.slice().sort((x, y) => x - y), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}}

function renderScat() {{
  const pts = scatData();
  const svg = document.getElementById('scat');
  if (!pts.length) {{ svg.innerHTML = ''; document.getElementById('scat-top').innerHTML = ''; return; }}
  const W = 1240, H = 430, L = 52, R = 26, T = 16, B = 40;
  const xmin = Math.min(...pts.map(p => p.t)), xmax = Math.max(...pts.map(p => p.t));
  const lx0 = Math.log10(Math.max(1, xmin * .8)), lx1 = Math.log10(xmax * 1.25);
  const ymax = Math.max(5, Math.max(...pts.map(p => p.p)) * 1.14);
  const X = t => L + (Math.log10(t) - lx0) / (lx1 - lx0) * (W - L - R);
  const Y = p => T + (1 - p / ymax) * (H - T - B);
  const rad = q => Math.max(6, Math.min(24, 5 + Math.sqrt(q) * 1.9));
  let g = '';
  /* grid + ejes */
  const xticks = [5, 10, 30, 100, 300, 1000, 3000, 10000].filter(v => v >= xmin * .8 && v <= xmax * 1.25);
  xticks.forEach(v => {{
    g += `<line x1="${{X(v)}}" y1="${{T}}" x2="${{X(v)}}" y2="${{H - B}}" stroke="#F0F3F8"/>` +
         `<text x="${{X(v)}}" y="${{H - B + 16}}" text-anchor="middle" font-size="10.5" fill="#5B6B85">${{fmtN(v)}}</text>`;
  }});
  const ystep = ymax > 40 ? 10 : ymax > 16 ? 5 : 2;
  for (let v = 0; v <= Math.min(100, ymax); v += ystep) {{
    g += `<line x1="${{L}}" y1="${{Y(v)}}" x2="${{W - R}}" y2="${{Y(v)}}" stroke="#F0F3F8"/>` +
         `<text x="${{L - 7}}" y="${{Y(v) + 3.5}}" text-anchor="end" font-size="10.5" fill="#5B6B85">${{v}}%</text>`;
  }}
  g += `<text x="${{(L + W - R) / 2}}" y="${{H - 6}}" text-anchor="middle" font-size="11" fill="#5B6B85" font-weight="700">Leads que trajo la fuente (escala log)</text>`;
  g += `<text x="14" y="${{(T + H - B) / 2}}" text-anchor="middle" font-size="11" fill="#5B6B85" font-weight="700" transform="rotate(-90 14 ${{(T + H - B) / 2}})">% calificados para venta</text>`;
  /* medianas */
  const mx = median(pts.map(p => p.t)), my = median(pts.map(p => p.p));
  g += `<line x1="${{X(mx)}}" y1="${{T}}" x2="${{X(mx)}}" y2="${{H - B}}" stroke="#C9D6E4" stroke-dasharray="5 4"/>`;
  g += `<line x1="${{L}}" y1="${{Y(my)}}" x2="${{W - R}}" y2="${{Y(my)}}" stroke="#C9D6E4" stroke-dasharray="5 4"/>`;
  g += `<text x="${{W - R - 4}}" y="${{T + 12}}" text-anchor="end" font-size="10.5" fill="#8A99A8" font-style="italic">↗ alto volumen · alta calificación</text>`;
  /* puntos (grandes debajo, pequeños encima) */
  const drawn = pts.slice().sort((a, b) => b.t - a.t);
  drawn.forEach((p, i) => {{
    g += `<circle class="dot" data-i="${{pts.indexOf(p)}}" cx="${{X(p.t)}}" cy="${{Y(p.p)}}" r="${{rad(p.q)}}"/>`;
  }});
  /* etiquetas directas: top 4 por nº calificados y top 3 por % */
  const lab = new Set();
  pts.slice().sort((a, b) => b.q - a.q).slice(0, 4).forEach(p => lab.add(p.fi));
  pts.slice().sort((a, b) => b.p - a.p).slice(0, 3).forEach(p => lab.add(p.fi));
  pts.filter(p => lab.has(p.fi)).forEach(p => {{
    const nm = D.fuentes[p.fi].length > 26 ? D.fuentes[p.fi].slice(0, 25) + '…' : D.fuentes[p.fi];
    const anchor = X(p.t) > W - 220 ? 'end' : 'start';
    const dx = anchor === 'end' ? -(rad(p.q) + 5) : rad(p.q) + 5;
    g += `<text x="${{X(p.t) + dx}}" y="${{Y(p.p) + 3.5}}" text-anchor="${{anchor}}" font-size="10.8" font-weight="700" fill="#2C4356">${{esc(nm)}}</text>`;
  }});
  svg.innerHTML = g;
  /* tooltip */
  const tip = document.getElementById('scat-tip'), wrap = document.getElementById('scat-wrap');
  svg.querySelectorAll('.dot').forEach(c => {{
    const show = e => {{
      const p = pts[+c.dataset.i];
      const det = Object.entries(p.st).sort((a, b) => b[1] - a[1]).slice(0, 6)
        .map(([s, n]) => `${{esc(D.status[+s])}}: <b>${{fmtN(n)}}</b>`).join(' · ');
      tip.innerHTML = `<b>${{esc(D.fuentes[p.fi])}}</b><br>` +
        `Leads: <b>${{fmtN(p.t)}}</b> · Calificados: <b>${{fmtN(p.q)}}</b> (${{p.p.toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}%)` +
        ` · 🔥 Calientes: <b>${{fmtN(p.hot)}}</b><br><span style="opacity:.85">${{det}}</span>`;
      const r = wrap.getBoundingClientRect();
      let tx = e.clientX - r.left + 14, ty = e.clientY - r.top - 10;
      tip.style.display = 'block';
      if (tx + 290 > r.width) tx = e.clientX - r.left - 300;
      tip.style.left = tx + 'px'; tip.style.top = ty + 'px';
    }};
    c.addEventListener('mousemove', show);
    c.addEventListener('mouseenter', show);
    c.addEventListener('mouseleave', () => tip.style.display = 'none');
  }});
  /* interpretación dinámica según el filtro activo */
  renderInterp(pts, mx, my);
  /* ranking accesible */
  document.getElementById('scat-top').innerHTML =
    '<div style="border:0;font-weight:800;color:var(--gris);text-transform:uppercase;font-size:10.5px;letter-spacing:.5px">Fuentes más eficientes (con el mínimo de leads elegido)</div><div style="border:0"></div>' +
    pts.slice().sort((a, b) => b.p - a.p || b.q - a.q).slice(0, 10).map((p, i) =>
      `<div><span class="rk">${{i + 1}}.</span> ${{esc(D.fuentes[p.fi])}}
       <span style="color:var(--gris)">${{fmtN(p.q)}} de ${{fmtN(p.t)}}</span>
       <span class="pc">${{p.p.toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}%</span></div>`).join('');
}}
function renderInterp(pts, mx, my) {{
  const el = document.getElementById('scat-interp');
  const pct = x => x.toLocaleString('es-CO', {{ maximumFractionDigits: 1 }}) + '%';
  const nm = p => `<b>${{esc(D.fuentes[p.fi])}}</b>`;
  const minN = +document.getElementById('sc-min').value;
  const checked = [...document.querySelectorAll('#sc-cks input:checked')];
  if (!checked.length) {{
    el.innerHTML = '<h3>Interpretación</h3>Marca al menos un estado en “Cuenta como calificado” para generar la lectura del gráfico.';
    return;
  }}
  const defTxt = checked.map(i => i.value === 'hot' ? '🔥 Calientes (score ≥ 55)' : D.status[+i.value]).join(' + ');
  const T = pts.reduce((a, p) => a + p.t, 0), Q = pts.reduce((a, p) => a + p.q, 0);
  const li = [];
  li.push(`Con la definición actual de calificado (<b>${{esc(defTxt)}}</b>) y fuentes de al menos ${{fmtN(minN)}} leads, se analizan <b>${{fmtN(pts.length)}} fuentes</b> que suman <b>${{fmtN(T)}}</b> leads, de los cuales <b>${{fmtN(Q)}}</b> (${{pct(T ? Q / T * 100 : 0)}}) están calificados. La fuente mediana convierte el ${{pct(my)}}.`);
  const stars = pts.filter(p => p.t >= mx && p.p >= my && p.q > 0).sort((a, b) => b.q - a.q);
  if (stars.length) {{
    li.push(`<b>Dónde está el negocio (volumen + calificación):</b> ${{stars.slice(0, 3).map(p =>
      `${{nm(p)}} (${{fmtN(p.q)}} calificados de ${{fmtN(p.t)}}, ${{pct(p.p)}})`).join(' · ')}}. Son las fuentes que combinan escala y calidad: protege su presupuesto y su seguimiento.`);
  }} else {{
    li.push(`<b>Ninguna fuente combina hoy volumen y calificación por encima de la mediana</b>: las eficientes son pequeñas y las masivas convierten poco.`);
  }}
  const gems = pts.filter(p => p.t < mx && p.p >= my * 1.5 && p.q >= 3 && p.p < 99).sort((a, b) => b.p - a.p);
  if (gems.length) {{
    li.push(`<b>Joyas por escalar (alta calificación, poco volumen):</b> ${{gems.slice(0, 3).map(p =>
      `${{nm(p)}} (${{pct(p.p)}} con ${{fmtN(p.t)}} leads)`).join(' · ')}}. Si su calidad se sostiene al crecer, son la mejor inversión marginal.`);
  }}
  const low = pts.filter(p => p.t >= mx && p.p < my).sort((a, b) => b.t - a.t);
  if (low.length) {{
    li.push(`<b>Volumen con baja calificación:</b> ${{low.slice(0, 3).map(p =>
      `${{nm(p)}} (${{fmtN(p.t)}} leads, solo ${{pct(p.p)}})`).join(' · ')}}. Aportan ${{fmtN(low.reduce((a, p) => a + p.q, 0))}} calificados por puro volumen, pero pagan mucho lead frío: revisar segmentación o el proceso de gestión de esos leads.`);
  }}
  const perfect = pts.filter(p => p.p >= 99).sort((a, b) => b.t - a.t);
  if (perfect.length) {{
    li.push(`<b>Ojo con ${{perfect.map(nm).join(' y ')}}</b>: convierte(n) ~100%, patrón típico de listas de clientes ya existentes importadas al CRM, no de una fuente real de captación. No usar como referencia de eficiencia.`);
  }}
  const hotOn = checked.some(i => i.value === 'hot');
  if (hotOn) {{
    const H = pts.reduce((a, p) => a + p.hot, 0);
    const topHot = pts.filter(p => p.hot > 0).sort((a, b) => b.hot - a.hot).slice(0, 3);
    if (topHot.length) li.push(`<b>Los ${{fmtN(H)}} leads calientes</b> de estas fuentes salen sobre todo de ${{topHot.map(p => `${{nm(p)}} (${{fmtN(p.hot)}})`).join(' · ')}}.`);
  }}
  el.innerHTML = '<h3>Interpretación (se actualiza con el filtro)</h3><ul>' + li.map(x => `<li>${{x}}</li>`).join('') + '</ul>';
}}

/* ---------- tabla maestra: categoría → fuente (drill-down) ---------- */
const EXP = new Set();
function mkAgg() {{ return {{n: 0, cli: 0, desc: 0, sum: 0, atnS: 0, atnN: 0, d90: 0, p90: 0, resp: 0, mql: 0, sql: 0}}; }}
function addTo(a, x, c90, c180) {{
  a.n++; a.sum += x[7];
  if (x[5] === CLI_I) a.cli++;
  if (x[5] === DESC_I) a.desc++;
  if (x[11] >= 0) {{ a.atnS += x[11]; a.atnN++; }}
  if (x[8] >= c90) a.d90++; else if (x[8] >= c180) a.p90++;
  if (x[16]) a.resp++;
  if (esMQL(x)) a.mql++;
  if (esSQL(x)) a.sql++;
}}
function renderFuentes() {{
  const base = filtro(['c', 'f']);
  const hoy = Date.now();
  const c90 = new Date(hoy - 90 * 86400000).toISOString().slice(0, 10);
  const c180 = new Date(hoy - 180 * 86400000).toISOString().slice(0, 10);
  const porCat = new Map(), porFu = new Map();
  base.forEach(x => {{
    if (!porCat.has(x[17])) porCat.set(x[17], mkAgg());
    addTo(porCat.get(x[17]), x, c90, c180);
    const k = x[17] + ':' + x[3];
    if (!porFu.has(k)) porFu.set(k, mkAgg());
    addTo(porFu.get(k), x, c90, c180);
  }});
  const pcc = (v, n) => n ? (v / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  const momTxt = a => {{
    if (a.p90 >= 5 || a.d90 >= 5) {{
      const d = a.p90 ? (a.d90 - a.p90) / a.p90 * 100 : 100;
      if (d > 15) return `<b style="color:var(--verde)">▲ ${{d.toFixed(0)}}%</b>`;
      if (d < -15) return `<b style="color:var(--rojo)">▼ ${{Math.abs(d).toFixed(0)}}%</b>`;
      return '<span style="color:var(--gris)">estable</span>';
    }}
    return (!a.d90 && !a.p90) ? '<span style="color:var(--gris)">sin llegada</span>' : '<span style="color:var(--gris)">estable</span>';
  }};
  const celdas = a => `
    <td>${{fmtN(a.n)}}</td><td>${{pcc(a.n, base.length)}}</td>
    <td>${{fmtN(a.d90)}}</td><td style="white-space:nowrap">${{momTxt(a)}}</td>
    <td><b style="color:${{a.n && a.resp / a.n >= .3 ? 'var(--verde)' : 'var(--tinta)'}}">${{pcc(a.resp, a.n)}}</b></td>
    <td style="color:var(--naranja);font-weight:700">${{pcc(a.mql, a.n)}}</td>
    <td style="color:var(--rojo);font-weight:700">${{pcc(a.sql, a.n)}}</td>
    <td>${{fmtN(a.cli)}}</td><td><b style="color:${{a.n && a.cli / a.n >= 0.035 ? 'var(--verde)' : 'var(--tinta)'}}">${{pcc(a.cli, a.n)}}</b></td>
    <td style="color:${{a.n && a.desc / a.n >= 0.2 ? 'var(--rojo)' : 'var(--tinta)'}}">${{pcc(a.desc, a.n)}}</td>
    <td>${{a.n ? (a.sum / a.n).toFixed(1).replace('.', ',') : '—'}}</td>
    <td style="white-space:nowrap">${{a.atnN ? atnT(a.atnS / a.atnN) : '—'}}</td>`;
  let out = '';
  [...porCat.entries()].sort((x, y) => y[1].n - x[1].n).forEach(([ci, a]) => {{
    const abierto = EXP.has(ci);
    out += `<tr class="clkd" data-cat="${{ci}}" style="background:var(--gris-fondo)" data-tip="${{esc(D.cats[ci])}}: ${{fmtN(a.n)}} leads en ${{[...porFu.keys()].filter(k => k.startsWith(ci + ':')).length}} fuentes. Clic para ${{abierto ? 'colapsar' : 'expandir'}} sus fuentes.">
      <td style="white-space:nowrap"><b>${{abierto ? '▾' : '▸'}} ${{esc(D.cats[ci])}}</b></td>${{celdas(a)}}</tr>`;
    if (abierto) {{
      const fus = [...porFu.entries()].filter(([k]) => k.startsWith(ci + ':'))
        .map(([k, a2]) => [+k.split(':')[1], a2]).sort((x, y) => y[1].n - x[1].n);
      const otras = mkAgg();
      fus.forEach(([fi, a2]) => {{
        if (a2.n >= 30) {{
          out += `<tr class="clkd" data-f="${{fi}}" data-tip="${{esc(D.fuentes[fi])}}: ${{fmtN(a2.n)}} leads. Clic para filtrar por esta fuente y ver sus leads abajo.">
            <td style="white-space:nowrap;padding-left:28px">${{esc(D.fuentes[fi]).slice(0, 34)}}</td>${{celdas(a2)}}</tr>`;
        }} else {{
          a2n = a2;
          otras.n += a2.n; otras.cli += a2.cli; otras.desc += a2.desc; otras.sum += a2.sum;
          otras.atnS += a2.atnS; otras.atnN += a2.atnN; otras.d90 += a2.d90; otras.p90 += a2.p90;
          otras.resp += a2.resp; otras.mql += a2.mql; otras.sql += a2.sql;
        }}
      }});
      if (otras.n) out += `<tr data-tip="Fuentes de ${{esc(D.cats[ci])}} con menos de 30 leads cada una, agrupadas.">
        <td style="white-space:nowrap;padding-left:28px;color:var(--gris)">Otras fuentes de la categoría</td>${{celdas(otras)}}</tr>`;
    }}
  }});
  document.getElementById('tb-fu').innerHTML = out;
  document.querySelectorAll('#tb-fu tr[data-cat]').forEach(tr => tr.addEventListener('click', () => {{
    const ci = +tr.dataset.cat;
    if (EXP.has(ci)) EXP.delete(ci); else EXP.add(ci);
    renderFuentes();
  }}));
  document.querySelectorAll('#tb-fu tr[data-f]').forEach(tr => tr.addEventListener('click', () => {{
    const sel = document.getElementById('f-f');
    sel.value = sel.value === tr.dataset.f ? '' : tr.dataset.f;
    apply();
    document.getElementById('ltab').scrollIntoView({{behavior: 'smooth'}});
  }}));
}}

/* ---------- campañas por etiqueta ---------- */
const GEN_TAGS = ['importacion', 'paid', 'always on', 'redes sociales', 'whatsapp', 'landing page',
                  'lead web site', 'happy birthday', 'nutrición - base cold', 'activaciones de',
                  'activaciones', 'base cold', 'pauta'];
function campDe(x) {{
  for (const i of (x[12] || [])) {{
    const t = D.tags[i], tl = t.toLowerCase().trim();
    if (!tl) continue;
    if (GEN_TAGS.some(g => tl.startsWith(g) || tl === g)) continue;
    return t;
  }}
  return null;
}}
function renderCampanas() {{
  const agg = new Map();
  view.forEach(x => {{
    const c = campDe(x);
    if (!c) return;
    if (!agg.has(c)) agg.set(c, {{n: 0, cli: 0, desc: 0, sum: 0, fu: new Map()}});
    const a = agg.get(c);
    a.n++; a.sum += x[7];
    if (x[5] === CLI_I) a.cli++;
    if (x[5] === DESC_I) a.desc++;
    a.fu.set(x[3], (a.fu.get(x[3]) || 0) + 1);
  }});
  const pcc = (v, n) => n ? (v / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  document.getElementById('tb-camp').innerHTML = [...agg.entries()]
    .filter(([, a]) => a.n >= 15).sort((x, y) => y[1].n - x[1].n).slice(0, 15)
    .map(([c, a]) => {{
      const fu = [...a.fu.entries()].sort((x, y) => y[1] - x[1])[0];
      return `<tr data-tip="${{esc(c)}}: ${{fmtN(a.n)}} leads, ${{fmtN(a.cli)}} clientes, ${{fmtN(a.desc)}} descartados.">
        <td><b>${{esc(c).slice(0, 46)}}</b></td><td>${{fmtN(a.n)}}</td>
        <td>${{fmtN(a.cli)}}</td><td><b style="color:${{a.cli / a.n >= 0.035 ? 'var(--verde)' : 'var(--tinta)'}}">${{pcc(a.cli, a.n)}}</b></td>
        <td style="color:${{a.desc / a.n >= 0.2 ? 'var(--rojo)' : 'var(--tinta)'}}">${{pcc(a.desc, a.n)}}</td>
        <td>${{(a.sum / a.n).toFixed(1).replace('.', ',')}}</td>
        <td>${{esc(D.fuentes[fu[0]])}} <small style="color:var(--gris)">(${{fmtN(fu[1])}})</small></td></tr>`;
    }}).join('') || '<tr><td colspan="7" style="color:var(--gris)">Sin campañas con 15+ leads en la selección.</td></tr>';
}}

/* ---------- atribución ---------- */
function renderAttr() {{
  const agg = new Map();
  view.forEach(x => {{
    if (!agg.has(x[15])) agg.set(x[15], {{n: 0, cli: 0}});
    const a = agg.get(x[15]);
    a.n++; if (x[5] === CLI_I) a.cli++;
  }});
  const pcc = (v, n) => n ? (v / n * 100).toFixed(1).replace('.', ',') + '%' : '—';
  document.getElementById('tb-attr').innerHTML = [...agg.entries()]
    .sort((x, y) => y[1].n - x[1].n).slice(0, 10)
    .map(([i, a]) => `<tr><td>${{esc(D.attrs[i]).slice(0, 40)}}</td><td>${{fmtN(a.n)}}</td>
      <td>${{fmtN(a.cli)}}</td><td>${{pcc(a.cli, a.n)}}</td></tr>`).join('');
}}

/* ---------- aprendizajes ---------- */
function renderLearn() {{
  const base = filtro(['f']);
  const agg = new Map();
  const hoy = Date.now();
  const c90 = new Date(hoy - 90 * 86400000).toISOString().slice(0, 10);
  const c180 = new Date(hoy - 180 * 86400000).toISOString().slice(0, 10);
  base.forEach(x => {{
    if (!agg.has(x[3])) agg.set(x[3], {{n: 0, cli: 0, desc: 0, d90: 0, p90: 0}});
    const a = agg.get(x[3]);
    a.n++;
    if (x[5] === CLI_I) a.cli++;
    if (x[5] === DESC_I) a.desc++;
    if (x[8] >= c90) a.d90++; else if (x[8] >= c180) a.p90++;
  }});
  const conVol = [...agg.entries()].filter(([, a]) => a.n >= 100);
  const li = [];
  if (conVol.length) {{
    const mejor = conVol.slice().sort((x, y) => y[1].cli / y[1].n - x[1].cli / x[1].n)[0];
    li.push(`<b>La fuente que mejor convierte (100+ leads):</b> ${{esc(D.fuentes[mejor[0]])}} — ${{(mejor[1].cli / mejor[1].n * 100).toFixed(1).replace('.', ',')}}% de conversión (${{fmtN(mejor[1].cli)}} clientes de ${{fmtN(mejor[1].n)}} leads). Ojo: conversiones ~100% suelen ser listas de clientes importadas, no captación real.`);
    const peor = conVol.slice().sort((x, y) => y[1].desc / y[1].n - x[1].desc / x[1].n)[0];
    li.push(`<b>La fuente que más se descarta:</b> ${{esc(D.fuentes[peor[0]])}} — ${{(peor[1].desc / peor[1].n * 100).toFixed(1).replace('.', ',')}}% de sus leads terminó en la basura. Revisar si el problema es la calidad del lead o la velocidad de atención.`);
    const crece = conVol.filter(([, a]) => a.p90 >= 10).sort((x, y) => (y[1].d90 - y[1].p90) / y[1].p90 - (x[1].d90 - x[1].p90) / x[1].p90)[0];
    if (crece) {{
      const d = (crece[1].d90 - crece[1].p90) / crece[1].p90 * 100;
      li.push(`<b>Momentum:</b> ${{esc(D.fuentes[crece[0]])}} ${{d >= 0 ? 'crece' : 'cae'}} ${{Math.abs(d).toFixed(0)}}% en llegada (${{fmtN(crece[1].d90)}} leads en los últimos 90 días vs ${{fmtN(crece[1].p90)}} en los 90 anteriores).`);
    }}
    const top1 = conVol.slice().sort((x, y) => y[1].n - x[1].n)[0];
    li.push(`<b>Concentración:</b> ${{esc(D.fuentes[top1[0]])}} aporta el ${{(top1[1].n / base.length * 100).toFixed(0)}}% de la adquisición de la selección — dependencia alta de un solo medio.`);
  }}
  li.push(`<b>Atribución de pauta rota:</b> solo ${{fmtN(D.attrCov.gclid)}} leads con gclid y ${{fmtN(D.attrCov.utm)}} con utmCampaign en toda la base (${{fmtN(D.attrCov.conAttr)}} traen algún registro de sesión). Hasta que el embudo de WhatsApp no herede UTMs, el ROI por campaña de Google no se puede medir desde el CRM.`);
  document.getElementById('adq-learn').innerHTML =
    '<b>🎓 Aprendizajes de la selección actual:</b><ul style="padding-left:20px;margin:6px 0">' +
    li.map(x => `<li style="margin:4px 0">${{x}}</li>`).join('') + '</ul>';
}}

/* ---------- tabla de leads ---------- */
function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tags[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
function renderTabla() {{
  const ls = view.slice(0, shown);
  const filas = ls.map(r => {{
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank">WA</a>' : ''}}` : '—';
    return `<tr><td><span class="sc" style="background:${{scoreCol(r[7])}}">${{r[7]}}</span></td>
      <td><b>${{esc(r[0])}}</b></td><td>${{esc(D.asesores[r[9]])}}</td>
      <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
      <td>${{esc(D.fuentes[r[3]])}}</td><td>${{esc(D.paises[r[4]])}}</td>
      <td>${{esc(D.status[r[5]])}}</td><td>${{esc(D.cursos[r[6]])}}</td><td>${{esc(r[8] || '—')}}</td>
      <td style="white-space:nowrap" data-tip="${{intTip(r[13])}}">${{intCell(r[13])}}</td>
      <td data-tip="${{intTip(r[13])}}">${{canCell(r[13])}}</td>
      <td>${{tagsCell(r[12])}}</td></tr>`;
  }}).join('');
  document.getElementById('ltab').innerHTML =
    `<table style="min-width:1150px"><thead><tr>
     <th data-tip="Lead scoring 0-100 (misma fórmula de todo el dashboard).">Score</th>
     <th>Lead</th><th data-tip="Usuario del CRM asignado.">Asesor</th>
     <th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp.">Teléfono</th>
     <th data-tip="Medio/fuente por el que se adquirió el lead.">Fuente</th>
     <th data-tip="País por prefijo del móvil.">País</th>
     <th>Lead Status</th><th>En curso por</th>
     <th data-tip="Fecha de adquisición (creación en el CRM).">Creado</th>
     <th data-tip="Intentos de contacto salientes: total · días distintos. Cobertura completa para carteras humanas; para el resto solo WhatsApp.">Intentos</th>
     <th data-tip="Canales usados: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS.">Canales</th>
     <th>Etiquetas</th>
     </tr></thead><tbody>${{filas}}</tbody></table>` +
    (shown < view.length ? `<button class="btn sec more" onclick="masFilas()">Mostrar ${{fmtN(Math.min(PAGE, view.length - shown))}} más (${{fmtN(view.length - shown)}} restantes)</button>` : '') +
    (view.length === 0 ? '<p style="color:var(--gris);margin:14px 0">Sin leads con los filtros actuales.</p>' : '');
}}
function masFilas() {{ shown += PAGE; renderTabla(); }}

/* ---------- XLSX nativo ---------- */
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
  const out = [['Score', 'Temperatura', 'Lead', 'Asesor', 'Realtor', 'Email', 'Telefono', 'Categoria', 'Fuente', 'Pais',
                'Lead Status', 'En curso por', 'Creado', 'Respondio', 'MQL', 'SQL', 'Interacciones', 'Intentos', 'Dias de intento',
                'Canales', 'Campania (etiqueta)', 'Atribucion', 'Etiquetas']];
  view.forEach(r => out.push([r[7], tempTxt(r[7]), r[0], D.asesores[r[9]], D.realtors[r[14]], r[1], r[2],
    D.cats[r[17]], D.fuentes[r[3]], D.paises[r[4]], D.status[r[5]], D.cursos[r[6]], r[8],
    r[16] ? 'Si' : 'No', esMQL(r) ? 'Si' : 'No', esSQL(r) ? 'Si' : 'No', r[10],
    r[13] ? r[13][0] : 0, r[13] ? r[13][1] : 0, canTxt(r[13]), campDe(r) || '',
    D.attrs[r[15]], (r[12] || []).map(i => D.tags[i]).join(' | ')]));
  XL('adquisicion-leads-filtrado.xlsx', out);
}}

['f-c', 'f-f', 'f-p', 'f-s', 'f-t', 'f-d1', 'f-d2'].forEach(id =>
  document.getElementById(id).addEventListener('change', apply));
document.getElementById('f-q').addEventListener('input', apply);
function reset() {{
  ['f-c', 'f-f', 'f-p', 'f-s', 'f-t', 'f-d1', 'f-d2'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-q').value = '';
  apply();
}}
/* arranque limpio contra la restauración de formularios del navegador */
function arranque() {{
  const defc = ['hot', String(D.status.indexOf('Negocio abierto')), String(D.status.indexOf('Cliente'))];
  document.querySelectorAll('#sc-cks input').forEach(i => {{
    i.checked = defc.includes(i.value);
    i.parentElement.classList.toggle('on', i.checked);
  }});
  const scm = document.getElementById('sc-min'); if (scm) scm.value = '10';
  reset();
}}
arranque();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranque(); }});
setTimeout(() => {{
  const alguno = ['f-c', 'f-f', 'f-p', 'f-s', 'f-t', 'f-q', 'f-d1', 'f-d2'].some(id => document.getElementById(id).value !== '');
  if (alguno) arranque();
}}, 250);
</script>
</body></html>'''

out = str(ROOT / f'adquisicion-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
cli = sum(1 for r in rows if r[5] == STATUS_ORDER.index('Cliente'))
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print(f'leads {TOTAL} | fuentes {len(DF)} | paises {len(DP)} | clientes {cli} | attr {ATTR_COV}')
