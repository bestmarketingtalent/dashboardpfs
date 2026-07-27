#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera los KITS DE COPY descargables en Word (.doc, formato Word-HTML) para el
Plan de acción por segmentos: un documento por cada segmento del plan y por cada
nivel de scoring, con mensajes de WhatsApp por etapa, emails y copy de landing.
Marco: Alex Hormozi ($100M Offers — ecuación de valor, stack de oferta, reversión
de riesgo, urgencia honesta) combinado con los insights reales del CRM: qué desean
los clientes según 4.888 conversaciones analizadas (renta en dólares, protección
patrimonial, zonas, crédito sin residencia, eventos y citas como ganchos) y los
buyer personas (colombianos 60%, profesionales/empresarios/médicos, USD 150-250k,
horizonte 1-6 meses). Salida: netlify-pfs/docs/copy-*.doc"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'netlify-pfs' / 'docs'
OUT.mkdir(parents=True, exist_ok=True)

# ---------- bloques compartidos (insights + Hormozi) ----------
OFERTA = """<p><b>El stack de valor</b> (preséntalo completo, no solo "la propiedad"):</p>
<ul>
<li>�躍 Propiedad seleccionada en la zona con mejor relación renta/valorización para su presupuesto (Brickell, Downtown, Hollywood, Kendall).</li>
<li>💵 <b>Renta administrada en dólares</b>: La compañía administra el arriendo — el cliente recibe renta sin gestionar inquilinos (el deseo #1 en nuestras conversaciones).</li>
<li>🏦 <b>Financiamiento para extranjeros sin residencia ni visa</b> — la objeción que más leads creen insalvable, y no lo es.</li>
<li>⚖️ Acompañamiento legal, contable y de estructuración (LLC, impuestos) incluido.</li>
<li>✈️ Tour presencial o virtual por los proyectos antes de decidir.</li>
</ul>"""

RIESGO = """<p><b>Reversión de riesgo (dilo explícito):</b> "El análisis de tu caso no cuesta nada y no te compromete a nada.
Te entregamos por escrito la proyección de renta y costos con datos reales del mercado — y si tu caso no encaja
todavía, te lo decimos de frente y te dejamos el plan para cuando sí."</p>"""

HORMOZI = """<p><b>Ecuación de valor aplicada:</b> sube el <i>resultado soñado</i> (patrimonio en dólares que se paga solo con la renta),
sube la <i>certeza</i> (casos reales, cifras por escrito, 20 años de trayectoria de la compañía), baja el <i>tiempo</i> (propiedades listas para rentar,
cita esta semana) y baja el <i>esfuerzo</i> (La compañía administra todo: crédito, cierre, inquilinos). Nunca vendas "una propiedad":
vende el resultado con la fricción eliminada.</p>"""

FIRMA_INS = """<p style='color:#5B6B85;font-size:10pt'><i>Basado en datos del CRM: 4.888 conversaciones analizadas
(los clientes preguntan sobre todo por eventos, citas, información concreta, zonas y renta; las objeciones reales son
"ahora no" y precio — solo 8%), buyer personas (Colombia ~60%, México, Perú, Ecuador; profesionales, empresarios y
médicos agremiados; presupuesto típico USD 150.000–250.000; horizonte declarado 1–6 meses) y biblioteca del blog corporativo para nutrición.</i></p>"""

def wa(etapa, cuando, msg):
    return (f"<h3>💬 {etapa} <span style='color:#5B6B85;font-weight:normal;font-size:10pt'>({cuando})</span></h3>"
            f"<p class='msg'>{msg}</p>")

def email(n, asunto, cuerpo):
    return (f"<h3>✉️ Email {n} — Asunto: <i>{asunto}</i></h3><p class='msg'>{cuerpo}</p>")

def landing(head, sub, bullets, cta, urg):
    b = ''.join(f'<li>{x}</li>' for x in bullets)
    return f"""<h2>3 · Copy de landing (estructura Hormozi)</h2>
<p><b>Headline:</b></p><p class='head'>{head}</p>
<p><b>Subheadline:</b></p><p class='msg'>{sub}</p>
<p><b>Bullets de valor (resultado, no característica):</b></p><ul>{b}</ul>
{OFERTA}{RIESGO}
<p><b>CTA:</b> <span class='head' style='font-size:12pt'>{cta}</span></p>
<p><b>Urgencia honesta:</b> {urg}</p>"""

def doc(fname, titulo, quien, regla, wa_html, emails_html, landing_html):
    html = f"""<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word'>
<head><meta charset='utf-8'><title>{titulo}</title>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->
<style>
body{{font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#152238;margin:2cm}}
h1{{color:#072031;font-size:17pt;border-bottom:3px solid #C4B284;padding-bottom:6px}}
h2{{color:#2C4356;font-size:13pt;margin-top:18pt;border-bottom:1px solid #E4E9F2}}
h3{{color:#2C4356;font-size:11.5pt;margin-bottom:2pt}}
.msg{{background:#F7F9FC;border-left:4px solid #C4B284;padding:8pt 12pt;font-style:italic}}
.head{{font-size:14pt;font-weight:bold;color:#072031}}
.regla{{background:#072031;color:#F2F6FA;padding:10pt 14pt}}
li{{margin-bottom:4pt}}
</style></head><body>
<h1>Kit de copy — {titulo}</h1>
<p><b>Para quién:</b> {quien}</p>
<p class='regla'><b>Regla de oro del segmento:</b> {regla}</p>
<h2>1 · Mensajes de WhatsApp por etapa</h2>
<p style='color:#5B6B85;font-size:10pt'>Personaliza SIEMPRE [nombre], [zona] y el dato que declaró el lead. Enviar en días y horarios distintos; nunca dos plantillas seguidas.</p>
{wa_html}
<h2>2 · Emails</h2>
{emails_html}
{landing_html}
<h2>4 · Nota de método (Hormozi)</h2>
{HORMOZI}
{FIRMA_INS}
</body></html>"""
    (OUT / fname).write_text(html, encoding='utf-8')
    return fname

