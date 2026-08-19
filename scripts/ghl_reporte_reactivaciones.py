#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Informe de REACTIVACIONES: leads que el flujo de nutrición logró despertar
(etiqueta del CRM «reactivo - flujo nutricion»). Muestra cuántos se reactivaron,
en qué lead status y etapa de oportunidad están, quién los tiene, su ficha
unificada (score v2 explicado, intentos, acciones para cerrar venta, WhatsApp)
y las recomendaciones de gestión. Sub-pestaña de Estrategia comercial.
Lee scripts/data/{contacts,users,gestion,wa_all_msgs,opps,pipelines,score_v2}.json
(solo consulta)."""
import json, re
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

try:
    _SC2 = json.load(open(DATA / 'score_v2.json'))
except Exception:
    _SC2 = {}

contacts = json.load(open(DATA / 'contacts.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW = datetime.now(timezone.utc)
_hoy = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

# ---------- helpers compartidos del dashboard ----------
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

STATUS_PTS = {'Negocio abierto':25,'En curso':15,'Intento de contacto':8,'Nuevo':5,'En Nutrición':3}
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

try:
    GESTION = json.load(open(DATA / 'gestion.json'))
except Exception:
    GESTION = {}

def intentos_of(cid):
    _g = GESTION.get(cid)
    _f = _g.get('f') if _g else None
    if _f:
        return [len(_f), len({x[0] for x in _f}),
                sum(1 for x in _f if x[1] == 'w'), sum(1 for x in _f if x[1] == 'c'),
                sum(1 for x in _f if x[1] == 'e'), sum(1 for x in _f if x[1] == 's')]
    return 0

# ---------- oportunidad en el pipeline ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DOP, giOP = dict_indexer()
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

# ---------- universo: la etiqueta de reactivación ----------
def es_reactivado(c):
    return any('reactivo' in t.lower() and 'nutricion' in t.lower() for t in (c.get('tags') or []))

REACT = [c for c in contacts if es_reactivado(c)]

DA, giA = dict_indexer()
DS, giS = dict_indexer()
DF, giF = dict_indexer()
DT, giT = dict_indexer()

ROWS = []
for c in REACT:
    a = USERS.get(c.get('assigned'), '(Sin asesor asignado)') if c.get('assigned') else '(Sin asesor asignado)'
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    ku = (c.get('enCursoPor') or '').strip() or '(Sin dato)'
    rl = c.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(x.strip() for x in rl if x and x.strip()) or '(Sin realtor)'
    _op = opp_of(c)
    ROWS.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c.get('email') or '', c.get('phone') or '',
        giA(a), giS(st), ku, giF(fuente_of(c)), rl,
        score_of(c), fecha_local(c.get('created')),
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        intentos_of(c['id']),
        (_SC2.get(c['id']) or {}).get('fl', ''),
        (_SC2.get(c['id']) or {}).get('d', []),
        ([giOP(_STG.get(_op['stage'], '(etapa desconocida)')),
          _ST_ES.get((_op.get('status') or '').lower(), _op.get('status') or ''),
          (_op.get('stageChange') or _op.get('created') or '')[:10]] if _op else 0)
    ])
ROWS.sort(key=lambda r: -r[8])

N = len(ROWS)
def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
ST_LIST = ordered(DS)

AVANZARON = sum(1 for r in ROWS if ST_LIST[r[4]] in ('En curso', 'Intento de contacto', 'Negocio abierto', 'Cliente'))
NUTRI = sum(1 for r in ROWS if ST_LIST[r[4]] == 'En Nutrición')
DESCARTADOS = sum(1 for r in ROWS if ST_LIST[r[4]] == 'Descartado')
CALIENTES = sum(1 for r in ROWS if r[8] >= 55)
TIBIOS = sum(1 for r in ROWS if 30 <= r[8] < 55)
OPP_ABIERTA = sum(1 for r in ROWS if r[14] and r[14][1] == 'abierta')
SC_PROM = round(sum(r[8] for r in ROWS) / N) if N else 0
SIN_HUMANO = sum(1 for r in ROWS if ordered(DA)[r[3]] in ('MARKETING PFS', '(Sin asesor asignado)'))
SIN_HORIZONTE = sum(1 for r in ROWS if r[5] in ('(Sin dato)', '_', 'No Aplica', 'Sin Oportunidad'))

def fmt(n): return f'{n:,}'.replace(',', '.')

def barras(counter_pairs, tot, tip):
    """lista [(etiqueta, n)] -> barras horizontales"""
    out = []
    for lbl, n in counter_pairs:
        pct = n / tot * 100 if tot else 0
        out.append(f'''<div class="brow" data-tip="{tip}">
<span class="blbl">{lbl}</span>
<div class="btrack"><div class="bfill" style="width:{pct:.0f}%"></div></div>
<span class="bnum">{fmt(n)} ({pct:.0f}%)</span></div>''')
    return ''.join(out)

st_cnt = Counter(ST_LIST[r[4]] for r in ROWS).most_common()
as_cnt = Counter(ordered(DA)[r[3]] for r in ROWS).most_common()
op_cnt = Counter((ordered(DOP)[r[14][0]] + ' · ' + r[14][1]) if r[14] else '(Sin oportunidad en pipeline)' for r in ROWS).most_common()

PAYLOAD = json.dumps({'rows': ROWS, 'ase': ordered(DA), 'sts': ST_LIST, 'fu': ordered(DF),
                      'tg': ordered(DT), 'opps': ordered(DOP)}, ensure_ascii=False)

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reactivaciones de leads</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:14.5px;line-height:1.5}}
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
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
[data-tip]{{cursor:help}}
th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:11px 13px;background:#fff}}
.kpi b{{font-size:22px;display:block}} .kpi span{{font-size:11.5px;color:var(--gris)}}
.intro{{background:var(--azul-oscuro);color:#F2F6FA;border-radius:13px;padding:16px 20px;font-size:13.8px;margin:16px 0;line-height:1.6}}
.intro b{{color:var(--amarillo)}}
h2{{font-size:16px;margin:22px 0 8px}}
.filtros{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:12px;padding:13px}}
.filtros label{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);font-weight:700;display:block;margin-bottom:3px}}
.filtros select,.filtros input{{width:100%;border:1px solid var(--gris-linea);border-radius:8px;padding:7px 9px;font-size:12.8px;background:#fff;color:var(--tinta)}}
.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:14px 0}}
.panel{{border:1px solid var(--gris-linea);border-radius:12px;padding:13px 16px}}
.panel h3{{font-size:13px;margin-bottom:8px}}
.brow{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12.3px}}
.blbl{{width:44%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.btrack{{flex:1;height:9px;background:var(--gris-fondo);border-radius:6px;overflow:hidden}}
.bfill{{height:100%;background:var(--amarillo);border-radius:6px}}
.bnum{{white-space:nowrap;color:var(--gris);font-size:11.5px}}
.reco{{border:1px solid var(--gris-linea);border-left:5px solid var(--amarillo);border-radius:10px;padding:12px 16px;margin:9px 0;font-size:13.3px}}
.reco b{{display:block;margin-bottom:2px}}
.guion{{background:#F3F7EC;border:1px solid #D6E4C4;border-radius:10px;padding:11px 14px;font-size:13px;font-style:italic;color:#3E5432;margin:10px 0}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
table{{border-collapse:collapse;width:100%;font-size:12.6px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
a{{color:var(--azul)}}
.tbox{{border:1px solid var(--gris-linea);border-radius:11px;overflow:auto;max-height:64vh;margin-top:10px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Reactivaciones de leads</h1>
<p>CRM comercial (solo lectura) · Leads que el flujo de nutrición despertó (etiqueta «reactivo - flujo nutricion») · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(N)}</b><span>leads reactivados</span></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html" class="act"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="intro">⚡ <b>Un lead reactivado es una segunda oportunidad que ya está pagada:</b> el flujo de nutrición
lo despertó y él REACCIONÓ (por eso el flujo le puso la etiqueta). Estos {fmt(N)} leads son la cosecha del flujo —
la regla de oro es responder su reacción <b>en menos de 1 hora con un humano</b>, calificar la intención
(¿invertir, vivir o arrendar?) y registrar el horizonte en el CRM. Abajo: quiénes son, en qué van y qué hacer con cada uno.</div>

<div class="kpis">
<div class="kpi" data-tip="Contactos con la etiqueta «reactivo - flujo nutricion»: el flujo automatizado los despertó y reaccionaron."><b>{fmt(N)}</b><span>leads reactivados</span></div>
<div class="kpi" data-tip="Reactivados que hoy están más allá de la nutrición: Intento de contacto, En curso, Negocio abierto o Cliente — la reactivación se convirtió en gestión comercial."><b style="color:var(--verde)">{fmt(AVANZARON)}</b><span>avanzaron a gestión</span></div>
<div class="kpi" data-tip="Reactivados que SIGUEN en status 'En Nutrición': reaccionaron pero nadie los ha tomado — la fuga nº1 de este informe."><b style="color:var(--naranja)">{fmt(NUTRI)}</b><span>siguen en nutrición</span></div>
<div class="kpi" data-tip="Reactivados con oportunidad ABIERTA en el pipeline de ventas."><b>{fmt(OPP_ABIERTA)}</b><span>con oportunidad abierta</span></div>
<div class="kpi" data-tip="Score v2 promedio de los reactivados (0-100)."><b>{str(SC_PROM).replace('.', ',')}</b><span>score promedio</span></div>
<div class="kpi" data-tip="Reactivados calientes (score ≥55) + tibios (30-54): los que hay que trabajar primero."><b style="color:var(--rojo)">{fmt(CALIENTES)} + {fmt(TIBIOS)}</b><span>calientes + tibios</span></div>
<div class="kpi" data-tip="Reactivados marcados Descartado DESPUÉS de haber reaccionado al flujo: contradicción a revisar uno a uno."><b style="color:var(--rojo)">{fmt(DESCARTADOS)}</b><span>descartados (revisar)</span></div>
</div>

<h2>Filtros</h2>
<div class="filtros">
<div><label>Asesor</label><select id="f-a"><option value="">Todos</option></select></div>
<div><label>Lead status</label><select id="f-s"><option value="">Todos</option></select></div>
<div><label>Fuente</label><select id="f-f"><option value="">Todas</option></select></div>
<div><label>Scoring (temperatura)</label><select id="f-t"><option value="">Todos</option>
<option value="hot">🔥 Calientes (≥55)</option><option value="warm">🌤 Tibios (30-54)</option><option value="cold">❄ Fríos (&lt;30)</option></select></div>
<div><label>Buscar (nombre, email, teléfono)</label><input id="f-q" placeholder="Escribe para filtrar…"></div>
</div>

<h2>Cómo están hoy los reactivados</h2>
<div class="grid3">
<div class="panel"><h3>Por lead status</h3>{barras(st_cnt, N, 'Distribución de los reactivados por su Lead Status actual en el CRM.')}</div>
<div class="panel"><h3>Por asesor</h3>{barras(as_cnt, N, 'Quién tiene asignado cada lead reactivado (owner del CRM).')}</div>
<div class="panel"><h3>Por etapa de oportunidad</h3>{barras(op_cnt, N, 'Etapa del embudo de ventas de la oportunidad de cada reactivado (cruce por email/teléfono con el pipeline).')}</div>
</div>

<h2>Leads reactivados <span id="cnt" style="color:var(--gris);font-weight:600;font-size:12px"></span></h2>
<div class="tbox"><table><thead><tr>
<th data-tip="Lead scoring v2 0-100. PASA EL MOUSE sobre el score de cada lead para ver POR QUÉ tiene esos puntos. Flags: 👍/👎 retroalimentación del asesor · 🏠 propiedad específica (MLS) · 💰 monto · 🛒 compra · ✋ respondió · ⏸ aplazado.">Score</th>
<th>Contacto</th><th>Email</th><th>Teléfono</th>
<th data-tip="Usuario del CRM asignado.">Asesor</th>
<th>Lead Status</th>
<th data-tip="Campo 'En curso por' del CRM (horizonte de oportunidad declarado).">En curso por</th>
<th data-tip="Si tiene OPORTUNIDAD en el pipeline de ventas y en qué etapa está, con su estado y fecha del último cambio. '—' = nunca entró al pipeline.">Etapa de oportunidad</th>
<th data-tip="Origen del lead (campo 'Fuente de contacto').">Origen</th>
<th data-tip="Realtor vinculado al contacto.">Realtor</th>
<th data-tip="Fecha de creación del lead en el CRM.">Creado</th>
<th data-tip="Intentos de contacto salientes: total · días distintos · canales (💬📞✉𝗌).">Intentos</th>
<th data-tip="Las principales acciones que el asesor debe ejecutar para CERRAR LA VENTA con este lead, según su diagnóstico de score. Pasa el mouse para el detalle.">Acciones para cerrar venta</th>
<th>Etiquetas</th>
<th data-tip="Escribirle directamente por WhatsApp.">WA</th>
</tr></thead><tbody id="tb"></tbody></table></div>

<h2>Recomendaciones</h2>
<div class="reco"><b>1. Los {fmt(NUTRI)} que siguen «En Nutrición» son la fuga principal.</b>
Reaccionaron al flujo y nadie los tomó: asignarlos HOY a un asesor humano (varios están en la bolsa MARKETING PFS),
con SLA de primer toque personal en menos de 1 hora desde la reacción. Un reactivado que vuelve a enfriarse
cuesta el doble de despertar la próxima vez.</div>
<div class="reco"><b>2. Calificar la intención en el primer toque.</b> {fmt(SIN_HORIZONTE)} de los {fmt(N)} no tienen
horizonte declarado («En curso por» vacío). La primera pregunta del asesor debe ser la calificadora —
¿comprar para invertir, para vivir o arrendar? — y registrarla en el CRM junto con el presupuesto.</div>
<div class="reco"><b>3. Priorizar por temperatura, no por orden de llegada.</b> Los {fmt(CALIENTES)} calientes y
{fmt(TIBIOS)} tibios van primero (la tabla ya viene ordenada por score). A los calientes que responden:
videollamada de precalificación en menos de 48 horas.</div>
<div class="reco"><b>4. Revisar los {fmt(DESCARTADOS)} descartados post-reactivación.</b> Si el flujo los despertó
y luego alguien los descartó, o el descarte fue un error o el motivo debe quedar registrado. Revisión
gerencial uno a uno — cruza con la hoja de Recuperación de leads.</div>
<div class="reco"><b>5. Medir el flujo cada mes.</b> Esta etiqueta es el KPI del flujo de nutrición: si el volumen
mensual de reactivados no crece, el flujo necesita nuevos ganchos (contenido, oferta, canal). Hoy la tasa de
avance a gestión es de {fmt(AVANZARON)}/{fmt(N)}.</div>
<div class="guion">💬 <b>Guion sugerido del primer toque humano:</b> «Hola [nombre], vi que reaccionaste a nuestro
contenido sobre inversión en Miami — soy [asesor] y quiero atenderte personalmente. Para orientarte mejor:
¿estás pensando en comprar para invertir, para vivir, o buscas arrendar? Te comparto opciones según lo que me digas.»</div>

<div class="warnpii"><b>⚠ Datos personales:</b> esta hoja contiene nombres, correos y teléfonos (Habeas Data). No publicarla ni circularla fuera del equipo comercial autorizado.</div>
<footer>Universo: contactos cuya lista de etiquetas contiene «reactivo» y «nutricion» (etiqueta que el flujo de
nutrición asigna cuando el lead reacciona). Score v2 0-100 con la fórmula de todo el dashboard (intención +
etapa + respuestas del lead + actividad reciente). Etapa de oportunidad por cruce email/teléfono con el
PIPELINE (si hay varias, la abierta más reciente). Generado desde la API de GHL, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
// búsqueda tolerante: texto en nombre/email y, si lo escrito tiene dígitos, compara solo dígitos contra el teléfono
// (así '(786) 932-6512', '786 932 6512' o '7869326512' encuentran +17869326512)
function matchQ(q, nombre, email, tel) {{
  if (!q) return true;
  if ((nombre + ' ' + email + ' ' + tel).toLowerCase().includes(q)) return true;
  const qd = q.replace(/[^0-9]/g, '');
  return qd.length >= 4 && (tel || '').replace(/[^0-9]/g, '').includes(qd);
}}
const scCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d ` + (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') : 'Sin intentos salientes registrados.';

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

function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tg[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
function scTip(d, fl, sc, st) {{
  if (!d || d.length < 4) return '';
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
  const e5 = d.length >= 5 && d[4] !== 0 ? (d[4] > 0 ? `el asesor dejó retroalimentación POSITIVA en sus notas (interesado, le gusta, agenda, tiene capital…): +${{d[4]}} pts` : `el asesor dejó retroalimentación NEGATIVA en sus notas (no interesa, sin capital, sin visa, molesto, cold…): ${{d[4]}} pts`) : 'sin retroalimentación del asesor en los últimos 6 meses (0 pts)';
  return `Este lead tiene ${{sc}} de 100 puntos por estas 5 razones: ① GANAS DE COMPRAR: ${{d[0]}} de 35 pts — ${{e1}}. ② ETAPA EN EL CRM: ${{d[1]}} de 25 pts — su lead status es «${{st}}». ③ RESPUESTAS DEL LEAD: ${{d[2]}} de 20 pts — ${{e3}}. ④ ACTIVIDAD RECIENTE: ${{d[3]}} de 20 pts — ${{e4}}. ⑤ RETROALIMENTACIÓN DEL ASESOR: ${{e5}}.`;
}}
const FLGV = {{P: '🏠', M: '💰', C: '🛒', R: '✋', Z: '⏸', G: '👍', B: '👎'}};
function opCellG(o) {{
  if (!o) return '<span style="color:#B9BDCC" data-tip="Este lead NO tiene oportunidad creada en el pipeline de ventas: nunca ha entrado al embudo comercial.">—</span>';
  const col = o[1] === 'abierta' ? '#1D7A46' : o[1] === 'ganada' ? '#0F6E56' : '#A33B3B';
  return `<span style="white-space:nowrap;cursor:help" data-tip="Tiene OPORTUNIDAD en el pipeline de ventas: etapa «${{esc(D.opps[o[0]])}}» (${{esc(o[1])}}). Último cambio de etapa: ${{esc(o[2] || 'sin fecha')}}."><b>${{esc(D.opps[o[0]])}}</b><small style="display:block;color:${{col}};font-size:.68rem">${{esc(o[1])}} · ${{esc(o[2] || '')}}</small></span>`;
}}
function tareasG(d, fl, sc, intTot) {{
  d = d && d.length >= 4 ? d : [0, 0, 0, 0, 0]; fl = fl || ''; const t = [];
  if (fl.indexOf('B') !== -1) t.push(['👎', 'Revisar la objeción que anotó el asesor', 'El asesor dejó retroalimentación negativa en sus notas: leerla antes de cualquier toque, resolver la objeción concreta (capital, visa, momento, precio) o pasar a nutrición con motivo registrado — no insistir a ciegas.']);
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

/* filtros */
const selA = document.getElementById('f-a'), selS = document.getElementById('f-s'),
      selF = document.getElementById('f-f'), selT = document.getElementById('f-t'),
      inQ = document.getElementById('f-q');
D.ase.forEach((a, i) => selA.add(new Option(a, i)));
D.sts.forEach((s, i) => selS.add(new Option(s, i)));
D.fu.forEach((f2, i) => selF.add(new Option(f2, i)));

function pasa(r) {{
  if (selA.value !== '' && r[3] !== +selA.value) return false;
  if (selS.value !== '' && r[4] !== +selS.value) return false;
  if (selF.value !== '' && r[6] !== +selF.value) return false;
  if (selT.value === 'hot' && r[8] < 55) return false;
  if (selT.value === 'warm' && (r[8] < 30 || r[8] >= 55)) return false;
  if (selT.value === 'cold' && r[8] >= 30) return false;
  const q = inQ.value.trim().toLowerCase();
  if (!matchQ(q, r[0], r[1], r[2])) return false;
  return true;
}}
function render() {{
  const view = D.rows.filter(pasa);
  document.getElementById('cnt').textContent = `(${{fN(view.length)}} de ${{fN(D.rows.length)}})`;
  document.getElementById('tb').innerHTML = view.map(r => {{
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = (r[2] || '').replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank">WA</a>' : ''}}` : '—';
    const sTip = scTip(r[13], r[12] || '', r[8], D.sts[r[4]]);
    const flgs = (r[12] || '').split('').map(ch => FLGV[ch] || '').join('');
    return `<tr><td style="white-space:nowrap${{sTip ? ';cursor:help' : ''}}"${{sTip ? ` data-tip="${{sTip}}"` : ''}}><span class="sc" style="background:${{scCol(r[8])}}">${{r[8]}}</span> ${{flgs}}</td>
    <td><b>${{esc(r[0])}}</b></td><td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
    <td>${{esc(D.ase[r[3]])}}</td><td>${{esc(D.sts[r[4]])}}</td><td>${{esc(r[5])}}</td>
    <td>${{opCellG(r[14])}}</td>
    <td>${{esc(D.fu[r[6]])}}</td><td>${{esc(r[7])}}</td><td>${{esc(r[9] || '—')}}</td>
    <td style="white-space:nowrap" data-tip="${{intTip(r[11])}}">${{intCell(r[11])}}</td>
    <td>${{tareasG(r[13], r[12], r[8], (r[11] && r[11][0]) || 0)}}</td>
    <td>${{tagsCell(r[10])}}</td><td>${{waBtn(dig)}}</td></tr>`;
  }}).join('') || '<tr><td colspan="15" style="color:var(--gris)">Sin leads con los filtros actuales.</td></tr>';
}}
[selA, selS, selF, selT].forEach(s => s.addEventListener('change', render));
inQ.addEventListener('input', render);
function arranque() {{
  [selA, selS, selF, selT].forEach(s => s.value = '');
  inQ.value = '';
  render();
}}
arranque();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranque(); }});
</script>
</body></html>'''

out = str(ROOT / f'reactivaciones-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB) | reactivados {N} | avanzaron {AVANZARON} | en nutrición {NUTRI} | descartados {DESCARTADOS}')
