#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de ADQUISICIÓN DE LEADS: análisis completo por medio/fuente — volumen y
momentum de llegada, calidad (conversión a cliente, descarte, temperatura, gestión
recibida), campañas detectadas por etiqueta, atribución digital (UTM/gclid) y
mercados por país. HTML autocontenido, misma lógica del resto del dashboard.
Lee scripts/data/{contacts,users,gestion,wa_all_msgs}.json (solo consulta)."""
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
        return 'Paid Search'
    if ('linkedin' in sl or 'linked in' in sl) and 'paid' in sl:
        return 'Paid LinkedIn'
    if ('linkedin' in sl or 'linked in' in sl):
        # todo lo demás de LinkedIn (organico explícito, formularios orgánicos, "LinkedIn" a secas) = orgánico
        return 'LinkedIn Orgánico'
    if sl in ('facebook', 'meta / facebook_mobile_feed', 'paid social', 'fb', 'facebook ads', 'meta ads'):
        return 'Paid Social'
    if ('instagram' in sl or 'tiktok' in sl or 'social media' in sl or 'redes' in sl) and ('organic' in sl or 'orgánic' in sl or 'social media' in sl or 'redes' in sl):
        return 'Social Media (orgánico)'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl or sl in ('rerefido', 'referral', 'pereonal', 'personall'):
        return 'Referidos / Personal'
    if sl.startswith('prensa'):
        return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog', 'pfsmain', 'external_form', 'miamisumejorinversion') or sl.endswith('pfsrealty.com'):
        # "web site" es el PUNTO DE CAPTURA (formulario/widget en la web), no el origen del tráfico.
        # El origen real está en el registro de atribución que GHL guarda al crear el contacto.
        a = c.get('attr') or {}
        ss = (a.get('sessionSource') or '').lower(); md = (a.get('medium') or '').lower()
        if 'organic search' in ss: return 'SEO (búsqueda orgánica)'
        if 'paid search' in ss: return 'Paid Search'
        if 'paid social' in ss: return 'Paid Social'
        if 'social' in ss: return 'Social Media (orgánico)'
        if 'direct' in ss: return 'Sitio Web (directo)'
        if 'referral' in ss: return 'Referidos / Personal'
        if 'crm' in ss or 'csv' in md or 'manual' in md: return 'Importaciones / creación manual'
        return 'Sitio Web (sin atribución)'
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
    if 'hubspot' in fl or 'migration' in fl or 'importa' in fl or 'creación manual' in fl: return 'Importaciones / listas'
    if 'referid' in fl or 'personal' in fl or 'aliado' in fl: return 'Referidos y aliados'
    if fl in ('antonio aguirre', 'pfs guardia'): return 'Equipo comercial'
    if any(k in fl for k in ('evento', 'celebra', 'simposio', 'torneo', 'master class', 'masterclass', 'mundial',
                             'concurso', 'cóctel', 'coctel', 'c�ctel', 'ágora', 'agora', 'amcham',
                             'cotelco', 'club lagos', 'campestre', 'salto', 'webinar', 'jornada', 'feria')):
        return 'Eventos'
    # lo explícitamente ORGÁNICO nunca es pauta, aunque nombre una red social
    if 'organic' in fl or 'orgánic' in fl or 'formulario' in fl or fl.startswith('sitio web') or fl.startswith('seo'):
        return 'Orgánico digital'
    # PAUTA DIGITAL: subcategorías Paid Search · Paid LinkedIn · Facebook (+ resto de pago)
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
DOP, giOP = dict_indexer()  # etapa de oportunidad en el pipeline

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
def opp_row(c):
    _op = opp_of(c)
    return ([giOP(_STG.get(_op['stage'], '(etapa desconocida)')),
             _ST_ES.get((_op.get('status') or '').lower(), _op.get('status') or ''),
             (_op.get('stageChange') or _op.get('created') or '')[:10],
             round(float(_op.get('value') or 0))] if _op else 0)
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
        giS(st), giK(ku), score_of(c), fecha_local(c['created']),
        giA(a),
        num(c.get('vecesContactado')) + num(c.get('salesActivities')),
        atn_of(c),
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        intentos_of(c['id']),
        giR(rl), giAT(at_lbl),
        respondio(c), giC(categoria_of(fuente_of(c))),
        (_SC2.get(c['id']) or {}).get('fl', ''),
        (_SC2.get(c['id']) or {}).get('d', []),
        opp_row(c)
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

# ---------- inversión por medio (scripts/inversiones.json, editable a mano) ----------
try:
    INV = json.load(open(Path(__file__).resolve().parent / 'inversiones.json'))
except Exception:
    INV = {'moneda': 'USD', 'fuentes': {}, 'categorias': {}}
# filas que SIEMPRE se muestran en su categoría aunque no tengan leads en la selección
FIJAS = {'Orgánico digital': ['SEO (búsqueda orgánica)', 'Sitio Web (directo)', 'Social Media (orgánico)', 'LinkedIn Orgánico'],
         'Pauta digital': ['Paid Search', 'Paid LinkedIn', 'Paid Social']}
for _cat, _fs in FIJAS.items():
    giC(_cat)
    for _f in _fs: giF(_f)
PAYLOAD = json.dumps({
    'rows': rows,
    'inv': INV, 'fijas': {ordered(DC).index(k): [ordered(DF).index(f) for f in v] for k, v in FIJAS.items()},
    'fuentes': ordered(DF), 'paises': ordered(DP), 'status': ordered(DS),
    'cursos': ordered(DK), 'asesores': ordered(DA), 'realtors': ordered(DR),
    'tags': ordered(DT), 'attrs': ordered(DAT), 'cats': ordered(DC),
    'opps': ordered(DOP),
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
<div><label data-tip="Filtra por el medio/fuente del lead: campo 'Fuente de contacto' del CRM con las variantes de Paid Search (Google Ads), Referidos, Prensa y Sitio Web agrupadas. Ordenado por volumen.">Medio / fuente</label><select id="f-f" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el país del lead, determinado por el prefijo internacional de su número móvil.">País (prefijo del móvil)</label><select id="f-p" autocomplete="off"></select></div>
<div><label data-tip="Filtra por el campo 'Lead Status' del CRM: en qué quedó el lead adquirido (Cliente, Descartado, En curso…).">Lead status</label><select id="f-s" autocomplete="off"></select></div>
<div><label data-tip="Filtra por la etapa de la oportunidad del lead en el pipeline de ventas. '(Sin oportunidad)' = nunca entró al pipeline.">Etapa de oportunidad</label><select id="f-o" autocomplete="off"></select></div>
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
<h2>🏆 Calidad de cada medio: la tabla maestra de adquisición</h2>
<p class="chart-sub">Agrupada por <b>categoría de medios</b> (pauta digital, orgánico, eventos, referidos…) con drill-down: clic en la fila de una categoría la expande a <b>todas</b> sus fuentes, sin agrupar ninguna en "otras" — para auditar exactamente qué contiene cada categoría. Cada nivel muestra: leads y score promedio → <b>tipificación de sus oportunidades en HOT / WARM / COLD</b> (por etapa del pipeline) → MQL y SQL → contactabilidad y tiempo de 1ª atención → % descartados → clientes, conversión y cierres. <b>Respeta todos los filtros activos (asesor, status, fechas…) excepto categoría y fuente.</b> Clic en una fuente = filtrarla y ver sus leads abajo.</p>
<div style="overflow-x:auto"><table style="min-width:2250px"><thead><tr>
<th data-tip="Categoría de medios (clic para expandir TODAS sus fuentes, ninguna se agrupa en otras) o fuente individual (clic para filtrar). Pauta digital: Paid Search (Google Ads y variantes), Paid LinkedIn y Paid Social (Facebook / Instagram / Meta) + resto de pago. Orgánico digital: SEO (búsqueda orgánica), Sitio Web (directo), Social Media (orgánico), LinkedIn Orgánico (todo LinkedIn no pagado), WhatsApp, Email, Prensa, oficinas y formularios. Los leads con fuente 'web site' se reclasifican por el registro de atribución de GHL (sessionSource): Organic Search→SEO, Direct→Sitio Web directo, Social→Social Media, Paid Social→Paid Social, CRM/CSV→Importaciones; sin atribución quedan como 'Sitio Web (sin atribución)'.">Categoría / fuente</th>
<th data-tip="Inversión en el medio (USD), tomada de scripts/inversiones.json — se diligencia a mano por fuente y/o categoría, con total y/o por mes. Con filtro de fechas suma solo los meses del rango; sin filtro usa el total. '—' = sin dato de inversión.">Inversión</th>
<th data-tip="Ingresos futuros: suma del VALOR registrado en las oportunidades ABIERTAS del pipeline de los leads de la fila (campo valor de la oportunidad en el CRM). Entre paréntesis: cuántas oportunidades tienen valor diligenciado — hoy solo una minoría lo tiene, así que es un piso, no el total.">Ingresos futuros</th>
<th data-tip="Leads adquiridos en la selección (respetan los filtros de arriba, salvo categoría y fuente).">Leads</th>
<th data-tip="Costo por lead = inversión ÷ leads de la selección. Solo se calcula donde hay inversión registrada.">CPL</th>
<th data-tip="% del total de la selección.">%</th>
<th data-tip="Lead scoring v2 promedio (0-100) de los leads de la fila.">Score prom.</th>
<th data-tip="Total de oportunidades creadas en el pipeline por los leads de la fila (HOT + WARM + COLD).">Opp. total</th>
<th data-tip="% de TODAS las oportunidades de la selección que aporta este medio (share).">% opp.</th>
<th data-tip="Oportunidades tipificadas HOT por su etapa en el pipeline: Date to Miami, Asistió Oficina Miami, Tour Miami, Toma Decisión (HOT), Recompra, Pending y Cierre (Elite Club). Entre paréntesis: % de las oportunidades de la fila.">Opp. HOT</th>
<th data-tip="% de las oportunidades HOT de la selección que aporta este medio (share).">% HOT</th>
<th data-tip="Oportunidades WARM: Cita/Asistió a jornada-evento-webinar, Cita Virtual, Asistió Presencial o Virtual, WARM, Llamada de Precalificación, Precalificación Financiera y Atención Contador.">Opp. WARM</th>
<th data-tip="% de las oportunidades WARM de la selección que aporta este medio (share).">% WARM</th>
<th data-tip="Oportunidades COLD: Nuevo Lead, Intento de Contacto, COLD y Sin Oportunidad.">Opp. COLD</th>
<th data-tip="% de las oportunidades COLD de la selección que aporta este medio (share).">% COLD</th>
<th data-tip="Leads de la fila que NO tienen oportunidad en el pipeline (nunca entraron al embudo de ventas).">Sin opp.</th>
<th data-tip="Costo por oportunidad = inversión ÷ TODAS las oportunidades creadas en el pipeline (HOT + WARM + COLD) de la selección. Solo donde hay inversión registrada.">Costo / opp.</th>
<th data-tip="% MQL: leads con señal de calificación de marketing — score ≥30 u oportunidad declarada (En curso por = Oportunidad…) o ya en Negocio abierto/Cliente.">MQL%</th>
<th data-tip="% SQL: leads aceptados por ventas — Negocio abierto o Cliente, o En curso CON oportunidad vigente. Todo SQL es MQL.">SQL%</th>
<th data-tip="% contactabilidad: leads que RESPONDIERON (mensaje entrante de WhatsApp o llamada contestada).">Contactab.</th>
<th data-tip="Tiempo promedio de 1ª atención (primer mensaje saliente de WhatsApp) de los leads con conversación.">1ª atención</th>
<th data-tip="% de leads que terminó con Lead Status Descartado.">Desc%</th>
<th data-tip="Leads que hoy son clientes.">Clientes</th>
<th data-tip="Tasa de conversión: clientes ÷ leads.">Conv%</th>
<th data-tip="Oportunidades en etapa Cierre (Elite Club) o ganadas.">En cierre</th>
<th data-tip="De los leads de la selección, cuántos llegaron en los últimos 90 días (informativa).">Últ. 90d</th>
<th data-tip="Momentum: variación de los últimos 90 días vs los 90 anteriores. ▲ crece, ▼ cae. Estable = ±15%.">Momentum</th>
</tr></thead><tbody id="tb-fu"></tbody></table></div>
</div>

<div class="chart-sec">
<h2>🥧 Cómo se reparte la selección</h2>
<p class="chart-sub">Los cortes clave de los leads que cumplen los filtros de arriba: de dónde vienen, en qué lead status están, en qué etapa del pipeline van, qué temperatura tienen — y de qué origen salen las oportunidades HOT, WARM y COLD. Clic en una porción aplica (o quita) ese filtro.</p>
<div class="pies">
<div class="pie-box"><h3 data-tip="Reparto de los leads de la selección por medio/fuente (top 7 + Otros). Clic = filtrar por esa fuente.">📣 Por origen (fuente)</h3>
<svg id="pie-fu" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-fu"></div></div>
<div class="pie-box"><h3 data-tip="Reparto por Lead Status del CRM (En curso, En Nutrición, Cliente, Descartado…). Clic = filtrar por ese status.">🏷 Por lead status</h3>
<svg id="pie-st" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-st"></div></div>
<div class="pie-box"><h3 data-tip="Reparto por etapa de la oportunidad en el pipeline de ventas (Nuevo Lead, Intento de Contacto, WARM, HOT, Cierre…). '(Sin oportunidad)' = el lead nunca entró al pipeline. Clic = filtrar por esa etapa.">🪜 Por etapa de oportunidad</h3>
<svg id="pie-op" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-op"></div></div>
<div class="pie-box"><h3 data-tip="Reparto por temperatura del lead scoring v2: Caliente ≥55, Tibio 30-54, Frío 10-29, Sin señales <10. Clic = filtrar por esa temperatura.">🌡 Por lead scoring</h3>
<svg id="pie-sc" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-sc"></div></div>
<div class="pie-box"><h3 data-tip="De los leads de la selección que tienen oportunidad en el pipeline (HOT + WARM + COLD): de qué origen vienen. Clic = filtrar por esa fuente.">🪜 Origen de TODAS las oportunidades</h3>
<svg id="pie-oppall" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-oppall"></div></div>
<div class="pie-box"><h3 data-tip="De los leads de la selección cuya oportunidad está en etapa HOT del pipeline (Date to Miami, Asistió Oficina Miami, Tour Miami, Toma Decisión, Recompra, Pending, Cierre): de qué origen vienen. Clic = filtrar por esa fuente.">🔥 Origen de las oportunidades HOT</h3>
<svg id="pie-hot" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-hot"></div></div>
<div class="pie-box"><h3 data-tip="De los leads de la selección cuya oportunidad está en etapa WARM (Cita/Asistió jornada, Cita Virtual, Asistió Presencial/Virtual, WARM, Precalificación, Contador): de qué origen vienen. Clic = filtrar por esa fuente.">🌤 Origen de las oportunidades WARM</h3>
<svg id="pie-warm" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-warm"></div></div>
<div class="pie-box"><h3 data-tip="De los leads de la selección cuya oportunidad está en etapa COLD (Nuevo Lead, Intento de Contacto, COLD, Sin Oportunidad): de qué origen vienen. Clic = filtrar por esa fuente.">❄ Origen de las oportunidades COLD</h3>
<svg id="pie-cold" viewBox="0 0 340 230"></svg><div class="pleg" id="pleg-cold"></div></div>
</div>
</div>

<div class="chart-sec" style="margin-top:20px">
<h2>📄 Leads de la selección</h2>
<p class="chart-sub">Ordenados por score. Con un filtro de fuente activo, esta es la lista de leads que trajo ese medio.</p>
<div id="ltab" style="overflow-x:auto"></div>
</div>

<div class="warnpii"><b>⚠ Datos personales:</b> este archivo contiene nombres, correos y teléfonos de {fmt(TOTAL)} personas — es la base de datos misma (Habeas Data). No publicarlo ni circularlo fuera del equipo comercial autorizado.</div>
<footer>Universo: los {fmt(TOTAL)} contactos del CRM. Fuente = campo "Fuente de contacto" con las familias de Paid Search (Google Ads), Referidos, Prensa y Sitio Web agrupadas; vacío = "(Sin fuente)". País por prefijo internacional del móvil. Conversión = Lead Status "Cliente" ÷ leads (con rango de fechas mide el cierre de esa camada). Descarte = Lead Status "Descartado". Score 0-100 con la fórmula de todo el dashboard. 1ª atención = primer mensaje saliente de WhatsApp menos creación del lead (solo leads con conversación). Campaña = primera etiqueta no genérica. Atribución = registro attributionSource de la plataforma. Generado desde la API de GHL, solo consulta.</footer>
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
const atnT = h => h < 1 ? Math.round(h * 60) + ' min' : h < 48 ? h.toLocaleString('es-CO', {{maximumFractionDigits: 0}}) + ' h' : (h / 24).toLocaleString('es-CO', {{maximumFractionDigits: 0}}) + ' días';
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
// etapa de oportunidad: ordenada por volumen en la base + '(Sin oportunidad)' al final
(() => {{ const cnt = new Map(); D.rows.forEach(x => {{ if (x[20]) cnt.set(x[20][0], (cnt.get(x[20][0]) || 0) + 1); }});
  const ids = [...cnt.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
  fill('f-o', ids.concat([-1]), ids.map(i => D.opps[i]).concat(['(Sin oportunidad)'])); }})();

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
  const f = g('f-f'), p = g('f-p'), s = g('f-s'), cc = g('f-c'), o = g('f-o'), q = g('f-q').trim().toLowerCase();
  return D.rows.filter(x =>
    (exceptos.includes('c') || cc === '' || x[17] == cc) &&
    (exceptos.includes('o') || o === '' || (o === '-1' ? !x[20] : (x[20] && x[20][0] == o))) &&
    (exceptos.includes('f') || f === '' || x[3] == f) &&
    (exceptos.includes('p') || p === '' || x[4] == p) &&
    (exceptos.includes('s') || s === '' || x[5] == s) &&
    (exceptos.includes('t') || matchTemp(x[7])) && inFecha(x) &&
    matchQ(q, x[0], x[1], x[2]));
}}

let view = [];
function apply() {{
  view = filtro([]).slice().sort((a, b) => b[7] - a[7]);
  shown = PAGE;
  renderKpis(); renderPies(); renderFuentes(); renderTabla();
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
  const pc = v => n ? (v / n * 100).toFixed(0).replace('.', ',') + '%' : '—';
  document.getElementById('adq-kpis').innerHTML =
    kp(fmtN(n), 'leads adquiridos (vista)', 'Leads de la selección actual según los filtros.') +
    kp(fmtN(d90), 'llegados últimos 90 días', 'Leads de la vista creados en los últimos 90 días: el ritmo de adquisición reciente.') +
    kp(fmtN(cli) + ` <small style="font-size:12px">(${{pc(cli)}})</small>`, 'clientes · conversión', 'Leads de la vista que hoy son clientes, y la tasa de conversión de la selección. Con rango de fechas mide el cierre de esa camada.', 'var(--verde)') +
    kp(fmtN(desc) + ` <small style="font-size:12px">(${{pc(desc)}})</small>`, 'descartados · tasa', 'Leads de la vista que terminaron descartados: adquisición que se botó.', 'var(--rojo)') +
    kp(fmtN(cal), 'calificados (🔥+🌤 score ≥30)', 'Leads calientes + tibios de la vista: el inventario con señales de compra vigentes.', 'var(--naranja)') +
    kp(n ? (sum / n).toLocaleString('es-CO', {{maximumFractionDigits: 0}}) : '—', 'score promedio', 'Temperatura promedio de la selección (lead scoring 0-100).') +
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
    tip: `${{nombres[i]}}: ${{fmtN(c)}} leads (${{(c / base.length * 100).toFixed(0)}}% de la selección). Clic para aplicar/quitar el filtro de ${{titulo}}.`,
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
function pieGen(svgId, legId, keyOf, labelOf, exc, onClick, colores, pre, centro) {{
  let base = filtro([exc]);
  if (pre) base = base.filter(pre);
  const cnt = new Map();
  base.forEach(x => {{ const k = keyOf(x); cnt.set(k, (cnt.get(k) || 0) + 1); }});
  const top = [...cnt.entries()].sort((a, b) => b[1] - a[1]);
  const datos = top.slice(0, 7).map(([k, c], j) => ({{
    label: labelOf(k), val: c, color: (colores && colores[k]) || PIE_COL[j],
    tip: `${{labelOf(k)}}: ${{fmtN(c)}} leads (${{(c / base.length * 100).toFixed(0)}}% de la selección). Clic para aplicar/quitar el filtro.`,
    click: onClick ? () => onClick(k) : null
  }}));
  const resto = top.slice(7).reduce((t, [, c]) => t + c, 0);
  if (resto) datos.push({{label: 'Otros', val: resto, color: '#C9D6E4', tip: `Otros ${{top.length - 7}} valores: ${{fmtN(resto)}} leads.`, click: null}});
  drawPie(svgId, legId, datos, centro || 'leads');
}}
const TEMP_OF = sc => sc >= 55 ? 'hot' : sc >= 30 ? 'warm' : sc >= 10 ? 'cold' : 'none';
const TEMP_LBL = {{hot: '🔥 Caliente (≥55)', warm: '🌤 Tibio (30-54)', cold: '❄ Frío (10-29)', none: 'Sin señales (<10)'}};
const TEMP_COL = {{hot: '#D64545', warm: '#AA9664', cold: '#3A566B', none: '#8A99A8'}};
function renderPies() {{
  pieDe('pie-fu', 'pleg-fu', 3, D.fuentes, 'f-f', 'fuente', 'f');
  pieDe('pie-st', 'pleg-st', 5, D.status, 'f-s', 'lead status', 's');
  pieGen('pie-op', 'pleg-op', x => x[20] ? x[20][0] : -1, k => k < 0 ? '(Sin oportunidad)' : D.opps[k], 'o',
    k => {{ const sel = document.getElementById('f-o'); sel.value = sel.value == k ? '' : k; apply(); }});
  pieGen('pie-sc', 'pleg-sc', x => TEMP_OF(x[7]), k => TEMP_LBL[k], 't',
    k => {{ const sel = document.getElementById('f-t'); sel.value = sel.value == k ? '' : k; apply(); }}, TEMP_COL);
  // por origen, restringido a la tipificación de la oportunidad (HOT / WARM / COLD)
  const clickFu = k => {{ const sel = document.getElementById('f-f'); sel.value = sel.value == k ? '' : k; apply(); }};
  const esTipo = tp => x => x[20] && tipoOpp(D.opps[x[20][0]] || '') === tp;
  pieGen('pie-oppall', 'pleg-oppall', x => x[3], k => D.fuentes[k], 'f', clickFu, null, x => !!x[20], 'oportunidades');
  pieGen('pie-hot', 'pleg-hot', x => x[3], k => D.fuentes[k], 'f', clickFu, null, esTipo('hot'), 'opp. HOT');
  pieGen('pie-warm', 'pleg-warm', x => x[3], k => D.fuentes[k], 'f', clickFu, null, esTipo('warm'), 'opp. WARM');
  pieGen('pie-cold', 'pleg-cold', x => x[3], k => D.fuentes[k], 'f', clickFu, null, esTipo('cold'), 'opp. COLD');
}}

/* ---------- tabla maestra: categoría → fuente (drill-down) ---------- */
const EXP = new Set();
function mkAgg() {{ return {{n: 0, cli: 0, desc: 0, sum: 0, atnS: 0, atnN: 0, d90: 0, p90: 0, resp: 0, mql: 0, sql: 0, opp: 0, oHot: 0, oWarm: 0, oCold: 0, oCierre: 0, valAb: 0, valAbN: 0}}; }}
// TIPIFICACIÓN de la oportunidad por bloque del embudo (etapa del PIPELINE):
//   COLD = Nuevo Lead · Intento de Contacto · COLD · Sin Oportunidad
//   WARM = Cita/Asistió jornada · Cita Virtual · Asistió Presencial/Virtual · WARM · Llamada/Precalificación financiera · Atención Contador
//   HOT  = Date to Miami · Asistió Oficina Miami · Tour Miami · Toma Decision (HOT) · Recompra · Pending · Cierre (Elite Club)
const RE_HOT = /date to miami|oficina miami|tour miami|toma decision|hot|recompra|pending|cierre/i;
const RE_WARM = /cita|asisti|warm|precalificaci|contador/i;
const RE_CIERRE = /cierre/i;
function tipoOpp(et) {{ if (RE_HOT.test(et)) return 'hot'; if (RE_WARM.test(et)) return 'warm'; return 'cold'; }}
function addTo(a, x, c90, c180) {{
  a.n++; a.sum += x[7];
  if (x[5] === CLI_I) a.cli++;
  if (x[5] === DESC_I) a.desc++;
  if (x[11] >= 0) {{ a.atnS += x[11]; a.atnN++; }}
  if (x[8] >= c90) a.d90++; else if (x[8] >= c180) a.p90++;
  if (x[16]) a.resp++;
  if (esMQL(x)) a.mql++;
  if (esSQL(x)) a.sql++;
  const o = x[20];
  if (o) {{
    a.opp++;
    const et = D.opps[o[0]] || '';
    const tp = tipoOpp(et);
    if (tp === 'hot') a.oHot++; else if (tp === 'warm') a.oWarm++; else a.oCold++;
    if (RE_CIERRE.test(et) || o[1] === 'ganada') a.oCierre++;
    if (o[1] === 'abierta' && o[3] > 0) {{ a.valAb += o[3]; a.valAbN++; }}
  }}
}}
// ---------- inversión (scripts/inversiones.json) según el filtro de fechas ----------
function invDe(entry) {{
  if (!entry) return null;
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  const meses = entry.meses || {{}};
  const hayMeses = Object.keys(meses).length > 0;
  if (!d1 && !d2) {{
    if (entry.total) return entry.total;
    if (hayMeses) return Object.values(meses).reduce((t, v) => t + (+v || 0), 0);
    return null;
  }}
  if (!hayMeses) return null;   // hay filtro de fechas pero solo hay un total: no se puede prorratear con certeza
  const m1 = d1 ? d1.slice(0, 7) : '0000-00', m2 = d2 ? d2.slice(0, 7) : '9999-99';
  let t = 0, alguno = false;
  Object.entries(meses).forEach(([m, v]) => {{ if (m >= m1 && m <= m2) {{ t += (+v || 0); alguno = true; }} }});
  return alguno ? t : null;
}}
const invFuente = nombre => invDe((D.inv.fuentes || {{}})[nombre]);
const invCat = (ci, porFu) => {{
  // categoría = inversión propia + suma de la inversión de sus fuentes
  let t = invDe((D.inv.categorias || {{}})[D.cats[ci]]), alguno = t !== null;
  [...porFu.keys()].filter(k => k.startsWith(ci + ':')).forEach(k => {{
    const v = invFuente(D.fuentes[+k.split(':')[1]]);
    if (v !== null) {{ t = (t || 0) + v; alguno = true; }}
  }});
  // fuentes fijas sin leads en la selección también pueden tener inversión
  (D.fijas[ci] || []).forEach(fi => {{ if (!porFu.has(ci + ':' + fi)) {{ const v = invFuente(D.fuentes[fi]); if (v !== null) {{ t = (t || 0) + v; alguno = true; }} }} }});
  return alguno ? t : null;
}};
const MON = D.inv.moneda || 'USD';
const money = v => v === null ? '<span style="color:#B9BDCC">—</span>' : `<b>${{MON === 'USD' ? 'US$' : MON + ' '}}${{Math.round(v).toLocaleString('es-CO')}}</b>`;
const cpoTxt = (v, n) => v === null ? '<span style="color:#B9BDCC">—</span>' : n ? `<b>US$${{Math.round(v / n).toLocaleString('es-CO')}}</b>` : '<span style="color:var(--rojo)" data-tip="Hay inversión pero 0 oportunidades en la selección">sin opp.</span>';
const cplTxt = (v, n) => v === null ? '<span style="color:#B9BDCC">—</span>' : n ? `<b>US$${{(v / n).toLocaleString('es-CO', {{maximumFractionDigits: 0}})}}</b>` : '<span style="color:var(--rojo)" data-tip="Hay inversión pero 0 leads en la selección">sin leads</span>';
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
  Object.keys(D.fijas).forEach(ci => {{ if (!porCat.has(+ci)) porCat.set(+ci, mkAgg()); }});
  // totales de oportunidades de la selección (denominador del % por medio)
  const TOT = mkAgg(); base.forEach(x => addTo(TOT, x, c90, c180));
  const shr = (v, t) => t ? `<small style="color:var(--gris)">${{(v / t * 100).toFixed(0)}}%</small>` : '';
  const pcc = (v, n) => n ? (v / n * 100).toFixed(0).replace('.', ',') + '%' : '—';
  const momTxt = a => {{
    if (a.p90 >= 5 || a.d90 >= 5) {{
      const d = a.p90 ? (a.d90 - a.p90) / a.p90 * 100 : 100;
      if (d > 15) return `<b style="color:var(--verde)">▲ ${{d.toFixed(0)}}%</b>`;
      if (d < -15) return `<b style="color:var(--rojo)">▼ ${{Math.abs(d).toFixed(0)}}%</b>`;
      return '<span style="color:var(--gris)">estable</span>';
    }}
    return (!a.d90 && !a.p90) ? '<span style="color:var(--gris)">sin llegada</span>' : '<span style="color:var(--gris)">estable</span>';
  }};
  const oPct = (v, a) => a.opp ? ` <small style="color:var(--gris)">(${{(v / a.opp * 100).toFixed(0)}}%)</small>` : '';
  const celdas = (a, inv) => `
    <td style="white-space:nowrap">${{money(inv)}}</td>
    <td style="white-space:nowrap">${{a.valAb ? `<b>US$${{Math.round(a.valAb).toLocaleString('es-CO')}}</b> <small style="color:var(--gris)">(${{a.valAbN}})</small>` : '<span style="color:#B9BDCC">—</span>'}}</td>
    <td><b>${{fmtN(a.n)}}</b></td><td style="white-space:nowrap">${{cplTxt(inv, a.n)}}</td><td>${{pcc(a.n, base.length)}}</td>
    <td><b>${{a.n ? (a.sum / a.n).toFixed(0).replace('.', ',') : '—'}}</b></td>
    <td style="white-space:nowrap"><b>${{fmtN(a.opp)}}</b></td><td>${{shr(a.opp, TOT.opp)}}</td>
    <td style="white-space:nowrap;color:var(--rojo);font-weight:700">${{fmtN(a.oHot)}}${{oPct(a.oHot, a)}}</td><td>${{shr(a.oHot, TOT.oHot)}}</td>
    <td style="white-space:nowrap;color:var(--naranja);font-weight:700">${{fmtN(a.oWarm)}}${{oPct(a.oWarm, a)}}</td><td>${{shr(a.oWarm, TOT.oWarm)}}</td>
    <td style="white-space:nowrap;color:var(--azul);font-weight:700">${{fmtN(a.oCold)}}${{oPct(a.oCold, a)}}</td><td>${{shr(a.oCold, TOT.oCold)}}</td>
    <td style="white-space:nowrap;color:var(--gris)">${{fmtN(a.n - a.opp)}}</td>
    <td style="white-space:nowrap">${{cpoTxt(inv, a.opp)}}</td>
    <td style="color:var(--naranja);font-weight:700">${{pcc(a.mql, a.n)}}</td>
    <td style="color:var(--rojo);font-weight:700">${{pcc(a.sql, a.n)}}</td>
    <td><b style="color:${{a.n && a.resp / a.n >= .3 ? 'var(--verde)' : 'var(--tinta)'}}">${{pcc(a.resp, a.n)}}</b></td>
    <td style="white-space:nowrap">${{a.atnN ? atnT(a.atnS / a.atnN) : '—'}}</td>
    <td style="color:${{a.n && a.desc / a.n >= 0.2 ? 'var(--rojo)' : 'var(--tinta)'}};font-weight:700">${{pcc(a.desc, a.n)}}</td>
    <td>${{fmtN(a.cli)}}</td><td><b style="color:${{a.n && a.cli / a.n >= 0.035 ? 'var(--verde)' : 'var(--tinta)'}}">${{pcc(a.cli, a.n)}}</b></td>
    <td style="color:var(--verde);font-weight:700">${{fmtN(a.oCierre)}}</td>
    <td>${{fmtN(a.d90)}}</td><td style="white-space:nowrap">${{momTxt(a)}}</td>`;
  let out = '';
  [...porCat.entries()].sort((x, y) => y[1].n - x[1].n).forEach(([ci, a]) => {{
    const abierto = EXP.has(ci);
    out += `<tr class="clkd" data-cat="${{ci}}" style="background:var(--gris-fondo)" data-tip="${{esc(D.cats[ci])}}: ${{fmtN(a.n)}} leads en ${{[...porFu.keys()].filter(k => k.startsWith(ci + ':')).length}} fuentes. Clic para ${{abierto ? 'colapsar' : 'expandir'}} sus fuentes.">
      <td style="white-space:nowrap"><b>${{abierto ? '▾' : '▸'}} ${{esc(D.cats[ci])}}</b></td>${{celdas(a, invCat(ci, porFu))}}</tr>`;
    if (abierto) {{
      const fus = [...porFu.entries()].filter(([k]) => k.startsWith(ci + ':'))
        .map(([k, a2]) => [+k.split(':')[1], a2]).sort((x, y) => y[1].n - x[1].n);
      // TODAS las fuentes de la categoría, sin agrupar en "Otras": auditoría completa de qué contiene cada categoría
      // + filas FIJAS (SEO, Social Media, LinkedIn Orgánico, Paid Search, Paid LinkedIn, Facebook) aunque tengan 0 leads
      (D.fijas[ci] || []).forEach(fi => {{ if (!fus.some(([f2]) => f2 === fi)) fus.push([fi, mkAgg()]); }});
      fus.sort((x, y) => y[1].n - x[1].n);
      fus.forEach(([fi, a2]) => {{
        out += `<tr class="clkd" data-f="${{fi}}" data-tip="${{esc(D.fuentes[fi])}}: ${{fmtN(a2.n)}} leads. Clic para filtrar por esta fuente y ver sus leads abajo.">
          <td style="white-space:nowrap;padding-left:28px${{a2.n ? '' : ';color:var(--gris)'}}" title="${{esc(D.fuentes[fi])}}">${{esc(D.fuentes[fi]).slice(0, 44)}}</td>${{celdas(a2, invFuente(D.fuentes[fi]))}}</tr>`;
      }});
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
/* ---------- tabla de leads ---------- */
function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tags[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
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
function opCellG(o, DOPP) {{
  if (!o) return '<span style="color:#B9BDCC" data-tip="Este lead NO tiene oportunidad creada en el pipeline de ventas: nunca ha entrado al embudo comercial.">—</span>';
  const col = o[1] === 'abierta' ? '#1D7A46' : o[1] === 'ganada' ? '#0F6E56' : '#A33B3B';
  return `<span style="white-space:nowrap;cursor:help" data-tip="Tiene OPORTUNIDAD en el pipeline de ventas: etapa «${{esc(DOPP[o[0]])}}» (${{esc(o[1])}}). Último cambio de etapa: ${{esc(o[2] || 'sin fecha')}}."><b>${{esc(DOPP[o[0]])}}</b><small style="display:block;color:${{col}};font-size:.68rem">${{esc(o[1])}} · ${{esc(o[2] || '')}}</small></span>`;
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
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank">WA</a>' : ''}}` : '—';
    const sTip = scTip(r, r[19], r[18] || '', r[7], D.status[r[5]]);
    const flgs = (r[18] || '').split('').map(ch => FLGV[ch] || '').join('');
    return `<tr><td style="white-space:nowrap${{sTip ? ';cursor:help' : ''}}"${{sTip ? ` data-tip="${{sTip}}"` : ''}}><span class="sc" style="background:${{scoreCol(r[7])}}">${{r[7]}}</span> ${{flgs}}</td>
      <td><b>${{esc(r[0])}}</b></td><td>${{esc(D.asesores[r[9]])}}</td>
      <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
      <td>${{esc(D.fuentes[r[3]])}}</td><td>${{esc(D.paises[r[4]])}}</td>
      <td>${{esc(D.status[r[5]])}}</td><td>${{esc(D.cursos[r[6]])}}</td>
      <td>${{opCellG(r[20], D.opps)}}</td><td>${{esc(D.realtors[r[14]])}}</td><td>${{esc(r[8] || '—')}}</td>
      <td style="white-space:nowrap" data-tip="${{intTip(r[13])}}">${{intCell(r[13])}}</td>
      <td data-tip="${{intTip(r[13])}}">${{canCell(r[13])}}</td>
      <td>${{tareasG(r[19], r[18], r[7], (r[13] && r[13][0]) || 0)}}</td>
      <td>${{tagsCell(r[12])}}</td><td>${{waBtn(dig)}}</td></tr>`;
  }}).join('');
  document.getElementById('ltab').innerHTML =
    `<table style="min-width:1150px"><thead><tr>
     <th data-tip="Lead scoring v2 0-100 (misma fórmula de todo el dashboard). PASA EL MOUSE sobre el score de cada lead para ver POR QUÉ tiene esos puntos. Flags: 🏠 propiedad específica (MLS) · 💰 monto · 🛒 compra · ✋ respondió · ⏸ aplazado.">Score</th>
     <th>Lead</th><th data-tip="Usuario del CRM asignado.">Asesor</th>
     <th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp.">Teléfono</th>
     <th data-tip="Medio/fuente por el que se adquirió el lead.">Fuente</th>
     <th data-tip="País por prefijo del móvil.">País</th>
     <th>Lead Status</th><th>En curso por</th>
     <th data-tip="Si el lead tiene OPORTUNIDAD creada en el pipeline de ventas y en qué etapa del embudo está, con su estado y fecha del último cambio. Cruce por email/teléfono; '—' = nunca entró al pipeline.">Etapa de oportunidad</th>
     <th data-tip="Realtor vinculado al contacto (campo del CRM).">Realtor</th>
     <th data-tip="Fecha de adquisición (creación en el CRM).">Creado</th>
     <th data-tip="Intentos de contacto salientes: total · días distintos. Cobertura completa para carteras humanas; para el resto solo WhatsApp.">Intentos</th>
     <th data-tip="Canales usados: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS.">Canales</th>
     <th data-tip="Las principales acciones que el asesor debe ejecutar para CERRAR LA VENTA con este lead, según su diagnóstico de score. Pasa el mouse para el detalle.">Acciones para cerrar venta</th>
     <th>Etiquetas</th>
     <th data-tip="Escribirle directamente por WhatsApp.">WA</th>
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

['f-c', 'f-f', 'f-p', 'f-s', 'f-o', 'f-t', 'f-d1', 'f-d2'].forEach(id =>
  document.getElementById(id).addEventListener('change', apply));
document.getElementById('f-q').addEventListener('input', apply);
function reset() {{
  ['f-c', 'f-f', 'f-p', 'f-s', 'f-o', 'f-t', 'f-d1', 'f-d2'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-q').value = '';
  apply();
}}
/* arranque limpio contra la restauración de formularios del navegador */
function arranque() {{ reset(); }}
arranque();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranque(); }});
setTimeout(() => {{
  const alguno = ['f-c', 'f-f', 'f-p', 'f-s', 'f-o', 'f-t', 'f-q', 'f-d1', 'f-d2'].some(id => document.getElementById(id).value !== '');
  if (alguno) arranque();
}}, 250);
</script>
</body></html>'''

out = str(ROOT / f'adquisicion-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
cli = sum(1 for r in rows if r[5] == STATUS_ORDER.index('Cliente'))
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print(f'leads {TOTAL} | fuentes {len(DF)} | paises {len(DP)} | clientes {cli} | attr {ATTR_COV}')
