#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de INSIGHTS de contactos y clientes: radiografía por país (prefijo móvil),
qué quieren y qué desean (evidencia de campos del CRM + conversaciones), buyer
personas construidas de los clusters reales, y guiones de persuasión por scoring.
Los números se calculan de los datos al generar; los textos interpretan esa
evidencia (revisarlos al regenerar). Solo lectura del CRM."""
import json
from collections import Counter
from datetime import datetime
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
cs = json.load(open(DATA / 'contacts.json'))
users = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
_hoy = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'
def fmt(n): return f'{n:,}'.replace(',', '.')
def pct(x): return f'{x:.0f}'.replace('.', ',') + '%'

CURSO_PTS = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
STATUS_PTS = {'Negocio abierto': 25, 'En curso': 15, 'Intento de contacto': 8, 'Nuevo': 5, 'En Nutrición': 3}
def _n(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0
def score_of(ct):
    _v2 = _SC2.get(ct.get('id') or '')
    if _v2 is not None: return _v2['s']
    s = CURSO_PTS.get((ct.get('enCursoPor') or '').strip(), 0) + STATUS_PTS.get((ct.get('leadStatus') or '').strip(), 0)
    s += min(20, _n(ct.get('vecesContactado')) + _n(ct.get('salesActivities')))
    la = ct.get('lastActivity') or ct.get('lastEngagement')
    if la:
        try:
            dt = datetime.fromisoformat(str(la).replace('Z', '+00:00'))
            d = (datetime.now(dt.tzinfo) - dt).days
            s += 20 if d <= 7 else 15 if d <= 30 else 8 if d <= 90 else 4 if d <= 180 else 0
        except ValueError: pass
    return min(100, s)

# país por PREFIJO DEL MÓVIL
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

base_p, cli_p, cal_p = Counter(), Counter(), Counter()
temps = Counter()
pres = Counter(); zonas = Counter(); hob = Counter(); intencion = 0; anio = Counter()
visa_si = visa_no = 0
for c in cs:
    p = pais_of(c.get('phone'))
    sc = score_of(c)
    st = (c.get('leadStatus') or '').strip()
    base_p[p] += 1
    if st == 'Cliente': cli_p[p] += 1
    if sc >= 30: cal_p[p] += 1
    temps['hot' if sc >= 55 else 'warm' if sc >= 30 else 'cold' if sc >= 10 else 'none'] += 1
    pr = str(c.get('presupuesto') or '').strip()
    if pr and 'No espec' not in pr: pres[pr.replace('\xa0', ' ').strip()] += 1
    for z in (c.get('zonaInteres') or []):
        if isinstance(z, str) and z.strip() and 'No espec' not in z: zonas[z.strip()] += 1
    h = c.get('hobbies')
    if h: hob[str(h).strip()] += 1
    ii = str(c.get('intencionInv') or '').strip().lower()
    if ii.startswith('si') or ii == 'sí': intencion += 1
    a = str(c.get('anoCompra') or '').strip()
    if a: anio[a] += 1
    v = str(c.get('visaVigente') or '').strip().upper()
    if v == 'SI': visa_si += 1
    elif v == 'NO': visa_no += 1
pres_total = sum(pres.values())
# unificar variantes de presupuesto
pres_u = Counter()
for k, v in pres.items():
    kk = k.replace('900,000 +', '900,000+').replace('150,000-250,000', '150,000 a 250,000')
    pres_u[kk] += v
TOTAL = len(cs)
TOT_CLI = sum(cli_p.values())

# ---------- filas lead a lead para "ver quiénes son" desde cada variable ----------
def grupo(src):
    s = ' '.join((src or '').split()); sl = s.lower()
    if not sl or sl == '<unspecified>': return '(Sin fuente)'
    if 'google' in sl or sl.startswith('goo ') or sl == 'paid search': return 'Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl: return 'Referidos / Personal'
    if sl.startswith('prensa'): return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'): return 'Sitio Web'
    return s

def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi
DA, giA = dict_indexer(); DRL, giRL = dict_indexer(); DFU, giFU = dict_indexer()
DST, giST = dict_indexer(); DCU, giCU = dict_indexer(); DPA, giPA = dict_indexer()
DPR, giPR = dict_indexer(); DZO, giZO = dict_indexer(); DHO, giHO = dict_indexer()
DTG, giTG = dict_indexer()

AGREM_KW = ('cirujan', 'interquirofan', 'amcham', 'agremiacion', 'agremiación', 'odonto', 'medic')

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

LEADROWS = []
ROW_BY_CID = {}
for ct in cs:
    a = users.get(ct['assigned'], '(Sin asesor)') if ct['assigned'] else '(Sin asesor)'
    rl = ct.get('realtor') or []
    if isinstance(rl, str): rl = [rl]
    rl = ', '.join(x.strip() for x in rl if x and x.strip()) or '—'
    st = (ct.get('leadStatus') or '').strip() or '(Sin status)'
    ku = (ct.get('enCursoPor') or '').strip() or '(Sin dato)'
    pr = str(ct.get('presupuesto') or '').replace('\xa0', ' ').strip()
    pr = pr.replace('900,000 +', '900,000+').replace('150,000-250,000', '150,000 a 250,000')
    if not pr or 'No espec' in pr: pr = '(Sin dato)'
    zo = next((z.strip() for z in (ct.get('zonaInteres') or [])
               if isinstance(z, str) and z.strip() and 'No espec' not in z), '(Sin dato)')
    ho = str(ct.get('hobbies') or '').strip() or '(Sin dato)'
    ii = str(ct.get('intencionInv') or '').strip().lower()
    tags = [t.strip() for t in (ct.get('tags') or []) if t and t.strip()]
    agrem = 1 if any(any(k in t.lower() for k in AGREM_KW) for t in tags) else 0
    v = str(ct.get('visaVigente') or '').strip().upper()
    ROW_BY_CID[ct['id']] = len(LEADROWS)
    LEADROWS.append([(ct.get('name') or '(sin nombre)').strip().title(),
                     ct.get('email') or '', ct.get('phone') or '',
                     giA(a), giRL(rl[:50]), giFU(grupo(ct.get('source'))), giST(st), giCU(ku),
                     score_of(ct), fecha_local(ct.get('created')), giPA(pais_of(ct.get('phone'))),
                     giPR(pr), giZO(zo), giHO(ho),
                     1 if (ii.startswith('si') or ii == 'sí') else 0,
                     1 if v == 'SI' else (0 if v == 'NO' else -1),
                     str(ct.get('anoCompra') or '').strip(), agrem,
                     [giTG(t) for t in tags[:8]], intentos_of(ct['id'])])


def barra(n, total, color='#3A566B'):
    w = max(2, n / max(total, 1) * 100)
    return f'<div class="bar"><div style="width:{w:.0f}%;background:{color}"></div></div>'

# tabla países
filas_p = ''
for p, n in base_p.most_common(14):
    conv = cli_p[p] / n * 100 if n else 0
    ccol = '#1E9E62' if conv >= 5 else '#AA9664' if conv >= 2.5 else '#5B6B85'
    filas_p += (f'<tr class="clkv" data-lf="pais:{giPA(p)}" data-tip="Clic para ver los {fmt(n)} leads de {p} con todos sus datos."><td><b>{p}</b></td><td>{fmt(n)}</td><td style="width:26%">{barra(n, base_p.most_common(1)[0][1])}</td>'
                f'<td>{fmt(cli_p[p])}</td><td>{fmt(cal_p[p])}</td>'
                f'<td style="color:{ccol};font-weight:800">{pct(conv)}</td></tr>')

def dist(counter, top, total, color='#3A566B', lf=None, idx=None):
    out = ''
    for k, n in counter.most_common(top):
        kk = k.replace('\xa0', ' ').strip()
        atr = ''
        if lf and idx is not None and kk in idx:
            atr = f' class="clkv" data-lf="{lf}:{idx[kk]}" data-tip="Clic para ver los {fmt(n)} leads con {kk}."'
        out += (f'<tr{atr}><td style="white-space:nowrap">{k[:34]}</td><td style="width:45%">{barra(n, counter.most_common(1)[0][1], color)}</td>'
                f'<td style="white-space:nowrap">{fmt(n)} · {pct(n/max(total,1)*100)}</td></tr>')
    return out

def persona(emoji, nombre, quien, datos, quiere, desea, decirle, evitar, lf=None):
    datos_h = ''.join(f'<span class="dato">{d}</span>' for d in datos)
    btn = f'<button class="verbtn" data-lf="{lf}">📋 Ver los leads de este perfil</button>' if lf else ''
    return f'''<div class="pcard">
<h3>{emoji} {nombre}</h3>
<div class="datos">{datos_h}</div>
<p><b>Quién es:</b> {quien}</p>
<p><b>🎯 Qué quiere (racional):</b> {quiere}</p>
<p><b>💭 Qué desea (emocional):</b> {desea}</p>
<p class="dile"><b>🗣 Qué decirle:</b> {decirle}</p>
<p class="nodile"><b>🚫 Cómo NO hablarle:</b> {evitar}</p>
{btn}
</div>'''

PERSONAS = ''
PERSONAS += persona('🏌️', 'El Socio de Club colombiano',
  f'El corazón de la base: Colombia tiene {fmt(base_p["Colombia"])} contactos ({pct(base_p["Colombia"]/TOTAL*100)}) captados sobre todo en activaciones de golf (2.325 contactos), torneos de tenis/squash y clubes campestres de Bogotá, Cali, Medellín, Armenia y Barranquilla. Su hobbie nº1 declarado es golf (745 personas).',
  [f'{fmt(base_p["Colombia"])} contactos', f'{fmt(cli_p["Colombia"])} clientes', 'conv 2,6%', 'presupuesto típico 250-499k USD'],
  'Dolarizar parte de su patrimonio con una propiedad que se pague sola en renta; presupuesto declarado dominante de USD 250.000-499.000.',
  'Estatus y pertenencia: invertir donde invierten sus pares del club. Seguridad para la familia y un pie en Miami sin dejar su vida en Colombia.',
  'Lenguaje de par a par y prueba social: "varios socios de su club ya invirtieron con nosotros". Invitación presencial (cata, torneo, charla en SU club) antes que llamada fría. Cifras de valorización + renta en dólares vs CDT en pesos.',
  'Goteo genérico de plantillas ni urgencia artificial: es un perfil de confianza y relación, se cierra en persona. Su conversión (2,6%) está por debajo de mercados menores: sobra volumen, falta seguimiento 1:1 post-evento.', lf='p1')

PERSONAS += persona('🩺', 'El Profesional de agremiación (médicos y empresarios)',
  'Cirujanos, odontólogos y empresarios captados vía agremiaciones: Celebración IQ Interquirófanos (169), masterclasses para cirujanos plásticos, asambleas AmCham en Cali y Medellín. Alto ingreso, cero tiempo.',
  ['~500 contactos de agremiaciones', 'ingreso alto', 'sin tiempo', 'Medellín · Cali · Bquilla'],
  'Inversión llave en mano: que otro administre (property management), financiamiento como extranjero resuelto, números claros de rendimiento.',
  'Eficiencia y respeto por su tiempo; construir patrimonio sin distraerse de su consulta/empresa. Que lo atienda alguien de su nivel.',
  'Directo a los números en el primer contacto: cuota inicial, renta esperada, quién administra. Ofrecer llamada de 15 minutos con especialista financiero, no "charla informativa". Property management como argumento central.',
  'Invitaciones masivas repetidas ni mensajes largos de marketing: si no ve el número y el siguiente paso en 2 líneas, no responde.', lf='agrem')

PERSONAS += persona('🇲🇽', 'El Empresario de CDMX / Monterrey',
  f'México es el segundo mercado: {fmt(base_p["México"])} contactos y {fmt(cli_p["México"])} clientes (conv {pct(cli_p["México"]/base_p["México"]*100)}, mejor que Colombia). Captado en eventos del Club de Industriales (Polanco) y Monterrey; la ciudad de residencia más declarada de la base es Ciudad de México.',
  [f'{fmt(base_p["México"])} contactos', f'{fmt(cli_p["México"])} clientes', 'conv 3,8%', 'eventos Polanco/MTY'],
  'Diversificar fuera de México: propiedad en EE.UU. como cobertura cambiaria y de riesgo político, con renta en dólares.',
  'Tranquilidad patrimonial y un plan B tangible para su familia; el orgullo discreto de "tener algo en Miami".',
  'Enfoque protección + oportunidad: "blindar su patrimonio en dólares mientras renta". Casos de clientes mexicanos. Eventos presenciales en CDMX/Monterrey funcionan: seguir ese canal y rematar con seguimiento personal a los 3 días.',
  'No mencionar política directamente (él ya la tiene en la cabeza); no dejar pasar más de una semana post-evento — este mercado convierte mejor que el promedio cuando se le da seguimiento.', lf='p3')

PERSONAS += persona('🔎', 'El Buscador Digital urgente (Google)',
  f'Llega por Google/Paid Search ({fmt(720)} contactos) buscando YA: "quiero asesoría para invertir o rentar en Hollywood/Downtown/Miami Beach". Pregunta precios, cuota inicial y requisitos de renta por WhatsApp. Es el lead con más intención… y la fuente con más abandono de respuesta (12%).',
  ['720 contactos', '17,1% calificados', 'canal: WhatsApp', 'horizonte corto'],
  'Respuestas concretas inmediatas: precio "desde", cuota inicial, requisitos de renta, opciones en SU zona de interés (Orlando y Miami Beach son las más declaradas).',
  'Resolver su necesidad esta semana — mudanza, inversión puntual o renta. Odia que le pidan una llamada antes de darle un solo dato.',
  'Responder en menos de 1 hora con la cifra + 2 opciones + siguiente paso ("¿le agendo visita virtual mañana?"). La ficha de crédito para extranjeros lista para enviar. Todo por WhatsApp, que es donde él vive.',
  'Plantillas del goteo de nutrición ni "un asesor lo llamará": la auditoría muestra a estos leads preguntando cuota inicial y quedándose sin respuesta. Cada hora sin responder es plata de pauta quemada.', lf='p4')

PERSONAS += persona('🇺🇸', 'El Latino que ya vive en EE.UU.',
  f'{fmt(base_p["EE.UU. / Canadá"])} contactos con número de EE.UU./Canadá — y la mejor conversión de los mercados grandes: {pct(cli_p["EE.UU. / Canadá"]/base_p["EE.UU. / Canadá"]*100)} ({fmt(cli_p["EE.UU. / Canadá"])} clientes). Conoce el mercado, tiene crédito local y no necesita visa. Nota aparte: Venezuela convierte 40,9% — comunidad migrante que compra y refiere en bloque.',
  [f'{fmt(base_p["EE.UU. / Canadá"])} contactos', f'{fmt(cli_p["EE.UU. / Canadá"])} clientes', 'conv 12,2%', 'sin barrera de visa'],
  'Segunda propiedad de inversión, renta corta vacacional u optimizar la que ya tiene (property management).',
  'Hacer crecer lo que ya construyó en EE.UU.; ser el de la familia que "llegó" y ahora invierte.',
  'Hablarle como a un local: cap rate, HOA, financiamiento convencional. Ofrecer análisis de valorización de su zona y oportunidades de preconstrucción con lista de precios. Es el mercado donde más rinde cada llamada.',
  'No explicarle lo básico de EE.UU. (le aburre) ni tratarlo como extranjero. Y no descuidarlo: con 12,2% de conversión, cada lead de este mercado vale 5 colombianos en probabilidad de cierre.', lf='p5')

PERSONAS += persona('💎', 'El Cliente que recompra y refiere',
  f'{fmt(TOT_CLI)} clientes, de los cuales 59 ya tienen NUEVA oportunidad registrada y 15 son Elite activos. Recibe invitaciones a catas, F1 y golf. Su hobbie dominante también es golf.',
  [f'{fmt(TOT_CLI)} clientes', '59 recompra declarada', '15 Elite activos', 'CAC = $0'],
  'Que su inversión rinda y enterarse PRIMERO de los lanzamientos (primicia de lista de precios); beneficios tangibles por su lealtad.',
  'Sentirse insider y VIP; el gusto de recomendar con autoridad ("yo ya compré ahí").',
  'Primicia + reporte de SU inversión ("su unidad se valorizó X%") + pedir el referido en el momento de satisfacción: "¿a qué socio de su club le gustaría este análisis?". El realtor (no marketing) hace esta llamada.',
  'Que su única comunicación sean broadcasts: la auditoría encontró clientes reclamando llamadas prometidas mientras recibían invitaciones a whisky. Un cliente ignorado no refiere.', lf='p6')

# ---------- análisis de conversaciones: necesidades y objeciones ----------
import math
try:
    _wa = [c for c in json.load(open(DATA / 'wa_all_msgs.json')) if c.get('msgs')]
except Exception:
    _wa = []
AUTO = ('gracias por tu mensaje', 'gracias por comunicarte', 'thank you for contacting',
        'no podemos responder', 'asistente virtual', 'bienvenido a', 'fuera de la oficina',
        'auto-reply', 'mensaje automático')
TEMAS_CONV = [
 ('Eventos (confirmar/asistir)', ('evento','charla','webinar','confirmo','confirmar','asistir','asistencia'), '#3A566B',
  'Logística de eventos: confirmaciones, acompañantes, lugar y hora. Necesidad de ATENCIÓN, no objeción.'),
 ('Pide cita / llamada', ('cita','llamada','llamar','llamame','llámame','agendar','reunion','reunión','zoom','hablar con'), '#2C4356',
  'Quiere hablar con un humano: pide agendar o que lo llamen. La necesidad más fácil de convertir en gestión.'),
 ('Pide información', ('informacion','información','comparteme','compárteme','enviame','envíame','mandame','mándame','más info','mas info','more information','interesa saber'), '#C4B284',
  'Pide que le envíen información — casi siempre por WhatsApp. Es un SÍ esperando material.'),
 ('Zona / tipo de propiedad', ('orlando','miami beach','brickell','doral','hollywood','downtown','apartament','casa ','estudio','studio','bedroom','habitacion','local comercial'), '#1E9E62',
  'Pregunta por zonas o tipos de propiedad concretos: necesidad de compra específica.'),
 ('Renta / alquiler', ('renta','rentar','alquil','arrend','lease','airbnb','hospeda'), '#AA9664',
  'Necesita rentar (corta o larga estadía) o quiere invertir para rentar: requisitos, precios por noche/mes.'),
 ('Precio / presupuesto', ('precio','cuanto','cuánto','costo','cuota inicial','presupuesto','vale ','valor de'), '#8A6D1A',
  'Pregunta cifras: cuánto cuesta, cuota inicial, presupuesto. Quiere números antes que discursos.'),
 ('Objeción: ahora no / dinero', ('no puedo','no me es viable','mas adelante','más adelante','no tengo dinero','no tengo recursos','otro momento','despues','después','no por ahora','económica','sin trabajo'), '#C47845',
  'Objeción de momento o de liquidez: interesa pero no ahora. Se maneja con recontacto agendado (modelo Natalia Cardenas).'),
 ('Objeción: no interesado', ('no me interesa','no estoy interesad','no quiero','dejen de','no molest','equivocado','perder dinero','eliminen','borrar mis datos'), '#D64545',
  'Rechazo explícito o queja. Requiere lista de supresión y, si hay queja, escalar a gerencia.'),
 ('Crédito / financiación', ('credito','crédito','financ','hipotec','prestamo','préstamo','banco','enganche'), '#5A6B78',
  'Pregunta por crédito hipotecario como extranjero: la objeción-necesidad nº1 del negocio.'),
 ('Visa / migración', ('visa','residencia','migra','green card'), '#8A99A8',
  'Dudas de visa o estatus migratorio: se responde con el guión de inversión sin visa.'),
]
conv_cnt = Counter(); CONV_N = 0
TEMASEG = {i: set() for i in range(len(TEMAS_CONV))}
for cv in _wa:
    textos = [m[2].lower() for m in cv['msgs'] if m[0] == 1 and m[2] and not any(a in m[2].lower() for a in AUTO)]
    if not textos: continue
    CONV_N += 1
    todo = ' | '.join(textos)
    ri = ROW_BY_CID.get(cv.get('contactId'))
    for i, (tema, kws, _c, _d) in enumerate(TEMAS_CONV):
        if any(k in todo for k in kws):
            conv_cnt[tema] += 1
            if ri is not None: TEMASEG[i].add(ri)
TEMASEG = {i: sorted(v2, key=lambda r: -LEADROWS[r][8]) for i, v2 in TEMASEG.items()}
TEMA_IDX = {t[0]: i for i, t in enumerate(TEMAS_CONV)}

def _arc(cx, cy, r0, r1, a0, a1):
    p = lambda r, a: (cx + r * math.cos(a), cy + r * math.sin(a))
    x0, y0 = p(r1, a0); x1, y1 = p(r1, a1); x2, y2 = p(r0, a1); x3, y3 = p(r0, a0)
    big = 1 if (a1 - a0) > math.pi else 0
    return f'M{x0:.0f} {y0:.0f} A{r1} {r1} 0 {big} 1 {x1:.0f} {y1:.0f} L{x2:.0f} {y2:.0f} A{r0} {r0} 0 {big} 0 {x3:.0f} {y3:.0f} Z'

def pie_conversaciones():
    if not conv_cnt: return ''
    total = sum(conv_cnt.values())  # nota: una convo puede tocar varios temas
    datos = [(t, conv_cnt[t], c, d) for t, k, c, d in TEMAS_CONV if conv_cnt.get(t)]
    datos.sort(key=lambda x: -x[1])
    cx, cy, r0, r1 = 175, 118, 55, 100
    a = -math.pi / 2
    svg = ''
    for t, n, c, d in datos:
        a2 = a + n / total * 2 * math.pi
        tip = f'{t}: {fmt(n)} conversaciones ({n/CONV_N*100:.0f}% de las {fmt(CONV_N)} con voz del cliente). {d}'
        svg += f'<path d="{_arc(cx, cy, r0, r1, a, a2)}" fill="{c}" stroke="#fff" stroke-width="2" data-tip="{tip.replace(chr(34), "&quot;")} Clic para ver esos leads." data-lf="tema:{TEMA_IDX[t]}" style="cursor:pointer"/>'
        if n / total >= 0.055:
            am = (a + a2) / 2
            rx, ry = cx + (r0 + r1) / 2 * math.cos(am), cy + (r0 + r1) / 2 * math.sin(am)
            svg += f'<text x="{rx:.0f}" y="{ry:.0f}" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" pointer-events="none">{n/total*100:.0f}%</text>'
        a = a2
    svg += f'<text x="{cx}" y="{cy-2}" text-anchor="middle" font-size="19" font-weight="900" fill="#152238">{fmt(CONV_N)}</text>'
    svg += f'<text x="{cx}" y="{cy+15}" text-anchor="middle" font-size="10" fill="#5B6B85">convos con voz del cliente</text>'
    leyenda = ''.join(
        f'<span class="li" data-lf="tema:{TEMA_IDX[t]}" data-tip="{d.replace(chr(34), "&quot;")} Clic para ver esos leads." style="cursor:pointer"><span class="dot" style="background:{c}"></span>{t}: <b>{fmt(n)}</b> ({n/CONV_N*100:.0f}%)</span>'
        for t, n, c, d in datos)
    return f'''<h2>💬 Lo que dicen en las conversaciones: necesidades y objeciones</h2>
<p style="font-size:12.5px;color:var(--gris)">Clasificación temática de los mensajes reales de clientes en las {fmt(len(_wa))} conversaciones de WhatsApp (excluyendo auto-respuestas): {fmt(CONV_N)} conversaciones tienen voz del cliente y una misma conversación puede tocar varios temas. Pasa el mouse sobre cada porción para el detalle y cómo manejarla.</p>
<div class="grid2" style="align-items:center">
<div><svg viewBox="0 0 350 240" style="width:100%;height:auto;display:block">{svg}</svg></div>
<div><div class="pleg">{leyenda}</div>
<div class="caveat" style="margin-top:12px"><b>La lectura clave:</b> el 56% de lo que dicen son <b>necesidades de atención</b> (eventos, citas, "mándame info") — gente pidiendo que la atiendan, no poniendo peros. Las <b>objeciones reales son solo el 8%</b> ({fmt(conv_cnt.get("Objeción: ahora no / dinero", 0) + conv_cnt.get("Objeción: no interesado", 0))} convos), y la mitad son "ahora no" manejables con recontacto agendado. Las <b>necesidades de compra concretas</b> (zona, renta, precio, crédito, visa) suman {fmt(conv_cnt.get("Zona / tipo de propiedad", 0) + conv_cnt.get("Renta / alquiler", 0) + conv_cnt.get("Precio / presupuesto", 0) + conv_cnt.get("Crédito / financiación", 0) + conv_cnt.get("Visa / migración", 0))} conversaciones que piden exactamente lo que el blog ya responde (ver biblioteca abajo). La barrera del embudo no es el "no" del cliente: es el silencio de PFS.</div></div>
</div>'''
PIE_CONV = pie_conversaciones()

def _ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
INS_PAYLOAD = json.dumps({'rows': LEADROWS, 'ase': _ordered(DA), 'rl': _ordered(DRL),
    'fu': _ordered(DFU), 'sts': _ordered(DST), 'cu': _ordered(DCU), 'pa': _ordered(DPA),
    'pr': _ordered(DPR), 'zo': _ordered(DZO), 'ho': _ordered(DHO), 'tg': _ordered(DTG),
    'tema': {str(i): v for i, v in TEMASEG.items()},
    'temaNom': [t[0] for t in TEMAS_CONV]}, ensure_ascii=False)


# artículos reales del blog corporativo/blog (catalogados el 2026-07-20) para el embudo
B = 'https://www.pfsrealty.com/blog/'
BLOG = {
 'manual':      (B + 'como-comprar-una-casa-en-florida', 'Cómo comprar una casa en Florida: manual para extranjeros'),
 'tasas':       (B + 'tasa-de-interes-para-comprar-casa-en-estados-unidos', 'Tasa de interés para comprar casa en EE.UU.'),
 'precios':     (B + 'cuanto-cuesta-una-casa-en-miami', 'Cuánto cuesta una casa en Miami: precios y zonas 2026'),
 'valoriza':    (B + 'valorizacion-de-inmuebles', 'Valorización de inmuebles: haz crecer tu patrimonio'),
 'mercadoMayo': (B + 'mercado-inmobiliario-de-miami-mayo-de-2026', 'Mercado inmobiliario de Miami: mayo 2026'),
 'record':      (B + 'mercado-inmobiliario-de-miami-abril-2026', 'Récord de ventas en abril de 2026'),
 'report':      (B + 'miami-report-marzo-2026', 'Miami Report Q1-2026'),
 'precon':      (B + 'preconstruccion-vs-reventa-en-miami', 'Preconstrucción vs reventa: ¿cuál conviene?'),
 'planos':      (B + 'proyectos-sobre-planos', 'Proyectos sobre planos: guía para extranjeros'),
 'zonas':       (B + 'invertir-en-brickell-vs-wynwood', 'Brickell vs Wynwood: qué ofrece cada zona'),
 'rentar':      (B + 'como-rentar-una-casa-de-forma-segura', 'Cómo rentar una casa de forma segura'),
 'gestion':     (B + 'gestion-inmobiliaria', 'Cómo cobrar tu renta desde el exterior'),
 'rentab':      (B + 'rentabilidad-de-una-propiedad', 'Rentabilidad de una propiedad en Miami'),
 'colombia':    (B + 'inversion-inmobiliaria-en-miami-colombia', 'Colombia lidera la inversión en Miami'),
 'ecuador':     (B + 'ecuatorianos-en-miami', 'Ecuatorianos en Miami: ¿buen momento para comprar?'),
 'eb5':         (B + 'visa-eb5-para-mexicanos', 'Visa EB5 para mexicanos: cómo aplicar'),
 'aeropuerto':  (B + 'aeropuerto-internacional-de-miami-expansion', 'Expansión millonaria del aeropuerto de Miami'),
 'empresas':    (B + 'empresas-mas-grandes-del-mundo-en-miami', 'Las empresas más grandes del mundo llegan a Miami'),
 'costo':       (B + 'costo-de-vida-en-florida', 'Costo de vida en Florida'),
 'propietarios':(B + 'propietarios-de-casas-en-miami', 'Claves de rentabilidad para propietarios'),
 'tipos':       (B + 'tipos-de-arrendamiento-de-inmuebles', 'Tipos de arrendamiento: cómo elegir'),
 'unifam':      (B + 'casas-unifamiliares-en-miami', 'Casas unifamiliares: tips para latinos'),
 'familia':     (B + 'vivir-con-familia-en-miami', 'Vivir con familia en Miami'),
}
def A(k, txt=None):
    u, t = BLOG[k]
    return f'<a href="{u}" target="_blank">{txt or t}</a>'

# flujos de nutrición por temperatura: etapas + hooks + herramientas
def temp_card(color, emoji, titulo, n, mental, objetivo, etapas, hooks, herr, nodo, tkey=""):
    et = ''.join(f'<div class="etapa"><span class="cuando" style="background:{color}">{c}</span><span>{m}</span></div>' for c, m in etapas)
    hk = ''.join(f'<li>{h}</li>' for h in hooks)
    hr = ''.join(f'<li>{h}</li>' for h in herr)
    return f'''<div class="tcard" style="border-top-color:{color}">
<h3 style="color:{color}">{emoji} {titulo} · {fmt(n)} leads</h3>
<p><b>Estado mental:</b> {mental}</p>
<p><b>Objetivo:</b> {objetivo}</p>
<button class="verbtn" data-lf="temp:{tkey}" style="float:right;margin:-2px 0 4px 8px">📋 Ver estos leads</button>
<b style="font-size:13px">📩 Flujo de nutrición (etapas y mensajes):</b>
{et}
<b style="font-size:13px">🪝 Hooks e ideas de contenido:</b><ul class="mini">{hk}</ul>
<b style="font-size:13px">🧰 Herramientas para retomarlos:</b><ul class="mini">{hr}</ul>
<p class="nodile"><b>🚫 No hacer:</b> {nodo}</p>
</div>'''

TCARDS = ''
TCARDS += temp_card('#D64545', '🔥', 'CALIENTE (score ≥55)', temps['hot'],
  'Ya decidió explorar en serio: horizonte declarado, estado activo e interacción reciente. Está comparando — probablemente también con la competencia.',
  'Al caliente NO se le nutre: se le cierra. Cadencia de cierre de 7 días, todo personal.',
  [('Día 0', '"[Nombre], según su horizonte de [X meses] le separé 2 opciones en [zona] dentro de su presupuesto. ¿Le muestro los números mañana 10 a.m. o 4 p.m.? Son 15 minutos."'),
   ('Día 2', 'Prueba social de su perfil: "un cliente de [su país/club] cerró esta semana en el mismo proyecto — le comparto cómo estructuró el crédito." Refuerzo: ' + A('colombia') + ' (o el artículo de su país).'),
   ('Día 5', 'Urgencia legítima (nunca inventada): "quedan N unidades de la lista de precios que le envié / la fase sube de precio el [fecha]."'),
   ('Día 7', 'Llamada de decisión: resolver la objeción final (normalmente crédito o cuota inicial) con el especialista financiero en la línea.')],
  ['Comparativo de 2 unidades lado a lado (precio, renta esperada, HOA) — decidir entre 2 es más fácil que decidir sí/no. Contexto: ' + A('precon') + '.',
   'Simulación de crédito para extranjero YA armada con su banda de presupuesto + el artículo ' + A('tasas') + ' como respaldo.',
   'Video corto de 60 seg del proyecto/unidad grabado por el asesor (no institucional).',
   'Fecha real: entrega de fase, cambio de lista de precios, cupo del evento de lanzamiento.'],
  ['La píldora 🔥 del dashboard (Gestión comercial) como cola de trabajo diaria del gerente.',
   'Tarea en GHL con vencimiento a 72h por cada caliente; si vence sin actividad → alerta y reasignación.',
   'Enlace de agenda (calendario GHL) en cada mensaje: que pueda auto-agendarse sin fricción.',
   'Registrar TODO: cada llamada suma interacción y mantiene el score arriba mientras decide.'],
  'Dejarlo enfriar más de 72 horas ni meterlo al goteo genérico. Solo hay ' + fmt(temps['hot']) + ': cada uno es oro.', tkey='hot')

TCARDS += temp_card('#AA9664', '🌤', 'TIBIO (30-54)', temps['warm'],
  'Interesado pero con UNA pieza faltante: o no declaró horizonte, o lleva semanas sin interacción. La intención existe: miles dijeron que SÍ quieren invertir.',
  'Recalificar y recalentar: una conversación real que actualice horizonte + registre interacción lo puede volver caliente (+40 pts).',
  [('Día 0', 'Mensaje personal que re-pregunta el horizonte: "[Nombre], el mercado se movió a su favor: [dato]. ¿Sigue pensando en invertir este año o lo ve más adelante? Se lo pregunto para enviarle solo lo que le sirva."'),
   ('Día 7', 'Contenido de valor sin pedir nada: enviar ' + A('precios') + ' o ' + A('zonas') + ' según su zona declarada, con 2 líneas personales del asesor.'),
   ('Día 21', 'Caso de éxito espejo por país: ' + A('colombia') + ' o ' + A('ecuador') + ' + números reales de renta. Cierre suave: "¿le armo unos números así para usted?"'),
   ('Día 45', 'Utilidad + pregunta binaria: enviar ' + A('manual') + ' y ' + A('tasas') + ' + "¿retomamos el tema o prefiere que le escriba en [trimestre]?" — cualquier respuesta reactiva el score.')],
  ['Valorización de su zona declarada con dato del mes: ' + A('mercadoMayo') + ' o ' + A('record') + '.',
   'Nuevo lanzamiento dentro de su banda de presupuesto, con ' + A('planos') + ' como educación de respaldo.',
   'Mundial FIFA 2026 en Miami: el gancho de demanda de renta corta con fechas reales.',
   'La objeción nº1 respondida antes de que la diga: ' + A('tasas') + ' y ' + A('manual') + '.',
   'Tasa de cambio / dolarización: el costo de esperar en moneda local, con ' + A('rentab') + '.'],
  ['Lista inteligente en GHL por score ≥30 (o por "En curso" + sin actividad 30 días) como cola semanal de cada asesor.',
   'Workflow "contestó → crear tarea al asesor + salir de la secuencia" (el que hoy falta y deja 220 esperando).',
   'Plantillas/snippets de WhatsApp por hook, personalizables en 20 segundos.',
   'Usar los tibios del dashboard → audiencia personalizada de remarketing en Meta/Google.'],
  'Venderle el cierre de una ni dejarlo en el goteo eterno: es el segmento más grande con potencial (' + fmt(temps['warm']) + ').', tkey='warm')

TCARDS += temp_card('#3A566B', '❄', 'FRÍO (10-29)', temps['cold'],
  'Señales débiles: interactuó alguna vez (evento, anuncio) y el interés quedó atrás. No te tiene presente.',
  'Re-despertar con un motivo NUEVO y de valor — nunca con "¿sigue interesado?" a secas. Una sola respuesta ya lo recalienta.',
  [('Mes 0', 'Gancho con memoria: "[Nombre], nos conocimos en [evento de su tag]. Desde entonces el mercado hizo esto: ' + A('valoriza') + '. ¿Le mando el análisis de su zona?"'),
   ('Mes 1', 'Contenido hito (sin pedir respuesta): ' + A('record') + ', ' + A('empresas') + ' o ' + A('aeropuerto') + ' — mantenerse presente con noticias, no con ventas.'),
   ('Mes 2', 'Pregunta de permanencia: "¿Miami sigue en sus planes? 1) Sí, este año · 2) Más adelante · 3) Ya no". Los 1 pasan a asesor, los 2 a cadencia trimestral, los 3 se despiden con elegancia.')],
  ['El "desde que nos conocimos": valorización acumulada desde SU fecha de registro (personalizado con su cohorte).',
   'Invitación a evento presencial en SU ciudad (el canal que ya funciona: clubes, catas, charlas).',
   'Historia narrada por país: ' + A('colombia') + ' / ' + A('eb5', 'Visa EB5 para mexicanos') + '.',
   'Cumpleaños (la etiqueta happy birthday ya existe) como excusa de contacto humano.'],
  ['Segmentar por el tag del evento de origen para personalizar el gancho (el dashboard los muestra por lead).',
   'Workflow de reactivación de 3 toques con salida automática al responder → tarea a asesor.',
   'Filtro ❄ + fuente en Gestión comercial para armar lotes de reactivación por campaña.',
   'Depurar rebotes y números inválidos en cada pasada (protege la reputación del canal).'],
  'Llamadas en frío sin contexto, mensajes largos, o frecuencia mayor a mensual.', tkey='cold')

TCARDS += temp_card('#8A99A8', '⚪', 'SIN SEÑALES (<10)', temps['none'],
  'Cero evidencia de interés registrada: importado, sin clasificar o agotado. Aquí vive casi la mitad de la base — y también los datos sucios.',
  'Separar el hielo del agua con el mínimo esfuerzo humano: campaña + workflow, no asesores uno a uno.',
  [('Único toque', '"[Nombre], ¿sigue en sus planes invertir en Miami? Responda 1 (sí, este año), 2 (más adelante) o 3 (ya no). Con eso le enviamos solo lo relevante — o dejamos de escribirle." (WhatsApp + email espejo).'),
   ('Si responde 1', 'Pasa a asesor con tarea de contacto en 24h — entra al flujo de tibios.'),
   ('Si responde 2', 'Cadencia trimestral de contenido hito (flujo de fríos, mes 1).'),
   ('Si responde 3 o calla 2 veces', 'Despedida elegante + archivar con motivo. Depurar también es ganar.')],
  ['Lead magnet de bajo esfuerzo: el ' + A('report') + ' como "reporte de mercado" a cambio de la respuesta.',
   '"Última comunicación": la honestidad de "si no respondes dejamos de escribirte" levanta tasas de respuesta.',
   'Sorteo/beneficio ligado a evento presencial (entradas, cata) para las plazas con eventos activos.'],
  ['Campaña masiva en GHL con workflow que clasifica por respuesta 1/2/3 automáticamente.',
   'Lista de supresión permanente: quejas, "no quiero saber nada" (la auditoría encontró casos) y rebotes.',
   'Medir el resultado en la sección "Evolución de la gestión": sin señales debe BAJAR mes a mes.',
   'Los archivados salen de las métricas activas: el score promedio del dashboard subirá solo con limpiar.'],
  'Gastar tiempo de asesores aquí uno a uno, o mantenerlos eternamente en la base inflando métricas y costos de envío.', tkey='none')

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Insights y buyer personas</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--verde:#1E9E62;--rojo:#D64545;--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff;font-size:14.5px;line-height:1.55}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 20px 50px}}
header{{background:var(--azul-oscuro);color:#fff;padding:20px 0}}
header .wrap{{display:flex;align-items:center;gap:14px;padding-bottom:0;flex-wrap:wrap}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:21px;letter-spacing:1px;padding:11px 13px;border-radius:9px}}
header h1{{font-size:18.5px;font-weight:800}} header p{{color:#C9D6E4;font-size:12.5px;margin-top:2px}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
h2{{font-size:17px;margin:26px 0 10px;border-bottom:2px solid var(--gris-linea);padding-bottom:6px}}
h3{{font-size:15px;margin:0 0 6px}}
.hero{{background:var(--azul-oscuro);color:#F2F6FA;border-radius:14px;padding:18px 22px;margin:16px 0;font-size:15px;line-height:1.6}}
.hero b{{color:var(--amarillo)}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:7px 8px;white-space:nowrap}}
td{{border-bottom:1px solid var(--gris-linea);padding:6px 8px;vertical-align:middle}}
tr:hover td{{background:var(--gris-fondo)}}
.bar{{background:var(--gris-fondo);border-radius:6px;height:15px;min-width:90px}}
.bar>div{{height:100%;border-radius:6px}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.pcard{{border:1px solid var(--gris-linea);border-left:5px solid var(--amarillo);border-radius:12px;padding:16px 18px;margin:12px 0}}
.pcard p{{margin:6px 0}}
.datos{{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}}
.dato{{background:var(--azul-suave);color:var(--azul-oscuro);border-radius:16px;padding:3px 11px;font-size:11.5px;font-weight:700}}
.dile{{background:#E9F6EF;border-radius:9px;padding:9px 12px}}
.nodile{{color:#7A2E2E;font-size:13px}}
.tcard{{border:1px solid var(--gris-linea);border-top:5px solid;border-radius:12px;padding:15px 17px}}
.tgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:14px;margin:10px 0}}
.tcard p{{margin:5px 0;font-size:13.3px}}
.etapa{{display:flex;gap:9px;align-items:flex-start;background:var(--gris-fondo);border-radius:9px;padding:7px 10px;margin:5px 0;font-size:12.8px;font-style:italic}}
.cuando{{flex-shrink:0;color:#fff;font-size:10px;font-weight:900;letter-spacing:.4px;padding:3px 9px;border-radius:14px;font-style:normal;white-space:nowrap;margin-top:1px}}
ul.mini{{padding-left:18px;margin:3px 0 8px}} ul.mini li{{margin:3px 0;font-size:12.8px}}
.clkv{{cursor:pointer}} tr.clkv:hover td{{background:var(--azul-suave)}}
.kpi.clkv:hover{{border-color:var(--azul);background:var(--gris-fondo)}}
.verbtn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:8px 13px;font-size:12px;font-weight:700;cursor:pointer;margin:6px 0 2px}}
.verbtn:hover{{background:#123c5c}}
.btn2{{border:0;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:8px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer}}
.tag{{display:inline-block;min-width:30px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
.tbox{{border:1px solid var(--gris-linea);border-radius:12px;overflow:auto;max-height:64vh}}
.tbox table{{font-size:12.6px}} .tbox th{{position:sticky;top:0;background:#fff}}
.pleg{{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.4px}}
.pleg .li{{cursor:help;white-space:nowrap}}
.pleg .dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:10px 12px}}
.kpi b{{font-size:20px;display:block}} .kpi span{{font-size:11px;color:var(--gris)}}
[data-tip]{{cursor:help}} th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.caveat{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.5px;margin:14px 0;color:#3d4c63}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Insights: quiénes son, qué desean y cómo persuadirlos</h1>
<p>[empresa] Group · Contactos y clientes · GoHighLevel (solo lectura) · Corte: {CORTE}</p></div>
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

<div class="hero">🧠 <b>El retrato de la base:</b> un inversionista hispano de clase alta, captado en persona (golf, clubes, agremiaciones) o buscando en Google, que quiere <b>dolarizar su patrimonio con una propiedad que se rente sola</b>. {fmt(intencion)} declararon explícitamente que SÍ desean invertir, el presupuesto más común es <b>USD 250.000-499.000</b>, su hobbie dominante es el <b>golf</b>, y sus preguntas reales por WhatsApp son de plata: cuota inicial, crédito como extranjero, requisitos de renta. Vive sobre todo en <b>Colombia ({pct(base_p["Colombia"]/TOTAL*100)})</b>, pero <b>convierte mejor donde menos volumen hay</b>: EE.UU. (12,2%) y Venezuela (40,9%).</div>

<h2>🌎 Dónde viven (país por prefijo del móvil) y dónde está la conversión</h2>
<table><thead><tr>
<th data-tip="País determinado por el indicativo telefónico del móvil del contacto.">País</th>
<th data-tip="Contactos totales de la base con ese indicativo.">Contactos</th><th></th>
<th data-tip="Contactos con Lead Status = Cliente.">Clientes</th>
<th data-tip="Leads tibios o calientes (score ≥30) de ese país.">Score ≥30</th>
<th data-tip="Clientes ÷ contactos del país: qué tan bien convierte ese mercado. Verde ≥5%, ámbar ≥2,5%.">Conversión</th>
</tr></thead><tbody>{filas_p}</tbody></table>
<p style="font-size:12.5px;color:var(--gris);margin-top:6px">Lecturas: <b>Colombia aporta el volumen pero convierte 2,6%</b> (sobra captación, falta seguimiento); <b>EE.UU. convierte 12,2%</b> — cada lead de ese mercado vale ~5 colombianos en probabilidad de cierre; <b>Venezuela 40,9%</b> — comunidad migrante que compra y refiere en bloque, ideal para programa de referidos.</p>

<h2>💭 Qué quieren y qué desean (la evidencia, no la suposición)</h2>
<div class="kpis">
<div class="kpi clkv" data-lf="int" data-tip="Contactos que respondieron SÍ en el campo 'Intención de Inversión' del CRM. Clic para ver quiénes son."><b style="color:var(--verde)">{fmt(intencion)}</b><span>declararon que SÍ quieren invertir</span></div>
<div class="kpi clkv" data-lf="presu-any" data-tip="Contactos con banda de presupuesto declarada (excluye 'No especifica'). Clic para ver quiénes son."><b>{fmt(sum(pres_u.values()))}</b><span>con presupuesto declarado</span></div>
<div class="kpi clkv" data-lf="visa-si" data-tip="Campo 'Tienes Visa Vigente'. Clic para ver los que SÍ tienen visa."><b>{fmt(visa_si)}/{fmt(visa_si+visa_no)}</b><span>con visa vigente (de los que respondieron)</span></div>
<div class="kpi clkv" data-lf="ano-2526" data-tip="Campo 'Posible Año de Compra' declarado 2025 o 2026. Clic para ver quiénes son."><b>{fmt(anio.get('2026', 0) + anio.get('2025', 0))}</b><span>declararon compra 2025-2026</span></div>
</div>
<div class="grid2">
<div><h3 style="margin-top:8px">💵 Presupuesto declarado (USD)</h3><table><tbody>{dist(pres_u, 6, sum(pres_u.values()), lf='presu', idx=DPR)}</tbody></table></div>
<div><h3 style="margin-top:8px">📍 Zona de interés declarada</h3><table><tbody>{dist(zonas, 6, sum(zonas.values()), '#AA9664', lf='zona', idx=DZO)}</tbody></table>
<h3>⛳ Hobbies declarados</h3><table><tbody>{dist(hob, 5, sum(hob.values()), '#1E9E62', lf='hobby', idx=DHO)}</tbody></table></div>
</div>
<div class="caveat"><b>Lo que piden en las conversaciones reales (auditoría WhatsApp):</b> requisitos y precios de <b>renta</b> ("¿cuánto sale el día?", "1 bedroom Miami Beach"), <b>cuota inicial y crédito como extranjero</b> ("¿cómo es el tema si es a crédito?"), <b>cifras concretas antes de agendar llamadas</b>, y que les manden la información <b>por WhatsApp</b>. Los deseos de fondo que se repiten: ingreso pasivo en dólares, plan B familiar (visa/migración), estatus frente a sus pares y patrimonio que se administre solo.</div>

{PIE_CONV}

<h2>👤 Buyer personas (construidas de los clusters reales de la base)</h2>
{PERSONAS}

<h2>🌡 Cómo persuadirlos según su scoring</h2>
<p style="font-size:12.5px;color:var(--gris)">El score dice en qué momento de la decisión está cada uno; el mensaje debe cambiar con la temperatura. Flujos de nutrición con etapas, hooks y herramientas — y los artículos del blog de PFS (pfsrealty.com/blog, 718 publicados) ya enlazados en cada etapa, listos para enviar por WhatsApp.</p>
<div class="tgrid">{TCARDS}</div>

<h2>📚 Biblioteca de contenido del blog para nutrición (por uso en el embudo)</h2>
<p style="font-size:12.5px;color:var(--gris)">Selección del blog corporativo (718 artículos) organizada por la objeción o momento que resuelve. Cada enlace es material listo para adjuntar en un mensaje de nutrición con 2 líneas personales del asesor.</p>
<div class="grid2">
<div><h3>💳 Crédito y proceso de compra (objeción nº1)</h3><ul class="mini">
<li>{A('manual')}</li><li>{A('tasas')}</li><li>{A('precon')}</li><li>{A('planos')}</li></ul>
<h3>🏘 Renta y gestión (lo que más preguntan por WhatsApp)</h3><ul class="mini">
<li>{A('rentar')}</li><li>{A('gestion')}</li><li>{A('tipos')}</li><li>{A('propietarios')}</li><li>{A('rentab')}</li></ul></div>
<div><h3>📈 Mercado y valorización (hooks de reactivación)</h3><ul class="mini">
<li>{A('mercadoMayo')}</li><li>{A('record')}</li><li>{A('report')}</li><li>{A('valoriza')}</li><li>{A('empresas')}</li><li>{A('aeropuerto')}</li></ul>
<h3>🌎 Por persona y estilo de vida</h3><ul class="mini">
<li>{A('colombia')} — para el Socio de Club</li><li>{A('eb5')} — para el Empresario de CDMX</li><li>{A('ecuador')}</li><li>{A('precios')} y {A('zonas')} — para el Buscador Digital</li><li>{A('unifam')} · {A('familia')} · {A('costo')}</li></ul></div>
</div>

<h2 id="verleads">📋 Los leads detrás de cada variable</h2>
<p style="font-size:12.5px;color:var(--gris)">Haz clic en cualquier variable de esta hoja — un país, una banda de presupuesto, una zona, un hobbie, un tema de conversación, una temperatura, un KPI o un buyer persona — y aquí aparece la tabla de esos leads con todos sus datos (asesor, realtor, contacto, WhatsApp, etiquetas).</p>
<div id="leadbox"><p style="color:var(--gris);font-size:13px">👆 Aún no has elegido una variable: haz clic en cualquier número, fila o porción de la hoja.</p></div>

<div class="caveat"><b>Nota metodológica.</b> Los números salen de los datos del CRM al corte {CORTE}: campos declarados (intención, presupuesto, zona, hobbies, visa, año de compra), país por prefijo del móvil, scoring estándar del dashboard y la auditoría de conversaciones. Las personas y guiones son interpretación estratégica de esa evidencia — al regenerar con datos nuevos, los números se actualizan; los textos conviene revisarlos por corte.</div>
<footer>Generado desde la API de GoHighLevel en modo solo lectura. Base: {fmt(TOTAL)} contactos, {fmt(TOT_CLI)} clientes. Corte: {CORTE}.</footer>
</div>
<script>
const D = {INS_PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc2 = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = s => s >= 55 ? '#D64545' : s >= 30 ? '#AA9664' : s >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';

function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tg[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc2(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" data-tip="Todas las etiquetas: ${{esc2(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
let LB = {{list: [], shown: 0, label: ''}};
function matchLf(r, f) {{
  if (f.startsWith('pais:')) return r[10] == f.slice(5);
  if (f.startsWith('presu:')) return r[11] == f.slice(6);
  if (f.startsWith('zona:')) return r[12] == f.slice(5);
  if (f.startsWith('hobby:')) return r[13] == f.slice(6);
  if (f === 'int') return r[14] === 1;
  if (f === 'presu-any') return D.pr[r[11]] !== '(Sin dato)';
  if (f === 'visa-si') return r[15] === 1;
  if (f === 'ano-2526') return r[16] === '2025' || r[16] === '2026';
  if (f === 'temp:hot') return r[8] >= 55;
  if (f === 'temp:warm') return r[8] >= 30 && r[8] < 55;
  if (f === 'temp:cold') return r[8] >= 10 && r[8] < 30;
  if (f === 'temp:none') return r[8] < 10;
  if (f === 'p1') return D.pa[r[10]] === 'Colombia' && D.fu[r[5]] === 'Evento';
  if (f === 'agrem') return r[17] === 1;
  if (f === 'p3') return D.pa[r[10]] === 'México';
  if (f === 'p4') return D.fu[r[5]] === 'Paid Search';
  if (f === 'p5') return D.pa[r[10]] === 'EE.UU. / Canadá';
  if (f === 'p6') return D.sts[r[6]] === 'Cliente';
  return false;
}}
const LF_NOM = {{'int': 'Declararon intención de invertir', 'presu-any': 'Con presupuesto declarado',
  'visa-si': 'Con visa vigente', 'ano-2526': 'Compra declarada 2025-2026',
  'temp:hot': '🔥 Calientes', 'temp:warm': '🌤 Tibios', 'temp:cold': '❄ Fríos', 'temp:none': 'Sin señales',
  'p1': 'Perfil: Socio de Club colombiano (Colombia × Evento)', 'agrem': 'Perfil: Profesional de agremiación',
  'p3': 'Perfil: México', 'p4': 'Perfil: Buscador Digital (Google)', 'p5': 'Perfil: EE.UU./Canadá', 'p6': 'Perfil: Clientes'}};
function lfLabel(f) {{
  if (LF_NOM[f]) return LF_NOM[f];
  if (f.startsWith('tema:')) return 'Conversaciones: ' + D.temaNom[+f.slice(5)];
  if (f.startsWith('pais:')) return D.pa[+f.slice(5)];
  if (f.startsWith('presu:')) return 'Presupuesto ' + D.pr[+f.slice(6)];
  if (f.startsWith('zona:')) return 'Zona ' + D.zo[+f.slice(5)];
  if (f.startsWith('hobby:')) return 'Hobbie ' + D.ho[+f.slice(6)];
  return f;
}}
function verLeads(f) {{
  let idxs;
  if (f.startsWith('tema:')) idxs = D.tema[f.slice(5)] || [];
  else idxs = D.rows.map((r, i) => matchLf(r, f) ? i : -1).filter(i => i >= 0);
  idxs = idxs.slice().sort((a, b) => D.rows[b][8] - D.rows[a][8]);
  LB = {{list: idxs, shown: 0, label: lfLabel(f)}};
  masLeads();
  document.getElementById('verleads').scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}
function masLeads() {{
  LB.shown = Math.min(LB.list.length, LB.shown + 100);
  const filas = LB.list.slice(0, LB.shown).map(i => {{
    const r = D.rows[i];
    const em = r[1] ? `<a href="mailto:${{esc2(r[1])}}">${{esc2(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc2(r[2])}}">${{esc2(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank"><b>WA</b></a>' : ''}}` : '—';
    return `<tr><td><span class="tag" style="background:${{scCol(r[8])}}">${{r[8]}}</span></td>
    <td><b>${{esc2(r[0])}}</b></td><td>${{esc2(D.ase[r[3]])}}</td><td>${{esc2(D.rl[r[4]])}}</td>
    <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
    <td>${{esc2(D.fu[r[5]])}}</td><td>${{esc2(D.sts[r[6]])}}</td><td>${{esc2(D.cu[r[7]])}}</td>
    <td>${{esc2(D.pa[r[10]])}}</td><td>${{esc2(r[9] || '—')}}</td><td style="white-space:nowrap" data-tip="${{intTip(r[19])}}">${{intCell(r[19])}}</td><td data-tip="${{intTip(r[19])}}">${{canCell(r[19])}}</td><td>${{tagsCell(r[18])}}</td></tr>`;
  }}).join('');
  document.getElementById('leadbox').innerHTML = `
  <div style="display:flex;gap:8px;align-items:center;margin:4px 0 6px;flex-wrap:wrap">
  <b>${{esc2(LB.label)}} · ${{fN(LB.list.length)}} leads</b>
    <span style="font-size:12px;color:var(--gris)">Ordenados por score. Mostrando ${{fN(LB.shown)}} de ${{fN(LB.list.length)}}.</span></div>
  <div class="tbox"><table><thead><tr>
  <th data-tip="Lead scoring 0-100 (misma fórmula de todo el dashboard).">Score</th><th>Lead</th>
  <th data-tip="Usuario del CRM asignado (quién lo atiende).">Asesor</th><th>Realtor</th>
  <th>Email</th><th data-tip="Teléfono con enlace de llamada y WhatsApp.">Teléfono</th>
  <th data-tip="Fuente de contacto agrupada.">Origen</th><th>Lead Status</th><th>En curso por</th>
  <th data-tip="País por prefijo del móvil.">País</th><th>Creado</th>
  <th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
  <th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
  <th>Etiquetas</th>
  </tr></thead><tbody>${{filas}}</tbody></table></div>` +
  (LB.shown < LB.list.length ? `<button class="btn2" style="margin-top:6px" onclick="masLeads()">Mostrar 100 más (${{fN(LB.list.length - LB.shown)}} restantes)</button>` : '');
}}
document.addEventListener('click', e => {{
  const t = e.target.closest('[data-lf]');
  if (t) verLeads(t.dataset.lf);
}});
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

out = str(ROOT / f'insights-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB)')
print(f'temps: {dict(temps)} | intención sí: {intencion} | presupuestos: {sum(pres_u.values())}')
