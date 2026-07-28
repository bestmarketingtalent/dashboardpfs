#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan de RECUPERACIÓN DE LEADS: los 6 bolsillos de valor perdido u olvidado del CRM
(descartes con señal viva, descartados que respondieron, descartes sin gestión,
esperando respuesta, conversaciones enfriadas y nunca contactados), cada uno con su
diagnóstico, su playbook de rescate paso a paso, su guion sugerido y la tabla de
leads para gestionarlos. Se muestra como sub-pestaña de Estrategia comercial.
Lee scripts/data/{contacts,users,convos,gestion,wa_all_msgs}.json (solo consulta)."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

contacts = json.load(open(DATA / 'contacts.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
convos = json.load(open(DATA / 'convos.json'))

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW   = datetime.now(timezone.utc)
NOW_MS = NOW.timestamp() * 1000
_hoy  = datetime.now()
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
        return 'Google / Paid Search'
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

def dias_sin_act(c):
    la = c.get('lastActivity') or c.get('lastEngagement')
    if not la: return -1
    try:
        return max(0, (NOW - datetime.fromisoformat(str(la).replace('Z','+00:00'))).days)
    except ValueError:
        return -1

try:
    GESTION = json.load(open(DATA / 'gestion.json'))
except Exception:
    GESTION = {}
try:
    _wa_all = json.load(open(DATA / 'wa_all_msgs.json'))
except Exception:
    _wa_all = []
INB_WA = set()
for _cv in _wa_all:
    if _cv.get('contactId') and any(_m[0] == 1 for _m in (_cv.get('msgs') or [])):
        INB_WA.add(_cv['contactId'])

def respondio(c):
    if c['id'] in INB_WA: return 1
    _g = GESTION.get(c['id'])
    if _g and (_g['c'][1] > 0 or _g['c'][2] > 0): return 1
    return 0

def intentos_of(cid):
    _g = GESTION.get(cid)
    _f = _g.get('f') if _g else None
    if _f:
        return [len(_f), len({x[0] for x in _f}),
                sum(1 for x in _f if x[1] == 'w'), sum(1 for x in _f if x[1] == 'c'),
                sum(1 for x in _f if x[1] == 'e'), sum(1 for x in _f if x[1] == 's')]
    return 0

# días esperando respuesta en WhatsApp (última palabra del cliente)
ESPERA = {}
for cv in convos:
    if cv.get('lastType') == 'TYPE_WHATSAPP' and cv.get('lastDir') == 'inbound' and cv.get('lastDate'):
        ESPERA[cv['contactId']] = int((NOW_MS - cv['lastDate']) / 86400000)

# ---------- filas y segmentos ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DA, giA = dict_indexer()
DF, giF = dict_indexer()
DT, giT = dict_indexer()

ROWS = []
SEG = {k: [] for k in ('senal', 'respondio', 'sinGestion', 'esperando', 'enfriados', 'nunca')}
UNION = set()

for c in contacts:
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    ku = (c.get('enCursoPor') or '').strip()
    sc = score_of(c)
    inter = num(c.get('vecesContactado')) + num(c.get('salesActivities'))
    oport = ku.startswith('Oportunidad')
    resp = respondio(c)
    dsa = dias_sin_act(c)
    esp = ESPERA.get(c['id'], -1)
    segs = []
    if st == 'Descartado':
        if sc >= 30 or oport: segs.append('senal')
        elif resp: segs.append('respondio')
        elif inter == 0 and c.get('phone'): segs.append('sinGestion')
    elif st not in ('Cliente', 'Aliado', 'Tenant', 'Relationship', 'Compra Problematica'):
        if esp >= 0: segs.append('esperando')
        if resp and dsa >= 60: segs.append('enfriados')
        if inter == 0 and c.get('phone') and (c.get('created') or '') < (NOW.strftime('%Y-%m-%d')[:8] + '01') and sc < 30:
            # nunca trabajados: sin una sola gestión, con teléfono, no recién llegados
            try:
                _dias_creado = (NOW - datetime.fromisoformat(str(c['created']).replace('Z', '+00:00'))).days
            except (ValueError, TypeError):
                _dias_creado = 0
            if _dias_creado > 30: segs.append('nunca')
    if not segs: continue
    a = USERS.get(c['assigned'], '(Sin asesor asignado)') if c['assigned'] else '(Sin asesor asignado)'
    mo = (c.get('motivoDescarte') or '').strip().replace('No caliifica', 'No califica') or '—'
    i = len(ROWS)
    ROWS.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c['email'] or '', c['phone'] or '',
        giA(a), giF(fuente_of(c)), st, ku or '—', sc,
        (c['created'] or '')[:10],
        [giT(t.strip()) for t in (c.get('tags') or [])[:8] if t and t.strip()],
        inter, mo, esp, dsa, resp, intentos_of(c['id'])
    ])
    UNION.add(c['id'])
    for sg in segs: SEG[sg].append(i)