KITS = []

# ================= POR SCORING =================
KITS.append(doc('copy-scoring-caliente.doc', 'Scoring CALIENTE (score ≥ 55)',
 'Leads con oportunidad vigente + estado activo + interacción reciente: los más cercanos a la venta.',
 'A un caliente no se le nutre — se le agenda. Cada día sin cita enfría 3 puntos de score.',
 wa('Apertura', 'hoy mismo', '"[Nombre], soy [asesor] de [empresa]. Veo que tu plan de invertir en [zona] está para los próximos [X meses]. Tengo 2 opciones que rentan en dólares desde el día 1 dentro de tu presupuesto — ¿te las muestro hoy en una llamada de 15 minutos, o prefieres mañana a primera hora?"') +
 wa('Seguimiento', '+48 h sin respuesta', '"[Nombre], te separé el análisis de renta de las 2 opciones de [zona] (lo tengo en PDF con números reales). Se lo estoy mostrando a otros 3 inversionistas esta semana — dime cuándo te llamo y es tuyo primero."') +
 wa('Valor', 'día 5', '"Dato para tu decisión: los inquilinos en [zona] están pagando USD [X]/mes por unidades como la que te propongo — la renta cubre la cuota del crédito. Si quieres te muestro el caso de un cliente colombiano que cerró igual que tú lo harías. ¿Llamada mañana?"') +
 wa('Cierre de ciclo', 'día 10', '"[Nombre], no quiero perseguirte 🙂. Si el momento es AHORA, te agendo con prioridad esta semana. Si prefieres esperar, dime cuándo te busco y te dejo mientras tanto la proyección por escrito. ¿Cuál de las dos?"'),
 email(1, 'Tu inversión en [zona]: los números que pediste',
 '"[Nombre], adjunto la proyección de renta y costos de las opciones que encajan con tu presupuesto de USD [rango]. La lectura corta: renta estimada USD [X]/mes, la cuota del financiamiento queda cubierta y el capital queda en dólares. Respondo tus 3 dudas más probables (crédito sin residencia, impuestos y administración) en una llamada de 15 minutos: [enlace de agenda]."') +
 email(2, '¿Lo dejamos para cuando suban los precios?',
 '"[Nombre], sin presión — solo contexto: el inventario que encaja con tu horizonte de [X meses] se mueve rápido y las tasas de financiamiento cambian. Decidir con números en la mano no te compromete; decidir tarde sí te cuesta. Mi agenda de esta semana: [enlace]."'),
 landing('Tu patrimonio en dólares, rentando desde el primer mes — sin vivir en EE.UU.',
 'Inversionistas latinoamericanos están comprando propiedad en Miami con crédito para extranjeros y renta administrada. Tú decides con los números por escrito; nosotros hacemos todo lo demás.',
 ['Renta en dólares que cubre la cuota del crédito (proyección por escrito antes de comprar).',
  'Financiamiento para extranjeros SIN residencia ni visa — aprobación con tus ingresos actuales.',
  'Propiedad lista para rentar: la administradora consigue y administra el inquilino por ti.',
  'Estructura legal y contable incluida (LLC e impuestos): cero sorpresas.'],
 'Agenda tu llamada de 15 minutos → recibe la proyección de TU caso',
 'Agenda de asesoría de esta semana limitada por asesor — los números de tu caso se entregan en 48 h.')))

