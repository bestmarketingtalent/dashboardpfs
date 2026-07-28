#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de análisis estratégico: diagnóstico por segmento (lead status × scoring ×
en curso por) con plan de acción para mover leads a caliente y a venta.
Los tamaños de segmento se calculan de los datos reales al generar; el texto
estratégico está redactado sobre esos números. Solo lectura del CRM."""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
cs = json.load(open(DATA / 'contacts.json'))
convos = json.load(open(DATA / 'convos.json'))

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
_hoy = datetime.now()
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'
def fmt(n): return f'{n:,}'.replace(',', '.')

CURSO_PTS = {'Oportunidad 1-3 meses': 35, 'Oportunidad 3-6 meses': 28, 'Oportunidad 6+ meses': 18}
STATUS_PTS = {'Negocio abierto': 25, 'En curso': 15, 'Intento de contacto': 8, 'Nuevo': 5, 'En Nutrición': 3}
def _n(v):
    try: return max(0, int(float(v)))
    except (TypeError, ValueError): return 0
def score(ct):
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

users = {u['id']: u['name'] for u in json.load(open(DATA / 'users.json'))}
wait_ids = {c['contactId'] for c in convos if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound'}
wait_dias = {}
last_conv = {}
NOW_TS = _hoy.timestamp() * 1000
for c in convos:
    if c.get('lastDate'):
        last_conv[c['contactId']] = max(last_conv.get(c['contactId'], 0), c['lastDate'])
    if c['lastType'] == 'TYPE_WHATSAPP' and c['lastDir'] == 'inbound' and c.get('lastDate'):
        wait_dias[c['contactId']] = int((NOW_TS - c['lastDate']) / 86400000)

def grupo(src):
    s = ' '.join((src or '').split()); sl = s.lower()
    if not sl or sl == '<unspecified>': return '(Sin fuente)'
    if 'google' in sl or sl.startswith('goo ') or sl == 'paid search': return 'Google / Paid Search'
    if 'personal' in sl or 'referid' in sl or 'refirio' in sl: return 'Referidos / Personal'
    if sl.startswith('prensa'): return 'Prensa'
    if sl in ('web site', 'sitio web', 'web blog', 'blog') or sl.endswith('pfsrealty.com'): return 'Sitio Web'
    return s
def d_creado(ct):
    try: return (_hoy - datetime.fromisoformat(ct['created'][:10])).days
    except Exception: return 9999

# ---------- segmentos + filas lead a lead ----------
def dict_indexer():
    d = {}
    def gi(k):
        if k not in d: d[k] = len(d)
        return d[k]
    return d, gi
DA, giA = dict_indexer(); DF, giF = dict_indexer()
DS, giS = dict_indexer(); DK, giK = dict_indexer()
DTG, giTG = dict_indexer()   # etiquetas (tags del CRM)

S = Counter()

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

LEADROWS = []          # [nombre,email,phone,aIdx,fIdx,stIdx,cuIdx,score,creado,waitDias|None,realtor]
SEGIDX = {k: [] for k in ('esperando30', 'hot', 'negocio', 'dormidos', 'nuevos90',
                          'sinAsesor', 'ecSinOport', 'nutricion', 'descSenal', 'clientes',
                          'cliRecompra', 'cliEsperando', 'cliElite', 'cliFrio', 'cliVivo')}
for ct in cs:
    sc = score(ct)
    st = (ct.get('leadStatus') or '').strip() or '(Sin status)'
    ku = (ct.get('enCursoPor') or '').strip() or '(Sin dato)'
    oport = ku.startswith('Oportunidad')
    la = ct.get('lastActivity') or ct.get('lastEngagement')
    rec = False
    if la:
        try:
            dt = datetime.fromisoformat(str(la).replace('Z', '+00:00'))
            rec = (datetime.now(dt.tzinfo) - dt).days <= 30
        except ValueError: pass
    miembro = []
    if sc >= 55: S['hot'] += 1; miembro.append('hot')
    if ct['id'] in wait_ids and sc >= 30: S['esperando30'] += 1; miembro.append('esperando30')
    if sc >= 30 and oport and not rec: S['dormidos'] += 1; miembro.append('dormidos')
    if st == 'Negocio abierto': S['negocio'] += 1; miembro.append('negocio')
    if st in ('Nuevo', 'Intento de contacto') and d_creado(ct) <= 90: S['nuevos90'] += 1; miembro.append('nuevos90')
    if st == 'En curso' and not oport: S['ecSinOport'] += 1; miembro.append('ecSinOport')
    if st == 'En curso': S['enCurso'] += 1
    if st == 'En Nutrición': S['nutricion'] += 1; miembro.append('nutricion')
    if st == 'En Nutrición' and ct.get('phone'): S['nutTel'] += 1
    if not ct.get('assigned') and st not in ('Descartado', 'Cliente'): S['sinAsesor'] += 1; miembro.append('sinAsesor')
    if st == 'Cliente': S['clientes'] += 1; miembro.append('clientes')
    if st == 'Cliente' and ct.get('realtor'): S['cliRealtor'] += 1
    if st == 'Cliente':
        _tags = [t.lower() for t in (ct.get('tags') or [])]
        _lc = last_conv.get(ct['id'])
        _ult = int((NOW_TS - _lc) / 86400000) if _lc else None
        if oport: S['cliRecompra'] += 1; miembro.append('cliRecompra')
        if ct['id'] in wait_ids: S['cliEsperando'] += 1; miembro.append('cliEsperando')
        if any('elite' in t for t in _tags): S['cliElite'] += 1; miembro.append('cliElite')
        if _ult is None or _ult > 180: S['cliFrio'] += 1; miembro.append('cliFrio')
        if _ult is not None and _ult <= 30: S['cliVivo'] += 1; miembro.append('cliVivo')
    if st == 'Descartado' and (oport or sc >= 30): S['descSenal'] += 1; miembro.append('descSenal')
    if oport: S['conOport'] += 1
    if oport and '1-3' in ku: S['oport13'] += 1
    if miembro:
        a = users.get(ct['assigned'], '(Sin asesor asignado)') if ct['assigned'] else '(Sin asesor asignado)'
        rl = ct.get('realtor') or []
        if isinstance(rl, str): rl = [rl]
        rl = ', '.join(x.strip() for x in rl if x and x.strip()) or '—'
        i = len(LEADROWS)
        LEADROWS.append([(ct.get('name') or '(sin nombre)').strip().title(),
                         ct.get('email') or '', ct.get('phone') or '',
                         giA(a), giF(grupo(ct.get('source'))), giS(st), giK(ku),
                         sc, (ct.get('created') or '')[:10], wait_dias.get(ct['id']), rl[:60],
                         [giTG(t.strip()) for t in (ct.get('tags') or [])[:8] if t and t.strip()],
                         intentos_of(ct['id'])])
        for m in miembro: SEGIDX[m].append(i)
for k in SEGIDX:
    SEGIDX[k].sort(key=lambda i: -LEADROWS[i][7])

def ordered(d): return [k for k, _ in sorted(d.items(), key=lambda x: x[1])]
PAYLOAD = json.dumps({'rows': LEADROWS, 'seg': SEGIDX, 'ase': ordered(DA), 'fu': ordered(DF),
                      'sts': ordered(DS), 'cu': ordered(DK), 'tg': ordered(DTG)}, ensure_ascii=False)
TOTAL = len(cs)

def card(pri, pcolor, emoji, titulo, tam, diag, opor, plan, meta, donde, segid=None):
    plan_html = ''.join(f'<li>{p}</li>' for p in plan)
    KITS_SEG = {'esperando30', 'hot', 'negocio', 'dormidos', 'nuevos90', 'sinAsesor',
                'ecSinOport', 'nutricion', 'descSenal', 'clientes'}
    kit = (f' <a class="verbtn" style="display:inline-block;text-decoration:none;background:#1E9E62" '
           f'href="docs/copy-{segid}.doc" download '
           f'data-tip="Descarga el kit de copy de este segmento en Word: mensajes de WhatsApp por etapa, emails y copy de landing con estructura Hormozi, basados en los insights de las conversaciones y buyer personas.">'
           f'📄 Kit de copy (Word)</a>') if segid in KITS_SEG else ''
    btn = (f'<button class="verbtn" data-seg="{segid}">📋 Ver y gestionar los {fmt(len(SEGIDX[segid]))} leads</button>{kit}'
           f'<div class="segtable" id="st-{segid}"></div>') if segid and SEGIDX.get(segid) else ''
    return f'''<div class="seg" style="border-left-color:{pcolor}">
<div class="seg-h"><span class="pri" style="background:{pcolor}">{pri}</span>
<h3>{emoji} {titulo}</h3><span class="tam">{tam}</span></div>
<p><b>📌 Diagnóstico (por qué están ahí):</b> {diag}</p>
<p><b>💰 La oportunidad:</b> {opor}</p>
<b>🎯 Plan para moverlos:</b><ol>{plan_html}</ol>
<p class="meta"><b>Meta:</b> {meta}</p>
{btn}
<p class="donde">🔎 También en el dashboard: {donde}</p>
</div>'''

CARDS = ''
CARDS += card('HOY', '#D64545', '⏳', 'Tibios y calientes esperando respuesta en WhatsApp', f'{fmt(S["esperando30"])} leads',
  'Escribieron por WhatsApp, tienen score ≥30 (intención real) y nadie les ha contestado. Están en la cola porque sus conversaciones viven en la bolsa MARKETING PFS o en asesores sin alarma de respuesta.',
  'Es la venta más barata del CRM: demanda activa ya pagada, con intención declarada, a un mensaje de distancia.',
  ['Responderlos HOY con mensaje personal (no plantilla) usando el enlace WA de la lista.',
   'Contestar lo que preguntaron (crédito, precio, renta) en el primer mensaje — la auditoría muestra que piden datos concretos.',
   'Registrar la interacción y el horizonte ("En curso por") en la misma llamada: eso solo ya los sube ~55 pts.'],
  'Cola en 0 cada día antes de las 6 p.m. (SLA < 1 hora hábil).',
  'Auditoría WhatsApp → tabla "Leads esperando respuesta" con filtro Temperatura = Tibios/Calientes.', segid='esperando30')

CARDS += card('HOY', '#D64545', '🔥', 'Los calientes: blindarlos', f'{fmt(S["hot"])} leads',
  f'Solo {fmt(S["hot"])} de {fmt(TOTAL)} leads están calientes (0,1%). No es que falte demanda: es que el score exige interacción reciente y casi nadie la registra. Los pocos calientes son oro estadístico.',
  'Cada caliente vale más que cientos de fríos: combinan oportunidad vigente + estado activo + actividad fresca. Perder uno por no dar seguimiento es la fuga más cara posible.',
  ['Cada caliente con "próxima acción" agendada en el CRM (fecha y hora, no "pendiente").',
   'Revisión diaria del gerente: los 25 caben en una pantalla.',
   'Si un caliente lleva 3 días sin toque → alerta y reasignación inmediata.'],
  '100% de calientes con actividad registrada cada 72 horas.',
  'Gestión comercial → píldora 🔥 Leads calientes (clic) — muestra asesor, etapa y en curso por.', segid='hot')

CARDS += card('HOY', '#D64545', '🤝', 'Negocios abiertos: el ritual de cierre', f'{fmt(S["negocio"])} leads',
  'Están en la puerta de la venta (Lead Status = Negocio abierto), pero algunos aparecen en la cola de espera de WhatsApp — incluido el lead más caliente de la base (score 60, Google Ads, sin asesor, 19+ días esperando).',
  f'{fmt(S["negocio"])} negociaciones activas: el revenue más próximo de todo el CRM.',
  ['Pipeline review semanal SOLO de estos: obstáculo, siguiente paso y fecha por cada uno.',
   'Asignar dueño a los que no lo tienen (hay negocios abiertos sin asesor).',
   'Involucrar financiamiento/contador proactivamente: la objeción nº1 en las conversaciones es crédito y cuota inicial.'],
  'Cada negocio abierto con próximo paso fechado; cierre o descarte justificado en máx. 60 días.',
  'Gestión comercial → píldora Negocio abierto · Asesores → KPI "negocios abiertos" (clic).', segid='negocio')

CARDS += card('SEMANA', '#AA9664', '😴', 'El pipeline dormido: la mina de oro', f'{fmt(S["dormidos"])} leads',
  f'Tienen oportunidad de compra REGISTRADA ("En curso por") y score tibio/caliente, pero sin actividad en 30+ días. Son el corazón del hallazgo central: hay {fmt(S["conOport"])} leads con intención declarada y solo {fmt(S["hot"])} calientes — la diferencia es pura falta de toque reciente. Además, solo {fmt(S["oport13"])} tienen horizonte 1-3 meses: el horizonte corto casi no se registra o se venció sin actualizar.',
  f'La palanca más grande del CRM: reactivar el 10% de estos {fmt(S["dormidos"])} genera ~{fmt(int(S["dormidos"]*0.1))} conversaciones comerciales con gente que YA dijo que quiere comprar.',
  ['Cadencia de reactivación por horizonte: 1-3 meses → llamada esta semana; 3-6 → llamada quincenal; 6+ → toque mensual con contenido + pregunta.',
   'En cada contacto, RE-preguntar y actualizar el horizonte (los 6+ meses de hace un año ya son 1-3 meses… o nada).',
   'Priorizar por score descendente y fuente eficiente (Referidos, Google) usando los filtros del home.',
   'Todo contacto queda registrado: la interacción + recencia suman hasta 40 pts del score.'],
  'Bajar los dormidos un 20% mensual (medible en esta misma hoja al regenerar).',
  'Gestión comercial → filtro En curso por = Oportunidad… + píldora 🌤 Tibios.', segid='dormidos')

CARDS += card('SEMANA', '#AA9664', '🚀', 'Nuevos que no arrancan (cosechas recientes heladas)', f'{fmt(S["nuevos90"])} leads',
  'Leads creados hace menos de 90 días que siguen en "Nuevo" o "Intento de contacto". La tabla de maduración muestra que las cohortes de 1-6 meses tienen score promedio 4-5: el lead nuevo NO se está calentando en su ventana de oro (las primeras semanas).',
  'El lead digital se decide en horas: responder rápido y calificar en la primera conversación es lo que más conversión marginal genera por peso invertido.',
  ['Guardia diaria de primera respuesta para todo lead nuevo (< 1 hora hábil).',
   'Guión de primera llamada que registre las 3 llaves del score: horizonte de compra, status real y la interacción.',
   'Los que no contestan en 3 intentos → secuencia corta de WhatsApp con pregunta concreta, no goteo genérico.'],
  'Score promedio de la cohorte 0-30 días > 15 (hoy ~8) en 60 días.',
  'Gestión comercial → Maduración por antigüedad + filtro de fechas "Creado desde".', segid='nuevos90')

CARDS += card('SEMANA', '#AA9664', '👻', 'La cartera huérfana', f'{fmt(S["sinAsesor"])} leads',
  'Leads activos (no descartados, no clientes) sin ningún asesor asignado. Es la cartera más helada de la base (score promedio ~6) porque nadie es responsable: la asignación existente fue masiva y de papel, no operativa.',
  'Entre ellos hay leads de pauta pagada esperando respuesta. Cada uno ya costó dinero adquirirlo.',
  ['Asignación por tandas pequeñas (100-200) a asesores con capacidad demostrada (ver semáforo en la hoja de Asesores), no repartos masivos.',
   'Cada tanda con SLA: primer toque en 72 horas y registro obligatorio.',
   'Crear el workflow que falta: "cliente respondió y lleva X horas sin respuesta → tarea + reasignar".'],
  '0 leads con score ≥30 sin asesor; el resto asignado en 30 días.',
  'Gestión comercial → filtro Asesor = (Sin asesor asignado) · Asesores → perfil "(Sin asesor asignado)".', segid='sinAsesor')

CARDS += card('MES', '#3A566B', '📝', 'En curso sin oportunidad registrada: puntos gratis', f'{fmt(S["ecSinOport"])} leads',
  f'Están en gestión activa ("En curso") pero el campo "En curso por" está vacío o sin oportunidad. El asesor probablemente SÍ conoce el horizonte — solo no lo registró. Nota: los otros {fmt(S["enCurso"] - S["ecSinOport"])} en curso sí lo tienen: la disciplina existe, hay que completarla.',
  'Registrar el horizonte vale hasta +35 pts de score por lead: es la forma más barata de "calentar" la vista del pipeline y priorizar bien.',
  ['Campaña interna de 2 semanas: cada asesor completa "En curso por" de sus leads en curso (la hoja de Asesores muestra cuántos le faltan a cada uno).',
   'Hacer el campo obligatorio al mover un lead a "En curso" (cambio de proceso, no de sistema).'],
  '90% de los "En curso" con horizonte registrado.',
  'Gestión comercial → filtro Lead Status = En curso + En curso por = (Sin dato).', segid='ecSinOport')

CARDS += card('MES', '#3A566B', '🧊', 'Nutrición: separar el hielo del agua', f'{fmt(S["nutricion"])} leads',
  f'La bolsa más grande del CRM (41% de la base) y casi toda sin señales: el goteo actual informa pero no pregunta, así que nadie sabe quién de los {fmt(S["nutTel"])} con teléfono sigue interesado. Cuando alguien responde al goteo, cae en la cola sin dueño (44 casos en la auditoría).',
  'Aunque solo el 3% siga interesado, son ~340 oportunidades escondidas en la bolsa.',
  ['Campaña de recalificación con UNA pregunta cerrada ("¿Sigue en sus planes invertir en Miami? 1. Sí, este año · 2. Sí, más adelante · 3. No").',
   'Los "1" pasan a asesor con tarea; los "2" a cadencia trimestral; los "3" se descartan con motivo — limpiar también es ganar.',
   'Toda respuesta al goteo debe crear tarea automática (hoy no existe ese workflow).'],
  'Nutrición segmentada al 100% en 90 días; bolsa reducida al menos 30%.',
  'Gestión comercial → píldora En Nutrición · torta libre por Lead Status.', segid='nutricion')

CARDS += card('MES', '#3A566B', '♻️', 'Descartados con señales: segunda mirada', f'{fmt(S["descSenal"])} leads',
  'Marcados como Descartado pero con oportunidad registrada o score ≥30 — contradicción que sugiere descartes apurados. Además existe el workflow "Asignar Descartados a MARKETING PFS": el descartado vuelve al goteo y sus respuestas caen al vacío.',
  'Revisar 55 leads toma una tarde; recuperar 2-3 paga el ejercicio completo.',
  ['Revisión gerencial de estos leads: ¿descarte real o falta de seguimiento?',
   'Configurar motivos de pérdida obligatorios (hoy hay 0 configurados) para que el descarte deje información.',
   'Sacar a los descartados del goteo de marketing (o crear lista de supresión).'],
  'Descarte siempre con motivo; re-aperturas documentadas.',
  'Gestión comercial → píldora Descartado + píldora 🌤 Tibios combinadas.', segid='descSenal')

CARDS_CLI = ''
CARDS_CLI += card('HOY', '#D64545', '🔁', 'Recompra declarada: la venta más fácil de la compañía', f'{fmt(S["cliRecompra"])} clientes',
  'Ya compraron Y tienen una NUEVA oportunidad registrada en "En curso por". Conocen el proceso, confían en la compañía y declararon horizonte de compra — pero están mezclados en la base general y nadie los trabaja como lo que son: la cola de ventas más caliente que existe.',
  f'{fmt(S["cliRecompra"])} recompras potenciales sin costo de adquisición: el CAC es cero y la tasa de cierre de un cliente que recompra multiplica la de un lead frío.',
  ['Llamada del realtor (no del asesor de leads) esta semana, con propuesta concreta según su horizonte declarado.',
   'Preparar la oferta antes de llamar: nuevo lanzamiento acorde a su perfil + financiamiento pre-armado.',
   'Registrar cada gestión: son los leads que deben vivir en "Negocio abierto" en 30 días.'],
  'Convertir 20% de las recompras declaradas en negocio abierto en 60 días.',
  'Hoja Clientes → chip "🔁 Recompra declarada" (para repartir por realtor).', segid='cliRecompra')

CARDS_CLI += card('HOY', '#D64545', '⏳', 'Post-venta roto: clientes esperando respuesta', f'{fmt(S["cliEsperando"])} clientes',
  'Clientes actuales que escribieron por WhatsApp y nadie les contestó (la auditoría encontró casos reclamando llamadas prometidas mientras recibían plantillas de F1). Un cliente ignorado no recompra, no refiere, y cuenta su experiencia.',
  'Responder cuesta minutos; cada uno protege recompra + referidos + reputación. Es la acción con mejor relación esfuerzo/impacto de todo el dashboard.',
  ['Responder HOY con mensaje personal del realtor asignado.',
   'Resolver el motivo real de su mensaje antes de cualquier oferta.',
   'Regla permanente: mensaje de cliente = respuesta en < 1 hora hábil, por encima de cualquier lead.'],
  'Cola de clientes en espera = 0, todos los días.',
  'Hoja Clientes → chip "⏳ Post-venta roto" · Auditoría WhatsApp → lista de espera.', segid='cliEsperando')

CARDS_CLI += card('SEMANA', '#AA9664', '👑', 'Elite Club: de 15 a cientos', f'{fmt(S["cliElite"])} activos',
  f'Solo {fmt(S["cliElite"])} de {fmt(S["clientes"])} clientes (1,5%) tienen la etiqueta de miembro Elite activo, pese a que los broadcasts Elite (F1, catas, golf, Mundial) ya existen y funcionan. El programa de fidelización está construido pero casi nadie está adentro.',
  'El Elite Club es el vehículo natural de la recompra y el referido: eventos presenciales con clientes = el canal "Eventos" que ya es la mayor fuente de captación, pero con audiencia de máxima calidad.',
  ['Campaña de enrolamiento: invitar a los ' + fmt(S['cliVivo']) + ' clientes con relación viva a activar su membresía.',
   'Beneficio de bienvenida tangible (análisis de valorización de SU propiedad — información que la compañía ya tiene).',
   'Medir recompra y referidos de miembros vs no miembros para justificar la inversión.'],
  'Llegar a 200 miembros Elite activos en un trimestre.',
  'Hoja Clientes → chip "👑 Elite activos" y filtro Elite = No para la campaña.', segid='cliElite')

CARDS_CLI += card('MES', '#3A566B', '🧊', 'Clientes sin contacto 180+ días: reactivación con motivo', f'{fmt(S["cliFrio"])} clientes',
  'Clientes sin ninguna conversación registrada en 6+ meses (o nunca). No es una base grande — la mayoría tiene relación viva por los broadcasts — pero son exactamente los que se pierden en silencio.',
  'Reactivar un cliente frío cuesta una llamada con motivo real; perderlo cuesta la recompra Y sus referidos.',
  ['Llamada de "estado de su inversión": valorización de su propiedad, mercado de su zona, opciones de renta.',
   'Aprovechar los ganchos que ya existen: aniversario de compra y cumpleaños (la etiqueta happy birthday ya se usa).',
   'Si no responde a 2 intentos, mantener en broadcasts y reintentar en 90 días.'],
  'Contacto real con el 100% de estos clientes en 60 días.',
  'Hoja Clientes → chip "🧊 Sin contacto 180+ días".', segid='cliFrio')

CARDS_CLI += card('TRIMESTRE', '#1E9E62', '💎', 'Clientes: la fábrica de referidos', f'{fmt(S["clientes"])} clientes',
  f'{fmt(S["clientes"])} clientes ({fmt(S["cliRealtor"])} con realtor asignado) reciben hoy broadcasts de eventos Elite, pero no existe un programa sistemático de referidos — y la evidencia dice que Referidos/Personal es de las fuentes que mejor madura (score 26,9, el doble del promedio) y Kendall/PG Personal las más eficientes en calificados.',
  'El canal de mayor conversión de la compañía está sub-explotado: cada cliente satisfecho es una fuente "Referidos" nueva y gratuita.',
  ['Programa de referidos con incentivo claro, pedido por el realtor del cliente (933 ya lo tienen) en el momento de mayor satisfacción (post-cierre, post-renta).',
   'Post-venta con seguimiento real: la auditoría encontró clientes reclamando llamadas prometidas — cada queja de cliente es un referido perdido.',
   'Medir: etiqueta "referido de cliente" en cada lead nuevo que llegue por esta vía.'],
  'Que Referidos/Personal crezca del 12% al 20% de la captación en 2 trimestres.',
  'Asesores → perfiles de realtors · Home → filtro Fuente = Referidos / Personal.', segid='clientes')

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estrategia y plan de acción</title>
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
.navgrp{{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}}
.navbtn{{background:#ffffff1a;border:1.5px solid #C9D6E455;color:#F2F6FA;text-decoration:none;font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:9px;white-space:nowrap}}
.navbtn:hover{{background:#ffffff2e}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
h2{{font-size:17px;margin:28px 0 10px;border-bottom:2px solid var(--gris-linea);padding-bottom:6px}}
.hero{{background:var(--azul-oscuro);color:#F2F6FA;border-radius:14px;padding:20px 24px;margin:18px 0;font-size:15.5px;line-height:1.6}}
.hero b{{color:var(--amarillo)}}
.ruta{{display:flex;gap:0;border-radius:12px;overflow:hidden;margin:10px 0 4px;min-height:64px}}
.ruta div{{color:#fff;padding:10px 12px;font-size:12px;line-height:1.35}}
.ruta b{{display:block;font-size:16px}}
.seg{{border:1px solid var(--gris-linea);border-left:5px solid;border-radius:12px;padding:16px 18px;margin:14px 0}}
.seg-h{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}}
.seg h3{{font-size:15.5px}}
.pri{{color:#fff;font-size:10.5px;font-weight:900;letter-spacing:.5px;padding:3px 10px;border-radius:20px}}
.tam{{margin-left:auto;font-weight:900;font-size:17px;color:var(--azul-oscuro)}}
.seg p{{margin:6px 0}} .seg ol{{margin:4px 0 6px 22px}} .seg li{{margin:4px 0}}
.meta{{color:#1E6E46;font-size:13px}}
.donde{{color:var(--gris);font-size:12.5px;border-top:1px dashed var(--gris-linea);padding-top:7px;margin-top:9px}}
.verbtn{{border:0;background:var(--azul-oscuro);color:#fff;border-radius:8px;padding:9px 15px;font-size:12.5px;font-weight:700;cursor:pointer;margin:6px 0 2px}}
.verbtn:hover{{background:#123c5c}}
.btn2{{border:0;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:8px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer}}
.segtable{{margin-top:8px}}
.segtable table{{border-collapse:collapse;width:100%;font-size:12.6px;margin:0}}
.segtable th{{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.4px;color:var(--gris);border-bottom:2px solid var(--gris-linea);padding:6px 7px;white-space:nowrap;position:sticky;top:0;background:#fff}}
.segtable td{{border-bottom:1px solid var(--gris-linea);padding:5px 7px;vertical-align:top}}
.segtable tr:hover td{{background:var(--gris-fondo)}}
.tbox{{border:1px solid var(--gris-linea);border-radius:11px;overflow:auto;max-height:56vh}}
.tag{{display:inline-block;min-width:30px;text-align:center;padding:2px 7px;border-radius:20px;font-weight:800;font-size:11px;color:#fff}}
.tagchip{{display:inline-block;background:var(--azul-suave);color:var(--azul-oscuro);border-radius:10px;padding:1px 8px;font-size:10.5px;font-weight:600;margin:1px 2px 1px 0;white-space:nowrap}}
a{{color:var(--azul)}}
th[data-tip]{{text-decoration:underline dotted;text-underline-offset:3px;text-decoration-color:#9FB0C4;cursor:help}}
#vtip{{position:fixed;display:none;background:var(--azul-oscuro);color:#F2F6FA;padding:10px 12px;border-radius:9px;font-size:11.8px;font-weight:500;line-height:1.45;max-width:310px;z-index:99;box-shadow:0 6px 18px rgba(7,32,49,.28);pointer-events:none}}
.warnpii{{background:#FBEAEA;border:1px solid #EFC7C7;color:#7A2E2E;border-radius:10px;padding:11px 15px;font-size:12px;margin-top:26px}}
.caveat{{background:var(--gris-fondo);border:1px solid var(--gris-linea);border-radius:11px;padding:12px 16px;font-size:12.5px;margin:14px 0;color:#3d4c63}}
footer{{color:var(--gris);font-size:11.5px;margin-top:18px;border-top:1px solid var(--gris-linea);padding-top:12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:14px 0}}
.kpi{{border:1px solid var(--gris-linea);border-radius:11px;padding:11px 13px}}
.kpi b{{font-size:21px;display:block}} .kpi span{{font-size:11px;color:var(--gris)}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Estrategia: dónde está la oportunidad y cómo aprovecharla</h1>
<p>[empresa] Group · Análisis sobre el CRM (solo lectura) · Corte: {CORTE}</p></div>
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

<div class="hero">💡 <b>El diagnóstico en una frase:</b> La compañía no tiene un problema de demanda — tiene <b>{fmt(S['conOport'])} leads con intención de compra declarada</b> ("En curso por" con oportunidad vigente) y solo <b>{fmt(S['hot'])} están calientes</b>. La diferencia no es interés del cliente: es <b>ausencia de toque reciente y de registro</b>. El score lo demuestra: sus 4 componentes (horizonte, estado, interacciones, recencia) son exactamente las 4 disciplinas de gestión que hoy no se están ejecutando. <b>La oportunidad no está en comprar más leads: está en trabajar los que ya pagaron.</b></div>

<div class="seg" style="border-left-color:#1E9E62">
<div class="seg-h"><span class="pri" style="background:#1E9E62">KIT</span>
<h3>📄 Kits de copy descargables (Word) — por scoring y por segmento</h3></div>
<p>Cada documento trae: <b>mensajes de WhatsApp por etapa</b> (apertura → seguimiento → valor → cierre de ciclo), <b>emails</b> con asunto y cuerpo, y <b>copy de landing</b> con estructura Alex Hormozi (ecuación de valor, stack de oferta, reversión de riesgo y urgencia honesta) — todo construido con los insights reales del CRM: lo que los clientes desean según las 4.888 conversaciones (renta en dólares, zonas, crédito sin residencia, eventos y citas) y los buyer personas. Los kits por segmento están también dentro de cada tarjeta de abajo.</p>
<p><b>Por temperatura de scoring:</b>
<a class="verbtn" style="display:inline-block;text-decoration:none;background:#D64545;margin-right:6px" href="docs/copy-scoring-caliente.doc" download>🔥 Calientes (≥55)</a>
<a class="verbtn" style="display:inline-block;text-decoration:none;background:#AA9664;margin-right:6px" href="docs/copy-scoring-tibio.doc" download>🌤 Tibios (30-54)</a>
<a class="verbtn" style="display:inline-block;text-decoration:none;background:#3A566B;margin-right:6px" href="docs/copy-scoring-frio.doc" download>❄ Fríos (10-29)</a>
<a class="verbtn" style="display:inline-block;text-decoration:none;background:#8A99A8" href="docs/copy-scoring-sinsenales.doc" download>Sin señales (&lt;10)</a></p>
</div>

<h2>La ruta a caliente: el score es un checklist de gestión</h2>
<p>Para mover CUALQUIER lead a caliente (score ≥55) hay que sumar puntos — y cada punto es una acción concreta del asesor. Esta es la palanca:</p>
<div class="ruta">
<div style="background:#2C4356;width:35%" data-s><b>+35</b>① Preguntar y registrar el horizonte de compra ("En curso por": 1-3, 3-6, 6+ meses)</div>
<div style="background:#3A566B;width:25%"><b>+25</b>② Avanzar el Lead Status con gestión real (En curso → Negocio abierto)</div>
<div style="background:#AA9664;width:20%"><b>+20</b>③ Registrar cada interacción (llamadas y actividades de venta)</div>
<div style="background:#C4B284;width:20%;color:#152238"><b>+20</b>④ Que el último toque sea RECIENTE (≤7 días = máximo puntaje)</div>
</div>
<p style="font-size:13px;color:var(--gris)">Ejemplo real: un lead "En Nutrición" (3 pts) al que hoy se le llama, se le registra la llamada y declara horizonte 3-6 meses pasa de ~3 a <b>66 puntos — caliente — en una sola gestión bien registrada</b>. Por eso casi no hay calientes: no faltan compradores, falta esta secuencia.</p>

<div class="kpis">
<div class="kpi"><b style="color:var(--rojo)">{fmt(S['esperando30'])}</b><span>tibios/calientes esperando respuesta HOY</span></div>
<div class="kpi"><b>{fmt(S['conOport'])}</b><span>con oportunidad de compra declarada</span></div>
<div class="kpi"><b style="color:#8A6D1A">{fmt(S['dormidos'])}</b><span>pipeline dormido (oportunidad sin toque 30+ días)</span></div>
<div class="kpi"><b>{fmt(S['negocio'])}</b><span>negocios abiertos</span></div>
<div class="kpi"><b style="color:var(--gris)">{fmt(S['sinAsesor'])}</b><span>cartera activa sin asesor</span></div>
<div class="kpi"><b style="color:var(--verde)">{fmt(S['clientes'])}</b><span>clientes para referidos</span></div>
</div>

<h2>PARTE 1 · Estrategia de LEADS: el playbook por segmento (en orden de prioridad)</h2>
<p style="font-size:13px;color:var(--gris)">Cada tarjeta: cuántos son, por qué están ahí (diagnóstico con evidencia de las otras hojas), qué vale la oportunidad, el plan concreto para moverlos a caliente o a venta, la meta medible y dónde ver la lista de leads.</p>
{CARDS}

<h2>PARTE 2 · Estrategia de CLIENTES: venta cruzada, fidelización y referidos</h2>
<div class="hero" style="font-size:14px">💎 <b>El segundo negocio está adentro de la casa:</b> {fmt(S['clientes'])} clientes con costo de adquisición cero. <b>{fmt(S['cliRecompra'])} ya declararon una nueva compra</b> (recompra registrada en el CRM), {fmt(S['cliEsperando'])} están esperando una respuesta que no llega, solo <b>{fmt(S['cliElite'])} son miembros Elite activos</b> de un programa que ya existe, y {fmt(S['cliVivo'])} tienen la relación viva (contacto ≤30 días) — el momento perfecto para pedir referidos, justo cuando Referidos/Personal es la fuente que mejor madura de toda la base. <b>Cada punto de recompra y referido vale más que cualquier campaña de pauta.</b> Detalle completo y segmentaciones en la <a href="clientes.html" style="color:var(--amarillo)">hoja de Clientes</a>.</div>
{CARDS_CLI}

<h2>Plan de choque: los primeros 30 días</h2>
<div class="seg" style="border-left-color:var(--azul-oscuro)">
<ol>
<li><b>Semana 1 — Parar la fuga:</b> cola de WhatsApp en cero (los {fmt(S['esperando30'])} tibios/calientes primero), blindar los {fmt(S['hot'])} calientes y los {fmt(S['negocio'])} negocios abiertos con próximo paso fechado.</li>
<li><b>Semana 2 — Registrar lo que ya se sabe:</b> campaña interna de "En curso por" ({fmt(S['ecSinOport'])} en curso sin horizonte) + asignar la primera tanda de la cartera huérfana con SLA.</li>
<li><b>Semana 3 — Despertar al dormido:</b> arrancar la cadencia de reactivación de los {fmt(S['dormidos'])} con oportunidad declarada, empezando por 1-3 meses y fuentes eficientes.</li>
<li><b>Semana 4 — Sistematizar:</b> workflow "respuesta sin atender → tarea", motivos de pérdida obligatorios, lista de supresión para quejas, y lanzar la recalificación de Nutrición.</li>
</ol>
<p class="meta"><b>Cómo medir el éxito:</b> regenerar este dashboard cada lunes — deben subir calientes y tibios, bajar la cola de espera y el pipeline dormido, y crecer la cohorte reciente en la tabla de maduración.</p></div>

<div class="caveat"><b>Nota metodológica.</b> Los tamaños de segmento se calculan de los datos reales del CRM al corte {CORTE} (mismas fórmulas de score y agrupaciones del resto del dashboard). El texto estratégico se apoya en la evidencia de las otras tres hojas: auditoría de conversaciones (229 en espera, plantillas, objeciones), maduración por cohortes, eficiencia por fuente y desempeño por asesor. Al regenerar con datos nuevos, los números se actualizan; el texto conviene revisarlo cada corte.</div>

<div class="warnpii"><b>⚠ Uso interno:</b> este análisis contiene información comercial estratégica de [empresa] y, en las tablas de gestión, datos de contacto de clientes (Habeas Data). No circular fuera del equipo directivo y comercial autorizado.</div>
<script>
const D = {PAYLOAD};
const fN = n => n.toLocaleString('es-CO');
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const scCol = s => s >= 55 ? '#D64545' : s >= 30 ? '#AA9664' : s >= 10 ? '#3A566B' : '#8A99A8';
const intCell = it => it ? `<b>${{it[0]}}</b> · ${{it[1]}}d` : '—';
const canCell = it => it ? (((it[2] ? '💬' : '') + (it[3] ? '📞' : '') + (it[4] ? '✉' : '') + (it[5] ? '𝗌' : '')) || '—') : '—';
const intTip = it => it ? `${{it[0]}} intento(s) de contacto saliente(s) en ${{it[1]}} día(s) distinto(s): ` + [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamada(s)' : '', it[4] ? it[4] + ' email(s)' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' · ') + '. Varios intentos con 1 día = ráfaga única sin seguimiento.' : 'Sin intentos salientes en las conversaciones descargadas.';
const canTxt = it => it ? [it[2] ? it[2] + ' WhatsApp' : '', it[3] ? it[3] + ' llamadas' : '', it[4] ? it[4] + ' emails' : '', it[5] ? it[5] + ' SMS' : ''].filter(Boolean).join(' | ') : '';

function tagsCell(idxs) {{
  if (!idxs || !idxs.length) return '—';
  const nm = idxs.map(i => D.tg[i]);
  let out = nm.slice(0, 2).map(t => `<span class="tagchip">${{esc(t)}}</span>`).join('');
  if (nm.length > 2) out += `<span class="tagchip" style="cursor:help" data-tip="Todas las etiquetas del lead en el CRM: ${{esc(nm.join(' · '))}}">+${{nm.length - 2}}</span>`;
  return out;
}}
const ST = {{}};   // estado por segmento: cuántos mostrados
function renderSeg(seg) {{
  const box = document.getElementById('st-' + seg);
  const idxs = D.seg[seg];
  ST[seg] = Math.min(idxs.length, (ST[seg] || 0) + 100);
  const filas = idxs.slice(0, ST[seg]).map(i => {{
    const r = D.rows[i];
    const em = r[1] ? `<a href="mailto:${{esc(r[1])}}">${{esc(r[1])}}</a>` : '—';
    const dig = r[2].replace(/[^0-9]/g, '');
    const ph = r[2] ? `<a href="tel:${{esc(r[2])}}">${{esc(r[2])}}</a>${{dig ? ' · <a href="https://wa.me/' + dig + '" target="_blank"><b>WA</b></a>' : ''}}` : '—';
    return `<tr><td><span class="tag" style="background:${{scCol(r[7])}}">${{r[7]}}</span></td>
    <td><b>${{esc(r[0])}}</b></td><td>${{esc(D.ase[r[3]])}}</td><td>${{esc(r[10])}}</td>
    <td>${{em}}</td><td style="white-space:nowrap">${{ph}}</td>
    <td>${{esc(D.fu[r[4]])}}</td><td>${{esc(D.sts[r[5]])}}</td><td>${{esc(D.cu[r[6]])}}</td>
    <td>${{r[9] === null || r[9] === undefined ? '—' : fN(r[9])}}</td><td style="white-space:nowrap" data-tip="${{intTip(r[12])}}">${{intCell(r[12])}}</td><td data-tip="${{intTip(r[12])}}">${{canCell(r[12])}}</td><td>${{tagsCell(r[11])}}</td></tr>`;
  }}).join('');
  box.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin:4px 0 6px;flex-wrap:wrap">
    <button class="btn2" onclick="cerrarSeg('${{seg}}')">✕ Cerrar</button>
    <span style="font-size:12px;color:var(--gris)">Ordenados por score (los más calientes primero). Mostrando ${{fN(ST[seg])}} de ${{fN(idxs.length)}}.</span></div>
  <div class="tbox"><table><thead><tr>
  <th data-tip="Lead scoring 0-100 (misma fórmula de todo el dashboard).">Score</th>
  <th data-tip="Nombre del contacto en el CRM.">Lead</th>
  <th data-tip="Quién lo atiende: usuario del CRM asignado (assignedTo).">Asesor</th>
  <th data-tip="Realtor vinculado al contacto.">Realtor</th>
  <th>Email</th><th data-tip="Teléfono con enlace de llamada y de WhatsApp para gestionarlo de inmediato.">Teléfono</th>
  <th data-tip="Origen del lead (Fuente de contacto, con agrupaciones).">Origen</th>
  <th>Lead Status</th><th>En curso por</th>
  <th data-tip="Días que lleva esperando respuesta en WhatsApp (solo si tiene conversación en cola).">Días ⏳</th>
  <th data-tip="Intentos de contacto SALIENTES a este lead: total · en cuántos días distintos. Varios intentos con 1d = ráfaga de un solo día sin seguimiento. Cobertura: todos los canales para carteras de asesores humanos; para el resto, solo WhatsApp.">Intentos</th>
  <th data-tip="Medios usados para (re)contactar a este lead: 💬 WhatsApp · 📞 llamada · ✉ email · 𝗌 SMS. Pasa el mouse sobre la celda para el detalle por canal.">Canales</th>
  <th data-tip="Etiquetas (tags) del lead tal como están en el CRM — campañas, eventos, listas e importaciones. El chip +N muestra el resto al pasar el mouse.">Etiquetas</th>
  </tr></thead><tbody>${{filas}}</tbody></table></div>` +
  (ST[seg] < idxs.length ? `<button class="btn2" style="margin-top:6px" onclick="renderSeg('${{seg}}')">Mostrar 100 más (${{fN(idxs.length - ST[seg])}} restantes)</button>` : '');
}}
function cerrarSeg(seg) {{ ST[seg] = 0; document.getElementById('st-' + seg).innerHTML = ''; }}

/* ---------- generador XLSX nativo (sin librerias): zip STORE + SpreadsheetML ---------- */
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

function csvSeg(seg) {{
  const rows = [['Score','Lead','Asesor','Realtor','Email','Telefono','Origen','Lead Status','En curso por','Dias esperando WA','Intentos','Dias de intento','Canales','Etiquetas']];
  D.seg[seg].forEach(i => {{
    const r = D.rows[i];
    rows.push([r[7], r[0], D.ase[r[3]], r[10], r[1], r[2], D.fu[r[4]], D.sts[r[5]], D.cu[r[6]], r[9] ?? '',
               r[12] ? r[12][0] : 0, r[12] ? r[12][1] : 0, canTxt(r[12]),
               (r[11] || []).map(x => D.tg[x]).join(' | ')]);
  }});
  XL('segmento-' + seg + '.xlsx', rows);
}}document.querySelectorAll('.verbtn').forEach(b => b.addEventListener('click', () => {{
  const seg = b.dataset.seg;
  if (ST[seg]) {{ cerrarSeg(seg); return; }}
  renderSeg(seg);
}}));
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
<footer>Generado desde la API de GoHighLevel en modo solo lectura. Segmentos: esperando = conversación WA con última palabra del cliente y score ≥30 · dormidos = score ≥30 con "En curso por" vigente y sin actividad en 30+ días · nuevos = creados ≤90 días en Nuevo/Intento · huérfanos = sin assignedTo excluyendo Descartado/Cliente · descartados con señal = Descartado con oportunidad o score ≥30. Corte: {CORTE}.</footer>
</div></body></html>'''

out = str(ROOT / f'estrategia-pfs-{_hoy:%Y-%m-%d}.html')
open(out, 'w', encoding='utf-8').write(HTML)
print('OK ->', out, f'({len(HTML)/1e3:.0f} KB)')
print('segmentos:', dict(S))
