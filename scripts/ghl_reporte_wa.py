#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría de conversaciones de WhatsApp ([empresa]): métricas por asesor y fuente
sobre TODAS las conversaciones + análisis cualitativo de una muestra de 224 convos
(1.119 mensajes) leída manualmente. Lee scripts/data/{convos,contacts,users,wa_sample}.json.
Solo lectura: nada se escribe en el CRM. Genera auditoria-whatsapp-pfs-AAAA-MM-DD.html."""
import json, html, statistics
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

# ---------- score v2 precalculado (notas, tareas, conversaciones, reciprocidad, recencia real) ----------
try:
    _SC2 = json.load(open(DATA / 'score_v2.json'))
except Exception:
    _SC2 = {}

convos   = json.load(open(DATA / 'convos.json'))
contacts = {c['id']: c for c in json.load(open(DATA / 'contacts.json'))}
users    = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
sample   = json.load(open(DATA / 'wa_sample.json'))
pendmsgs = json.load(open(DATA / 'pend_msgs.json'))
workflows = json.load(open(DATA / 'workflows.json'))

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
_hoy = datetime.now()
NOW_TS = _hoy.timestamp() * 1000

# ---------- lead scoring (misma fórmula del reporte de contactos) ----------
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
            d = (datetime.now(datetime.fromisoformat(str(la).replace('Z', '+00:00')).tzinfo)
                 - datetime.fromisoformat(str(la).replace('Z', '+00:00'))).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'
def fmt(n): return f'{n:,}'.replace(',', '.')
def pct(x): return f'{x:.1f}'.replace('.', ',') + '%'

# ---------- universo completo WhatsApp ----------
wa = [c for c in convos if c['lastType'] == 'TYPE_WHATSAPP']
astat = defaultdict(lambda: [0, 0])
for c in wa:
    a = users.get(c['assigned'], '(Sin asesor)')
    astat[a][0] += 1
    if c['lastDir'] == 'inbound': astat[a][1] += 1
TOTAL_WA = len(wa)
ESPERANDO = sum(v[1] for v in astat.values())

def grupo(src):
    s = ' '.join((src or '').split()); sl = s.lower()
    if not sl or sl == '<unspecified>': return '(Sin fuente)'
    if 'google' in sl or sl.startswith('goo ') or sl == 'paid search': return 'Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl: return 'Referidos / Personal'
    if sl.startswith('prensa'): return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'): return 'Sitio Web'
    return s
fstat = defaultdict(lambda: [0, 0])
for c in wa:
    ct = contacts.get(c['contactId'])
    f = grupo(ct['source']) if ct else '(sin match)'
    fstat[f][0] += 1
    if c['lastDir'] == 'inbound': fstat[f][1] += 1

# ---------- muestra: dinámica ----------
def parse(d):
    try: return datetime.fromisoformat(d.replace('Z', '+00:00'))
    except Exception: return None
per = defaultdict(lambda: {'rts': [], 'convs': 0, 'mono': 0, 'dial': 0})
for cv in sample:
    p = per[cv['asesor']]; p['convs'] += 1
    msgs = cv['msgs']
    inb = sum(1 for m in msgs if m['dir'] == 'inbound')
    if inb == 0: p['mono'] += 1
    if inb >= 2: p['dial'] += 1
    for i, m in enumerate(msgs):
        if m['dir'] != 'inbound': continue
        t0 = parse(m['date'])
        for m2 in msgs[i + 1:]:
            if m2['dir'] == 'outbound':
                t1 = parse(m2['date'])
                if t0 and t1: p['rts'].append((t1 - t0).total_seconds() / 3600)
                break

def rt_txt(rts):
    if not rts: return '—'
    h = statistics.median(rts)
    if h < 1: return f'{h*60:.0f} min'
    if h < 48: return f'{h:.1f} h'.replace('.', ',')
    return f'{h/24:.0f} días'

# tabla por asesor (universo >= 50 convos)
rows_a = []
for a, (t, i) in sorted(astat.items(), key=lambda x: -x[1][0]):
    if t < 50: continue
    s = per.get(a)
    rows_a.append((a, t, i, i / t * 100,
                   rt_txt(s['rts']) if s else '—',
                   f"{s['dial']}/{s['convs']}" if s else '—',
                   f"{s['mono']}/{s['convs']}" if s else '—'))

rows_f = [(f, t, i, i / t * 100) for f, (t, i) in sorted(fstat.items(), key=lambda x: -x[1][0]) if t >= 40]

# ---------- datos para el filtro por medio/fuente (render en JS) ----------
# fuentes-grupo con >=40 convos; el resto va a "Otras fuentes"
f_top = {f for f, (t, i) in fstat.items() if t >= 40}
def fgrp(c):
    ct = contacts.get(c['contactId'])
    f = grupo(ct['source']) if ct else '(sin match)'
    return f if f in f_top else 'Otras fuentes'

AS_LIST, as_idx = [], {}
F_LIST, f_idx = [], {}
def gi(lst, idx, k):
    if k not in idx: idx[k] = len(lst); lst.append(k)
    return idx[k]
ROWS = []            # [asesorIdx, fuenteIdx, inbound(0/1), fechaCreacionLead]

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
    """[total, dias distintos, whatsapp, llamadas, emails, sms] o 0 si no hay datos."""
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

PEND = []            # esperando respuesta: [score, nombre, telDigits, aIdx, fIdx, status, dias, ultimo, email, phone, creado]
for c in wa:
    a = users.get(c['assigned'], '(Sin asesor)')
    f = fgrp(c)
    ai, fi = gi(AS_LIST, as_idx, a), gi(F_LIST, f_idx, f)
    inb = 1 if c['lastDir'] == 'inbound' else 0
    ctx = contacts.get(c['contactId']) or {}
    creado = (ctx.get('created') or '')[:10]
    ROWS.append([ai, fi, inb, creado])
    if inb:
        ct = ctx
        dias = int((NOW_TS - c['lastDate']) / 86400000) if c.get('lastDate') else -1
        PEND.append([score_of(ct) if ct else 0,
                     (ct.get('name') or '(sin nombre)').strip().title(),
                     ''.join(ch for ch in (ct.get('phone') or '') if ch.isdigit()),
                     ai, fi, (ct.get('leadStatus') or '—').strip() or '—',
                     dias, ' '.join((c.get('lastBody') or '').split())[:110],
                     ct.get('email') or '', ct.get('phone') or '', creado,
                     ' · '.join(t.strip() for t in (ct.get('tags') or [])[:3] if t.strip()) +
                     (f' (+{len(ct.get("tags") or []) - 3})' if len(ct.get('tags') or []) > 3 else ''),
                     intentos_of(c['contactId'])])
PEND.sort(key=lambda p: (-p[0], -p[6]))
F_ORDEN = sorted(range(len(F_LIST)), key=lambda i: -sum(1 for r in ROWS if r[1] == i))
SAMPLE_STATS = {a: [rt_txt(s['rts']), f"{s['dial']}/{s['convs']}", f"{s['mono']}/{s['convs']}"]
                for a, s in per.items()}

# ---------- automatizaciones/flujos que dejan leads sin respuesta ----------
def flujo_of(last_out):
    t = ' '.join((last_out or '').split()).lower()
    if not t:
        return ('Entrada orgánica jamás contestada',
                'El cliente escribió por WhatsApp y en la conversación no existe NI UN mensaje saliente de la compañía.')
    if 'sabía que' in t or 'sabia que' in t or 'hay ciudades para visitar' in t or '1.500 personas' in t or 'delegar la administración' in t or 'delegar la administracion' in t:
        return ('Goteo de nutrición "¿Sabía que…?"',
                'Secuencia automática de plantillas educativas (crédito, preconstrucción, ciudades, property management). El lead respondió al goteo y nadie tomó la conversación.')
    if 'solidaridad' in t or 'dejan huella' in t or 'día del padre' in t or 'dia del padre' in t:
        return ('Broadcasts de fechas especiales',
                'Mensajes masivos emocionales (solidaridad con Venezuela, Día del Padre). Generan respuestas que ningún flujo recoge.')
    if 'somos el equipo de pfs' in t:
        return ('Flujo de bienvenida "Somos el equipo de PFS"',
                'Auto-respuesta de registro. El lead contestó a la bienvenida y quedó en el limbo.')
    if 'ruta del éxito' in t or 'ruta del exito' in t or 'estamos en vivo' in t or 'webinar' in t or 'charla' in t or 'lanzamiento' in t or 'invitamos' in t or 'mitos y tendencias' in t:
        return ('Invitaciones a eventos y webinars',
                'Flujos de convocatoria/confirmación de eventos. El lead respondió (confirmando o preguntando) y el flujo no escaló a un humano.')
    if 'último seguimiento' in t or 'ultimo seguimiento' in t or 'le saludo nuevamente' in t or 'quería hacer un último' in t or 'queria hacer un ultimo' in t or 'quería darle seguimiento' in t:
        return ('Secuencia de "último seguimiento"',
                'Plantilla automática de cierre de seguimiento enviada a nombre del asesor. El cliente respondió que sí le interesa… y no hubo siguiente paso.')
    if 'notificación de recepción' in t or 'notificacion de recepcion' in t or 'hemos recibido' in t:
        return ('Flujo de recepción de datos',
                'Confirmación automática de que "recibimos su información". El lead contestó con su interés y ahí murió el flujo.')
    if 'confirma tu asistencia' in t or 'confirmación de cita' in t or 'confirmacion de cita' in t or 'importante que confirme' in t or 'queda reservada su cita' in t:
        return ('Confirmación de citas de evento',
                'Flujo de confirmación de asistencia. El lead confirmó o preguntó algo y el flujo no escaló la respuesta.')
    if 'invierte en miami' in t or 'preconstrucción' in t or 'preconstruccion' in t or 'desde usd' in t or 'brickell' in t or 'residences' in t:
        return ('Promos de proyectos inmobiliarios',
                'Broadcast comercial de lanzamientos/proyectos. El interesado respondió y nadie continuó la venta.')
    if 'élite' in t or 'elite' in t or 'formula 1' in t or 'fórmula 1' in t or 'cadillac' in t or 'mundial fifa' in t or 'cata de' in t or 'pga tour' in t:
        return ('Broadcasts Elite Club (clientes)',
                'Beneficios y eventos para clientes Elite. Las respuestas de clientes actuales quedan enterradas en el hilo de marketing.')
    return ('Conversación humana abandonada',
            'No es plantilla: un asesor venía conversando de verdad y dejó de responder.')

fl_agg = defaultdict(lambda: {'n': 0, 'mkt': 0, 'sina': 0, 'sc': [], 'ej': '', 'desc': ''})
for p in pendmsgs:
    nom, desc = flujo_of(p['lastOut'])
    if nom == 'Conversación humana abandonada' and users.get(p['assigned'], '') == 'MARKETING PFS':
        nom, desc = ('Otras plantillas de marketing',
                     'Mensajes de la bolsa MARKETING PFS con plantillas variadas no clasificadas. El lead respondió y sigue en la bolsa de automatización.')
    g = fl_agg[nom]
    g['n'] += 1; g['desc'] = desc
    a = users.get(p['assigned'], '(Sin asesor)')
    if a == 'MARKETING PFS': g['mkt'] += 1
    if a == '(Sin asesor)': g['sina'] += 1
    ct = contacts.get(p['contactId']) or {}
    g['sc'].append(score_of(ct) if ct else 0)
    if not g['ej'] and p['lastBody']: g['ej'] = ' '.join(p['lastBody'].split())[:90]
FL_ROWS = sorted(fl_agg.items(), key=lambda x: -x[1]['n'])
N_ASIG_MASIVA = sum(1 for w in workflows if 'asignacion' in (w.get('name') or '').lower().replace('ó', 'o')
                    or 'asignación' in (w.get('name') or '').lower())
WF_PUB = sum(1 for w in workflows if w.get('status') == 'published')

def tr_fl(nom, g):
    prom = sum(g['sc']) / len(g['sc']) if g['sc'] else 0
    calientes = sum(1 for s in g['sc'] if s >= 30)
    return (f'<tr><td><b>{html.escape(nom)}</b><br><span style="color:var(--gris);font-size:11.5px">{html.escape(g["desc"])}</span></td>'
            f'<td style="font-weight:800;color:var(--rojo)">{fmt(g["n"])}</td>'
            f'<td>{fmt(g["mkt"])} / {fmt(g["sina"])}</td>'
            f'<td>{prom:.0f} <span style="color:var(--gris)">({fmt(calientes)} con ≥30)</span></td>'
            f'<td style="color:var(--gris);font-size:12px">“{html.escape(g["ej"])}”</td></tr>')
TABLA_FLUJOS = ''.join(tr_fl(n, g) for n, g in FL_ROWS)
WA_PAYLOAD = json.dumps({'as': AS_LIST, 'f': F_LIST, 'forden': F_ORDEN,
                         'rows': ROWS, 'pend': PEND, 'sample': SAMPLE_STATS}, ensure_ascii=False)

def tr_a(r):
    a, t, i, p_, rt, dial, mono = r
    col = '#D64545' if p_ >= 6 else '#AA9664' if p_ >= 3 else '#1E9E62'
    return (f'<tr><td><b>{html.escape(a)}</b></td><td>{fmt(t)}</td>'
            f'<td style="color:{col};font-weight:700">{fmt(i)} ({pct(p_)})</td>'
            f'<td>{rt}</td><td>{dial}</td><td>{mono}</td></tr>')
def tr_f(r):
    f, t, i, p_ = r
    col = '#D64545' if p_ >= 10 else '#AA9664' if p_ >= 4 else '#1E9E62'
    return (f'<tr><td><b>{html.escape(f)}</b></td><td>{fmt(t)}</td>'
            f'<td style="color:{col};font-weight:700">{fmt(i)} ({pct(p_)})</td></tr>')

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Análisis de conversaciones</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:14.5px;line-height:1.5}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 20px 50px}}
header{{background:var(--azul-oscuro);color:#fff;padding:20px 0}}
header .wrap{{display:flex;align-items:center;gap:16px;padding-bottom:0}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:21px;letter-spacing:1px;padding:11px 13px;border-radius:9px}}
header h1{{font-size:18.5px;font-weight:800}} header p{{color:#C9D6E4;font-size:12.5px;margin-top:2px}}
.hstats{{margin-left:auto;text-align:right}} .hstats b{{font-size:26px;display:block}} .hstats span{{font-size:12px;color:#C9D6E4}}
.navbtn{{margin-left:auto;background:#ffffff1a;border:1.5px solid #C9D6E455;color:#F2F6FA;text-decoration:none;
font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:9px;white-space:nowrap}}
.navbtn:hover{{background:#ffffff2e}}
.navbtn + .hstats{{margin-left:14px}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
h2{{font-size:16.5px;margin:28px 0 8px;border-bottom:2px solid var(--gris-linea);padding-bottom:5px}}
h3{{font-size:14px;margin:16px 0 5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:11px 13px}}
.kpi b{{font-size:22px;display:block}} .kpi span{{font-size:11.5px;color:var(--gris)}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 4px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:7px 8px}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:top}}
tr:hover td{{background:var(--gris-fondo)}}
.note{{font-size:12px;color:var(--gris);margin:4px 0 10px}}
.quote{{border-left:3px solid var(--amarillo);background:var(--gris-fondo);padding:8px 12px;border-radius:0 9px 9px 0;margin:7px 0;font-size:13px}}
.quote small{{color:var(--gris);display:block;margin-top:3px}}
.good{{border-left-color:var(--verde)}} .bad{{border-left-color:var(--rojo)}}
ul{{padding-left:20px;margin:6px 0}} li{{margin:5px 0}}
.reco{{background:var(--azul-suave);border-radius:11px;padding:13px 16px;margin:8px 0}}
.reco b{{color:var(--azul-oscuro)}}
[data-tip]{{cursor:help}}
th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.fbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:11px 14px;margin:16px 0 6px;font-size:13px}}
.fbar b{{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris)}}
.fbar select{{border:1.5px solid var(--gris-linea);border-radius:8px;padding:6px 10px;font-size:13px;background:#fff;color:var(--tinta);font-weight:600}}
.fbar #f-note{{font-size:12px;color:var(--gris)}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:11px 13px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:26px}}
.tag{{display:inline-block;padding:2px 9px;border-radius:20px;font-weight:700;font-size:11px;color:#fff}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Análisis de conversaciones (WhatsApp)</h1>
<p>CRM comercial (solo lectura) · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(TOTAL_WA)}</b><span>conversaciones WA analizadas</span></div>
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

<h2>Metodología</h2>
<p>Se analizaron las <b>{fmt(len(convos))}</b> conversaciones del CRM, de las cuales <b>{fmt(TOTAL_WA)}</b> tienen WhatsApp como último canal. Sobre ese universo se midió, para cada asesor y fuente, cuántas conversaciones quedaron con <b>el cliente esperando respuesta</b> (el último mensaje lo escribió el cliente). Además se leyó en detalle una <b>muestra de {fmt(len(sample))} conversaciones ({fmt(sum(len(c['msgs']) for c in sample))} mensajes)</b> — hasta 16 por asesor, priorizando las que el cliente dejó con la última palabra — para evaluar tiempos de respuesta, calidad de la gestión, preguntas y objeciones. Todo con lecturas GET/consulta; nada se modificó en el CRM.</p>

<div class="fbar"><b>Ver cómo se atiende cada medio / fuente:</b>
<select id="f-src" autocomplete="off"></select>
<b data-tip="Filtra todo el informe por la fecha de creación del lead en el CRM (campo dateAdded del contacto dueño de la conversación).">Lead creado desde</b>
<input type="date" id="f-d1" autocomplete="off" style="border:1.5px solid var(--gris-linea);border-radius:8px;padding:5px 8px;font-size:12.5px">
<b>hasta</b>
<input type="date" id="f-d2" autocomplete="off" style="border:1.5px solid var(--gris-linea);border-radius:8px;padding:5px 8px;font-size:12.5px">
<b data-tip="Filtra la lista de leads esperando respuesta por su temperatura de lead scoring. El score (0-100) suma: 'En curso por' hasta 35 pts + Lead Status hasta 25 + interacciones registradas hasta 20 + recencia de última actividad hasta 20. Caliente ≥55 (dos señales fuertes combinadas) · Tibio 30-54 (una señal fuerte, falta otra) · Frío 10-29 (solo señales débiles) · Sin señales <10 (cero evidencia de interés).">Temperatura</b>
<select id="f-temp" autocomplete="off">
<option value="">Todas</option><option value="hot">🔥 Calientes (≥55)</option>
<option value="warm">🌤 Tibios (30-54)</option><option value="cold">❄ Fríos (10-29)</option>
<option value="none">Sin señales (&lt;10)</option></select>
<span id="f-note"></span></div>

<div class="kpis">
<div class="kpi" data-tip="Qué es: conversaciones del CRM cuyo último mensaje fue por WhatsApp, de la fuente seleccionada. Cómo se calcula: conteo de conversaciones con lastMessageType = TYPE_WHATSAPP en GoHighLevel."><b id="k-total">—</b><span>conversaciones WhatsApp</span></div>
<a class="kpi" href="#sin-responder" style="text-decoration:none;color:inherit;display:block;border-color:#EFC7C7" data-tip="Qué es: conversaciones donde la última palabra la tiene el cliente — alguien escribió y nadie le ha contestado. Cómo se calcula: conversaciones con lastMessageDirection = inbound. Clic para ver la lista lead a lead."><b id="k-esp" style="color:var(--rojo)">—</b><span>con el cliente esperando respuesta · <u>ver la lista</u></span></a>
<div class="kpi" data-tip="Qué es: conversaciones asignadas al usuario 'MARKETING PFS', que es la bolsa de automatización de marketing (goteo de plantillas), no un asesor humano. Cómo se calcula: conteo de conversaciones con ese assignedTo."><b id="k-mkt">—</b><span>en la bolsa MARKETING PFS (automatización)</span></div>
<div class="kpi" data-tip="Qué es: conversaciones sin ningún usuario asignado en el CRM — no tienen dueño y nadie es responsable de contestarlas. Cómo se calcula: conversaciones con el campo assignedTo vacío." ><b id="k-sina" style="color:#8A6D1A">—</b><span>sin asesor asignado</span></div>
</div>

<h2>1 · Desempeño por asesor <span id="h-src" style="color:var(--naranja)"></span></h2>
<p class="note">"Sin responder" = conversaciones donde la última palabra es del cliente (del universo completo, filtrado por la fuente elegida). "Respuesta mediana", "diálogos" y "monólogos" vienen de la muestra leída de 224 convos y solo se muestran en la vista de todas las fuentes (la muestra no alcanza para desagregarlos por medio).</p>
<table><thead id="th-a"></thead><tbody id="tb-a"></tbody></table>

<h3>Quiénes lo hacen mejor</h3>
<ul>
<li><b>Sol Angeris</b> — responde en minutos, califica de inmediato (presupuesto, fechas, habitaciones, mascotas, crédito), explica requisitos y mueve a llamada. Es el estándar a replicar en leads de renta/compra entrantes. Su punto débil: 9 conversaciones del universo quedaron sin responder (6,1%), justo donde había preguntas concretas de cuota inicial y crédito.</li>
<li><b>Natalia Cardenas</b> — la menor tasa de abandono (0,9%) y el mejor manejo de objeción económica de la muestra: empatía + compromiso de recontacto con fecha ("en dos meses me comunicaré nuevamente").</li>
<li><b>Diana Navas</b> — gestión ágil de eventos: confirma, pide cédula y acompañantes, cierra el registro completo en la misma conversación.</li>
<li><b>Fatima Gouveia y Valentina Reyes</b> — buen volumen con tasas de abandono bajas (1,4% y 1,6%), aunque gran parte de su actividad es reenvío de plantillas.</li>
</ul>

<h3>Dónde están los problemas</h3>
<ul>
<li><b>MARKETING PFS (la automatización)</b> concentra {fmt(astat['MARKETING PFS'][0])} conversaciones y <b>{fmt(astat['MARKETING PFS'][1])} clientes esperando respuesta (7,3%)</b>: gente que contestó al goteo de plantillas y nadie tomó la conversación.</li>
<li><b>{fmt(astat['(Sin asesor)'][0])} conversaciones sin asesor asignado</b> — sin dueño, nadie es responsable de contestar.</li>
<li><b>Catalina Wills</b> — en su muestra la respuesta mediana fue de <b>~125 días</b>: los clientes contestan y la respuesta llega meses después (o nunca). 12 de 16 convos fueron monólogo de plantillas.</li>
<li><b>Alexandra Delgado</b> — respuesta mediana de ~28 horas en la muestra; leads que preguntaron por un evento recibieron la respuesta al día siguiente.</li>
<li><b>Yatianna Yanez y Sol Angeris</b> — 7,0% y 6,1% de convos con el cliente en espera, las tasas más altas entre asesores humanos con volumen.</li>
<li><b>Patricia Gomez</b> — 0 conversaciones "sin responder" en el universo, pero la muestra revela por qué: casi todo es broadcast saliente (15/16 monólogos); cuando un cliente pidió seguimiento de una llamada prometida, la siguiente interacción fue otra plantilla de marketing (ver caso Milagdis abajo).</li>
</ul>

<h2>2 · Conversaciones por fuente</h2>
<p class="note">La tasa de "sin responder" por fuente muestra dónde se está perdiendo la demanda entrante. Google/Paid Search y las fuentes agrupadas usan el mismo criterio del reporte de contactos.</p>
<table><thead><tr>
<th data-tip="Qué es: el origen del lead dueño de la conversación. Cómo se calcula: campo 'Fuente de contacto' del CRM, con las variantes de Paid Search (Google Ads), Referidos, Prensa y Sitio Web agrupadas como en el reporte de contactos.">Fuente</th>
<th data-tip="Qué es: cuántas conversaciones de WhatsApp corresponden a leads de esa fuente. Cómo se calcula: cruce conversación → contacto → fuente.">Convos WA</th>
<th data-tip="Qué es: la tasa de abandono de esa fuente — conversaciones donde el cliente escribió de último y no ha recibido respuesta, y su % del total. Colores: verde <4%, ámbar 4-10%, rojo ≥10%.">Cliente sin respuesta</th>
</tr></thead>
<tbody id="tb-f">{''.join(tr_f(r) for r in rows_f)}</tbody></table>
<ul>
<li><b>La fuente "Whatsapp" (mensajes orgánicos entrantes) tiene un 64% de abandono</b>: 34 de 53 personas que escribieron por iniciativa propia nunca recibieron respuesta. Es la fuga más grave: máxima intención, mínima atención.</li>
<li><b>Paid Search (12%) y Sitio Web (10,7%)</b> — leads pagados y de alta intención ("quiero asesoría para invertir en…") con 4-7 veces más abandono que los leads de Evento (1,7%). El embudo atiende bien lo que ya conoce (eventos) y desatiende el tráfico de intención.</li>
<li><b>(Sin fuente): 21%</b> — sin atribución tampoco hay proceso: nadie sabe de quién es ese lead.</li>
</ul>

<h2 id="sin-responder">3 · Leads esperando respuesta (<span id="n-pend">—</span>), uno a uno <span id="h-src2" style="color:var(--naranja)"></span></h2>
<p class="note">Toda conversación de WhatsApp cuyo último mensaje lo escribió el cliente, filtrada por la fuente elegida arriba y ordenada por lead score (los más calientes primero) y días de espera. El enlace "WA" abre el chat para responder de inmediato. Score con la misma fórmula del reporte de contactos (0-100).</p>
<div style="border:1px solid var(--gris-linea);border-radius:12px;overflow:auto;max-height:64vh">
<table style="margin:0"><thead><tr>
<th data-tip="Qué es: lead scoring 0-100 del contacto, el mismo del reporte de contactos. Cómo se calcula: 'En curso por' hasta 35 pts + Lead Status hasta 25 + interacciones registradas hasta 20 + recencia de última actividad hasta 20. Rojo ≥55 (caliente), ámbar 30-54 (tibio), azul 10-29 (frío), gris <10.">Score</th>
<th data-tip="Qué es: el nombre del contacto en el CRM. El enlace 'WA' abre el chat de WhatsApp del lead (wa.me + su teléfono) para responderle de inmediato.">Lead</th>
<th data-tip="Qué es: el email del lead registrado en el CRM; el enlace abre tu cliente de correo.">Email</th>
<th data-tip="Qué es: el teléfono del lead registrado en el CRM, con enlace de llamada y de WhatsApp.">Teléfono</th>
<th data-tip="Qué es: el usuario del CRM al que está asignada la conversación. '(Sin asesor)' significa que la conversación no tiene dueño.">Asesor</th>
<th data-tip="Qué es: el origen del lead. Cómo se calcula: campo 'Fuente de contacto' del CRM con las agrupaciones de Paid Search (Google Ads y variantes), Referidos, Prensa y Sitio Web.">Fuente</th>
<th data-tip="Qué es: la clasificación comercial del contacto. Cómo se calcula: campo 'Lead Status' del CRM tal cual (Nuevo, En curso, En Nutrición, Cliente, etc.).">Lead Status</th>
<th data-tip="Qué es: cuánto lleva el cliente esperando. Cómo se calcula: días transcurridos entre el último mensaje (que escribió el cliente) y hoy.">Días esperando</th>
<th data-tip="Qué es: el texto del último mensaje que escribió el cliente, recortado a 110 caracteres, tal cual quedó en el CRM.">Último mensaje del cliente</th>
<th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
<th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
<th data-tip="Qué es: las etiquetas (tags) del lead tal como están en el CRM — campañas, eventos, listas e importaciones (se muestran hasta 3).">Etiquetas</th>
<th data-tip="Escribirle directamente por WhatsApp.">WA</th>
</tr></thead>
<tbody id="tb-p"></tbody></table></div>

<h2>4 · Qué automatizaciones y flujos dejan leads sin respuesta</h2>
<p class="note">Para cada una de las {fmt(len(pendmsgs))} conversaciones con el cliente esperando, se bajó el historial y se identificó el <b>último mensaje real que la compañía le envió</b> (WhatsApp/SMS, excluyendo registros del sistema y notas internas). Ese último toque delata qué automatización o flujo dejó al lead hablando solo. "En MKT / sin asesor" = cuántos de esos leads quedaron asignados a la bolsa MARKETING PFS o sin asesor (la mala asignación que impide que alguien responda).</p>
<table><thead><tr>
<th data-tip="Qué es: el flujo o automatización responsable del último mensaje que recibió el lead antes de quedar esperando. Cómo se calcula: se agrupan las plantillas por su texto (el CRM no registra el nombre del workflow en el mensaje).">Flujo / automatización (último toque)</th>
<th data-tip="Qué es: cuántos leads respondieron a ese flujo y siguen esperando respuesta humana.">Leads sin respuesta</th>
<th data-tip="Qué es: de esos leads, cuántos están asignados a MARKETING PFS (bolsa de automatización) / cuántos sin ningún asesor. Ambos casos = nadie responsable de contestar.">En MKT / sin asesor</th>
<th data-tip="Qué es: score promedio (fórmula del reporte de contactos) de los leads que dejó esperando ese flujo, y cuántos tienen score ≥30 (tibios o calientes): el valor comercial que se está enfriando.">Score prom.</th>
<th data-tip="Qué es: ejemplo textual del último mensaje que escribió uno de esos clientes y quedó sin respuesta.">Ejemplo de lo que el cliente escribió</th>
</tr></thead><tbody>{TABLA_FLUJOS}</tbody></table>

<h3>Malas asignaciones: por qué nadie contesta</h3>
<ul>
<li><b>La bolsa MARKETING PFS no es una persona.</b> {fmt(astat['MARKETING PFS'][1])} de los {fmt(ESPERANDO)} leads esperando están asignados a ese usuario de automatización: sus respuestas no le suenan a ningún asesor. Existe además un workflow llamado <b>"Asignar Descartados a MARKETING PFS"</b>: los descartados vuelven a la bolsa, siguen recibiendo goteo, y cuando contestan ("Quiero más información") nadie lo ve.</li>
<li><b>{fmt(astat['(Sin asesor)'][1])} leads esperando no tienen asesor asignado</b> — incluido el lead más caliente de toda la cola (score 60, Negocio abierto, Google Ads).</li>
<li><b>La asignación es masiva, no operativa:</b> de los {fmt(WF_PUB)} workflows publicados, {fmt(N_ASIG_MASIVA)} son de "ASIGNACIÓN (MASIVA)" por asesor — reparten miles de contactos de una vez (por eso los "monólogos" de la sección 1), pero no existe un flujo que detecte "cliente respondió y lleva X horas sin respuesta" y cree una tarea o reasigne. La automatización asigna dueños en papel, no responsables en la práctica.</li>
<li><b>Los broadcasts emocionales y de fechas especiales</b> (solidaridad, Día del Padre) también generan respuestas — y son los que más caen en conversaciones de clientes Elite ya cerrados, donde la respuesta del cliente queda enterrada en el hilo de marketing.</li>
</ul>

<h2>5 · Qué preguntan los clientes</h2>
<p class="note">De los 190 mensajes reales de clientes en la muestra (excluyendo auto-respuestas), los temas dominantes:</p>
<ul>
<li><b>Logística de eventos</b> (14): confirmar cita, acompañantes, costo de entrada ("¿Qué costo tiene?").</li>
<li><b>"Mándame la info por aquí"</b> (12): piden recibir información por WhatsApp y evitar llamadas ("Hola gracias prefiero por aquí por fa", "me puede mandar la información por este medio").</li>
<li><b>Rentas corta y larga</b> (12): "cuánto sale el día", presupuesto mensual, fechas, zona ("quiero rentar departamento para dos personas… ¿cuánto sale el día?").</li>
<li><b>Precio / cifras concretas</b> (10): "Cuota inicial ¿de cuánto?", "¿Do you have any studios for 300,000 dollars?", presupuestos desde $1.000/mes de renta hasta $560k de compra.</li>
<li><b>Tipo de propiedad y zona</b> (9): casa vs apartamento vs local, Brickell, Hollywood, Hallandale, Downtown.</li>
<li><b>Financiamiento como extranjero y visa</b>: menos frecuentes en volumen pero críticas — aparecen justo en los leads más avanzados ("¿Cómo es el tema si es a crédito?", "no cuento con visa por el momento").</li>
</ul>

<h2>6 · Objeciones y cómo se manejan</h2>
<h3>Bien manejadas</h3>
<div class="quote good">CLIENTE: "…tuve una salida de mi empresa y estoy reorganizando temas financieros. Invertir en este momento no me sería viable."<br>ASESOR (Natalia Cardenas): "Entiendo perfectamente… tal como me indicó, <b>en dos meses me comunicaré nuevamente</b> con usted para retomar."<small>Objeción económica → empatía + recontacto con fecha concreta. Modelo a seguir.</small></div>
<div class="quote good">CLIENTE: "Me interesa local comercial en avenida importante."<br>ASESOR (Sandra Osorio): explica que los locales en EE.UU. rara vez se venden, son de los desarrolladores, y reorienta a una alternativa con oficina incluida.<small>Objeción de producto → conocimiento de mercado + redirección. (Mejorable: la respuesta tenía varios errores de digitación.)</small></div>
<h3>Mal manejadas o sin manejar</h3>
<div class="quote bad">CLIENTE: "Siempre he querido invertir en Miami. Pero por temas de visa ya ha sido imposible. Fui a renovarla y me la negaron."<br>ASESOR: "Lamento mucho la situación… estamos a su disposición."<small>La objeción nº1 del negocio (visa) se dejó pasar — cuando el propio goteo afirma que "puede obtener crédito hipotecario sin ser residente". Falta un playbook: invertir sin visa es posible y nadie lo explicó.</small></div>
<div class="quote bad">CLIENTE: "¿Cuota inicial de cuánto? ¿Cómo es el tema si es a crédito, y qué tipo de vivienda?"<br><small>Última pregunta de la conversación: quedó SIN respuesta (lead de paid search, caliente, esperando desde entonces).</small></div>
<div class="quote bad">CLIENTE: "No quiero saber nada de Uds. <b>Me hicieron perder dinero</b>."<br><small>Tras la queja, el sistema le siguió enviando invitaciones a catas de whisky y beneficios Elite. Riesgo reputacional: no existe supresión de marketing ni escalamiento de quejas.</small></div>
<div class="quote bad">CLIENTE (Milagdis, Cliente actual): "Buenas tardes. Aún no recibo llamadas o alguna información adicional. Quedo atenta."<br><small>La promesa de "el lunes le contactamos" no se cumplió; los siguientes mensajes fueron plantillas de F1 y lanzamientos. Post-venta sin seguimiento.</small></div>
<div class="quote bad">ASESOR: "Hola <b>Guidion</b>, confirma tu asistencia…" (enviado al lead <b>Bernardo</b>)<small>Mensajes con el nombre de otro lead (también hubo un "María Elena" a un número equivocado). La personalización automática está enviando datos cruzados.</small></div>

<h2>7 · Recomendaciones</h2>
<div class="reco"><b>1. Cola "cliente esperando" con SLA.</b> Hoy hay {fmt(ESPERANDO)} conversaciones WhatsApp con la última palabra del cliente. Ese dato sale del CRM en tiempo real (lastMessageDirection = inbound): crear una vista diaria por asesor con SLA de respuesta &lt; 1 hora hábil, y dueño explícito para las {fmt(astat['(Sin asesor)'][0])} sin asesor y las {fmt(astat['MARKETING PFS'][1])} de MARKETING PFS.</div>
<div class="reco"><b>2. Rutear la demanda entrante de alta intención.</b> La fuente "Whatsapp" (64% de abandono), Google/Paid Search (12%) y Sitio Web (10,7%) necesitan asignación inmediata a un asesor de guardia. Son leads que YA preguntaron por invertir o rentar: cada uno perdido es pauta pagada desperdiciada.</div>
<div class="reco"><b>3. Playbook de objeciones (1 página).</b> Visa negada/sin visa → se puede invertir e incluso financiar sin residencia (guión con requisitos). "No tengo dinero ahora" → nutrición + recontacto agendado con fecha (modelo Natalia Cardenas). Cliente molesto → supresión de marketing + escalamiento a gerencia el mismo día.</div>
<div class="reco"><b>4. Respuestas tipo para las 6 preguntas más frecuentes.</b> Cuota inicial y crédito para extranjeros, precios "desde", requisitos de renta, rentas cortas, zonas. Los clientes piden la info por WhatsApp: tener fichas listas (PDF/mensaje) en vez de insistir en llamada.</div>
<div class="reco"><b>5. Aprovechar la calificación que el bot ya recoge.</b> La encuesta automática (horizonte de inversión, crédito, visa, profesión) se responde y luego el lead sigue en goteo genérico (caso Rafael: contestó todo, tiene visa, necesita crédito, horizonte 6 meses — y quedó en plantillas). Un lead que responde la encuesta debe generar tarea a asesor con vencimiento.</div>
<div class="reco"><b>6. Higiene de datos y de imagen.</b> Corregir la personalización que cruza nombres entre leads; filtrar auto-respuestas (bots de los clientes) de las métricas; revisar ortografía en mensajes manuales ("vendarle una llamada", "infromación") — es la cara escrita de la marca.</div>

<div class="warnpii"><b>⚠ Datos personales:</b> este documento contiene nombres y fragmentos de conversaciones reales de clientes (Habeas Data). Uso interno exclusivo del equipo comercial autorizado. No publicar ni circular por fuera.</div>
<script>
const W = {WA_PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = s => s >= 55 ? '#D64545' : s >= 30 ? '#AA9664' : s >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';

const espCol = p => p >= 6 ? '#D64545' : p >= 3 ? '#AA9664' : '#1E9E62';

const sel = document.getElementById('f-src');
sel.innerHTML = '<option value="">Todas las fuentes</option>' + W.forden.map(i => {{
  const n = W.rows.filter(r => r[1] === i).length;
  return `<option value="${{i}}">${{esc(W.f[i])}} (${{fN(n)}})</option>`;
}}).join('');
sel.addEventListener('change', render);
['f-d1', 'f-d2', 'f-temp'].forEach(id => document.getElementById(id).addEventListener('change', render));
function inFecha(cr) {{
  const d1 = document.getElementById('f-d1').value, d2 = document.getElementById('f-d2').value;
  return (d1 === '' || (cr && cr >= d1)) && (d2 === '' || (cr && cr <= d2));
}}
function inTemp(sc) {{
  const t = document.getElementById('f-temp').value;
  return t === '' || (t === 'hot' ? sc >= 55 : t === 'warm' ? sc >= 30 && sc < 55
    : t === 'cold' ? sc >= 10 && sc < 30 : sc < 10);
}}

function render() {{
  const fv = sel.value === '' ? null : +sel.value;
  const rows = W.rows.filter(r => (fv === null || r[1] === fv) && inFecha(r[3]));
  const pend = W.pend.filter(p => (fv === null || p[4] === fv) && inFecha(p[10]) && inTemp(p[0]));
  const srcName = fv === null ? '' : ' · ' + W.f[fv];
  document.getElementById('h-src').textContent = srcName;
  document.getElementById('h-src2').textContent = srcName;
  document.getElementById('f-note').textContent = fv === null ? ''
    : `${{fN(rows.length)}} conversaciones de esta fuente · ${{fN(pend.length)}} esperando respuesta`;
  /* KPIs */
  const mkt = W.as.indexOf('MARKETING PFS'), sina = W.as.indexOf('(Sin asesor)');
  document.getElementById('k-total').textContent = fN(rows.length);
  document.getElementById('k-esp').textContent = fN(pend.length);
  document.getElementById('k-mkt').textContent = fN(rows.filter(r => r[0] === mkt).length);
  document.getElementById('k-sina').textContent = fN(rows.filter(r => r[0] === sina).length);
  document.getElementById('n-pend').textContent = fN(pend.length);
  /* tabla por asesor */
  const agg = new Map();
  rows.forEach(r => {{
    if (!agg.has(r[0])) agg.set(r[0], [0, 0]);
    const a = agg.get(r[0]); a[0]++; a[1] += r[2];
  }});
  const minN = fv === null ? 50 : 5;
  const lista = [...agg.entries()].filter(([, v]) => v[0] >= minN).sort((x, y) => y[1][0] - x[1][0]);
  const conMuestra = fv === null;
  document.getElementById('th-a').innerHTML = '<tr>' +
    '<th data-tip="Qué es: el usuario del CRM al que están asignadas las conversaciones. MARKETING PFS es la automatización de marketing y (Sin asesor) son conversaciones sin dueño.">Asesor</th>' +
    '<th data-tip="Qué es: total de conversaciones de WhatsApp asignadas a ese asesor, en la fuente seleccionada. Cómo se calcula: conteo sobre todas las conversaciones con lastMessageType = TYPE_WHATSAPP.">Convos WA</th>' +
    '<th data-tip="Qué es: cuántas de sus conversaciones tienen al cliente con la última palabra (nadie le respondió) y qué % de sus convos representa. Colores: verde <3%, ámbar 3-6%, rojo ≥6%.">Sin responder</th>' +
    (conMuestra ? '<th data-tip="Qué es: qué tan rápido responde cuando el cliente escribe. Cómo se calcula: mediana del tiempo entre cada mensaje del cliente y la siguiente respuesta del asesor, medida sobre la muestra leída de 16 conversaciones por asesor.">Respuesta mediana (muestra)</th>' +
     '<th data-tip="Qué es: conversaciones de verdad. Cómo se calcula: de las 16 convos muestreadas del asesor, en cuántas el cliente escribió 2 o más veces.">Diálogos reales</th>' +
     '<th data-tip="Qué es: envíos sin conversación. Cómo se calcula: de las 16 convos muestreadas, cuántas solo tienen mensajes salientes (plantillas masivas que el cliente nunca respondió).">Monólogos</th>' : '') + '</tr>';
  document.getElementById('tb-a').innerHTML = lista.map(([ai, [t, i]]) => {{
    const p = i / t * 100;
    const sm = W.sample[W.as[ai]];
    return `<tr><td><b>${{esc(W.as[ai])}}</b></td><td>${{fN(t)}}</td>` +
      `<td style="color:${{espCol(p)}};font-weight:700">${{fN(i)}} (${{p.toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}%)</td>` +
      (conMuestra ? `<td>${{sm ? sm[0] : '—'}}</td><td>${{sm ? sm[1] : '—'}}</td><td>${{sm ? sm[2] : '—'}}</td>` : '') + '</tr>';
  }}).join('') || '<tr><td colspan="6" style="color:var(--gris)">Sin asesores con volumen suficiente en esta fuente.</td></tr>';
  /* tabla por fuente (todas las fuentes, respetando el rango de fechas) */
  const fAgg = new Map();
  W.rows.filter(r => inFecha(r[3])).forEach(r => {{
    if (!fAgg.has(r[1])) fAgg.set(r[1], [0, 0]);
    const x = fAgg.get(r[1]); x[0]++; x[1] += r[2];
  }});
  document.getElementById('tb-f').innerHTML = [...fAgg.entries()]
    .filter(([, v]) => v[0] >= 10).sort((a, b) => b[1][0] - a[1][0]).map(([fi2, [t, i]]) => {{
      const pp = i / t * 100;
      const col = pp >= 10 ? '#D64545' : pp >= 4 ? '#AA9664' : '#1E9E62';
      return `<tr><td><b>${{esc(W.f[fi2])}}</b></td><td>${{fN(t)}}</td>` +
        `<td style="color:${{col}};font-weight:700">${{fN(i)}} (${{pp.toLocaleString('es-CO', {{maximumFractionDigits: 1}})}}%)</td></tr>`;
    }}).join('');
  /* tabla de pendientes */
  document.getElementById('tb-p').innerHTML = pend.map(p => {{
    const wa = p[2] ? ` · <a href="https://wa.me/${{p[2]}}" target="_blank">WA</a>` : '';
    const em = p[8] ? `<a href="mailto:${{esc(p[8])}}">${{esc(p[8])}}</a>` : '—';
    const ph = p[9] ? `<a href="tel:${{esc(p[9])}}">${{esc(p[9])}}</a>` : '—';
    return `<tr><td><span class="tag" style="background:${{scCol(p[0])}}">${{p[0]}}</span></td>` +
      `<td><b>${{esc(p[1])}}</b>${{wa}}</td><td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>` +
      `<td>${{esc(W.as[p[3]])}}</td><td>${{esc(W.f[p[4]])}}</td>` +
      `<td>${{esc(p[5])}}</td><td>${{p[6] >= 0 ? fN(p[6]) : '—'}}</td>` +
      `<td style="color:var(--gris);font-size:12px">${{esc(p[7])}}</td>` +
      `<td style="white-space:nowrap" data-tip="${{intTip(p[12])}}">${{intCell(p[12])}}</td>` +
      `<td data-tip="${{intTip(p[12])}}">${{canCell(p[12])}}</td>` +
      `<td style="font-size:11px;color:var(--azul-oscuro)">${{esc(p[11] || '—')}}</td>` +
      `<td>${{p[2] ? `<a href="https://wa.me/${{p[2]}}" target="_blank" style="display:inline-block;background:#25D366;color:#fff;border-radius:8px;padding:4px 9px;white-space:nowrap;font-size:.74rem;font-weight:700;text-decoration:none" data-tip="Escribirle directamente por WhatsApp.">💬 WhatsApp</a>` : '—'}}</td></tr>`;
  }}).join('') || '<tr><td colspan="13" style="color:var(--gris)">Ningún lead de esta fuente está esperando respuesta. 👏</td></tr>';
}}
/* arranque limpio: el navegador restaura valores de formulario entre visitas */
function arranqueWA() {{
  ['f-src', 'f-d1', 'f-d2', 'f-temp'].forEach(id => document.getElementById(id).value = '');
  render();
}}
arranqueWA();
window.addEventListener('pageshow', e => {{ if (e.persisted) arranqueWA(); }});
setTimeout(() => {{
  if (['f-src', 'f-d1', 'f-d2', 'f-temp'].some(id => document.getElementById(id).value !== '')) arranqueWA();
}}, 250);

/* tooltip global: sigue al cursor y no se recorta dentro de tablas con scroll */
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
<footer>Auditoría generada desde la API de GoHighLevel en modo solo lectura (conversaciones y mensajes vía GET/consulta). Universo: {fmt(TOTAL_WA)} conversaciones con último mensaje WhatsApp. Muestra cualitativa: {fmt(len(sample))} conversaciones / {fmt(sum(len(c['msgs']) for c in sample))} mensajes de los 14 asesores con más volumen. Las citas se transcriben tal cual (con errores originales). Corte: {CORTE}.</footer>
</div></body></html>'''

out = str(ROOT / f'auditoria-whatsapp-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB)')
