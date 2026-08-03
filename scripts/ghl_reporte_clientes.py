#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de CLIENTES para venta cruzada: los 983 clientes con toda su información y
todas las segmentaciones (recompra declarada, Elite, mercado, realtor, fuente,
último contacto real por conversaciones, antigüedad, temperatura), filtros
combinables, distribuciones con barras y playbook de venta cruzada.
Solo lectura del CRM."""
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
contacts = json.load(open(DATA / 'contacts.json'))
convos = json.load(open(DATA / 'convos.json'))
users = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
_hoy = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'
NOW_TS = _hoy.timestamp() * 1000
def fmt(n): return f'{n:,}'.replace(',', '.')

CURSO_PTS = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
def _n(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0
def score_of(ct):
    s = CURSO_PTS.get((ct.get('enCursoPor') or '').strip(), 0)
    s += min(20, _n(ct.get('vecesContactado')) + _n(ct.get('salesActivities')))
    la = ct.get('lastActivity') or ct.get('lastEngagement')
    if la:
        try:
            dt = datetime.fromisoformat(str(la).replace('Z', '+00:00'))
            d = (datetime.now(dt.tzinfo) - dt).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)

PAISES = [('57','Colombia'),('52','México'),('51','Perú'),('593','Ecuador'),('58','Venezuela'),
          ('34','España'),('56','Chile'),('54','Argentina'),('507','Panamá'),('506','Costa Rica'),
          ('502','Guatemala'),('55','Brasil'),('598','Uruguay'),('591','Bolivia'),('53','Cuba'),
          ('504','Honduras'),('503','El Salvador'),('595','Paraguay'),('1','EE.UU. / Canadá')]
PAISES.sort(key=lambda x: -len(x[0]))
def pais_of(ph):
    if not ph or not ph.startswith('+'): return 'Sin teléfono'
    for pre, nm in PAISES:
        if ph[1:].startswith(pre): return nm
    return 'Otros países'

def grupo(src):
    s = ' '.join((src or '').split()); sl = s.lower()
    if not sl or sl == '<unspecified>': return '(Sin fuente)'
    if 'google' in sl or sl.startswith('goo ') or sl == 'paid search': return 'Google / Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl: return 'Referidos / Personal'
    if sl.startswith('prensa'): return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'): return 'Sitio Web'
    return s

# último contacto real por conversaciones (cualquier canal) + espera WA
last_conv = defaultdict(int)
wait_dias = {}
for c in convos:
    if c.get('lastDate'):
        last_conv[c['contactId']] = max(last_conv[c['contactId']], c['lastDate'])
    if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound' and c.get('lastDate'):
        wait_dias[c['contactId']] = int((NOW_TS - c['lastDate']) / 86400000)

def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi
DR, giR = dict_indexer(); DA, giA = dict_indexer()
DM, giM = dict_indexer(); DF, giF = dict_indexer()
DK, giK = dict_indexer(); DTG, giTG = dict_indexer()

clientes = [ct for ct in contacts if (ct.get('leadStatus') or '').strip() == 'Cliente']

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


# ---------- followers: el asesor cuenta como owner O seguidor (solo lectura) ----------
try:
    _FWMAP = json.load(open(DATA / 'followers.json'))
except Exception:
    _FWMAP = {}
def fols(c):
    """user ids que siguen al contacto (del fetch o del mapa aparte)."""
    return c.get('followers') or _FWMAP.get(c['id'], [])
ROWS = []
for ct in clientes:
    rl = ct.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(x.strip() for x in rl if x and x.strip()) or '(Sin realtor)'
    a = users.get(ct['assigned'], '(Sin asesor)') if ct['assigned'] else '(Sin asesor)'
    ku = (ct.get('enCursoPor') or '').strip() or '(Sin dato)'
    tags = [t.strip() for t in (ct.get('tags') or []) if t and t.strip()]
    elite = 1 if any('elite' in t.lower() for t in tags) else 0
    lc = last_conv.get(ct['id'])
    ultimo = int((NOW_TS - lc) / 86400000) if lc else None
    inter = _n(ct.get('vecesContactado')) + _n(ct.get('salesActivities'))
    ROWS.append([(ct.get('name') or '(sin nombre)').strip().title(),
                 ct.get('email') or '', ct.get('phone') or '',
                 giR(rl[:60]), giA(a), giM(pais_of(ct.get('phone'))), giF(grupo(ct.get('source'))),
                 giK(ku), score_of(ct), (ct.get('created') or '')[:10],
                 ultimo, wait_dias.get(ct['id']), elite, inter,
                 [giTG(t) for t in tags[:8]], intentos_of(ct['id']),
                 [giA(users[u]) for u in fols(ct) if u in users]])

TOTAL = len(ROWS)
n_oport = sum(1 for r in ROWS if 'Oportunidad' in list(DK)[r[7]] if True) if False else 0
# conteos (en python, para el hero)
K_LIST = [k for k, _ in sorted(DK.items(), key=lambda x: x[1])]
n_oport = sum(1 for r in ROWS if K_LIST[r[7]].startswith('Oportunidad'))
n_esp = sum(1 for r in ROWS if r[11] is not None)
n_elite = sum(1 for r in ROWS if r[12])
n_frios180 = sum(1 for r in ROWS if r[10] is None or r[10] > 180)
n_activos30 = sum(1 for r in ROWS if r[10] is not None and r[10] <= 30)
n_tel = sum(1 for r in ROWS if r[2])
M_LIST = [k for k, _ in sorted(DM.items(), key=lambda x: x[1])]
top_merc = Counter(M_LIST[r[5]] for r in ROWS).most_common(1)[0]

def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
PAYLOAD = json.dumps({'rows': ROWS, 'rl': ordered(DR), 'ase': ordered(DA), 'me': ordered(DM),
                      'fu': ordered(DF), 'cu': ordered(DK), 'tg': ordered(DTG)}, ensure_ascii=False)


HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fidelización de clientes</title>
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
h2{{font-size:16.5px;margin:24px 0 8px;border-bottom:2px solid var(--gris-linea);padding-bottom:5px}}
h3{{font-size:14px;margin:14px 0 5px}}
.hero{{background:var(--azul-oscuro);color:#F2F6FA;border-radius:14px;padding:18px 22px;margin:16px 0;font-size:15px;line-height:1.6}}
.hero b{{color:var(--amarillo)}}
.filters{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:13px;padding:14px;margin-top:14px;
display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px}}
.filters label{{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gris);font-weight:800;display:block;margin-bottom:3px}}
.filters select,.filters input{{width:100%;border:1.5px solid var(--gris-linea);border-radius:8px;padding:7px 9px;font-size:13px;background:#fff;color:var(--tinta)}}
.fbar{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
.chip{{display:inline-flex;align-items:center;gap:6px;border:1.5px solid var(--gris-linea);border-radius:20px;
padding:6px 13px;font-size:12.5px;font-weight:700;cursor:pointer;user-select:none;background:#fff;color:var(--azul-oscuro)}}
.chip:hover{{border-color:var(--azul)}}
.chip.on{{background:var(--azul-oscuro);color:#fff;border-color:var(--azul-oscuro)}}
.chip b{{color:var(--rojo)}} .chip.on b{{color:var(--amarillo)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:10px;margin:12px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:10px 12px}}
.kpi b{{font-size:21px;display:block}} .kpi span{{font-size:11px;color:var(--gris)}}
.kpi[data-kf]{{cursor:pointer}} .kpi[data-kf]:hover{{border-color:var(--azul);background:var(--gris-fondo)}}
.kpi.on{{outline:2px solid var(--azul-oscuro);outline-offset:1px}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}}
table{{border-collapse:collapse;width:100%;font-size:12.8px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:7px 8px;white-space:nowrap;position:sticky;top:0;background:#fff}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:top}}
tr:hover td{{background:var(--gris-fondo)}}
tr.clk{{cursor:pointer}}
.bar{{background:var(--gris-fondo);border-radius:6px;height:15px;min-width:110px}}
.bar>div{{height:100%;border-radius:6px;background:var(--azul)}}
.tag{{display:inline-block;min-width:30px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
.tbox{{border:1px solid var(--gris-linea);border-radius:12px;overflow:auto;max-height:70vh}}
a{{color:var(--azul)}}
[data-tip]{{cursor:help}} th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:24px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Fidelización de clientes y venta cruzada</h1>
<p>CRM comercial (solo lectura) · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(TOTAL)}</b><span>clientes</span></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html" class="act"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="hero">💎 <b>La base de clientes es un activo dormido:</b> {fmt(TOTAL)} clientes, y <b>{fmt(n_oport)} tienen una nueva oportunidad de compra REGISTRADA</b> ("En curso por" vigente) — recompra declarada esperando gestión. Hay <b>{fmt(n_esp)} clientes esperando respuesta en WhatsApp</b> (post-venta roto), solo <b>{fmt(n_elite)} son miembros Elite activos</b>, y <b>{fmt(n_frios180)} llevan 180+ días sin ninguna conversación</b>. El mercado más grande es <b>{top_merc[0]} ({fmt(top_merc[1])} clientes)</b> y {fmt(n_tel)} tienen teléfono directo. Cada fila de esta hoja es una venta cruzada o un referido potencial.</div>

<h2>Segmentos de venta cruzada <span style="color:var(--gris);font-weight:600;font-size:12px">(clic para filtrar la hoja completa)</span></h2>
<div class="fbar" id="chips">
<span class="chip" data-p="oport" data-tip="Clientes con 'En curso por' = Oportunidad vigente: declararon una NUEVA compra y está registrado en el CRM. La recompra más fácil del mundo: llamar esta semana.">🔁 Recompra declarada: <b>{fmt(n_oport)}</b></span>
<span class="chip" data-p="esp" data-tip="Clientes que escribieron por WhatsApp y nadie les respondió. Un cliente ignorado no recompra ni refiere: responder HOY.">⏳ Post-venta roto: <b>{fmt(n_esp)}</b></span>
<span class="chip" data-p="elite" data-tip="Clientes con etiqueta de miembro Elite Club activo. El programa de beneficios que genera recompra: la meta es crecer este número.">👑 Elite activos: <b>{fmt(n_elite)}</b></span>
<span class="chip" data-p="frio" data-tip="Clientes sin ninguna conversación en 180+ días (o nunca). Reactivarlos con motivo real: aniversario de compra, valorización de su propiedad, nuevo lanzamiento.">🧊 Sin contacto 180+ días: <b>{fmt(n_frios180)}</b></span>
<span class="chip" data-p="activo" data-tip="Clientes con conversación en los últimos 30 días: la relación está viva. El mejor momento para pedir referidos y ofrecer la siguiente inversión.">🤝 Relación viva (≤30 días): <b>{fmt(n_activos30)}</b></span>
<span class="chip" data-p="" data-tip="Quitar el segmento y ver todos los clientes.">Todos: <b>{fmt(TOTAL)}</b></span>
</div>

<div class="filters">
<div><label data-tip="Realtor vinculado al cliente: el dueño natural de la relación post-venta.">Realtor</label><select id="f-r" autocomplete="off"></select></div>
<div><label data-tip="Asesor del cliente contando OWNER (assignedTo) o SEGUIDOR (followers) — solo cambia la consulta, el CRM no se toca.">Asesor</label><select id="f-a" autocomplete="off"></select></div>
<div><label data-tip="Mercado por indicativo telefónico del cliente.">Mercado (país)</label><select id="f-m" autocomplete="off"></select></div>
<div><label data-tip="Fuente original por la que llegó (campo Fuente de contacto, agrupado).">Fuente original</label><select id="f-f" autocomplete="off"></select></div>
<div><label data-tip="Campo 'En curso por': si tiene una nueva oportunidad de compra registrada.">Oportunidad vigente</label><select id="f-k" autocomplete="off"><option value="">Todos</option><option value="si">🔁 Con oportunidad (recompra)</option><option value="no">Sin oportunidad</option></select></div>
<div><label data-tip="Días desde la última conversación del cliente en cualquier canal (calculado de las conversaciones del CRM, no del campo de actividad que está vacío para clientes).">Último contacto</label><select id="f-u" autocomplete="off"><option value="">Todos</option><option value="30">≤ 30 días</option><option value="90">31-90 días</option><option value="180">91-180 días</option><option value="viejo">180+ días o nunca</option></select></div>
<div><label data-tip="Clientes esperando respuesta en WhatsApp.">Esperando respuesta</label><select id="f-e" autocomplete="off"><option value="">Todos</option><option value="si">⏳ Sí</option></select></div>
<div><label data-tip="Miembros del Elite Club (por etiqueta).">Elite Club</label><select id="f-el" autocomplete="off"><option value="">Todos</option><option value="si">👑 Elite activo</option><option value="no">No Elite</option></select></div>
<div><label>Buscar (nombre, email, teléfono)</label><input id="f-q" autocomplete="off" placeholder="Escribe para filtrar…"></div>
</div>

<div class="fbar">
<button class="btn sec" onclick="reset()">✕ Limpiar</button>
<span id="resumen" style="font-size:12.5px;color:var(--gris)"></span>
</div>

<div class="kpis">
<div class="kpi" data-kf="ver" data-tip="Clientes que cumplen los filtros activos. Clic para ir directo a la lista."><b id="k-n">—</b><span>clientes en la vista</span></div>
<div class="kpi" data-kf="oport" data-tip="De la vista, cuántos tienen oportunidad de recompra registrada. Clic para ver exactamente cuáles son en la tabla."><b id="k-o" style="color:var(--verde)">—</b><span>recompra declarada</span></div>
<div class="kpi" data-kf="esp" data-tip="De la vista, cuántos esperan respuesta en WhatsApp. Clic para ver cuáles son."><b id="k-e" style="color:var(--rojo)">—</b><span>esperando respuesta</span></div>
<div class="kpi" data-kf="elite" data-tip="De la vista, cuántos son Elite activos. Clic para ver cuáles son."><b id="k-el" style="color:#8A6D1A">—</b><span>elite activos</span></div>
<div class="kpi" data-kf="frio" data-tip="De la vista, sin conversación en 180+ días o nunca. Clic para ver cuáles son."><b id="k-f" style="color:var(--azul)">—</b><span>sin contacto 180+ d</span></div>
<div class="kpi" data-kf="tel" data-tip="De la vista, con teléfono directo para llamar. Clic para ver cuáles son."><b id="k-t">—</b><span>con teléfono</span></div>
</div>

<h2>Segmentaciones <span style="color:var(--gris);font-weight:600;font-size:12px">(reaccionan a los filtros; clic en una fila para filtrar por ella)</span></h2>
<div class="grid2">
<div><h3>🌎 Mercado (país)</h3><table><tbody id="d-me"></tbody></table></div>
<div><h3>🏠 Realtor (dueño de la relación)</h3><table><tbody id="d-rl"></tbody></table></div>
<div><h3>📣 Fuente original</h3><table><tbody id="d-fu"></tbody></table></div>
<div><h3>🔁 En curso por (recompra)</h3><table><tbody id="d-cu"></tbody></table>
<h3>🕓 Último contacto</h3><table><tbody id="d-ul"></tbody></table></div>
</div>

<h2>Los clientes, uno a uno</h2>
<p style="font-size:12px;color:var(--gris)">Ordenados por score de recompra (oportunidad + interacciones + recencia). "Últ. contacto" = días desde su última conversación en cualquier canal.</p>
<div class="tbox"><table><thead><tr>
<th data-tip="Score de recompra 0-100: 'En curso por' hasta 35 pts + interacciones hasta 20 + recencia de actividad hasta 40. (Para clientes el Lead Status no suma.)">Score</th>
<th>Cliente</th>
<th data-tip="Realtor vinculado: el dueño natural de la relación.">Realtor</th>
<th data-tip="Usuario del CRM asignado.">Asesor</th>
<th data-tip="Mercado por indicativo telefónico.">Mercado</th>
<th data-tip="Fuente original por la que llegó como lead.">Fuente</th>
<th data-tip="Nueva oportunidad registrada (campo En curso por).">En curso por</th>
<th data-tip="Días desde su última conversación en cualquier canal. '—' = nunca registrada.">Últ. contacto</th>
<th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp.">Teléfono</th>
<th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
<th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
<th data-tip="Etiquetas del CRM (Elite, eventos, campañas).">Etiquetas</th>
</tr></thead><tbody id="tb"></tbody></table></div>
<div class="fbar" id="pag"></div>

<div class="warnpii"><b>⚠ Datos personales:</b> esta hoja contiene nombres, correos y teléfonos de {fmt(TOTAL)} clientes (Habeas Data). Uso exclusivo del equipo comercial autorizado.</div>
<footer>Generado desde la API de GoHighLevel en modo solo lectura. Cliente = Lead Status "Cliente". Último contacto calculado como la conversación más reciente del cliente en cualquier canal (el campo de actividad del CRM está vacío para clientes). Elite = etiqueta con "elite". Score de recompra con la fórmula estándar del dashboard (sin puntos de Lead Status). Corte: {CORTE}.</footer>
</div>
<script>
const D = {PAYLOAD};
const fmtN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = s => s >= 55 ? '#D64545' : s >= 30 ? '#AA9664' : s >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';

const pc = (a, b) => b ? (a / b * 100).toLocaleString('es-CO', {{maximumFractionDigits: 1}}) + '%' : '—';
function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tg[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" data-tip="Todas las etiquetas: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
function fill(id, nombres, orden) {{
  const s = document.getElementById(id);
  s.innerHTML = '<option value="">Todos</option>' + orden.map(i =>
    `<option value="${{i}}">${{esc(nombres[i])}}</option>`).join('');
}}
const volumen = col => {{
  const c = new Map();
  D.rows.forEach(r => c.set(r[col], (c.get(r[col]) || 0) + 1));
  return [...c.entries()].sort((a, b) => b[1] - a[1]).map(e => e[0]);
}};
fill('f-r', D.rl, volumen(3)); fill('f-a', D.ase, volumen(4));
fill('f-m', D.me, volumen(5)); fill('f-f', D.fu, volumen(6));

let PRESET = '', TEL = '', view = [], page = 0;
const ULT = (u, v) => v === '30' ? u !== null && u <= 30 : v === '90' ? u !== null && u > 30 && u <= 90
  : v === '180' ? u !== null && u > 90 && u <= 180 : v === 'viejo' ? (u === null || u > 180) : true;
function apply() {{
  const g = id => document.getElementById(id).value;
  const fr = g('f-r'), fa = g('f-a'), fm = g('f-m'), ff = g('f-f'), fk = g('f-k'),
        fu = g('f-u'), fe = g('f-e'), fel = g('f-el'), q = g('f-q').trim().toLowerCase();
  view = D.rows.filter(r => {{
    const oport = D.cu[r[7]].startsWith('Oportunidad');
    if (PRESET === 'oport' && !oport) return false;
    if (PRESET === 'esp' && r[11] === null) return false;
    if (PRESET === 'elite' && !r[12]) return false;
    if (PRESET === 'frio' && !(r[10] === null || r[10] > 180)) return false;
    if (PRESET === 'activo' && !(r[10] !== null && r[10] <= 30)) return false;
    return (fr === '' || r[3] == fr) && (fa === '' || r[4] == fa || (r[16] && r[16].indexOf(+fa) !== -1)) && (fm === '' || r[5] == fm) &&
      (ff === '' || r[6] == ff) &&
      (fk === '' || (fk === 'si' ? oport : !oport)) &&
      ULT(r[10], fu) &&
      (fe === '' || r[11] !== null) &&
      (fel === '' || (fel === 'si' ? r[12] === 1 : r[12] === 0)) &&
      (TEL === '' || r[2] !== '') &&
      (q === '' || (r[0] + ' ' + r[1] + ' ' + r[2]).toLowerCase().includes(q));
  }}).sort((x, y) => y[8] - x[8]);
  document.querySelectorAll('#chips .chip').forEach(c => c.classList.toggle('on', c.dataset.p === PRESET && PRESET !== ''));
  const n = view.length;
  let o = 0, e = 0, el = 0, f = 0, t = 0;
  view.forEach(r => {{
    if (D.cu[r[7]].startsWith('Oportunidad')) o++;
    if (r[11] !== null) e++;
    if (r[12]) el++;
    if (r[10] === null || r[10] > 180) f++;
    if (r[2]) t++;
  }});
  document.getElementById('k-n').textContent = fmtN(n);
  document.getElementById('k-o').textContent = fmtN(o);
  document.getElementById('k-e').textContent = fmtN(e);
  document.getElementById('k-el').textContent = fmtN(el);
  document.getElementById('k-f').textContent = fmtN(f);
  document.getElementById('k-t').textContent = fmtN(t);
  document.getElementById('resumen').textContent = n === D.rows.length
    ? `Mostrando los ${{fmtN(n)}} clientes.` : `Filtro activo${{TEL === 'si' ? ' · solo con teléfono' : ''}}: ${{fmtN(n)}} de ${{fmtN(D.rows.length)}} clientes.`;
  pintaKpis(); dists(); page = 0; tabla();
}}
function distTable(elId, col, nombres, filtroSel, topN) {{
  const c = new Map();
  view.forEach(r => c.set(r[col], (c.get(r[col]) || 0) + 1));
  const tot = view.length || 1;
  document.getElementById(elId).innerHTML = [...c.entries()].sort((a, b) => b[1] - a[1]).slice(0, topN).map(([i, n]) =>
    `<tr class="clk" data-sel="${{filtroSel}}" data-v="${{i}}" data-tip="Clic para filtrar por ${{esc(nombres[i])}}."><td style="white-space:nowrap">${{esc(nombres[i]).slice(0, 30)}}</td>
    <td style="width:42%"><div class="bar"><div style="width:${{Math.max(2, n / tot * 100)}}%"></div></div></td>
    <td style="white-space:nowrap">${{fmtN(n)}} · ${{pc(n, tot)}}</td></tr>`).join('');
}}
function dists() {{
  distTable('d-me', 5, D.me, 'f-m', 12);
  distTable('d-rl', 3, D.rl, 'f-r', 12);
  distTable('d-fu', 6, D.fu, 'f-f', 10);
  distTable('d-cu', 7, D.cu, 'f-k2', 8);
  // último contacto (buckets)
  const b = {{'≤ 30 días': 0, '31-90 días': 0, '91-180 días': 0, '180+ días o nunca': 0}};
  view.forEach(r => {{
    const u = r[10];
    if (u !== null && u <= 30) b['≤ 30 días']++;
    else if (u !== null && u <= 90) b['31-90 días']++;
    else if (u !== null && u <= 180) b['91-180 días']++;
    else b['180+ días o nunca']++;
  }});
  const tot = view.length || 1;
  const vals = {{'≤ 30 días': '30', '31-90 días': '90', '91-180 días': '180', '180+ días o nunca': 'viejo'}};
  document.getElementById('d-ul').innerHTML = Object.entries(b).map(([k, n]) =>
    `<tr class="clk" data-sel="f-u" data-v="${{vals[k]}}" data-tip="Clic para filtrar por ${{k}}."><td style="white-space:nowrap">${{k}}</td>
    <td style="width:42%"><div class="bar"><div style="width:${{Math.max(2, n / tot * 100)}}%"></div></div></td>
    <td style="white-space:nowrap">${{fmtN(n)}} · ${{pc(n, tot)}}</td></tr>`).join('');
  document.querySelectorAll('tr.clk[data-sel]').forEach(tr => tr.addEventListener('click', () => {{
    const sel = tr.dataset.sel;
    if (sel === 'f-k2') {{
      const nombre = D.cu[+tr.dataset.v];
      document.getElementById('f-k').value = nombre.startsWith('Oportunidad') ? 'si' : 'no';
    }} else {{
      const s = document.getElementById(sel);
      s.value = s.value == tr.dataset.v ? '' : tr.dataset.v;
    }}
    apply();
  }}));
}}
function tabla() {{
  const P = 100;
  const pages = Math.max(1, Math.ceil(view.length / P));
  page = Math.min(page, pages - 1);
  document.getElementById('tb').innerHTML = view.slice(page * P, page * P + P).map(r => {{
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank"><b>WA</b></a>' : ''}}` : '—';
    const ec = D.cu[r[7]];
    return `<tr><td><span class="tag" style="background:${{scCol(r[8])}}">${{r[8]}}</span>${{r[11] !== null ? ' <span data-tip="Esperando respuesta en WhatsApp hace ' + fmtN(r[11]) + ' días">⏳</span>' : ''}}${{r[12] ? ' <span data-tip="Miembro Elite Club activo">👑</span>' : ''}}</td>
    <td><b>${{esc(r[0])}}</b></td><td>${{esc(D.rl[r[3]])}}</td><td>${{esc(D.ase[r[4]])}}</td>
    <td>${{esc(D.me[r[5]])}}</td><td>${{esc(D.fu[r[6]])}}</td>
    <td>${{ec.startsWith('Oportunidad') ? '<b style="color:var(--verde)">' + esc(ec) + '</b>' : esc(ec)}}</td>
    <td>${{r[10] === null ? '—' : fmtN(r[10]) + ' d'}}</td>
    <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td><td style="white-space:nowrap" data-tip="${{intTip(r[15])}}">${{intCell(r[15])}}</td><td data-tip="${{intTip(r[15])}}">${{canCell(r[15])}}</td><td>${{tagsCell(r[14])}}</td></tr>`;
  }}).join('');
  document.getElementById('pag').innerHTML = pages > 1
    ? `<button class="btn sec" onclick="page--;tabla()" ${{page === 0 ? 'disabled' : ''}}>‹ Anterior</button>
       página ${{fmtN(page + 1)}} de ${{fmtN(pages)}}
       <button class="btn sec" onclick="page++;tabla()" ${{page >= pages - 1 ? 'disabled' : ''}}>Siguiente ›</button>`
    : (view.length ? `${{fmtN(view.length)}} clientes` : 'Sin resultados.');
}}
function reset() {{
  PRESET = ''; TEL = '';
  ['f-r','f-a','f-m','f-f','f-k','f-u','f-e','f-el'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-q').value = '';
  apply();
}}
['f-r','f-a','f-m','f-f','f-k','f-u','f-e','f-el'].forEach(id => document.getElementById(id).addEventListener('change', apply));
document.getElementById('f-q').addEventListener('input', apply);
document.querySelectorAll('#chips .chip').forEach(c => c.addEventListener('click', () => {{
  PRESET = PRESET === c.dataset.p ? '' : c.dataset.p;
  apply();
}}));
/* KPIs clicables: aplican el filtro y bajan a la tabla para ver cuáles son */
document.querySelectorAll('.kpi[data-kf]').forEach(k => k.addEventListener('click', () => {{
  const f = k.dataset.kf;
  const tgl = (id, v) => {{ const s = document.getElementById(id); s.value = s.value === v ? '' : v; }};
  if (f === 'oport') tgl('f-k', 'si');
  else if (f === 'esp') tgl('f-e', 'si');
  else if (f === 'elite') tgl('f-el', 'si');
  else if (f === 'frio') tgl('f-u', 'viejo');
  else if (f === 'tel') TEL = TEL === 'si' ? '' : 'si';
  apply();
  document.getElementById('tb').closest('.tbox').scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}));
function pintaKpis() {{
  const g = id => document.getElementById(id).value;
  const act = {{oport: g('f-k') === 'si', esp: g('f-e') === 'si', elite: g('f-el') === 'si',
               frio: g('f-u') === 'viejo', tel: TEL === 'si', ver: false}};
  document.querySelectorAll('.kpi[data-kf]').forEach(k => k.classList.toggle('on', !!act[k.dataset.kf]));
}}
reset();
window.addEventListener('pageshow', e => {{ if (e.persisted) reset(); }});
setTimeout(() => {{
  if (['f-r','f-a','f-m','f-f','f-k','f-u','f-e','f-el','f-q'].some(id => document.getElementById(id).value !== '')) reset();
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

out = str(ROOT / f'clientes-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB)')
print(f'clientes: {TOTAL} | recompra: {n_oport} | esperando: {n_esp} | elite: {n_elite} | frios180: {n_frios180} | activos30: {n_activos30}')