KITS.append(doc('copy-scoring-tibio.doc', 'Scoring TIBIO (score 30-54)',
 'Leads con UNA señal fuerte (oportunidad declarada o interacción reciente) a los que les falta la otra. Primeros candidatos a volverse calientes.',
 'Al tibio le falta UNA pieza: o registrar su horizonte de compra o una conversación reciente. El objetivo de cada toque es conseguir esa pieza, no vender el apartamento entero.',
 wa('Reapertura', 'día 1', '"[Nombre], soy [asesor] de [empresa]. La última vez hablamos de invertir en Miami y quedó en el aire una pregunta clave: ¿tu plan es más para los próximos 6 meses o para el otro año? Con eso te preparo exactamente lo que te sirve (y no te lleno el WhatsApp de cosas que no)."') +
 wa('Valor', 'día 3', '"Te comparto lo que más están preguntando inversionistas como tú: cómo funciona el crédito sin residencia. Respuesta corta: sí se puede, con tus ingresos de [país], desde ~30% de cuota inicial. ¿Te armo los números de tu caso?"') +
 wa('Gancho de evento', 'día 7', '"[Nombre], esta semana tenemos [evento/webinar] donde mostramos los proyectos y resolvemos crédito e impuestos en vivo (es lo que más cupo llena — sin costo). ¿Te reservo lugar?"') +
 wa('Cierre de ciclo', 'día 14', '"Última de mi parte 🙂 ¿Retomamos tu plan de inversión o prefieres que te busque en [mes]? Cualquiera de las dos me sirve — lo que no quiero es dejarte en visto."'),
 email(1, 'La pregunta que define tu inversión en Miami',
 '"[Nombre]: ¿tu meta es renta mensual en dólares o valorización a 3-5 años? De esa respuesta depende la zona, el tipo de unidad y el crédito que te conviene. Respóndeme este correo con una palabra (renta / valorización / ambas) y te devuelvo 2 opciones con números. Sin compromiso — es el análisis que hacemos gratis."') +
 email(2, 'Cómo compró Mauricio sin visa (caso real)',
 '"Cliente colombiano, profesional, presupuesto USD 180.000: crédito para extranjeros aprobado con extractos de su empresa, unidad en Hollywood rentada al mes 1, la renta paga la cuota. No es magia — es el proceso estándar de la compañía. Si quieres el paso a paso aplicado a ti: [enlace de agenda]."'),
 landing('¿Invertir en Miami? La respuesta empieza con tus números, no con un vendedor',
 'En 15 minutos te decimos qué puedes comprar HOY con tu presupuesto, cuánto rentaría y cómo funciona el crédito sin residencia. Por escrito y sin compromiso.',
 ['Descubre tu capacidad real de compra con crédito para extranjeros (sin afectar tu historial).',
  'Proyección de renta en dólares de las zonas que encajan con tu presupuesto.',
  'El error #1 del inversionista primerizo (y cómo evitarlo) explicado en la llamada.',
  'Si tu momento no es ahora, te dejamos el plan por escrito para cuando sí.'],
 'Quiero mi análisis gratuito de 15 minutos',
 'Cada asesor toma máximo [N] análisis nuevos por semana para entregarlos en 48 h.')))

KITS.append(doc('copy-scoring-frio.doc', 'Scoring FRÍO (score 10-29)',
 'Leads con señales débiles: estado inicial o interacciones viejas, sin oportunidad vigente. Necesitan recalentamiento con contenido antes de gestión comercial.',
 'Al frío no se le pide cita en el primer toque — se le da una razón para volver a hablar. Contenido primero, agenda después.',
 wa('Reactivación con valor', 'día 1', '"[Nombre], soy [asesor] de [empresa]. Hace un tiempo te interesó invertir en EE.UU. — te comparto algo corto que le está sirviendo a inversionistas de [país]: la guía de cuánto rinde hoy una propiedad en Miami vs dejar la plata en el banco [enlace del blog]. Si la ves y te hace clic, me dices y aterrizamos tu caso."') +
 wa('Pregunta de bajo compromiso', 'día 4', '"Pregunta corta 🙂: ¿lo tuyo sería más renta mensual en dólares o proteger capital de la devaluación? Con una palabra que me respondas te oriento sin llenarte de mensajes."') +
 wa('Gancho de evento', 'día 10', '"Este [fecha] hacemos [webinar/evento] gratuito: proyectos reales, crédito sin residencia e impuestos, todo en una hora. Es la forma más fácil de ponerte al día sin compromiso. ¿Te mando el enlace?"') +
 wa('Pausa elegante', 'día 18', '"[Nombre], te dejo descansar del tema 🙂 Quedas en mi lista de novedades importantes (solo lo grande: proyectos nuevos y cambios de tasas). Cuando quieras retomar, un mensaje y seguimos donde quedamos."'),
 email(1, 'Lo que USD 150.000 compran hoy en Miami (te va a sorprender)',
 '"[Nombre]: con el presupuesto típico de nuestros inversionistas (USD 150.000–250.000) hoy se accede a unidades en Hollywood y Kendall que rentan USD 1.500–2.200/mes administradas por nosotros. Te dejo la guía completa de zonas del blog: [enlace]. Cuando quieras convertir la curiosidad en números propios, respondes este correo y listo."') +
 email(2, 'La devaluación no espera (y tu capital tampoco debería)',
 '"Cada año que el capital duerme en moneda local pierde contra el dólar. No te decimos que compres mañana — te decimos que sepas exactamente qué podrías comprar, cuánto rentaría y qué crédito alcanzarías. Ese análisis es gratis y queda por escrito: [enlace de agenda]."'),
 landing('Deja de ver cómo tu plata pierde contra el dólar',
 'Guía gratuita + análisis personalizado: qué compra hoy tu presupuesto en Miami, cuánto renta y cómo acceder a crédito sin residencia. Para decidir con datos, no con afán.',
 ['La comparación honesta: propiedad en Miami vs CDT/banco vs finca raíz local.',
  'Zonas que rentan mejor por rango de presupuesto (con cifras de arriendo reales).',
  'Crédito para extranjeros explicado en 5 preguntas.',
  'Errores caros de primerizos que nuestra trayectoria nos enseñaron a evitar.'],
 'Descarga la guía y pide tu análisis sin costo',
 'La proyección personalizada se entrega en 48 h — cupos de análisis limitados por semana.')))