for k in SEG:
    SEG[k].sort(key=lambda i: -ROWS[i][7])

def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
def fmt(n): return f'{n:,}'.replace(',', '.')

N = {k: len(v) for k, v in SEG.items()}
TOT_U = len(UNION)
MQL_U = sum(1 for r in ROWS if r[7] >= 30 or r[6].startswith('Oportunidad'))
TEL_U = sum(1 for r in ROWS if r[2])

PAYLOAD = json.dumps({'rows': ROWS, 'seg': SEG, 'ase': ordered(DA), 'fu': ordered(DF),
                      'tg': ordered(DT)}, ensure_ascii=False)

def card(key, icono, titulo, n, diag, plan, guion, tip):
    plan_html = ''.join(f'<li>{p}</li>' for p in plan)
    return f'''<div class="seg">
<div class="seghead" data-tip="{tip}">
<span class="segico">{icono}</span>
<div><h3>{titulo}</h3><p class="segdiag">{diag}</p></div>
<span class="segn">{fmt(n)}</span>
</div>
<div class="segbody">
<div class="grid2">
<div><h4>📋 Playbook de rescate</h4><ol class="plan">{plan_html}</ol></div>
<div><h4>💬 Guion sugerido (primer toque)</h4><div class="guion">{guion}</div></div>
</div>
<button class="btn verbtn" data-seg="{key}">👁 Ver y gestionar los {fmt(n)} leads</button>
<div class="segtable" id="st-{key}"></div>
</div>
</div>'''

