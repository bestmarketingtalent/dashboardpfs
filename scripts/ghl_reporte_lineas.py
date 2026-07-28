#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja ARRIENDO Y CRÉDITO: clasifica los leads con más potencial para las otras
líneas de negocio de la compañía — (1) arrendamiento de propiedades de corta y
larga estancia y (2) financiación de vivienda. Un lead que no compra NO es un lead
perdido: puede arrendar hoy o financiar mañana. Cada segmento trae diagnóstico,
pitch de entrega al área y la tabla de leads con sus señales.
Señales usadas: menciones de renta/crédito en las 4.888 conversaciones de WhatsApp,
campos declarados (tipo de inversión renta corta/larga, interés en crédito, visa),
status Tenant, motivo de descarte "sin capital" y horizonte de compra.
Lee scripts/data/{contacts,users,wa_all_msgs}.json (solo consulta)."""
import json, re
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

# ---------- helpers compartidos ----------
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

# ---------- señales de conversación (mensajes ENTRANTES del lead) ----------
try:
    _wa_all = json.load(open(DATA / 'wa_all_msgs.json'))
except Exception:
    _wa_all = []
RE_RENTA = re.compile(r'\b(rentar|renta corta|renta larga|arrien|arrend|alquil|airbnb|estancia)', re.I)
RE_CORTA = re.compile(r'\b(renta corta|airbnb|estancia corta|corta estancia|d[ií]as|semanas|vacacion)', re.I)
RE_LARGA = re.compile(r'\b(renta larga|largo plazo|estancia larga|larga estancia|anual|meses de contrato)', re.I)
RE_CRED  = re.compile(r'\b(cr[eé]dito|financia|hipotec|preaprob|cuota inicial|pr[eé]stamo|loan|mortgage)', re.I)
WA_RENTA, WA_CORTA, WA_LARGA, WA_CRED, WA_EJ = {}, set(), set(), {}, {}
for cv in _wa_all:
    cid = cv.get('contactId')
    for m in cv.get('msgs') or []:
        if m[0] != 1: continue
        txt = m[2] or ''
        if RE_RENTA.search(txt):
            WA_RENTA[cid] = WA_RENTA.get(cid, 0) + 1
            WA_EJ.setdefault(cid, ' '.join(txt.split())[:120])
            if RE_CORTA.search(txt): WA_CORTA.add(cid)
            if RE_LARGA.search(txt): WA_LARGA.add(cid)
        if RE_CRED.search(txt):
            WA_CRED[cid] = WA_CRED.get(cid, 0) + 1
            WA_EJ.setdefault(cid, ' '.join(txt.split())[:120])

# ---------- clasificación por lead ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi

DA, giA = dict_indexer()
DF, giF = dict_indexer()

ROWS = []
SEG = {k: [] for k in ('r_convo', 'r_declarado', 'r_tenant', 'r_capital',
                       'c_convo', 'c_visa', 'c_capital', 'c_futuro')}
PA_IDS, PC_IDS = set(), set()

for c in contacts:
    cid = c['id']
    st = (c.get('leadStatus') or '').strip() or '(Sin status)'
    if st in ('Aliado', 'Relationship', 'Compra Problematica'): continue
    sc = score_of(c)
    mo = str(c.get('motivoDescarte') or '').lower()
    ti = str(c.get('tipoInversion') or '')
    icr = str(c.get('interesCredito') or '').strip()
    visa = str(c.get('visaVigente') or '').strip().upper()
    oport = (c.get('enCursoPor') or '').strip()
    señales_a, señales_c = [], []
    sub = []
    # ----- potencial ARRIENDO -----
    pa = 0
    if cid in WA_RENTA:
        pa += 40; señales_a.append(f'pidió renta en conversación ({WA_RENTA[cid]}×)')
        if cid in WA_CORTA: sub.append('corta')
        if cid in WA_LARGA: sub.append('larga')
    if 'Renta Corta' in ti or 'Renta Larga' in ti:
        pa += 35; señales_a.append('declaró tipo de inversión: ' + ('Renta Corta' if 'Renta Corta' in ti else '') + (' y ' if 'Renta Corta' in ti and 'Renta Larga' in ti else '') + ('Renta Larga' if 'Renta Larga' in ti else ''))
        if 'Renta Corta' in ti: sub.append('corta')
        if 'Renta Larga' in ti: sub.append('larga')
    if st == 'Tenant':
        pa += 30; señales_a.append('inquilino actual (Tenant)')
    if 'capital' in mo:
        pa += 25; señales_a.append('descartado por falta de capital → puede arrendar mientras compra')
    if 'renta larga' in icr.lower():
        pa += 20; señales_a.append('interés declarado: renta larga')
        sub.append('larga')
    # ----- potencial CRÉDITO -----
    pc = 0
    if cid in WA_CRED:
        pc += 40; señales_c.append(f'preguntó por crédito/financiación ({WA_CRED[cid]}×)')
    if icr and icr.lower() not in ('', 'no responde', 'no'):
        pc += 30; señales_c.append('interés en crédito declarado: ' + icr)
    if 'capital' in mo:
        pc += 30; señales_c.append('descartado por falta de capital → la financiación ES la solución')
    if visa == 'NO' and (oport.startswith('Oportunidad') or sc >= 15):
        pc += 20; señales_c.append('sin visa con intención de compra → crédito para extranjeros')
    if oport == 'Oportunidad 6+ meses' and sc >= 30:
        pc += 12; señales_c.append('horizonte 6+ meses calificado: ventana para preaprobación')
    if pa < 20 and pc < 12: continue
    a = USERS.get(c.get('assigned'), '(Sin asesor)') if c.get('assigned') else '(Sin asesor)'
    i = len(ROWS)
    ROWS.append([
        (c['name'] or '(sin nombre)').strip().title(),
        c.get('email') or '', c.get('phone') or '',
        giA(a), giF(fuente_of(c)), st, sc,
        (c.get('created') or '')[:10],
        pa, pc, ' + '.join(señales_a), ' + '.join(señales_c),
        '/'.join(sorted(set(sub))) or '—',
        WA_EJ.get(cid, '')
    ])
    if pa >= 20: PA_IDS.add(cid)
    if pc >= 20: PC_IDS.add(cid)
    if cid in WA_RENTA: SEG['r_convo'].append(i)
    if 'Renta Corta' in ti or 'Renta Larga' in ti or 'renta larga' in icr.lower(): SEG['r_declarado'].append(i)
    if st == 'Tenant': SEG['r_tenant'].append(i)
    if 'capital' in mo: SEG['r_capital'].append(i); SEG['c_capital'].append(i)
    if cid in WA_CRED: SEG['c_convo'].append(i)
    if visa == 'NO' and (oport.startswith('Oportunidad') or sc >= 15): SEG['c_visa'].append(i)
    if oport == 'Oportunidad 6+ meses' and sc >= 30 and pc >= 12: SEG['c_futuro'].append(i)

for k in SEG:
    col = 8 if k.startswith('r_') else 9
    SEG[k].sort(key=lambda i: (-ROWS[i][col], -ROWS[i][6]))
N_FUT_FULL = len(SEG['c_futuro'])
SEG['c_futuro'] = SEG['c_futuro'][:150]   # el bolsillo grande: top 150 por potencial

def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
def fmt(n): return f'{n:,}'.replace(',', '.')
N = {k: len(v) for k, v in SEG.items()}
AMBAS = len(PA_IDS & PC_IDS)

PAYLOAD = json.dumps({'rows': ROWS, 'seg': SEG, 'ase': ordered(DA), 'fu': ordered(DF)},
                     ensure_ascii=False)

def card(key, icono, titulo, n, diag, pitch, tip):
    return f'''<div class="seg">
<div class="seghead" data-tip="{tip}">
<span class="segico">{icono}</span>
<div><h3>{titulo}</h3><p class="segdiag">{diag}</p></div>
<span class="segn">{fmt(n)}</span>
</div>
<div class="segbody">
<p class="pitch"><b>🤝 Cómo entregarlo al área:</b> {pitch}</p>
<button class="btn verbtn" data-seg="{key}">👁 Ver los {fmt(n)} leads</button>
<div class="segtable" id="st-{key}"></div>
</div>
</div>'''

CARDS_R = (
card('r_convo', '💬', 'Pidieron renta o arriendo en sus conversaciones', N['r_convo'],
     'Lo escribieron con sus propias palabras en WhatsApp: preguntaron por rentar, arrendar, alquilar o Airbnb. La demanda más explícita que existe — y hoy está sentada en el embudo de VENTAS, que no vende eso.',
     'Entregar con la conversación como contexto (la columna "Lo que dijo" trae la frase textual). El área retoma el hilo exacto: "nos preguntaste por rentar en [zona] — soy del equipo de arriendos y te tengo opciones".',
     'Leads con al menos un mensaje ENTRANTE que menciona rentar/arriendo/alquiler/Airbnb/estancia en las 4.888 conversaciones de WhatsApp analizadas. La columna Estancia distingue corta/larga cuando el texto o el campo declarado lo permite.'),
card('r_declarado', '📋', 'Declararon inversión en renta corta o larga', N['r_declarado'],
     'En el campo "Tipo de Inversión" del CRM declararon Renta Corta o Renta Larga: son compradores-inversionistas, pero mientras compran (o si no compran) son clientes naturales del área de administración de estancias.',
     'Doble oferta: al que quiere renta corta, el área le administra la propiedad que compre O le renta unidades por estancia; al de renta larga, contratos anuales. Presentarlo como "el mismo grupo que te acompaña en la inversión".',
     'Campo tipoInversion del CRM contiene "Renta Corta" o "Renta Larga", o interés en crédito declarado como renta larga.'),
card('r_tenant', '🏠', 'Inquilinos actuales (Tenant)', N['r_tenant'],
     'Ya son clientes del área de arriendos. Valor doble: renovaciones/upgrades de estancia, y el día que quieran comprar ya confían en la casa.',
     'Lista para el área de arriendos como base de renovación y para ofrecer upgrade (de corta a larga, de unidad a unidad mayor). Bandera verde para el equipo de crédito cuando el arriendo mensual se parezca a una cuota.',
     'Contactos con Lead Status = Tenant.'),
card('r_capital', '💸', 'Descartados por falta de capital → arrendar mientras compran', N['r_capital'],
     'Ventas los descartó porque "no cuenta con el capital necesario"… para COMPRAR. Pero quieren vivir o invertir en EE.UU.: el arriendo es su producto puente, y mantiene la relación viva hasta que el capital llegue.',
     'Guion de entrega: "comprar puede esperar; vivir la propiedad no. Te conseguimos arriendo de corta o larga estancia y cuando estés listo, la compra la hacemos juntos". El área gana un cliente hoy y ventas recupera un comprador mañana.',
     'Descartados con motivo "No cuenta con el capital necesario". Aparecen también en la sección de crédito: la financiación es la otra solución al mismo problema.'),
)
CARDS_C = (
card('c_convo', '🏦', 'Preguntaron por crédito o financiación', N['c_convo'],
     'Preguntaron explícitamente por crédito, financiación, hipoteca o cuota inicial en sus conversaciones. Interés financiero declarado con sus propias palabras.',
     'El área de financiación los contacta con la respuesta a SU pregunta textual (columna "Lo que dijo"). Producto estrella: crédito para extranjeros sin residencia — la duda que más los frena.',
     'Leads con al menos un mensaje entrante que menciona crédito/financiación/hipoteca/preaprobación/cuota inicial/préstamo/loan/mortgage.'),
card('c_visa', '🌎', 'Sin visa y con intención → crédito para extranjeros', N['c_visa'],
     'Declararon NO tener visa vigente y aun así tienen intención u oportunidad de compra: el cliente perfecto del foreign national loan, y el que más cree (equivocadamente) que no puede.',
     'Mensaje de entrega: "no necesitas visa ni residencia para financiar tu propiedad en EE.UU. — te preaprobamos con tus ingresos actuales". Es el producto con la objeción más fácil de voltear.',
     'Campo "Tienes Visa Vigente" = NO, con oportunidad declarada o señales de interés (score ≥15).'),
card('c_capital', '💰', 'Descartados por falta de capital → la financiación ES la solución', N['c_capital'],
     'El mismo bolsillo de la sección de arriendo, visto desde crédito: si el problema fue el capital, el producto financiero (cuota inicial menor, plan de preaprobación, crédito extranjeros) es exactamente lo que resuelve su descarte.',
     'Preaprobación sin compromiso: "te descartaron por capital — veamos cuánto SÍ alcanzas con financiación". Recuperar 2-3 de estos como créditos paga toda la gestión de la lista.',
     'Descartados con motivo "No cuenta con el capital necesario".'),
card('c_futuro', '📅', 'Horizonte 6+ meses calificado: pipeline de preaprobación', N['c_futuro'],
     'Compradores calificados (score ≥30) con horizonte a 6+ meses: la ventana perfecta para armar la preaprobación CON TIEMPO — historial, cuota inicial, estructura. Cuando llegue su momento de comprar, ya llegan financiados.',
     'Programa de "preaprobación anticipada": el área de crédito los madura 6 meses con checkpoints, y se los devuelve a ventas listos para firmar. Se muestran los 150 de mayor potencial.',
     'Leads con "En curso por" = Oportunidad 6+ meses y score ≥30, ordenados por potencial de crédito. Se listan los 150 primeros.'),
)

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arriendo y crédito</title>
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
h2.area{{font-size:17px;margin:26px 0 4px;padding-bottom:6px;border-bottom:2px solid var(--gris-linea)}}
.areasub{{font-size:12.5px;color:var(--gris);margin-bottom:10px}}
.seg{{border:1px solid var(--gris-linea);border-radius:13px;margin:14px 0;overflow:hidden}}
.seghead{{display:flex;gap:14px;align-items:center;padding:14px 18px;background:var(--gris-fondo)}}
.segico{{font-size:26px}}
.seghead h3{{font-size:15px}}
.segdiag{{font-size:12.5px;color:var(--gris);margin-top:2px}}
.segn{{margin-left:auto;font-size:24px;font-weight:900;color:var(--azul-oscuro);white-space:nowrap}}
.segbody{{padding:14px 18px}}
.pitch{{background:#F3F7EC;border:1px solid #D6E4C4;border-radius:10px;padding:10px 14px;font-size:13px;margin-bottom:10px}}
.btn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer}}
.btn.sec{{background:var(--azul-suave);color:var(--azul-oscuro)}}
table{{border-collapse:collapse;width:100%;font-size:12.6px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.sc{{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11.5px;color:#fff}}
.chipsig{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0}}
a{{color:var(--azul)}}
.tbox{{border:1px solid var(--gris-linea);border-radius:11px;overflow:auto;max-height:60vh;margin-top:10px}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:22px}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Arriendo y crédito — potencial para otras líneas</h1>
<p>CRM comercial (solo lectura) · Leads que no compran hoy pero arriendan o financian · Corte: {CORTE}</p></div>
<div class="hstats"><b>{fmt(len(PA_IDS | PC_IDS))}</b><span>leads con potencial identificado</span></div>
</div></header>
<nav class="mainnav"><div class="mnwrap">
<a href="index.html"><span class="ic">📊</span> Gestión comercial</a>
<a href="adquisicion.html"><span class="ic">📣</span> Adquisición</a>
<a href="asesores.html"><span class="ic">👤</span> Asesores comerciales</a>
<a href="clientes.html"><span class="ic">💎</span> Fidelización clientes</a>
<a href="lineas.html" class="act"><span class="ic">🔑</span> Arriendo y crédito</a>
<a href="estrategia.html"><span class="ic">🎯</span> Estrategia comercial</a>
</div></nav>
<div class="strip"></div>
<div class="wrap">

<div class="intro">💡 <b>La tesis:</b> el embudo de ventas descarta o congela leads que las OTRAS líneas del negocio pueden convertir HOY.
Aquí están clasificados por señal real (lo que dijeron en sus conversaciones, lo que declararon en el CRM y por qué se descartaron):
<b>{fmt(len(PA_IDS))} con potencial de arrendamiento</b> (corta y larga estancia) y <b>{fmt(len(PC_IDS))} con potencial INMEDIATO de financiación</b> (más {fmt(N_FUT_FULL)} en pipeline de preaprobación a 6+ meses)
— {fmt(AMBAS)} califican para ambas. Un lead que no compra con ventas puede pagar arriendo o un crédito con otra área: el costo de adquisición ya está pagado.</div>

<div class="kpis">
<div class="kpi" data-tip="Leads únicos con al menos una señal de potencial de arrendamiento (pidió renta, la declaró, es tenant o fue descartado por capital)."><b style="color:var(--verde)">{fmt(len(PA_IDS))}</b><span>potencial ARRIENDO</span></div>
<div class="kpi" data-tip="De los de arriendo, cuántos muestran señal de estancia CORTA (Airbnb, días/semanas, renta corta declarada)."><b>{fmt(sum(1 for r in ROWS if 'corta' in r[12]))}</b><span>señal de estancia corta</span></div>
<div class="kpi" data-tip="De los de arriendo, cuántos muestran señal de estancia LARGA (renta larga declarada o pedida)."><b>{fmt(sum(1 for r in ROWS if 'larga' in r[12]))}</b><span>señal de estancia larga</span></div>
<div class="kpi" data-tip="Leads con señal FUERTE de financiación: preguntaron por crédito, lo declararon, fueron descartados por capital o no tienen visa con intención de compra."><b style="color:var(--rojo)">{fmt(len(PC_IDS))}</b><span>potencial CRÉDITO inmediato</span></div>
<div class="kpi" data-tip="Pipeline de preaprobación anticipada: calificados (score ≥30) con horizonte de compra a 6+ meses. En su tarjeta se listan los 150 de mayor potencial."><b>{fmt(N_FUT_FULL)}</b><span>pipeline preaprobación 6+ meses</span></div>
<div class="kpi" data-tip="Leads que califican para las dos áreas a la vez: la conversación puede abrir con arriendo y escalar a financiación (o al revés)."><b style="color:var(--naranja)">{fmt(AMBAS)}</b><span>en ambas bolsas</span></div>
<div class="kpi" data-tip="Del total con potencial, cuántos tienen teléfono registrado: contactables por WhatsApp o llamada de inmediato."><b>{fmt(sum(1 for r in ROWS if r[2]))}</b><span>con teléfono</span></div>
</div>

<h2 class="area">🏠 ÁREA DE ARRENDAMIENTO — corta y larga estancia</h2>
<p class="areasub">Ordenados por potencial: primero los que lo pidieron con sus propias palabras, luego los que lo declararon, los inquilinos actuales y los descartados por capital (su producto puente). Cada tarjeta trae el pitch de entrega al área.</p>
{''.join(CARDS_R)}

<h2 class="area">🏦 ÁREA DE FINANCIACIÓN DE VIVIENDA</h2>
<p class="areasub">El orden es la prioridad: interés financiero explícito, el nicho de crédito para extranjeros sin visa, los descartados que la financiación rescata, y el pipeline de preaprobación anticipada a 6+ meses.</p>
{''.join(CARDS_C)}

<div class="warnpii"><b>⚠ Datos personales:</b> esta hoja contiene nombres, correos y teléfonos (Habeas Data). Uso exclusivo del equipo comercial autorizado.</div>
<footer>Universo: los {fmt(len(contacts))} contactos del CRM (excluye Aliados y Relationship). Señal de conversación = menciones en mensajes ENTRANTES de las 4.888 conversaciones de WhatsApp descargadas (renta/arriendo/alquiler/Airbnb/estancia · crédito/financiación/hipoteca/preaprobación/cuota inicial). Señales declaradas = campos del CRM (Tipo de Inversión, Interesado en crédito, Visa vigente, En curso por) y motivo de descarte. El "potencial" de cada tabla suma puntos por señal (conversación 40 · declarado 30-35 · tenant 30 · capital 25-30 · sin visa 20 · pipeline 12) — es independiente del lead score de ventas, que se muestra al lado. Generado desde la API del CRM, solo consulta.</footer>
</div>
<script>
const D = {PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = sc => sc >= 55 ? '#D64545' : sc >= 30 ? '#AA9664' : sc >= 10 ? '#3A566B' : '#8A99A8';
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

function renderSeg(seg) {{
  const esR = seg.startsWith('r_');
  const box = document.getElementById('st-' + seg);
  const idxs = D.seg[seg];
  ST[seg] = Math.min(idxs.length, (ST[seg] || 0) + 100);
  const filas = idxs.slice(0, ST[seg]).map(i => {{
    const r = D.rows[i];
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank"><b>WA</b></a>' : ''}}` : '—';
    const pot = esR ? r[8] : r[9];
    const sig = esR ? r[10] : r[11];
    return `<tr><td><span class="sc" style="background:${{pot >= 60 ? '#1E9E62' : pot >= 35 ? '#AA9664' : '#5B6B85'}}">${{pot}}</span></td>
    <td><b>${{esc(r[0])}}</b></td>
    <td>${{sig.split(' + ').map(s2 => '<span class="chipsig">' + esc(s2) + '</span>').join('')}}</td>
    <td>${{esR ? esc(r[12]) : ''}}</td>
    <td>${{esc(D.ase[r[3]])}}</td>
    <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
    <td>${{esc(D.fu[r[4]])}}</td><td>${{esc(r[5])}}</td>
    <td><span class="sc" style="background:${{scCol(r[6])}}">${{r[6]}}</span></td>
    <td>${{esc(r[7] || '—')}}</td>
    <td style="color:var(--gris);font-size:11.5px">${{esc(r[13] || '')}}</td></tr>`;
  }}).join('');
  box.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap">
    <button class="btn sec" onclick="cerrarSeg('${{seg}}')">✕ Cerrar</button>
    <span style="font-size:12px;color:var(--gris)">Ordenados por potencial. Mostrando ${{fN(ST[seg])}} de ${{fN(idxs.length)}}.</span></div>
  <div class="tbox"><table><thead><tr>
  <th data-tip="Potencial para ESTA área: suma de puntos por señal (conversación 40, declarado 30-35, tenant 30, capital 25-30, sin visa 20, pipeline 12). Verde ≥60, dorado ≥35.">Potencial</th>
  <th>Lead</th>
  <th data-tip="Las señales concretas que lo clasifican en este segmento.">Señales</th>
  <th data-tip="${{esR ? 'Estancia corta, larga o ambas, según lo que dijo o declaró.' : ''}}">${{esR ? 'Estancia' : ''}}</th>
  <th data-tip="Asesor de VENTAS que lo tiene hoy: coordinar la entrega con él/ella.">Asesor origen</th>
  <th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp.">Teléfono</th>
  <th data-tip="Medio por el que se adquirió.">Fuente</th><th>Lead Status</th>
  <th data-tip="Lead score de VENTAS (0-100) — referencia de temperatura general.">Score venta</th>
  <th>Creado</th>
  <th data-tip="Frase textual del lead en WhatsApp que disparó la señal (recortada a 120 caracteres).">Lo que dijo</th>
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

out = str(ROOT / f'lineas-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e6:.2f} MB)')
print('segmentos:', {k: len(v) for k, v in SEG.items()})
print(f'potencial arriendo: {len(PA_IDS)} | crédito: {len(PC_IDS)} | ambas: {AMBAS}')