KITS.append(doc('copy-scoring-sinsenales.doc', 'Scoring SIN SEÑALES (score < 10)',
 'Leads sin oportunidad registrada, sin estado activo y sin interacciones: cero evidencia de interés en el CRM. Volumen alto, expectativa baja: activación masiva, no gestión 1 a 1.',
 'Aquí gana la máquina, no el asesor: goteo de activación de 3 toques y solo pasa a humano quien levante la mano. No gastes horas de asesor en este pozo.',
 wa('Toque 1 — reactivación', 'día 1 (masivo)', '"Hola [nombre], somos [empresa] 🇺🇸. Te registraste interesado en invertir en propiedades en EE.UU. y queremos saber si sigue en tus planes. Responde con un número: 1️⃣ Sí, quiero información actual · 2️⃣ Más adelante · 3️⃣ Ya no me interesa. Con eso te atendemos como corresponde (y si es 3, no te molestamos más)."') +
 wa('Toque 2 — prueba social', 'día 5 (masivo, solo a los que no respondieron)', '"[Nombre], solo esto: el mes pasado [N] familias latinoamericanas compraron con nosotros propiedad en Miami — la mayoría con crédito sin residencia y renta administrada. Si quieres ver cómo lo hicieron: [enlace del blog/caso]. Responde INFO y te aterrizamos tu caso."') +
 wa('Toque 3 — cierre de lista', 'día 10 (masivo)', '"Última de nuestra parte, [nombre] 🙂 Si invertir en EE.UU. quedó para otro momento, todo bien — quedas solo en novedades grandes. Si quieres retomarlo algún día, escribe INVERTIR y un asesor te toma el caso el mismo día."'),
 email(1, '¿Sigue en pie tu idea de invertir en EE.UU.?',
 '"[Nombre], hace un tiempo te interesaste y no te hemos atendido como mereces. Un clic y te decimos qué compra hoy tu presupuesto, cuánto renta en dólares y cómo funciona el crédito sin residencia: [enlace]. Y si ya no es tu momento, abajo puedes silenciar estos correos sin drama."') +
 email(2, 'Esto compró una familia como la tuya (números reales)',
 '"USD 185.000 · unidad en Kendall · rentada al primer mes en USD 1.900 · crédito aprobado sin visa. No todos los casos son iguales — por eso el análisis personalizado es gratis y por escrito. Pídelo aquí: [enlace]."'),
 landing('¿Todavía quieres invertir en EE.UU.? Retomemos donde quedaste',
 'Tu interés quedó registrado y nunca te atendimos bien — eso es culpa nuestra. Corrijámoslo: análisis gratuito de qué puedes comprar hoy, cuánto rentaría y qué crédito alcanzas.',
 ['2 minutos para retomar: respondes 3 preguntas y recibes tu análisis en 48 h.',
  'Sin llamadas sorpresa: tú eliges el canal y el horario.',
  'Crédito para extranjeros sin residencia — el mito que más gente frena, resuelto.',
  'Si ya no es tu momento, un clic y no te contactamos más.'],
 'Retomar mi caso (2 minutos)',
 'Los análisis se toman por orden de llegada — entrega por escrito en 48 h.')))

# ================= POR SEGMENTO DEL PLAN =================
KITS.append(doc('copy-esperando30.doc', 'Segmento: Esperando respuesta (tibios/calientes en cola WA)',
 'Leads score ≥30 cuya última palabra en WhatsApp es SUYA: preguntaron algo y nadie contestó.',
 'Aquí no hay copy que valga más que la velocidad: responder LO QUE PREGUNTARON, hoy, con persona y no con plantilla.',
 wa('Respuesta de rescate', 'HOY', '"[Nombre], mil disculpas por la demora — tu mensaje merecía respuesta antes. Sobre lo que preguntabas de [tema exacto: crédito/precio/zona]: [respuesta concreta en 2 líneas]. ¿Te llamo hoy y lo cerramos en 10 minutos?"') +
 wa('Seguimiento', '+24 h', '"[Nombre], quedo pendiente de ti. Para compensarte la espera te preparé [dato/PDF de la zona que preguntó]. ¿Mañana a las [hora A] o [hora B]?"') +
 wa('Último intento del ciclo', 'día 5', '"No quiero ser insistente — solo confirmar que no perdiste el interés por culpa de nuestra demora. Si sigues en el plan, tu caso queda con prioridad conmigo esta semana. ¿Lo retomamos?"'),
 email(1, 'Te respondí por WhatsApp — y esto es lo que pediste',
 '"[Nombre], te dejé mensaje por WhatsApp con la respuesta a tu pregunta sobre [tema]. Te la dejo también aquí por escrito: [respuesta]. Mi agenda directa para resolver el resto: [enlace]."'),
 landing('¿Preguntaste y no te contestaron? Eso se acabó',
 'Tu caso queda con un asesor titular y compromiso de respuesta el mismo día. La primera respuesta incluye los números que pediste.',
 ['Asesor titular con nombre y apellido (no un bot ni una cola).',
  'Respuesta a tu pregunta original + proyección de tu caso por escrito.',
  'Canal y horario los eliges tú.'],
 'Retomar mi caso con prioridad',
 'Los casos de la cola de espera se toman primero — hoy.')))