CARDS = (
card('senal', '🔥', 'Descartes con señal de compra viva', N['senal'],
     'Leads marcados Descartado que HOY tienen score ≥30 u oportunidad de compra declarada vigente: la contradicción más rentable del CRM.',
     ['Revisión gerencial uno a uno (una tarde alcanza): validar que el descarte fue un error.',
      'Reasignar al asesor con mejor conversión del medio de origen — no al que lo descartó.',
      'Primer toque personal por WhatsApp mencionando su interés declarado (horizonte de compra).',
      'Si responde: llamada de recalificación en 24 h y quitar el status Descartado.',
      'Si no responde en 7 días con 3 intentos en días distintos: devolver a nutrición, no re-descartar.'],
     '"Hola [nombre], soy [asesor] de [empresa]. Revisando tu caso veo que nos indicaste interés en invertir en un horizonte de [X meses] — quiero retomarlo personalmente porque hay opciones nuevas en Miami que encajan con lo que buscabas. ¿Tienes 10 minutos esta semana?"',
     'Descartado con lead score ≥30 u &quot;En curso por&quot; = Oportunidad vigente. Ordenados por score.'),
card('respondio', '💬', 'Descartados que sí respondían', N['respondio'],
     'Leads descartados que en su historial SÍ contestaron (mensaje de WhatsApp o llamada): el canal funcionaba — lo que falló fue la continuidad.',
     ['Leer la última conversación antes de tocar: retomar el hilo, no empezar de cero.',
      'Primer toque referenciando el último tema hablado.',
      'Cadencia 1-3-7: WhatsApp día 1, llamada día 3, audio corto día 7.',
      'Registrar motivo real si vuelve a caerse — "Nunca contestó" no aplica a quien contestaba.'],
     '"Hola [nombre], quedamos en una conversación pendiente hace un tiempo y no quiero dejarla morir. ¿Sigue en pie tu interés en [tema de la última conversación]? Tengo novedades que valen la pena."',
     'Descartado que registra al menos una respuesta (mensaje entrante de WhatsApp o llamada contestada) y no está en el segmento anterior.'),
card('sinGestion', '🗑', 'Descartados sin una sola gestión', N['sinGestion'],
     'Descartados con CERO interacciones registradas y teléfono válido: nadie habló con ellos antes de botarlos — el descarte fue del proceso, no del cliente.',
     ['Campaña de reactivación masiva por WhatsApp (plantilla aprobada + variable de fuente de origen).',
      'Los que respondan pasan a un asesor con SLA de respuesta de 1 hora.',
      'Excluir a los que pidieron ser eliminados (Habeas Data) — ya están fuera de esta lista si el motivo lo registró.',
      'Medir: si >5% responde, el "descarte temprano" está botando plata todos los meses.'],
     '"Hola [nombre], hace un tiempo te interesaste en invertir en propiedades en Miami con [empresa] y quizá no te contactamos como merecías. ¿Sigues explorando esa idea? Si sí, te comparto en 2 minutos lo que hay hoy."',
     'Descartado con 0 interacciones registradas, con teléfono, sin señal viva ni respuesta previa (excluye los dos segmentos anteriores).'),
card('esperando', '⏳', 'Esperando respuesta AHORA en WhatsApp', N['esperando'],
     'Leads activos cuya última palabra en WhatsApp es del CLIENTE: escribieron y nadie contestó. El rescate más barato que existe — solo hay que responder.',
     ['Ordenar por score y responder HOY los tibios/calientes (arriba en la tabla).',
      'Responder con mensaje personal, no plantilla: leyeron y escribieron — merecen persona.',
      'Los asignados a MARKETING PFS o sin asesor: reasignar de inmediato a un humano.',
      'Instalar el hábito: cola de espera en cero al final de cada día.'],
     '"[Nombre], mil disculpas por la demora en responderte — tu mensaje merecía respuesta antes. Sobre lo que preguntabas: [respuesta concreta]. ¿Te llamo hoy y lo resolvemos en 10 minutos?"',
     'Lead activo (no Cliente ni Descartado) con conversación de WhatsApp cuyo último mensaje es entrante. La columna Espera = días desde ese mensaje.'),
card('enfriados', '🧊', 'Conversaciones reales que se dejaron enfriar', N['enfriados'],
     'Leads que respondieron alguna vez (hubo conversación de verdad) pero llevan 60+ días sin ninguna actividad: relación construida y abandonada.',
     ['Retomar con contexto: leer la conversación previa y mencionar el último interés.',
      'Ofrecer contenido puente del blog (mercado, crédito para extranjeros, zonas) antes de pedir cita.',
      'Cadencia suave: 3 toques en 2 semanas mezclando WhatsApp y llamada.',
      'Registrar "En curso por" en cada recontacto: sin horizonte declarado no hay seguimiento posible.'],
     '"Hola [nombre], hace unas semanas hablamos sobre [tema] y quedó en pausa. El mercado de Miami se movió desde entonces — te preparé un dato que te puede interesar: [dato del blog]. ¿Lo retomamos?"',
     'Lead activo que registra respuesta (WhatsApp o llamada) y lleva 60+ días sin actividad en el CRM. La columna Sin act. = días desde la última actividad.'),
card('nunca', '📵', 'Nunca contactados con teléfono válido', N['nunca'],
     'Leads de más de 30 días con teléfono y CERO gestiones registradas: inventario pagado que nunca se tocó. Priorizar por fuente de calidad.',
     ['Priorizar por fuente: primero Referidos y Google (convierten 7,8% y 4%+), de último Eventos masivos.',
      'Goteo de activación de 3 toques por WhatsApp en 10 días; los que abran/respondan pasan a asesor.',
      'Validar teléfonos en el primer envío: los inválidos se marcan con su motivo real y salen del inventario.',
      'Meta: que este segmento tienda a cero — cada lead nuevo debe recibir su primer toque en el día 1.'],
     '"Hola [nombre], soy [asesor] de la compañía. Te registraste interesado en invertir en propiedades en EE.UU. y quiero presentarme como tu contacto directo. ¿Te comparto las 3 opciones más pedidas del momento?"',
     'Lead activo de 30+ días de antigüedad, con teléfono, sin una sola interacción registrada y score frío.'),
)

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recuperación de leads</title>
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
.seg{{border:1px solid var(--gris-linea);border-radius:13px;margin:14px 0;overflow:hidden}}
.seghead{{display:flex;gap:14px;align-items:center;padding:14px 18px;background:var(--gris-fondo)}}
.segico{{font-size:26px}}
.seghead h3{{font-size:15px}}
.segdiag{{font-size:12.5px;color:var(--gris);margin-top:2px}}
.segn{{margin-left:auto;font-size:24px;font-weight:900;color:var(--azul-oscuro);white-space:nowrap}}
.segbody{{padding:14px 18px}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-bottom:10px}}
.segbody h4{{font-size:12.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);margin-bottom:6px}}
.plan{{padding-left:20px;font-size:13.2px}} .plan li{{margin:4px 0}}
.guion{{background:#F3F7EC;border:1px solid #D6E4C4;border-radius:10px;padding:11px 14px;font-size:13px;font-style:italic;color:#3E5432}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
table{{border-collapse:collapse;width:100%;font-size:12.6px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
a{{color:var(--azul)}}
.tbox{{border:1px solid var(--gris-linea);border-radius:11px;overflow:auto;max-height:60vh;margin-top:10px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Plan de recuperación de leads</h1>
<p>CRM comercial (solo lectura) · Los 6 bolsillos de valor perdido y cómo rescatarlos · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(TOT_U)}</b><span>leads recuperables únicos</span></div>
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

<div class="intro">💡 <b>La recuperación es la adquisición más barata:</b> estos {fmt(TOT_U)} leads ya se pagaron una vez — están descartados por error, esperando una respuesta que nunca llegó, o nunca fueron tocados. Cada segmento de abajo tiene su diagnóstico, su playbook de rescate y su guion de primer toque. El orden de los segmentos ES la prioridad: arriba lo más caliente y barato de rescatar.</div>

<div class="kpis">
<div class="kpi" data-tip="Leads únicos en al menos uno de los 6 segmentos de recuperación (un lead puede estar en más de uno)."><b>{fmt(TOT_U)}</b><span>leads recuperables únicos</span></div>
<div class="kpi" data-tip="De los recuperables, cuántos son MQL: score ≥30 u oportunidad de compra declarada."><b style="color:var(--naranja)">{fmt(MQL_U)}</b><span>con calificación (MQL)</span></div>
<div class="kpi" data-tip="Recuperables con teléfono registrado: contactables por WhatsApp o llamada de inmediato."><b style="color:var(--verde)">{fmt(TEL_U)}</b><span>con teléfono</span></div>
<div class="kpi" data-tip="Leads esperando respuesta en WhatsApp ahora mismo: el rescate de HOY."><b style="color:var(--rojo)">{fmt(N['esperando'])}</b><span>esperando respuesta YA</span></div>
</div>

{''.join(CARDS)}

<div class="warnpii"><b>⚠ Datos personales:</b> esta hoja contiene nombres, correos y teléfonos (Habeas Data). No publicarla ni circularla fuera del equipo comercial autorizado.</div>
<footer>Segmentos calculados al corte sobre los {fmt(len(contacts))} contactos del CRM: (1) Descartado con score ≥30 u oportunidad vigente · (2) Descartado con respuesta registrada (mensaje entrante de WhatsApp o llamada contestada) · (3) Descartado con 0 interacciones y teléfono · (4) activo con última palabra del cliente en WhatsApp · (5) activo con respuesta registrada y 60+ días sin actividad · (6) activo de 30+ días, con teléfono y 0 interacciones. Los segmentos de descarte son excluyentes entre sí en ese orden; un lead activo puede estar en más de uno. Score 0-100 con la fórmula de todo el dashboard. Generado desde la API de GHL, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d ` + (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') : 'Sin intentos salientes en las conversaciones descargadas.';
const ST = {{}};

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
function renderSeg(seg) {{
  const box = document.getElementById('st-' + seg);
  const idxs = D.seg[seg];
  ST[seg] = Math.min(idxs.length, (ST[seg] || 0) + 100);
  const filas = idxs.slice(0, ST[seg]).map(i => {{
    const r = D.rows[i];
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank"><b>WA</b></a>' : ''}}` : '—';
    return `<tr><td><span class="sc" style="background:${{scCol(r[7])}}">${{r[7]}}</span></td>
    <td><b>${{esc(r[0])}}</b></td><td>${{esc(D.ase[r[3]])}}</td>
    <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
    <td>${{esc(D.fu[r[4]])}}</td><td>${{esc(r[5])}}</td><td>${{esc(r[6])}}</td>
    <td>${{esc(r[11])}}</td>
    <td>${{r[12] >= 0 ? fN(r[12]) : '—'}}</td><td>${{r[13] >= 0 ? fN(r[13]) : '—'}}</td>
    <td style="white-space:nowrap" data-tip="${{intTip(r[15])}}">${{intCell(r[15])}}</td>
    <td>${{esc(r[8] || '—')}}</td><td>${{tagsCell(r[9])}}</td></tr>`;
  }}).join('');
  box.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap">
    <button class="btn sec" onclick="cerrarSeg('${{seg}}')">✕ Cerrar</button>
    <span style="font-size:12px;color:var(--gris)">Ordenados por score (los más calientes primero). Mostrando ${{fN(ST[seg])}} de ${{fN(idxs.length)}}.</span></div>
  <div class="tbox"><table><thead><tr>
  <th data-tip="Lead scoring 0-100 (misma fórmula de todo el dashboard).">Score</th>
  <th>Lead</th><th data-tip="Usuario del CRM asignado.">Asesor</th>
  <th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp para rescatarlo de inmediato.">Teléfono</th>
  <th data-tip="Medio por el que se adquirió.">Fuente</th><th>Lead Status</th><th>En curso por</th>
  <th data-tip="Motivo de descarte registrado (solo aplica a los segmentos de descarte).">Motivo</th>
  <th data-tip="Días que lleva esperando respuesta en WhatsApp ('—' = no está en cola).">Espera</th>
  <th data-tip="Días sin ninguna actividad registrada en el CRM ('—' = sin dato).">Sin act.</th>
  <th data-tip="Intentos de contacto salientes: total · días distintos · canales (💬📞✉).">Intentos</th>
  <th>Creado</th><th>Etiquetas</th>
  </tr></thead><tbody>${{filas}}</tbody></table></div>` +
  (ST[seg] < idxs.length ? `<button class="btn sec" style="margin-top:6px" onclick="renderSeg('${{seg}}')">Mostrar 100 más (${{fN(idxs.length - ST[seg])}} restantes)</button>` : '');
}}
function cerrarSeg(seg) {{ ST[seg] = 0; document.getElementById('st-' + seg).innerHTML = ''; }}
document.querySelectorAll('.verbtn').forEach(b => b.addEventListener('click', () => {{
  const seg = b.dataset.seg;
  if (ST[seg]) {{ cerrarSeg(seg); return; }}
  renderSeg(seg);
}}));

</script>
</body></html>'''

out = str(ROOT / f'recuperacion-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print('segmentos:', {k: len(v) for k, v in SEG.items()}, '| únicos:', TOT_U)
