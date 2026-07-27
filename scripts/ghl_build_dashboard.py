#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el dashboard HTML autocontenido de gestión comercial PFS Realty Group
a partir de scripts/data/{opps,users,pipelines}.json (lecturas GHL, cero escritura).
Ejecutar siempre después de ghl_fetch.py. Salida: raíz del proyecto, con fecha en el nombre."""
import json, html
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'

# ---------- carga ----------
opps  = json.load(open(DATA / 'opps.json'))
USERS = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
STG   = {s['id']: s['name'] for p in json.load(open(DATA / 'pipelines.json'))['pipelines'] for s in p['stages']}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
NOW   = datetime.now(timezone.utc)
_hoy  = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

EARLY = {'Nuevo Lead','Intento de Contacto','COLD'}
PRO   = {'WARM','Llamada de Precalificación','Precalificación Financiera','Atención Contador',
         'Date to Miami','Asistió Oficina Miami','Tour Miami','Toma Decision (HOT)','Pending (Elite Club)'}
ACT   = {'Intento de Contacto','Cita a Jornada/Evento/Webinar','Asistió a Jornada/Evento/Webinar',
         'Cita Virtual','Asisitió Presencial o Virtual'}
S1 = {'Toma Decision (HOT)','Pending (Elite Club)'}
S2 = {'Llamada de Precalificación','Precalificación Financiera','Atención Contador'}
S3 = {'Date to Miami','Asistió Oficina Miami','Tour Miami'}
S4 = {'Asistió a Jornada/Evento/Webinar','Asisitió Presencial o Virtual'}
CATS  = ['cli','pro','act','cold','sin','pc','des']
CATN  = {'cli':'Cierres (Elite Club)','pro':'Etapas avanzadas','act':'Gestión activa',
         'cold':'Base fría (COLD)','sin':'Sin gestionar','pc':'Perdidos por no-contacto','des':'Otros descartes'}
CATC  = {'cli':'#1E9E62','pro':'#AA9664','act':'#3A566B','cold':'#8A99A8','sin':'#C4B284','pc':'#D64545','des':'#5A6B78'}
BOLSAS = {'MARKETING PFS','Admin PFS Elite','Administrative PFS Realty','(Sin asesor asignado)'}

def cat_of(o):
    st = STG.get(o['stage'], '?'); s = o['status']
    if st == 'Cierre (Elite Club)' or s == 'won': return 'cli'
    if s in ('lost','abandoned'): return 'pc' if st in EARLY else 'des'
    if st in PRO: return 'pro'
    if st in ACT: return 'act'
    if st == 'COLD': return 'cold'
    return 'sin'

def fuente_of(o):
    s = (o['source'] or '').lower(); tg = [t.lower() for t in o['tags']]
    def anyt(*subs): return any(any(x in t for t in tg) for x in subs)
    if 'paid' in s or s in ('facebook','instagram','linkedin'): return 'Pauta digital'
    if any(k in s for k in ('evento','torneo','mundial','sanedr','master','proam','futbol','jornada')): return 'Eventos y activaciones'
    if any(k in s for k in ('formulario','web','landing')): return 'Web / Formularios'
    if 'organic' in s or 'orgánic' in s: return 'Redes orgánicas'
    if s == 'personal': return 'Referidos / Personal'
    if anyt('paid','always on','pauta'): return 'Pauta digital'
    if anyt('evento','jornada','activacion','torneo','congreso','interclubes','campestre','master','cdmx','golf','squash','proam'): return 'Eventos y activaciones'
    if anyt('lead web site','landing','formulario'): return 'Web / Formularios'
    if anyt('personal ','referido','rocio spurrier','marianela martinez'): return 'Referidos / Personal'
    if anyt('redes sociales','whatsapp','instagram','facebook','linkedin'): return 'Redes orgánicas'
    if anyt('nutrición','nutricion'): return 'Base cold (nutrición)'
    if anyt('importacion','importación'): return 'Base importada'
    return 'Sin atribución'

PAISES = [('57','Colombia'),('52','México'),('51','Perú'),('593','Ecuador'),('58','Venezuela'),
          ('34','España'),('56','Chile'),('54','Argentina'),('507','Panamá'),('506','Costa Rica'),
          ('502','Guatemala'),('55','Brasil'),('598','Uruguay'),('591','Bolivia'),('53','Cuba'),
          ('504','Honduras'),('503','El Salvador'),('595','Paraguay'),('1','EE.UU. / Canadá')]
PAISES.sort(key=lambda x: -len(x[0]))
def pais_of(ph):
    if not ph or not ph.startswith('+'): return 'Sin teléfono'
    n = ph[1:]
    for pre, nm in PAISES:
        if n.startswith(pre): return nm
    return 'Otros países'

GENERIC_TAGS = ('importacion','paid','always on','redes sociales','whatsapp','landing page',
                'lead web site','happy birthday','nutrición - base cold','activaciones de',
                'activaciones','base cold','pauta')
def campana_of(o):
    for t in o['tags']:
        tl = t.lower().strip()
        if not tl or any(tl.startswith(g) or tl == g for g in GENERIC_TAGS): continue
        return t.strip().title()[:60]
    return '—'

# ---------- clasificación ----------
tot = Counter(); fts = defaultdict(Counter); mkt = defaultdict(Counter)
adv = defaultdict(Counter); seg_tot = Counter()
adv_seg = defaultdict(Counter)
fte_camp = defaultdict(lambda: defaultdict(Counter))
audit = defaultdict(lambda: {c: [] for c in CATS})
s1_leads = defaultdict(list)
idx = {'cmp': {}, 'mer': {}, 'et': {}, 'org': {}}
def gi(d, k):
    if k not in idx[d]: idx[d][k] = len(idx[d])
    return idx[d][k]
stale = Counter(); stale_tot = Counter()

for o in opps:
    c = cat_of(o); st = STG.get(o['stage'], '?')
    f = fuente_of(o); m = pais_of(o['phone']); cp = campana_of(o)
    a = USERS.get(o['assigned'], '(Sin asesor asignado)') if o['assigned'] else '(Sin asesor asignado)'
    tot[c] += 1
    fts[f]['total'] += 1; fts[f][c] += 1
    mkt[m]['total'] += 1; mkt[m][c] += 1
    adv[a]['total'] += 1; adv[a][c] += 1
    fte_camp[f][cp][c] += 1; fte_camp[f][cp]['total'] += 1
    et_lbl = st + {'lost': ' · perdida', 'abandoned': ' · abandonada', 'won': ' · ganada'}.get(o['status'], '')
    nm = (o['name'] or '(sin nombre)').strip().title()
    row = [nm, o['email'], o['phone'], gi('cmp', cp), gi('mer', m), gi('et', et_lbl), gi('org', f)]
    audit[a][c].append(row)
    if o['status'] == 'open':
        if st in S1:
            adv_seg[a]['s1'] += 1; seg_tot['s1'] += 1
            s1_leads[a].append(row + [st])
        if st in S2: adv_seg[a]['s2'] += 1; seg_tot['s2'] += 1
        if st in S3: adv_seg[a]['s3'] += 1; seg_tot['s3'] += 1
        if st in S4: adv_seg[a]['s4'] += 1; seg_tot['s4'] += 1
    if o['stageChange'] and c in ('sin','act','pro'):
        d = (NOW - datetime.fromisoformat(o['stageChange'].replace('Z','+00:00'))).days
        stale_tot[c] += 1
        if d > 30: stale[c] += 1

TOTAL = sum(tot.values())
CONV  = tot['cli'] / TOTAL * 100
PARQ  = tot['sin'] + tot['cold']
CONTACT_PCT = (PARQ + tot['pc']) / TOTAL * 100
POT   = round(PARQ * CONV / 100)
huerf_cli = adv['(Sin asesor asignado)']['cli']
bolsa_total = sum(adv[b]['total'] for b in BOLSAS if b in adv)

# ---------- helpers formato ----------
def fmt(n):
    return f'{n:,}'.replace(',', '.')
def pct(x, d=1):
    return f'{x:.{d}f}'.replace('.', ',') + '%'
def esc(s):
    return html.escape(str(s), quote=True)

def sem(v, verde, ambar, invert=False):
    if invert:
        cls = 'ok' if v <= verde else ('warn' if v <= ambar else 'bad')
    else:
        cls = 'ok' if v >= verde else ('warn' if v >= ambar else 'bad')
    return f'<span class="pill {cls}">{pct(v)}</span>'

# ---------- SVG: embudo macro ----------
def svg_funnel():
    order = ['sin','cold','act','pro','cli','pc','des']
    W, RH, GAP, LX, BX = 760, 44, 14, 250, 260
    H = len(order) * (RH + GAP) + 20
    mx = max(tot[c] for c in order)
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" style="width:100%;height:auto">']
    y = 10
    for c in order:
        v = tot[c]; bw = max(4, v / mx * (W - BX - 130))
        parts.append(f'<text x="{LX-10}" y="{y+RH/2+5}" text-anchor="end" font-size="15" fill="#152238" font-weight="600">{esc(CATN[c])}</text>')
        parts.append(f'<rect x="{BX}" y="{y}" width="{bw:.0f}" height="{RH}" rx="7" fill="{CATC[c]}"/>')
        parts.append(f'<text x="{BX+bw+10:.0f}" y="{y+RH/2+5}" font-size="15" fill="#152238" font-weight="700">{fmt(v)}</text>')
        parts.append(f'<text x="{BX+bw+10:.0f}" y="{y+RH/2+21}" font-size="12" fill="#5B6B85">{pct(v/TOTAL*100)}</text>')
        y += RH + GAP
    parts.append('</svg>')
    return ''.join(parts)

# ---------- SVG: dona fuentes ----------
PIE_COLS = ['#2C4356','#C4B284','#AA9664','#5A7187','#9AB3D9','#CFD6E2','#3A566B','#8A99A8']
import math
def arc_path(cx, cy, r0, r1, a0, a1):
    la = 1 if (a1 - a0) > math.pi else 0
    def pt(r, a): return f'{cx + r*math.cos(a):.2f},{cy + r*math.sin(a):.2f}'
    return (f'M{pt(r1,a0)} A{r1},{r1} 0 {la} 1 {pt(r1,a1)} L{pt(r0,a1)} '
            f'A{r0},{r0} 0 {la} 0 {pt(r0,a0)} Z')

def svg_donut(items, total, center_top, center_bot, pid=''):
    cx = cy = 150; parts = [f'<svg viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:290px;height:auto">']
    a = -math.pi / 2
    for i, (name, v) in enumerate(items):
        if v <= 0: continue
        a1 = a + v / total * 2 * math.pi
        seg = arc_path(cx, cy, 62, 118, a, min(a1, a + 2*math.pi - 1e-4))
        extra = f' data-pie="{pid}" data-i="{i}" class="pieseg"' if pid else ''
        parts.append(f'<path d="{seg}" fill="{PIE_COLS[i % len(PIE_COLS)]}" stroke="#fff" stroke-width="2"{extra}><title>{esc(name)}: {fmt(v)}</title></path>')
        a = a1
    parts.append(f'<text x="150" y="145" text-anchor="middle" font-size="26" font-weight="800" fill="#152238" class="dcenter-top">{esc(center_top)}</text>')
    parts.append(f'<text x="150" y="168" text-anchor="middle" font-size="12" fill="#5B6B85" class="dcenter-bot">{esc(center_bot)}</text>')
    parts.append('</svg>')
    return ''.join(parts)

# ---------- SVG: mercados ----------
MK = [m for m, _ in sorted(mkt.items(), key=lambda x: -x[1]['total']) if m not in ('Sin teléfono',)][:12]
def svg_mercados_conv():
    W, RH, GAP = 720, 30, 10; H = len(MK) * (RH + GAP) + 30
    mxc = max(mkt[m]['cli'] / mkt[m]['total'] * 100 for m in MK)
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']
    y = 12
    for m in MK:
        d = mkt[m]; cv = d['cli'] / d['total'] * 100
        bw = max(3, cv / max(mxc, 1) * (W - 360))
        parts.append(f'<text x="150" y="{y+RH/2+5}" text-anchor="end" font-size="13.5" fill="#152238" font-weight="600">{esc(m)}</text>')
        parts.append(f'<rect x="160" y="{y}" width="{bw:.0f}" height="{RH}" rx="6" fill="{"#1E9E62" if cv >= CONV else "#5A7187"}"/>')
        parts.append(f'<text x="{160+bw+8:.0f}" y="{y+RH/2+5}" font-size="13.5" font-weight="700" fill="#152238">{pct(cv)}</text>')
        parts.append(f'<text x="{W-10}" y="{y+RH/2+5}" text-anchor="end" font-size="12" fill="#5B6B85">{fmt(d["total"])} leads · {fmt(d["cli"])} cierres</text>')
        y += RH + GAP
    parts.append(f'<line x1="160" y1="6" x2="160" y2="{H-14}" stroke="#E4E9F2"/>')
    parts.append('</svg>')
    return ''.join(parts)

def svg_mercados_stack():
    W, RH, GAP = 720, 26, 9; H = len(MK) * (RH + GAP) + 66
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']
    y = 12
    for m in MK:
        d = mkt[m]; t = d['total']; x = 160.0
        parts.append(f'<text x="150" y="{y+RH/2+5}" text-anchor="end" font-size="13.5" fill="#152238" font-weight="600">{esc(m)}</text>')
        for c in ['cli','pro','act','cold','sin','pc','des']:
            w = d[c] / t * (W - 260)
            if w > 0.4:
                parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{RH}" fill="{CATC[c]}"><title>{esc(CATN[c])}: {fmt(d[c])} ({pct(d[c]/t*100)})</title></rect>')
            x += w
        parts.append(f'<text x="{x+8:.0f}" y="{y+RH/2+5}" font-size="12" fill="#5B6B85">{fmt(t)}</text>')
        y += RH + GAP
    lx, ly = 160, y
    for c in ['cli','pro','act','cold','sin','pc','des']:
        lbl = CATN[c].replace(' (Elite Club)','').replace(' (COLD)','').replace(' por no-contacto',' no-contacto')
        w = 16 + 6.5 * len(lbl) + 18
        if lx + w > W - 10:
            lx = 160; ly += 20
        parts.append(f'<rect x="{lx:.0f}" y="{ly+4}" width="12" height="12" rx="3" fill="{CATC[c]}"/>')
        parts.append(f'<text x="{lx+16:.0f}" y="{ly+14}" font-size="10.5" fill="#5B6B85">{esc(lbl)}</text>')
        lx += w
    parts.append('</svg>')
    return ''.join(parts)

# ---------- SVG: matriz burbujas ----------
HUM = [(a, d) for a, d in adv.items() if a not in BOLSAS and d['total'] >= 50]
def svg_matriz():
    W, H, ML, MB, MT, MR = 860, 560, 70, 56, 24, 30
    pw, ph = W - ML - MR, H - MT - MB
    XLINE, YLINE = 55.0, 8.0
    xmax, ymax = 100.0, max(12.0, max(d['cli']/d['total']*100 for _, d in HUM) * 1.12)
    mxt = max(d['total'] for _, d in HUM)
    def X(v): return ML + v / xmax * pw
    def Y(v): return MT + ph - v / ymax * ph
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']
    for gv in range(0, 101, 20):
        p.append(f'<line x1="{X(gv):.0f}" y1="{MT}" x2="{X(gv):.0f}" y2="{MT+ph}" stroke="#EFF2F7"/>')
        p.append(f'<text x="{X(gv):.0f}" y="{H-30}" text-anchor="middle" font-size="12" fill="#5B6B85">{gv}%</text>')
    gy = 0
    while gy <= ymax:
        p.append(f'<line x1="{ML}" y1="{Y(gy):.0f}" x2="{ML+pw}" y2="{Y(gy):.0f}" stroke="#EFF2F7"/>')
        p.append(f'<text x="{ML-8}" y="{Y(gy)+4:.0f}" text-anchor="end" font-size="12" fill="#5B6B85">{gy:.0f}%</text>')
        gy += max(2, round(ymax / 6))
    p.append(f'<line x1="{X(XLINE):.0f}" y1="{MT}" x2="{X(XLINE):.0f}" y2="{MT+ph}" stroke="#AA9664" stroke-dasharray="6 5" stroke-width="1.6"/>')
    p.append(f'<line x1="{ML}" y1="{Y(YLINE):.0f}" x2="{ML+pw}" y2="{Y(YLINE):.0f}" stroke="#AA9664" stroke-dasharray="6 5" stroke-width="1.6"/>')
    xl, xr = X(XLINE/2), X(XLINE + (100-XLINE)/2)
    p.append(f'<text x="{xl:.0f}" y="{MT+16}" text-anchor="middle" font-size="12.5" font-weight="800" fill="#5B6B85" opacity=".75">CIERRAN BIEN · ACTIVAR SU BASE PARQUEADA</text>')
    p.append(f'<text x="{xr:.0f}" y="{MT+16}" text-anchor="middle" font-size="12.5" font-weight="800" fill="#1E9E62" opacity=".8">REFERENTES</text>')
    p.append(f'<text x="{xl:.0f}" y="{MT+ph-10}" text-anchor="middle" font-size="12.5" font-weight="800" fill="#D64545" opacity=".75">PRIORIDAD DE INTERVENCIÓN</text>')
    p.append(f'<text x="{xr:.0f}" y="{MT+ph-10}" text-anchor="middle" font-size="12.5" font-weight="800" fill="#AA9664" opacity=".9">COACHING DE CIERRE</text>')
    for a, d in sorted(HUM, key=lambda x: -x[1]['total']):
        t = d['total']; cx = (d['act']+d['pro']+d['cli']) / t * 100; cy = d['cli'] / t * 100
        r = 7 + (t / mxt) ** .5 * 26
        col = '#1E9E62' if (cx >= XLINE and cy >= YLINE) else ('#D64545' if (cx < XLINE and cy < YLINE) else '#3A566B')
        p.append(f'<circle cx="{X(cx):.1f}" cy="{Y(cy):.1f}" r="{r:.1f}" fill="{col}" opacity=".34" stroke="{col}" stroke-width="1.6"><title>{esc(a)} · {fmt(t)} leads · cobertura efectiva {pct(cx)} · conversión {pct(cy)}</title></circle>')
        p.append(f'<text x="{X(cx):.1f}" y="{Y(cy)-r-3:.1f}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#152238">{esc(a.split()[0])} {esc((a.split()[1][:1]+".") if len(a.split())>1 else "")}</text>')
    p.append(f'<text x="{ML+pw/2}" y="{H-8}" text-anchor="middle" font-size="13" fill="#152238" font-weight="700">Cobertura efectiva (% de leads en gestión activa, etapas avanzadas o cierre) →</text>')
    p.append(f'<text x="18" y="{MT+ph/2}" text-anchor="middle" font-size="13" fill="#152238" font-weight="700" transform="rotate(-90 18 {MT+ph/2})">Conversión a cierre →</text>')
    p.append('</svg>')
    return ''.join(p)

# ---------- datos para JS ----------
FTS_ORDER = [f for f, _ in sorted(fts.items(), key=lambda x: -x[1]['total'])]
fte_js = {}
for f in FTS_ORDER:
    d = fts[f]
    camps = sorted(fte_camp[f].items(), key=lambda x: -x[1]['total'])
    camps = [[c, v['total'], v['cli'], v['pro']] for c, v in camps if c != '—'][:10]
    fte_js[f] = {'t': d['total'], **{c: d[c] for c in CATS}, 'camps': camps}

ADV_ORDER = [a for a, _ in sorted(adv.items(), key=lambda x: -x[1]['total'])]
audit_js = {'dicts': {d: [k for k, _ in sorted(v.items(), key=lambda x: x[1])] for d, v in idx.items()},
            'adv': {a: audit[a] for a in ADV_ORDER}}
s1_js = {a: v for a, v in s1_leads.items()}
segdef = [
 ('s1','🔥 Cierre inmediato','Toma Decision (HOT) + Pending (Elite Club)','Llamada HOY. Cierre de condiciones y agenda de firma. SLA <24 h.', seg_tot['s1']),
 ('s2','Precalificación en curso','Llamada de Precalificación + Precalif. Financiera + Atención Contador','Empujar el expediente financiero: checklist por WhatsApp y seguimiento cada 48 h.', seg_tot['s2']),
 ('s3','Experiencia Miami','Date to Miami + Asistió Oficina + Tour Miami','Cerrar agenda de visita/tour y llamada post-tour en <48 h con propuesta concreta.', seg_tot['s3']),
 ('s4','Asistieron y esperan paso','Asistió a jornada/evento/webinar o cita presencial-virtual','Cadencia de 3 toques en 5 días con oferta de siguiente paso (precalificación).', seg_tot['s4'])]

# ---------- tablas HTML ----------
def info(txt):
    return f'<button class="info" data-tip="{esc(txt)}" onclick="tip(this,event)" aria-label="definición">&#9432;</button>'

def tabla_fuentes():
    rows = []
    for i, f in enumerate(FTS_ORDER):
        d = fts[f]; cv = d['cli'] / d['total'] * 100; pq = (d['sin'] + d['cold']) / d['total'] * 100
        rows.append(f'<tr><td><span class="dot" style="background:{PIE_COLS[i%len(PIE_COLS)]}"></span>{esc(f)}</td>'
                    f'<td data-v="{d["total"]}">{fmt(d["total"])}</td><td data-v="{d["total"]/TOTAL*100:.2f}">{pct(d["total"]/TOTAL*100)}</td>'
                    f'<td data-v="{d["cli"]}">{fmt(d["cli"])}</td><td data-v="{cv:.2f}">{sem(cv,7.5,4)}</td>'
                    f'<td data-v="{pq:.2f}">{sem(pq,35,55,invert=True)}</td></tr>')
    return ''.join(rows)

def tabla_asesores():
    rows = []; mx = max(d['total'] for d in adv.values())
    for a in ADV_ORDER:
        d = adv[a]
        if d['total'] < 10: continue
        t = d['total']; cv = d['cli']/t*100; cob = (d['act']+d['pro']+d['cli'])/t*100
        cold = d['cold']/t*100; pcp = d['pc']/t*100
        bolsa = ' <span class="tagb">bolsa</span>' if a in BOLSAS else ''
        rows.append(f'<tr><td>{esc(a)}{bolsa}</td>'
            f'<td data-v="{t}"><div class="mb"><i style="width:{t/mx*100:.1f}%"></i></div>{fmt(t)}</td>'
            f'<td data-v="{cob:.2f}">{sem(cob,60,40)}</td>'
            f'<td data-v="{d["cli"]}">{fmt(d["cli"])}</td>'
            f'<td data-v="{cv:.2f}">{sem(cv,10,5)}</td>'
            f'<td data-v="{cold:.2f}">{sem(cold,30,55,invert=True)}</td>'
            f'<td data-v="{pcp:.2f}">{sem(pcp,2,6,invert=True)}</td>'
            f'<td data-v="{adv_seg[a]["s1"]}">{fmt(adv_seg[a]["s1"])}</td>'
            f'<td data-v="{adv_seg[a]["s3"]}">{fmt(adv_seg[a]["s3"])}</td></tr>')
    return ''.join(rows)

def tabla_segmentos():
    rows = []
    for a in ADV_ORDER:
        s = adv_seg[a]
        if sum(s.values()) == 0: continue
        drill = f' class="segrow" data-a="{esc(a)}"' if s['s1'] else ''
        rows.append(f'<tr{drill}><td>{esc(a)}{" &#9662;" if s["s1"] else ""}</td>'
                    + ''.join(f'<td data-v="{s[k]}">{fmt(s[k])}</td>' for k in ('s1','s2','s3','s4'))
                    + f'<td data-v="{sum(s.values())}"><b>{fmt(sum(s.values()))}</b></td></tr>')
    return ''.join(rows)

def cards_auditoria():
    cards = []
    for n, a in enumerate(ADV_ORDER):
        d = adv[a]; t = d['total']
        bar = ''.join(f'<i style="width:{d[c]/t*100:.2f}%;background:{CATC[c]}"></i>' for c in CATS if d[c])
        bolsa = ' <span class="tagb">bolsa</span>' if a in BOLSAS else ''
        cards.append(f'<a class="acard" href="#a/{n}"><b>{esc(a)}</b>{bolsa}<span>{fmt(t)} leads · {fmt(d["cli"])} cierres ({pct(d["cli"]/t*100)})</span><div class="cbar">{bar}</div></a>')
    return ''.join(cards)

# ---------- pies de calidad ----------
def pie_data(cat):
    items = [(f, fts[f][cat]) for f in FTS_ORDER]
    return [[f, v, fts[f]['total']] for f, v in items]

PIE_JS = {'cli': pie_data('cli'), 'pro': pie_data('pro'), 'pc': pie_data('pc')}

kpis = [
 ('Leads en pipeline', fmt(TOTAL), 'Oportunidades en PIPELINE PFS a la fecha de corte', ''),
 ('Cierres (Elite Club)', f'{fmt(tot["cli"])}', f'Conversión {pct(CONV)} de la base', 'k-ok'),
 ('Etapas avanzadas', fmt(tot['pro']), 'WARM → Pending: precalificación, Miami, decisión', ''),
 ('Gestión activa', fmt(tot['act']), 'Contacto, citas y asistencia a eventos', ''),
 ('Base fría (COLD)', fmt(tot['cold']), pct(tot['cold']/TOTAL*100) + ' de la base parqueada en COLD', 'k-warn'),
 ('Sin gestionar', fmt(tot['sin']), 'En "Nuevo Lead" sin avance de etapa', 'k-warn'),
 ('Perdidos no-contacto', fmt(tot['pc']), 'Perdidas/abandonadas en etapas de contacto', 'k-bad'),
]
kpi_html = ''.join(f'<div class="kpi {k[3]}"><span class="kv">{k[1]}</span><span class="kt">{k[0]}</span><span class="ks">{k[2]}</span></div>' for k in kpis)

seg_cards = ''.join(f'''<div class="segcard"><div class="segn">{fmt(s[4])}</div><b>{esc(s[1])}</b>
<span class="segd">{esc(s[2])}</span><p>{esc(s[3])}</p></div>''' for s in segdef)

stale_act_pct = stale['act']/max(stale_tot['act'],1)*100
mkx_rows = tabla_fuentes()

DATA_JS = json.dumps({'fts': fte_js, 'pies': PIE_JS, 'audit': audit_js, 's1': s1_js,
                      'cats': CATS, 'catn': CATN, 'catc': CATC, 'total': TOTAL,
                      'convProm': round(CONV, 2)}, ensure_ascii=False)

# =====================================================================  HTML
HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PFS Realty Group · Análisis de Gestión Comercial</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--rojo-suave:#FBEAEA;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;
--gris-fondo:#F7F9FC;--ok-bg:#E7F5EE;--warn-bg:#F7F1E3}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:15px;line-height:1.45}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 22px 60px}}
header{{background:var(--azul-oscuro);color:#fff;padding:26px 0 22px}}
header .wrap{{display:flex;align-items:center;gap:18px;padding-bottom:0}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:24px;letter-spacing:1px;padding:14px 16px;border-radius:10px}}
header h1{{font-size:21px;font-weight:800;line-height:1.25}}
header p{{color:#C9D6E4;font-size:13.5px;margin-top:3px}}
.hstats{{margin-left:auto;text-align:right}}
.hstats b{{font-size:30px;display:block}}
.hstats span{{font-size:12.5px;color:#C9D6E4}}
.strip{{height:7px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
h2{{font-size:19px;margin:44px 0 6px;color:var(--azul-oscuro)}}
h2 .num{{color:var(--naranja);margin-right:6px}}
.sub{{color:var(--gris);font-size:13.5px;margin-bottom:16px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:22px}}
.kpi{{border:1px solid var(--gris-linea);border-radius:12px;padding:14px 14px 12px;background:var(--gris-fondo)}}
.kpi .kv{{font-size:25px;font-weight:800;display:block}}
.kpi .kt{{font-weight:700;font-size:13px;display:block;margin-top:2px}}
.kpi .ks{{font-size:11.5px;color:var(--gris);display:block;margin-top:4px}}
.k-ok{{background:var(--ok-bg);border-color:#BFE3D0}} .k-ok .kv{{color:var(--verde)}}
.k-warn{{background:var(--warn-bg);border-color:#E4D6B0}} .k-warn .kv{{color:#8A6D1A}}
.k-bad{{background:var(--rojo-suave);border-color:#EFC7C7}} .k-bad .kv{{color:var(--rojo)}}
.banner{{background:var(--azul-oscuro);color:#fff;border-radius:14px;padding:26px 28px;margin-top:34px;border-left:10px solid var(--amarillo)}}
.banner b{{color:var(--amarillo)}} .banner .big{{font-size:34px;font-weight:900;color:var(--amarillo)}}
.banner p{{margin-top:8px;font-size:14.5px;color:#DCE5EE}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-items:start}}
@media(max-width:900px){{.grid2{{grid-template-columns:1fr}}}}
.card{{border:1px solid var(--gris-linea);border-radius:14px;padding:20px;background:#fff}}
.card h3{{font-size:15.5px;margin-bottom:10px;color:var(--azul-oscuro)}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th{{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:8px 8px;cursor:pointer;user-select:none;white-space:nowrap}}
th.noord{{cursor:default}}
td{{border-bottom:1px solid var(--gris-linea);padding:8px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.pill{{display:inline-block;padding:2px 9px;border-radius:20px;font-weight:700;font-size:12.5px}}
.ok{{background:var(--ok-bg);color:#137048}} .warn{{background:var(--warn-bg);color:#8A6D1A}} .bad{{background:var(--rojo-suave);color:var(--rojo)}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px}}
.mb{{background:var(--azul-suave);border-radius:4px;height:8px;width:110px;display:inline-block;margin-right:8px;vertical-align:middle}}
.mb i{{display:block;height:8px;border-radius:4px;background:var(--azul)}}
.tagb{{background:var(--warn-bg);color:#8A6D1A;font-size:10.5px;font-weight:800;padding:1px 7px;border-radius:9px;vertical-align:middle}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}
.chip{{border:1.5px solid var(--gris-linea);background:#fff;border-radius:22px;padding:7px 15px;font-size:13px;font-weight:600;cursor:pointer}}
.chip.on{{background:var(--azul-oscuro);color:#fff;border-color:var(--azul-oscuro)}}
.fkpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:14px 0}}
.fk{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:10px;padding:10px}}
.fk b{{font-size:20px;display:block}} .fk span{{font-size:11.5px;color:var(--gris)}}
.legend{{width:100%;font-size:13px}}
.legend td{{padding:5px 6px;border:0;cursor:pointer}}
.legend tr.dim{{opacity:.35}}
.toggle{{display:inline-flex;border:1.5px solid var(--gris-linea);border-radius:20px;overflow:hidden;margin-bottom:10px}}
.toggle button{{border:0;background:#fff;padding:6px 14px;font-size:12.5px;font-weight:700;cursor:pointer;color:var(--gris)}}
.toggle button.on{{background:var(--azul-oscuro);color:#fff}}
.pieseg{{cursor:pointer}} .pieseg.dim{{opacity:.25}}
.pieread{{background:var(--azul-suave);border-radius:10px;padding:10px 14px;font-size:13.5px;margin-top:10px;min-height:44px}}
.segcards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:16px 0 22px}}
.segcard{{border:1px solid var(--gris-linea);border-left:6px solid var(--naranja);border-radius:12px;padding:16px}}
.segcard .segn{{font-size:28px;font-weight:900;color:var(--azul-oscuro)}}
.segcard b{{display:block;margin:2px 0 6px}} .segcard .segd{{font-size:11.5px;color:var(--gris);display:block}}
.segcard p{{font-size:12.5px;margin-top:8px;background:var(--gris-fondo);border-radius:8px;padding:8px}}
.segrow{{cursor:pointer}} .segrow td:first-child{{color:var(--azul);font-weight:700}}
.drill td{{background:var(--gris-fondo)}}
.drillbox{{padding:12px}}
.search{{border:1.5px solid var(--gris-linea);border-radius:8px;padding:7px 12px;font-size:13.5px;width:250px;max-width:100%}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:8px 14px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
.reccards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}
.reccard{{border:1px solid var(--gris-linea);border-radius:12px;padding:16px;background:var(--gris-fondo)}}
.reccard b{{display:block;margin-bottom:6px;color:var(--azul-oscuro)}}
.reccard p{{font-size:13px}}
.pend{{border:2px dashed var(--naranja);border-radius:14px;padding:20px;margin-top:26px;background:#FDFBF6}}
.pend h3{{color:var(--naranja);font-size:15px;margin-bottom:10px}}
.pend li{{margin:7px 0 7px 18px;font-size:13.5px}}
.dec{{counter-reset:d}}
.deccard{{border-left:6px solid var(--amarillo);background:var(--gris-fondo);border-radius:10px;padding:16px 18px;margin:12px 0}}
.deccard b{{color:var(--azul-oscuro)}}
.acards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:11px;margin-top:14px}}
.acard{{border:1px solid var(--gris-linea);border-radius:11px;padding:12px 13px;text-decoration:none;color:var(--tinta);display:block}}
.acard:hover{{border-color:var(--azul)}}
.acard b{{font-size:13.5px}} .acard span{{display:block;font-size:11.5px;color:var(--gris);margin:4px 0 7px}}
.cbar{{display:flex;height:9px;border-radius:5px;overflow:hidden;background:var(--gris-linea)}}
.cbar i{{display:block;height:9px}}
.sheet{{display:none}} .sheet.on{{display:block}}
.statechips{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}
.schip{{border-radius:9px;padding:8px 13px;font-size:12.5px;font-weight:700;color:#fff}}
.colsec{{border:1px solid var(--gris-linea);border-radius:11px;margin:10px 0;overflow:hidden}}
.colsec>button{{width:100%;text-align:left;border:0;background:var(--gris-fondo);padding:11px 15px;font-size:13.5px;font-weight:700;cursor:pointer;color:var(--tinta)}}
.colsec .body{{padding:12px 15px;display:none}} .colsec.open .body{{display:block}}
.pag{{display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12.5px}}
.glos dt{{font-weight:800;margin-top:12px;color:var(--azul-oscuro)}} .glos dd{{margin-left:0;font-size:13.5px;color:var(--gris)}}
.info{{border:0;background:none;color:var(--azul);cursor:pointer;font-size:13px;padding:0 2px}}
#tipbox{{position:fixed;z-index:50;background:var(--azul-oscuro);color:#fff;padding:10px 13px;border-radius:9px;font-size:12.5px;max-width:290px;display:none;box-shadow:0 6px 24px rgba(7,32,49,.35)}}
.warnpii{{background:var(--rojo-suave);border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:12px 16px;font-size:12.5px;margin-top:30px}}
footer{{color:var(--gris);font-size:12px;margin-top:34px;border-top:1px solid var(--gris-linea);padding-top:14px}}
@media print{{.chips,.btn,.search{{display:none}}}}
</style></head><body>
<header><div class="wrap"><div class="logo">PFS</div>
<div><h1>Análisis de Gestión Comercial · Gerencia de Ventas</h1>
<p>PFS Realty Group · PIPELINE PFS (GoHighLevel) · Corte: {CORTE} · Solo lectura, la base del CRM no fue modificada</p></div>
<div class="hstats"><b>{fmt(TOTAL)}</b><span>oportunidades analizadas</span></div>
</div></header><div class="strip"></div>
<div class="wrap">

<div class="kpis">{kpi_html}</div>

<div class="banner"><span class="big">{pct(CONTACT_PCT)}</span> de la base está sin resultado por <b>contactabilidad, no por desinterés</b>: {fmt(tot['sin'])} leads sin gestionar, {fmt(tot['cold'])} parqueados en COLD y {fmt(tot['pc'])} perdidos por no-contacto — frente a solo {fmt(tot['des'])} descartes en etapas avanzadas ({pct(tot['des']/TOTAL*100)}).
<p>Si la base parqueada ({fmt(PARQ)} leads) se reactivara a la conversión promedio del pipeline ({pct(CONV)}), habría <b>≈{fmt(POT)} cierres potenciales</b> hoy dentro del CRM. Estimación, no proyección garantizada.</p></div>

<h2><span class="num">01</span>Embudo por macro-etapa {info('Cada lead se clasifica en un único macro-estado según su etapa de pipeline y su status. Cierres = etapa Cierre (Elite Club) o status won. Perdidos por no-contacto = oportunidades perdidas/abandonadas estando en Nuevo Lead, Intento de Contacto o COLD.')}</h2>
<p class="sub">Distribución de las {fmt(TOTAL)} oportunidades del PIPELINE PFS por macro-estado.</p>
<div class="card">{svg_funnel()}</div>

<h2><span class="num">02</span>Fuentes de la base {info('Fuente derivada: se usa el campo source de la oportunidad y, cuando está vacío (92% de los casos), los tags del contacto (pauta, eventos, importación, etc.).')}</h2>
<p class="sub">El campo "fuente" está vacío en el 92% de las oportunidades; la atribución se reconstruyó desde los tags. Ver módulo de datos pendientes.</p>
<div class="grid2"><div class="card" style="text-align:center">{svg_donut([(f, fts[f]['total']) for f in FTS_ORDER], TOTAL, fmt(TOTAL), 'leads')}</div>
<div class="card"><h3>Conversión y base parqueada por fuente</h3>
<table class="sortable" id="tf"><thead><tr><th data-k="0" class="noord">Fuente</th><th data-k="1" data-n="1">Leads</th><th data-k="2" data-n="1">% base</th><th data-k="3" data-n="1">Cierres</th><th data-k="4" data-n="1">Conv. {info('Cierres ÷ leads de la fuente × 100. Verde ≥7,5% · ámbar ≥4%.')}</th><th data-k="5" data-n="1">% parqueada {info('(Sin gestionar + COLD) ÷ leads de la fuente. Verde ≤35% · ámbar ≤55%.')}</th></tr></thead>
<tbody>{mkx_rows}</tbody></table></div></div>

<h2><span class="num">03</span>Comparador de eficiencia por fuente</h2>
<p class="sub">Selecciona una fuente para ver sus indicadores y sus principales campañas/eventos.</p>
<div class="card"><div class="chips" id="fchips"></div><div id="fpanel"></div></div>

<h2><span class="num">04</span>Calidad de fuente: ¿de dónde vienen los que cierran… y los que se pierden?</h2>
<div class="grid2">
<div class="card"><h3>¿De qué fuente vienen los cierres?</h3>
<div class="toggle"><button id="tg-cli" class="on" onclick="setPieA('cli')">Cierres</button><button id="tg-pro" onclick="setPieA('pro')">Etapas avanzadas</button></div>
<div style="text-align:center" id="pieA"></div><table class="legend" id="legA"></table><div class="pieread" id="readA"></div></div>
<div class="card"><h3>¿De qué fuente vienen los perdidos por no-contacto?</h3>
<div style="height:38px"></div><div style="text-align:center" id="pieB"></div><table class="legend" id="legB"></table><div class="pieread" id="readB"></div></div>
</div>
<p class="sub" style="margin-top:10px">La columna <b>Tasa</b> (casos ÷ leads de la fuente) es la medida de calidad sin sesgo de volumen: una porción grande puede ser solo una fuente grande.</p>

<h2><span class="num">05</span>Mercados (país del lead por indicativo telefónico) {info('El país se deriva del indicativo internacional del teléfono del contacto. 808 leads no tienen teléfono registrado.')}</h2>
<div class="grid2">
<div class="card"><h3>Conversión a cierre por mercado</h3>{svg_mercados_conv()}</div>
<div class="card"><h3>Composición del pipeline por mercado</h3>{svg_mercados_stack()}</div>
</div>

<h2><span class="num">06</span>Desempeño por asesor {info('Solo asesores con ≥10 leads. Las cuentas marcadas como "bolsa" (MARKETING PFS, administrativas, sin asignar) no son asesores humanos: son inventario sin dueño comercial.')}</h2>
<p class="sub">Clic en los encabezados para ordenar. Umbrales en el glosario.</p>
<div class="card" style="overflow-x:auto"><table class="sortable" id="ta"><thead><tr>
<th data-k="0" class="noord">Asesor</th><th data-k="1" data-n="1">Leads</th>
<th data-k="2" data-n="1">Cobertura efectiva {info('(Gestión activa + etapas avanzadas + cierres) ÷ leads. Mide cuánta de su cartera está realmente en trabajo. Verde ≥60% · ámbar ≥40%.')}</th>
<th data-k="3" data-n="1">Cierres</th><th data-k="4" data-n="1">Conversión {info('Cierres ÷ leads × 100. Verde ≥10% · ámbar ≥5%.')}</th>
<th data-k="5" data-n="1">% base fría {info('Leads en COLD ÷ leads. Verde ≤30% · ámbar ≤55% (invertido).')}</th>
<th data-k="6" data-n="1">Pérd. contacto {info('Perdidos por no-contacto ÷ leads. Verde ≤2% · ámbar ≤6% (invertido).')}</th>
<th data-k="7" data-n="1">HOT/Pending</th><th data-k="8" data-n="1">Miami</th></tr></thead>
<tbody>{tabla_asesores()}</tbody></table></div>

<h2><span class="num">07</span>Matriz cobertura efectiva × conversión {info('Cada burbuja es un asesor humano con ≥50 leads; el tamaño es su volumen de cartera. Líneas de referencia: 55% de cobertura efectiva y 8% de conversión.')}</h2>
<p class="sub">Cuatro cuadrantes: referentes · coaching de cierre · activar base parqueada · prioridad de intervención. Bolsas administrativas excluidas.</p>
<div class="card">{svg_matriz()}</div>

<h2><span class="num">08</span>Segmentos de alto interés</h2>
<div class="segcards">{seg_cards}</div>
<div class="card" style="overflow-x:auto"><h3>Leads de alto interés por asesor — clic en un asesor con 🔥 para ver su lista de llamadas {info('El drill-down muestra los leads en Toma Decision (HOT) y Pending (Elite Club) del asesor, con contacto directo.')}</h3>
<table class="sortable" id="ts"><thead><tr><th data-k="0" class="noord">Asesor</th><th data-k="1" data-n="1">🔥 Cierre inmediato</th><th data-k="2" data-n="1">Precalificación</th><th data-k="3" data-n="1">Miami</th><th data-k="4" data-n="1">Asistieron</th><th data-k="5" data-n="1">Total</th></tr></thead>
<tbody>{tabla_segmentos()}</tbody></table></div>

<h2><span class="num">09</span>Plan de recuperación</h2>
<div class="reccards">
<div class="reccard"><b>Nuevo Lead estancado ({fmt(stale['sin'])} de {fmt(tot['sin'])})</b><p>El {pct(stale['sin']/max(stale_tot['sin'],1)*100)} de los leads "Nuevo Lead" lleva más de 30 días sin movimiento de etapa. Definir SLA de primer toque &lt;24 h y barrido de asignación semanal.</p></div>
<div class="reccard"><b>Base fría COLD ({fmt(tot['cold'])})</b><p>El bloque más grande del pipeline. Campaña de nutrición segmentada por mercado + agente IA de recontacto por WhatsApp antes de descartar.</p></div>
<div class="reccard"><b>Bolsas sin dueño comercial ({fmt(bolsa_total)})</b><p>MARKETING PFS, cuentas administrativas y leads sin asignar concentran el {pct(bolsa_total/TOTAL*100)} de la base — incluidos <b>{fmt(huerf_cli)} cierres sin asesor asignado</b>. Redistribuir con reglas de asignación automática.</p></div>
<div class="reccard"><b>El dato que falta</b><p>Sin motivos de pérdida (0 de {fmt(865)} perdidas los registran) ni atribución de fuente en el 92% de las oportunidades, no se puede separar problema de canal vs. problema de gestión. Ver datos pendientes.</p></div>
</div>

<div class="pend"><h3>⚠ Métricas no calculables hoy — y la fuente exacta en GHL que las habilitaría</h3><ul>
<li><b>Atribución real de fuente:</b> el campo <i>source</i> viene vacío en 13.715 de 14.880 oportunidades (92%). Habilitar UTMs/fuente obligatoria en formularios y workflows de creación de oportunidad.</li>
<li><b>Motivos de pérdida:</b> las 865 oportunidades perdidas no tienen <i>lost reason</i>. Configurar motivos obligatorios en Opportunities → Settings.</li>
<li><b>Status "won" desalineado:</b> solo 4 oportunidades marcadas <i>won</i> frente a 991 en etapa Cierre (Elite Club). Marcar won al cerrar para poder medir ciclo de venta y forecast.</li>
<li><b>Tiempo de primera respuesta y llamadas por asesor:</b> requiere export de Conversations/llamadas (API de Conversations o reporte nativo), no viene en las oportunidades.</li>
<li><b>Tendencias temporales de captación:</b> el 82% de las oportunidades se creó el 12-14 de abril de 2026 (importación masiva); la fecha de creación no refleja la fecha real de captación.</li>
<li><b>Valor monetario:</b> monetaryValue = 0 en la práctica totalidad; sin él no hay forecast de ingresos por etapa.</li>
</ul></div>

<h2><span class="num">10</span>Tres decisiones recomendadas</h2>
<div class="dec">
<div class="deccard"><b>1 · Rescatar los {fmt(huerf_cli)} cierres y {fmt(bolsa_total)} leads sin dueño comercial.</b><p>El {pct(bolsa_total/TOTAL*100)} de la base vive en bolsas (MARKETING PFS: {fmt(adv['MARKETING PFS']['total'])}, sin asignar: {fmt(adv['(Sin asesor asignado)']['total'])}). Regla de asignación automática + barrido semanal de huérfanos. Es la palanca más rápida: ahí ya hay {fmt(adv_seg['(Sin asesor asignado)']['s1'] + adv_seg['MARKETING PFS']['s1'])} leads en cierre inmediato.</p></div>
<div class="deccard"><b>2 · Llamar HOY a los {fmt(seg_tot['s1'])} leads en Toma Decision (HOT) y Pending (Elite Club).</b><p>Con la conversión de referencia, cada semana de espera en este segmento cuesta cierres. La lista de llamadas por asesor está en la sección 08 con teléfono y WhatsApp.</p></div>
<div class="deccard"><b>3 · Programa de reactivación de la base parqueada ({fmt(PARQ)} leads).</b><p>El {pct(PARQ/TOTAL*100)} del pipeline está en COLD o sin gestionar y el {pct(stale_act_pct)} de la gestión activa lleva +30 días sin moverse. Nutrición segmentada por mercado + recontacto IA antes de cualquier compra de leads nueva: ≈{fmt(POT)} cierres potenciales estimados dentro de la base actual.</p></div>
</div>

<h2><span class="num">11</span>Hojas de auditoría por asesor {info('Cada tarjeta abre la hoja del asesor con sus leads clasificados por macro-estado, filtro por fuente y buscador. La barra muestra la composición de su cartera.')}</h2>
<p class="sub">Navegación con enlaces #a/N — se puede compartir el enlace de una hoja específica.</p>
<div id="home" class="acards">{cards_auditoria()}</div>
<div id="sheet" class="sheet"></div>

<h2><span class="num">12</span>Glosario de métricas</h2>
<div class="card glos"><dl>
<dt>Macro-estados (clasificación excluyente, en este orden)</dt><dd><b>Cierres (Elite Club):</b> etapa "Cierre (Elite Club)" o status won. · <b>Perdidos por no-contacto:</b> status lost/abandoned estando en Nuevo Lead, Intento de Contacto o COLD. · <b>Otros descartes:</b> lost/abandoned en etapas posteriores. · <b>Etapas avanzadas:</b> WARM, Llamada de Precalificación, Precalificación Financiera, Atención Contador, Date to Miami, Asistió Oficina Miami, Tour Miami, Toma Decision (HOT), Pending (Elite Club). · <b>Gestión activa:</b> Intento de Contacto, Cita a Jornada/Evento/Webinar, Asistió a Jornada/Evento/Webinar, Cita Virtual, Asisitió Presencial o Virtual. · <b>Base fría:</b> COLD. · <b>Sin gestionar:</b> Nuevo Lead.</dd>
<dt>Conversión</dt><dd>Cierres ÷ leads × 100. Global: {pct(CONV)}. Semáforo asesor: verde ≥10% · ámbar ≥5%. Semáforo fuente: verde ≥7,5% · ámbar ≥4%.</dd>
<dt>Cobertura efectiva</dt><dd>(Gestión activa + etapas avanzadas + cierres) ÷ leads × 100. Mide cartera realmente en trabajo. Verde ≥60% · ámbar ≥40%. Línea de la matriz: 55%.</dd>
<dt>% base fría / % parqueada</dt><dd>COLD ÷ leads (asesor) o (COLD + sin gestionar) ÷ leads (fuente). Verde ≤30/35% · ámbar ≤55% (invertido).</dd>
<dt>Pérdida de contacto</dt><dd>Perdidos por no-contacto ÷ leads × 100. Verde ≤2% · ámbar ≤6% (invertido).</dd>
<dt>Tasa (pies de calidad)</dt><dd>Casos del estado ÷ leads totales de esa fuente × 100 — calidad sin sesgo de volumen.</dd>
<dt>Cierres potenciales</dt><dd>Base parqueada × conversión promedio ({pct(CONV)}). Estimación de orden de magnitud, no forecast.</dd>
<dt>Fuente derivada</dt><dd>Prioridad: campo source → tags de pauta → tags de evento/jornada → web/formularios → referidos → redes → nutrición cold → importación → sin atribución.</dd>
<dt>Mercado</dt><dd>País por indicativo telefónico internacional del contacto.</dd>
<dt>Segmentos</dt><dd>🔥 Cierre inmediato: HOT + Pending (solo oportunidades abiertas). Precalificación: 3 etapas financieras. Miami: Date/Oficina/Tour. Asistieron: asistencia a evento o cita sin avance posterior.</dd>
</dl></div>

<div class="warnpii"><b>⚠ Este archivo contiene datos personales</b> (nombres, correos y teléfonos de {fmt(TOTAL)} personas). El HTML <b>es</b> la base de datos: trátalo bajo la política de datos de PFS Realty y Habeas Data — no publicarlo ni circularlo fuera del equipo comercial autorizado.</div>

<footer>Generado el {CORTE} desde la API de GoHighLevel (solo lectura; ninguna escritura sobre el CRM). Pipeline: PIPELINE PFS · {fmt(TOTAL)} oportunidades · {len(ADV_ORDER)} propietarios. Formato numérico es-CO.</footer>
</div>
<div id="tipbox"></div>
<script>
const D = {DATA_JS};
const fmtN = n => n.toLocaleString('es-CO');
const fmtP = (x,d=1) => x.toLocaleString('es-CO',{{minimumFractionDigits:d,maximumFractionDigits:d}}) + '%';
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const PIECOLS = {json.dumps(PIE_COLS)};

/* ---------- popovers ⓘ ---------- */
const tipbox = document.getElementById('tipbox');
function tip(el, ev) {{
  ev.stopPropagation();
  if (tipbox.style.display === 'block' && tipbox.dataset.src === el.dataset.tip) {{ tipbox.style.display = 'none'; return; }}
  tipbox.textContent = el.dataset.tip; tipbox.dataset.src = el.dataset.tip;
  tipbox.style.display = 'block';
  const r = el.getBoundingClientRect();
  tipbox.style.left = Math.min(window.innerWidth - 300, Math.max(8, r.left - 40)) + 'px';
  tipbox.style.top = (r.bottom + 8) + 'px';
}}
document.addEventListener('click', () => tipbox.style.display = 'none');

/* ---------- tablas ordenables ---------- */
document.querySelectorAll('table.sortable').forEach(t => {{
  t.querySelectorAll('tbody tr').forEach(tr => tr.dataset.base = '1');
  t.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', e => {{
    if (e.target.classList.contains('info')) return;
    const k = +th.dataset.k, num = th.dataset.n === '1';
    const tb = t.querySelector('tbody');
    tb.querySelectorAll('tr.drill').forEach(r => r.remove());
    const rows = [...tb.querySelectorAll('tr')];
    const dir = th.dataset.dir === 'a' ? -1 : 1; th.dataset.dir = dir === 1 ? 'a' : 'd';
    rows.sort((a, b) => {{
      const av = a.cells[k].dataset.v ?? a.cells[k].textContent.trim();
      const bv = b.cells[k].dataset.v ?? b.cells[k].textContent.trim();
      return num ? dir * (parseFloat(bv) - parseFloat(av)) : dir * String(av).localeCompare(bv, 'es');
    }});
    rows.forEach(r => tb.appendChild(r));
  }}));
}});

/* ---------- comparador de fuentes ---------- */
const FORDER = Object.keys(D.fts);
const chipsEl = document.getElementById('fchips');
FORDER.forEach((f, i) => {{
  const b = document.createElement('button');
  b.className = 'chip' + (i === 0 ? ' on' : ''); b.textContent = f;
  b.onclick = () => {{ document.querySelectorAll('#fchips .chip').forEach(c => c.classList.remove('on')); b.classList.add('on'); renderF(f); }};
  chipsEl.appendChild(b);
}});
function renderF(f) {{
  const d = D.fts[f], t = d.t, conv = d.cli / t * 100, parq = (d.sin + d.cold) / t * 100;
  let h = `<div class="fkpis">
    <div class="fk"><b>${{fmtN(t)}}</b><span>leads (${{fmtP(t / D.total * 100)}} de la base)</span></div>
    <div class="fk"><b>${{fmtN(d.cli)}}</b><span>cierres</span></div>
    <div class="fk"><b style="color:${{conv >= 7.5 ? '#1E9E62' : conv >= 4 ? '#8A6D1A' : '#D64545'}}">${{fmtP(conv)}}</b><span>conversión</span></div>
    <div class="fk"><b>${{fmtN(d.pro)}}</b><span>etapas avanzadas</span></div>
    <div class="fk"><b>${{fmtN(d.act)}}</b><span>gestión activa</span></div>
    <div class="fk"><b style="color:${{parq <= 35 ? '#1E9E62' : parq <= 55 ? '#8A6D1A' : '#D64545'}}">${{fmtP(parq)}}</b><span>base parqueada</span></div></div>`;
  if (d.camps.length) {{
    h += '<h3 style="font-size:14px;margin:8px 0">Principales campañas / eventos de esta fuente</h3><table><thead><tr><th class="noord">Campaña</th><th class="noord">Leads</th><th class="noord">Cierres</th><th class="noord">Avanzadas</th></tr></thead><tbody>';
    d.camps.forEach(c => h += `<tr><td>${{esc(c[0])}}</td><td>${{fmtN(c[1])}}</td><td>${{fmtN(c[2])}}</td><td>${{fmtN(c[3])}}</td></tr>`);
    h += '</tbody></table>';
  }} else h += '<p class="sub">Sin campañas identificables en los tags de esta fuente.</p>';
  h += `<h3 style="font-size:14px;margin:16px 0 8px">Comparativa entre fuentes</h3><table><thead><tr><th class="noord">Fuente</th><th class="noord">Composición</th><th class="noord">Leads</th><th class="noord">Conv.</th><th class="noord">% parqueada</th></tr></thead><tbody>`;
  FORDER.forEach(g => {{
    const x = D.fts[g], cv = x.cli / x.t * 100, pq = (x.sin + x.cold) / x.t * 100;
    let bar = '<div class="cbar" style="width:150px">';
    D.cats.forEach(c => {{ if (x[c]) bar += `<i style="width:${{(x[c] / x.t * 100).toFixed(1)}}%;background:${{D.catc[c]}}"></i>`; }});
    bar += '</div>';
    h += `<tr${{g === f ? ' style="outline:2px solid #C4B284"' : ''}}><td>${{esc(g)}}</td><td>${{bar}}</td><td>${{fmtN(x.t)}}</td>
      <td><span class="pill ${{cv >= 7 ? 'ok' : cv >= 4 ? 'warn' : 'bad'}}">${{fmtP(cv)}}</span></td>
      <td><span class="pill ${{pq <= 35 ? 'ok' : pq <= 55 ? 'warn' : 'bad'}}">${{fmtP(pq)}}</span></td></tr>`;
  }});
  h += '</tbody></table><p class="sub" style="margin-top:8px">Nota fija: no existe atribución confiable de pauta (Google/Meta) porque el campo fuente y los UTMs no se están registrando — la fuente aquí es derivada de tags.</p>';
  document.getElementById('fpanel').innerHTML = h;
}}
renderF(FORDER[0]);

/* ---------- pies de calidad ---------- */
function arcPath(cx, cy, r0, r1, a0, a1) {{
  const la = (a1 - a0) > Math.PI ? 1 : 0;
  const pt = (r, a) => `${{(cx + r * Math.cos(a)).toFixed(2)}},${{(cy + r * Math.sin(a)).toFixed(2)}}`;
  return `M${{pt(r1, a0)}} A${{r1}},${{r1}} 0 ${{la}} 1 ${{pt(r1, a1)}} L${{pt(r0, a1)}} A${{r0}},${{r0}} 0 ${{la}} 0 ${{pt(r0, a0)}} Z`;
}}
const pieState = {{ A: {{ cat: 'cli', sel: -1 }}, B: {{ cat: 'pc', sel: -1 }} }};
const CATLBL = {{ cli: 'cierres', pro: 'leads en etapas avanzadas', pc: 'perdidos por no-contacto' }};
function drawPie(which) {{
  const st = pieState[which], data = D.pies[st.cat];
  const totalC = data.reduce((s, x) => s + x[1], 0);
  let svg = `<svg viewBox="0 0 300 300" style="width:100%;max-width:270px;height:auto">`;
  let a = -Math.PI / 2;
  data.forEach((x, i) => {{
    if (!x[1]) return;
    const a1 = a + x[1] / totalC * 2 * Math.PI - 1e-4;
    svg += `<path d="${{arcPath(150, 150, 60, 116, a, a1)}}" fill="${{PIECOLS[i % PIECOLS.length]}}" stroke="#fff" stroke-width="2"
      class="pieseg${{st.sel >= 0 && st.sel !== i ? ' dim' : ''}}" onclick="selPie('${{which}}',${{i}});event.stopPropagation()"><title>${{esc(x[0])}}</title></path>`;
    a = a1 + 1e-4;
  }});
  const selN = st.sel >= 0 ? data[st.sel][1] : totalC;
  svg += `<text x="150" y="145" text-anchor="middle" font-size="25" font-weight="800" fill="#152238">${{fmtN(selN)}}</text>
    <text x="150" y="167" text-anchor="middle" font-size="11.5" fill="#5B6B85">${{CATLBL[st.cat]}}</text></svg>`;
  document.getElementById('pie' + which).innerHTML = svg;
  let leg = '<tr><td></td><td style="font-weight:700;color:#5B6B85;font-size:11px">FUENTE</td><td style="font-weight:700;color:#5B6B85;font-size:11px">CASOS</td><td style="font-weight:700;color:#5B6B85;font-size:11px">% DEL PIE</td><td style="font-weight:700;color:#5B6B85;font-size:11px">TASA</td></tr>';
  data.forEach((x, i) => {{
    const rate = x[2] ? x[1] / x[2] * 100 : 0;
    leg += `<tr class="${{st.sel >= 0 && st.sel !== i ? 'dim' : ''}}" onclick="selPie('${{which}}',${{i}});event.stopPropagation()">
      <td><span class="dot" style="background:${{PIECOLS[i % PIECOLS.length]}}"></span></td><td>${{esc(x[0])}}</td>
      <td>${{fmtN(x[1])}}</td><td>${{totalC ? fmtP(x[1] / totalC * 100) : '—'}}</td><td><b>${{fmtP(rate)}}</b></td></tr>`;
  }});
  document.getElementById('leg' + which).innerHTML = leg;
  const rd = document.getElementById('read' + which);
  if (st.sel >= 0) {{
    const x = data[st.sel], rate = x[2] ? x[1] / x[2] * 100 : 0;
    rd.innerHTML = `<b>${{esc(x[0])}}</b> aporta ${{fmtN(x[1])}} de ${{fmtN(totalC)}} ${{CATLBL[st.cat]}} (${{totalC ? fmtP(x[1] / totalC * 100) : '—'}} del pie). Su tasa propia es <b>${{fmtP(rate)}}</b>: de cada 1.000 leads de esta fuente, ${{Math.round(rate * 10)}} terminan en este estado.`;
  }} else rd.innerHTML = 'Clic en una porción o en la leyenda para aislarla y leer su tasa de calidad.';
}}
function selPie(which, i) {{ const st = pieState[which]; st.sel = st.sel === i ? -1 : i; drawPie(which); }}
function setPieA(cat) {{
  pieState.A.cat = cat; pieState.A.sel = -1;
  document.getElementById('tg-cli').classList.toggle('on', cat === 'cli');
  document.getElementById('tg-pro').classList.toggle('on', cat === 'pro');
  drawPie('A');
}}
drawPie('A'); drawPie('B');

/* ---------- drill-down segmento cierre inmediato ---------- */
const DICT = D.audit.dicts;
function leadCells(r) {{
  const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
  const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a> · <a href="https://wa.me/${{esc(String(r[2]).replace(/[^0-9]/g, ''))}}">WA</a>` : '—';
  return `<td>${{esc(r[0])}}</td><td>${{esc(DICT.cmp[r[3]])}}</td><td>${{esc(DICT.mer[r[4]])}}</td><td>${{esc(DICT.et[r[5]])}}</td><td>${{esc(DICT.org[r[6]])}}</td><td>${{em}}</td><td>${{ph}}</td>`;
}}
document.querySelectorAll('.segrow').forEach(tr => tr.addEventListener('click', () => {{
  const next = tr.nextElementSibling;
  if (next && next.classList.contains('drill')) {{ next.remove(); return; }}
  document.querySelectorAll('#ts .drill').forEach(r => r.remove());
  const a = tr.dataset.a, leads = D.s1[a] || [];
  const dr = document.createElement('tr'); dr.className = 'drill';
  let h = `<td colspan="6"><div class="drillbox"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:9px">
    <b>🔥 ${{esc(a)}} — ${{fmtN(leads.length)}} leads en cierre inmediato</b>
    <input class="search" placeholder="Buscar…" oninput="filtDrill(this)"></div>
    <div style="overflow-x:auto"><table><thead><tr><th class="noord">Lead</th><th class="noord">Campaña</th><th class="noord">Mercado</th><th class="noord">Etapa</th><th class="noord">Fuente</th><th class="noord">Email</th><th class="noord">Teléfono</th></tr></thead><tbody>`;
  leads.forEach(r => h += `<tr>${{leadCells(r)}}</tr>`);
  h += '</tbody></table></div></div></td>';
  dr.innerHTML = h;
  tr.after(dr);
}}));
function filtDrill(inp) {{
  const q = inp.value.toLowerCase();
  inp.closest('.drillbox').querySelectorAll('tbody tr').forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
}}

/* ---------- SPA auditoría ---------- */
const ADVS = Object.keys(D.audit.adv);
const sheetEl = document.getElementById('sheet'), homeEl = document.getElementById('home');
let curFte = '';
function route() {{
  const m = location.hash.match(/^#a\\/(\\d+)$/);
  if (!m || !ADVS[+m[1]]) {{ sheetEl.classList.remove('on'); sheetEl.innerHTML = ''; homeEl.style.display = ''; return; }}
  curFte = '';
  renderSheet(+m[1]);
}}
function renderSheet(n) {{
  const a = ADVS[n], cats = D.audit.adv[a];
  homeEl.style.display = 'none'; sheetEl.classList.add('on');
  const all = D.cats.flatMap(c => cats[c] || []);
  const ftesHere = [...new Set(all.map(r => DICT.org[r[6]]))].sort();
  const flt = r => !curFte || DICT.org[r[6]] === curFte;
  const t = all.filter(flt).length;
  let h = `<div class="card"><div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
    <a class="btn sec" href="#" onclick="location.hash='';return false">← Todos los asesores</a>
    <h3 style="font-size:17px">${{esc(a)}} · ${{fmtN(t)}} leads${{curFte ? ' · fuente: ' + esc(curFte) : ''}}</h3>
    ${{n > 0 ? `<a class="btn sec" href="#a/${{n - 1}}">‹ anterior</a>` : ''}}
    ${{n < ADVS.length - 1 ? `<a class="btn sec" href="#a/${{n + 1}}">siguiente ›</a>` : ''}}
    <select class="search" style="width:auto" onchange="curFte=this.value;renderSheet(${{n}})">
      <option value="">Todas las fuentes</option>${{ftesHere.map(f => `<option${{f === curFte ? ' selected' : ''}} value="${{esc(f)}}">${{esc(f)}}</option>`).join('')}}</select></div>
    <div class="statechips">`;
  D.cats.forEach(c => {{
    const k = (cats[c] || []).filter(flt).length;
    h += `<span class="schip" style="background:${{D.catc[c]}}">${{D.catn[c]}}: ${{fmtN(k)}}${{t ? ' (' + fmtP(k / t * 100) + ')' : ''}}</span>`;
  }});
  h += '</div>';
  D.cats.forEach(c => {{
    const rows = (cats[c] || []).filter(flt);
    if (!rows.length) return;
    h += `<div class="colsec" id="cs-${{c}}"><button onclick="this.parentElement.classList.toggle('open')">${{D.catn[c]}} — ${{fmtN(rows.length)}} leads ▾</button><div class="body">
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px"><input class="search" placeholder="Buscar en ${{D.catn[c]}}…" oninput="filtState(this,'${{c}}')"></div>
      <div style="overflow-x:auto"><table><thead><tr><th class="noord">Lead</th><th class="noord">Campaña</th><th class="noord">Mercado</th><th class="noord">Etapa</th><th class="noord">Fuente</th><th class="noord">Email</th><th class="noord">Teléfono</th></tr></thead>
      <tbody id="tb-${{c}}"></tbody></table></div><div class="pag" id="pg-${{c}}"></div></div></div>`;
  }});
  h += '</div>';
  sheetEl.innerHTML = h;
  D.cats.forEach(c => {{
    const rows = (cats[c] || []).filter(flt);
    if (rows.length) pageState[c] = {{ rows, page: 0, q: '' }}, renderPage(c);
  }});
  sheetEl.scrollIntoView({{ behavior: 'smooth' }});
}}
const pageState = {{}};
function renderPage(c) {{
  const st = pageState[c];
  const rows = st.q ? st.rows.filter(r => (r[0] + ' ' + r[1] + ' ' + r[2] + ' ' + DICT.cmp[r[3]] + ' ' + DICT.mer[r[4]] + ' ' + DICT.et[r[5]]).toLowerCase().includes(st.q)) : st.rows;
  const pages = Math.max(1, Math.ceil(rows.length / 100));
  st.page = Math.min(st.page, pages - 1);
  const slice = rows.slice(st.page * 100, st.page * 100 + 100);
  document.getElementById('tb-' + c).innerHTML = slice.map(r => `<tr>${{leadCells(r)}}</tr>`).join('');
  const pg = document.getElementById('pg-' + c);
  pg.innerHTML = pages > 1 ? `<button class="btn sec" onclick="pageState['${{c}}'].page--;renderPage('${{c}}')" ${{st.page === 0 ? 'disabled' : ''}}>‹</button>
    página ${{st.page + 1}} de ${{pages}} (${{fmtN(rows.length)}} leads)
    <button class="btn sec" onclick="pageState['${{c}}'].page++;renderPage('${{c}}')" ${{st.page >= pages - 1 ? 'disabled' : ''}}>›</button>` : (rows.length ? fmtN(rows.length) + ' leads' : 'Sin resultados');
}}
function filtState(inp, c) {{ pageState[c].q = inp.value.toLowerCase(); pageState[c].page = 0; renderPage(c); }}
window.addEventListener('hashchange', route);
route();
</script>
</body></html>'''

out = str(ROOT / f'dashboard-gestion-comercial-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e6:.1f} MB)')
print('macro:', dict(tot), '| conv global', round(CONV,2))
print('asesores:', len(ADV_ORDER), '| seg:', dict(seg_tot), '| stale act %', round(stale_act_pct,1))