KITS.append(doc('copy-hot.doc', 'Segmento: Leads calientes (inventario listo para cerrar)',
 'El inventario de score ≥55 del CRM: oportunidad declarada + actividad reciente.',
 'Mismo playbook del scoring CALIENTE pero con dueño y fecha: cada caliente debe tener asesor titular y cita agendada esta semana — sin excepción.',
 wa('Apertura con dato', 'hoy', '"[Nombre], tu interés en invertir en [zona] con horizonte de [X meses] está vigente y el mercado también: hay [N] unidades en tu rango ahora mismo. Te muestro las 2 mejores hoy — ¿[hora A] o [hora B]?"') +
 wa('Escasez honesta', '+48 h', '"De las 2 que te mencioné, una ya tiene oferta de otro comprador. La otra sigue disponible y los números dan: renta estimada USD [X], cuota cubierta. ¿La revisamos hoy?"') +
 wa('Cierre alternativo', 'día 7', '"[Nombre], decide con datos, no conmigo insistiéndote 🙂: te mando la proyección por escrito Y te agendo 15 minutos para dudas — o si prefieres, pausa formal y te busco en [mes]. ¿Cuál de las dos?"'),
 email(1, 'Las 2 unidades que encajan con tu plan (números adentro)',
 '"[Nombre]: unidad A en [zona], USD [precio], renta estimada USD [X]/mes. Unidad B en [zona], USD [precio], renta USD [Y]. Ambas con crédito para extranjeros pre-evaluable en 48 h. La proyección completa está adjunta. Agenda para resolver dudas: [enlace]."'),
 landing('Estás a una llamada de tu propiedad en Miami',
 'Tu perfil ya califica: presupuesto definido, horizonte claro. Lo único que falta son los números finales de las unidades disponibles — y eso lo resolvemos en 15 minutos.',
 ['2 unidades preseleccionadas para TU rango (no un catálogo genérico).',
  'Pre-evaluación de crédito para extranjeros en 48 h.',
  'Proyección de renta y costos por escrito antes de cualquier compromiso.'],
 'Ver mis 2 opciones esta semana',
 'El inventario en rangos de USD 150-250k rota en semanas, no meses — la preselección se actualiza cada lunes.')))

KITS.append(doc('copy-negocio.doc', 'Segmento: Negocio abierto (negociaciones activas)',
 'Leads en la etapa más cercana al cierre: negociación en curso.',
 'En negociación el enemigo es el silencio: cada 72 h sin novedad el negocio pierde temperatura. Toque corto, específico y con el siguiente paso SIEMPRE definido.',
 wa('Pulso de negociación', 'cada 72 h máximo', '"[Nombre], novedad de tu negociación: [avance concreto: respuesta del seller/banco/documento]. El siguiente paso es [acción] y lo tenemos para [fecha]. ¿Todo firme de tu lado?"') +
 wa('Manejo de frío repentino', 'si deja de responder 4-5 días', '"[Nombre], sé que en esta etapa aparecen dudas de última hora — es normal y para eso estoy. ¿Es tema de números, de tiempos o de papeles? Dímelo sin filtro y lo resolvemos: has llegado muy lejos para dejarlo caer por una duda con solución."') +
 wa('Protección del cierre', 'previo a firma', '"Checklist de tu cierre: ✅ [doc1] ✅ [doc2] ⬜ [pendiente]. Solo falta eso — si lo tenemos el [día], firmas el [fecha]. Confirmo contigo mañana."'),
 email(1, 'Estado de tu negociación — [propiedad] ([fecha])',
 '"[Nombre], resumen ejecutivo de dónde vamos: hecho: [lista corta]. En curso: [ítem, responsable, fecha]. Te bloqueo 10 minutos el [día] para dejar todo alineado: [enlace]. Cualquier duda de última hora, respóndeme directo — para eso estoy."'),
 landing('(Este segmento no usa landing: la conversión es 1 a 1)',
 'Usa este espacio como guion de llamada de destrabe: 1) reconoce el avance, 2) nombra la duda sin rodeos, 3) resuélvela con dato o experto (contador/abogado de la compañía), 4) recompromete fecha.',
 ['Toda objeción de cierre es de 3 tipos: números, tiempos o papeles — identifícala antes de contestar.',
  'Nunca cierres una llamada de negociación sin fecha del siguiente paso.',
  'Si la duda es de impuestos/estructura: sube al contador de la compañía a la llamada, no lo dejes para "después".'],
 'Siguiente paso agendado antes de colgar',
 'Un negocio sin fecha de siguiente paso es un negocio muerto con pulso.')))

KITS.append(doc('copy-dormidos.doc', 'Segmento: Pipeline dormido (oportunidad vigente sin actividad 90+ días)',
 'Leads con horizonte de compra declarado que llevan más de 90 días sin un toque.',
 'No pidas perdón por la ausencia — vuelve con una NOVEDAD que justifique el mensaje. El pretexto del recontacto es el mercado, no tu CRM.',
 wa('Recontacto con novedad', 'día 1', '"[Nombre], soy [asesor] de [empresa]. Cuando hablamos, tu plan era invertir en unos [X meses] — y justo cambió algo que te toca: [novedad real: proyecto nuevo en su rango/cambio de tasas/inventario en su zona]. ¿Sigue vivo el plan? Te pongo al día en 10 minutos."') +
 wa('Puente de valor', 'día 4', '"Mientras decides si retomamos: así está hoy [zona que le interesaba] — arriendos en USD [X-Y], inventario [dato]. Es distinto a como estaba cuando hablamos. Si quieres los números de tu caso actualizados, me dices."') +
 wa('Recompromiso o pausa', 'día 10', '"[Nombre], lo dejo así: si tu plan sigue, te preparo el análisis actualizado esta semana. Si se movió para [fecha], me lo dices y te busco entonces con todo listo. ¿Cuál va?"'),
 email(1, 'Tu plan de invertir — esto cambió desde la última vez',
 '"[Nombre]: cuando hablamos, tu horizonte era [X meses]. Desde entonces: (1) [novedad de mercado], (2) [novedad de crédito/tasas], (3) tu análisis quedó desactualizado. Actualizarlo toma 15 minutos y vuelve a quedar por escrito: [enlace]. Si el plan cambió de fecha, respóndeme con el mes y te busco entonces — sin goteo molesto de por medio."'),
 landing('Tu plan de invertir en Miami sigue vivo — tus números no',
 'Declaraste un horizonte de compra y el mercado se movió desde entonces. Actualiza tu análisis en 15 minutos: qué compra hoy tu presupuesto, cuánto renta y qué crédito alcanzas.',
 ['Comparación honesta: tu escenario de entonces vs el de hoy.',
  'Inventario actual en tus zonas con cifras de renta reales.',
  'Si el momento se corrió, plan por fechas — sin insistencia de por medio.'],
 'Actualizar mi análisis (15 min)',
 'El análisis actualizado se entrega en 48 h y queda por escrito.')))

KITS.append(doc('copy-nuevos90.doc', 'Segmento: Nuevos sin gestionar (últimos 90 días)',
 'Leads recién adquiridos que aún no reciben primera gestión real.',
 'La ventana de oro son las primeras 24 horas: el lead nuevo se atiende el DÍA 1 o se paga caro después (nuestro promedio de 1ª atención es la prueba).',
 wa('Primer toque', 'día 1 (idealmente < 1 h)', '"Hola [nombre], soy [asesor], tu contacto directo en [empresa] 🙂 Vi tu registro por [fuente]. Para orientarte sin hacerte perder tiempo, una sola pregunta: ¿tu interés es más renta mensual en dólares, valorización, o ambas?"') +
 wa('Calificación suave', '+24 h', '"Gracias por responder 🙌 Con eso te preparo 2 opciones concretas. Última pregunta para afinar: ¿tu presupuesto está más cerca de USD 150k, 250k o más? (Con crédito para extranjeros la cuota inicial arranca en ~30%)."') +
 wa('Entrega de valor', 'día 3', '"Listo [nombre]: [opción A] y [opción B] en tu rango, ambas con renta administrada. Te las presento en 15 minutos con los números al lado — ¿[hora A] o [hora B]?"') +
 wa('Rescate del ciclo', 'día 7', '"[Nombre], no te suelto todavía 🙂 Si esta semana no es buena, dime cuál sí. Y si el registro fue solo curiosidad, también me sirve saberlo — te dejo en novedades grandes y listo."'),
 email(1, 'Bienvenido — tu siguiente paso toma 2 minutos',
 '"[Nombre], gracias por tu interés en invertir en EE.UU. Soy [asesor], tu contacto directo (persona real, no un embudo 🙂). Para armarte propuestas que valgan tu tiempo: responde este correo con tu rango de presupuesto y si buscas renta o valorización. Con eso te mando 2 opciones con números en 48 h."'),
 landing('Registraste tu interés — esto es lo que pasa ahora (y toma 15 minutos)',
 'Nada de spam ni llamadas eternas: un asesor titular, 2 opciones concretas para tu presupuesto y la proyección por escrito. Tú decides el ritmo.',
 ['Respuesta de un asesor titular en menos de 24 h.',
  '2 opciones seleccionadas para tu rango — no un catálogo.',
  'Crédito para extranjeros pre-evaluado sin afectar tu historial.',
  'Proyección de renta por escrito antes de cualquier compromiso.'],
 'Empezar mi análisis ahora',
 'Los registros de esta semana se asignan a asesor el mismo día.')))

KITS.append(doc('copy-sinAsesor.doc', 'Segmento: Huérfanos (sin asesor asignado)',
 'Leads sin dueño en el CRM: nadie los llama porque no son de nadie.',
 'El primer mensaje debe sonar a "ya tienes dueño": el gancho es la titularidad, no el producto.',
 wa('Presentación del titular', 'al asignarse', '"[Nombre], soy [asesor] de [empresa] y desde hoy soy tu contacto directo — tu caso quedó conmigo personalmente. Para retomarlo bien: ¿sigue en pie tu interés de invertir en EE.UU.? Un sí o un "más adelante" me basta para atenderte como corresponde."') +
 wa('Continuidad', '+48 h', '"Para que no repitas nada: ya revisé tu registro ([fuente], [fecha]). Lo que me falta saber es tu presupuesto aproximado y si buscas renta o valorización. Con esas 2 respuestas te traigo opciones concretas esta semana."') +
 wa('Cierre de ciclo', 'día 7', '"[Nombre], mi compromiso es no dejarte otra vez sin atención. Si no es el momento, dime cuándo te busco. Si lo es, tu análisis sale esta semana. Tú mandas."'),
 email(1, 'Tu caso ya tiene titular (soy yo)',
 '"[Nombre], una disculpa institucional: tu registro estuvo un tiempo sin asesor asignado. Eso terminó — soy [asesor], tu contacto directo, y tu caso está en mi lista personal. Retomamos donde quedaste: [enlace de agenda] o simplemente responde este correo."'),
 landing('Tu interés no se perdió — ahora tiene dueño',
 'Tu registro quedó asignado a un asesor titular que responde por tu caso. Retómalo en 2 minutos y recibe tu análisis por escrito esta semana.',
 ['Asesor con nombre, apellido y WhatsApp directo.',
  'Historial respetado: no vuelves a empezar de cero.',
  'Análisis de tu caso por escrito en 48 h.'],
 'Retomar mi caso con mi asesor',
 'Las reasignaciones de esta semana se atienden con prioridad.')))

KITS.append(doc('copy-ecSinOport.doc', 'Segmento: En curso sin oportunidad registrada',
 'Leads en gestión activa a los que nadie les ha preguntado (o registrado) su horizonte de compra.',
 'Este segmento se arregla con UNA pregunta bien hecha: la del horizonte. Es la pregunta que más score mueve en todo el CRM (+35 pts).',
 wa('La pregunta de oro', 'próximo toque', '"[Nombre], para atenderte como corresponde y no llenarte de mensajes que no aplican: ¿tu plan de compra es más para los próximos 3 meses, entre 3 y 6, o más adelante? Con esa sola respuesta te organizo TODO lo demás."') +
 wa('Refuerzo', '+72 h', '"Insisto solo porque cambia todo 🙂: si es pronto, te reservo opciones del inventario actual; si es más adelante, te preparo el plan sin presión. ¿3 meses, 6, o el otro año?"') +
 wa('Registro y siguiente paso', 'al responder', '"Perfecto, queda anotado: [horizonte]. Siguiente paso: [si 1-3m: cita esta semana / si 3-6m: análisis + evento / si 6+: plan de contenidos y check mensual]. Te muevo yo — tú solo confirma."'),
 email(1, 'Una pregunta que define cómo te atendemos',
 '"[Nombre], estamos en contacto pero nos falta el dato que ordena todo: ¿para cuándo es tu plan de compra? Responde con: A) próximos 3 meses · B) 3 a 6 · C) más adelante. Según tu respuesta te llega exactamente lo que corresponde — ni más mensajes, ni menos oportunidades."'),
 landing('(Segmento interno: no requiere landing)',
 'Guion para asesores: la pregunta del horizonte se hace en TODO canal disponible hasta obtener respuesta, y se registra en "En curso por" el mismo día. Sin ese campo el lead no puntúa y el seguimiento vuela a ciegas.',
 ['Pregunta cerrada de 3 opciones — no abierta (responde 3× más).',
  'Registrar la respuesta en el CRM el mismo día (campo En curso por).',
  'El siguiente paso depende de la respuesta: cita / análisis / nutrición.'],
 'Horizonte registrado = lead que puntúa',
 'Meta del segmento: bajar el "(Sin dato)" a la mitad en 30 días.')))

KITS.append(doc('copy-nutricion.doc', 'Segmento: En Nutrición (goteo automático)',
 'La bolsa más grande del CRM: leads en secuencias automáticas sin gestión comercial.',
 'La nutrición no vende: levanta manos. Cada pieza debe tener UNA acción medible que dispare el pase a asesor (responder, hacer clic, registrarse).',
 wa('Pieza de valor mensual', 'goteo', '"[Nombre], dato del mes de Miami 📊: [dato concreto de renta/tasas/zona con cifra]. Si quieres ver qué significa para un presupuesto como el tuyo, responde NÚMEROS y un asesor te lo aterriza (sin compromiso)."') +
 wa('Invitación a evento', 'según calendario', '"[Nombre], [fecha] hacemos [evento/webinar]: proyectos en vivo + crédito sin residencia + impuestos, en una hora. Es gratuito y es la vía rápida para ponerte al día. ¿Te reservo cupo? Responde SÍ y listo."') +
 wa('Detector de momento', 'trimestral', '"Pregunta de control 🙂: ¿tu plan de invertir sigue para [horizonte que declaró] o cambió? Responde con un mes o con \'pausa\' y ajustamos todo a tu ritmo."'),
 email(1, '[Dato del mes] — y qué significa para tu bolsillo',
 '"[Nombre]: [dato de mercado con cifra + 2 líneas de qué significa]. Del blog esta semana: [artículo del blog con enlace]. ¿Quieres estos números aplicados a tu caso? Responde este correo con la palabra ANÁLISIS."') +
 email(2, 'Invitación: [evento] (cupo gratuito)',
 '"Una hora, sin costo, sin compromiso: proyectos reales de Miami, cómo funciona el crédito sin residencia y qué está rentando cada zona. Los eventos son, por lejos, lo que más preguntan nuestros contactos — por algo será 🙂 Reserva: [enlace]."'),
 landing('Aprende a invertir en Miami — a tu ritmo, sin vendedores encima',
 'Contenido quincenal con cifras reales del mercado + eventos gratuitos. Y cuando decidas dar el paso, un análisis por escrito te espera.',
 ['Datos de mercado con cifras (no humo motivacional).',
  'Eventos y webinars con proyectos reales y expertos de crédito e impuestos.',
  'Análisis personalizado disponible cuando TÚ digas.'],
 'Recibir el contenido (y nada más)',
 'Los cupos de los eventos presenciales se llenan — el registro es gratuito.')))

KITS.append(doc('copy-descSenal.doc', 'Segmento: Descartados con señal viva (rescate)',
 'Leads marcados Descartado que hoy puntúan ≥30 o tienen oportunidad vigente: descartes probablemente erróneos.',
 'Reabre sin mencionar jamás que estuvo "descartado": el gancho es su interés declarado, que sigue vigente.',
 wa('Reapertura', 'tras revisión gerencial', '"[Nombre], soy [asesor] de [empresa]. Revisando tu caso veo que nos indicaste interés en invertir con horizonte de [X meses] — quiero retomarlo personalmente porque hay opciones nuevas que encajan con lo que buscabas. ¿Tienes 10 minutos esta semana?"') +
 wa('Valor + disculpa implícita', '+48 h', '"Para retomar con hechos: te preparé el panorama actual de [zona/presupuesto que declaró] — arriendos, inventario y crédito. Sea cual sea tu decisión, esos números te sirven. ¿Te los presento?"') +
 wa('Cierre limpio', 'día 7', '"[Nombre], si el interés sigue, tu caso queda activo conmigo esta semana. Si de verdad ya no va, dímelo y lo cierro bien (nada de mensajes eternos). ¿Cuál de las dos?"'),
 email(1, 'Tu plan de inversión — lo retomo personalmente',
 '"[Nombre]: tu interés por invertir quedó registrado con horizonte de [X meses] y me hago cargo de que recibas la atención que eso merece. Análisis actualizado de tu caso, por escrito y sin costo: [enlace]. Si prefieres cerrarlo definitivamente, respóndeme \'cerrar\' y así queda — sin más contactos."'),
 landing('Tu caso merecía una segunda mirada — y la tiene',
 'Tu interés de inversión sigue vigente en nuestros registros. Un asesor titular lo retomó: análisis actualizado por escrito, y tú decides si avanza o se cierra.',
 ['Retoma exactamente donde quedaste — sin repetir información.',
  'Números actualizados de tu zona y presupuesto declarados.',
  'Cierre limpio garantizado si decides no seguir: un clic y listo.'],
 'Retomar mi caso · o cerrarlo bien',
 'Los casos reabiertos esta semana tienen prioridad de agenda.')))

KITS.append(doc('copy-clientes.doc', 'Segmento: Clientes y referidos (recompra + embajadores)',
 'Los 988 clientes: la fuente de referidos con 7,8% de conversión (la mejor de la casa) y de recompra declarada.',
 'Al cliente no se le vende: se le rinde cuentas y se le pide la referencia con naturalidad. La renta administrada es tu excusa de contacto perpetua.',
 wa('Rendición de cuentas', 'trimestral', '"[Nombre], reporte corto de tu inversión 📊: tu unidad en [zona] [rentada en USD X / estado]. El mercado de tu zona se valorizó [dato]. ¿Todo bien de tu lado? Cualquier tema de la propiedad, aquí estoy."') +
 wa('Semilla de recompra', 'cuando hay novedad', '"[Nombre], dato para dueños como tú: con la valorización de tu unidad + las tasas actuales, varios clientes están usando su primera propiedad para apalancar la segunda. Si algún día quieres ver esos números, me dices — sin compromiso."') +
 wa('Petición de referido', 'tras un buen momento', '"Me alegra que todo marche 🙌 Un favor de los que valen: si tienes UN amigo o colega que hable de invertir en Miami, preséntamelo — lo atiendo con el mismo estándar que a ti y me haces el mejor cumplido posible. ¿Se te ocurre alguien?"'),
 email(1, 'El reporte de tu inversión — [trimestre]',
 '"[Nombre]: estado de tu unidad ([renta/ocupación/gastos]), mercado de tu zona ([valorización]) y una oportunidad para dueños ([novedad de apalancamiento/segunda unidad]). Si quieres explorar la segunda propiedad, los números están a una llamada: [enlace]. Y ya sabes: tus referidos tienen atención prioritaria conmigo."'),
 landing('Dueños: tu primera propiedad puede pagar la segunda',
 'Programa para clientes: apalanca la valorización de tu unidad para ampliar tu portafolio — y gana beneficios por cada referido que invierte.',
 ['Análisis de apalancamiento con tu unidad actual (sin costo).',
  'Prioridad de inventario para clientes existentes.',
  'Programa de referidos: tu red accede a tu mismo asesor y estándar.'],
 'Ver mi análisis de segunda propiedad',
 'El análisis para dueños se agenda con tu asesor de siempre.')))

print(f'OK -> {len(KITS)} kits de copy en {OUT}')
for k in KITS: print('  ', k)
