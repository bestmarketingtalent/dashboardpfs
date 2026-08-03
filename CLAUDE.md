# Ventas Agénticas BMT — PFS Realty Group

Proyecto de análisis y automatización comercial sobre el CRM GoHighLevel (GHL) de
PFS Realty Group (inmobiliaria, Weston FL, pfsrealty.com).

## Regla de oro
**Todo acceso al CRM es SOLO LECTURA (peticiones GET).** Nunca escribir, modificar ni
borrar nada en GHL salvo instrucción explícita del usuario.

## Conexión GHL
- Credenciales en `.env` (raíz): `GHL_PIT` (token de integración privada) y
  `GHL_LOCATION_ID=nbqsauwBcmgQF0wP5mxx` (subcuenta PFS Realty Group).
- API v2: `https://services.leadconnectorhq.com`, headers
  `Authorization: Bearer $GHL_PIT` + `Version: 2021-07-28`.
- ⚠ La API rechaza el User-Agent de python-urllib (403): enviar `User-Agent: curl/8.4.0`.
- El token es de subcuenta: los endpoints de agencia (p. ej. `/locations/search`) dan 403.
- Pipeline: "PIPELINE PFS" (`NYSibydwpiishOSJm56z`), 17 etapas, ~14.900 oportunidades.

## Scripts (`scripts/`)
1. `ghl_fetch.py` — descarga oportunidades (~150 páginas), usuarios y pipelines a
   `scripts/data/*.json`. Tarda 2-4 min.
2. `ghl_build_dashboard.py` — genera `dashboard-gestion-comercial-pfs-AAAA-MM-DD.html`
   (dashboard gerencial completo, skill dashboard-gestion-comercial).
3. `ghl_fetch_contactos.py` — descarga la tabla completa de contactos (~28.000)
   con campos personalizados (Lead Status, En curso por, Realtor, interacción) a
   `scripts/data/contacts.json`. Usa `POST /contacts/search` (endpoint de consulta
   paginada, 56 páginas de 500; el listado GET no trae customFields y el detalle
   uno a uno tardaría ~1 h). Es solo lectura: no escribe nada. Tarda <1 min.
4. `ghl_reporte_contactos.py` — genera `reporte-contactos-pfs-AAAA-MM-DD.html`:
   base COMPLETA de contactos (con y sin oportunidad), drill-down Asesor →
   Lead Status → leads ordenados por lead scoring 0-100 (En curso por hasta 35 +
   Lead Status hasta 25 + interacciones hasta 20 + recencia hasta 20; Caliente ≥55,
   Tibio 30-54, Frío 10-29). Filtros: asesor, lead status, en curso por, realtor,
   búsqueda; CSV. Origen = campo "Fuente de contacto" tal cual. Requiere ejecutar
   antes el 3 (y el 1 solo por users.json). Nota: los campos "Nivel de Interés" y
   "Riesgo de Pérdida" existen pero están 100% vacíos (no se usan en el score).
5. `ghl_fetch_convos.py` — metadata de TODAS las conversaciones (~25.700, GET
   /conversations/search paginado) a `scripts/data/convos.json`. ~2 min.
6. `ghl_fetch_wa_sample.py` — muestrea ~224 convos de WhatsApp (16 por asesor top,
   prioriza últimas palabras del cliente) y baja sus mensajes a
   `scripts/data/wa_sample.json`. ~1 min.
7. `ghl_reporte_wa.py` — genera `auditoria-whatsapp-pfs-AAAA-MM-DD.html`: métricas
   por asesor/fuente (universo, filtrables por fuente) + flujos que dejan leads sin
   respuesta + análisis cualitativo (la parte cualitativa del HTML es texto estático
   redactado al corte 2026-07-18; si se regenera con datos nuevos hay que revisarla).
   Requiere 1 (users), 3 (contacts), 5, 6 y 8.
8. `ghl_fetch_pend_msgs.py` — mensajes de las convos WA con cliente esperando +
   lista de workflows, a `scripts/data/{{pend_msgs,workflows}}.json`. ~1 min.
9. `ghl_reporte_asesores.py` — genera `auditoria-asesores-pfs-AAAA-MM-DD.html`:
   auditoría individual filtrable por asesor y por realtor (cartera, actividad WA/
   llamadas/email, cola de espera, semáforo y retroalimentación por reglas + notas
   cualitativas estáticas del corte 2026-07-18). Incluye análisis conversacional
   completo si existe wa_all_msgs.json (script 10): tiempo de respuesta mediano
   real, % mensajes respondidos, % plantillas (texto repetido en 5+ convos) y
   análisis/recomendación por lead generados por reglas. Requiere 1, 3, 5 y 6.
10. `ghl_fetch_wa_all.py` — baja los mensajes de TODAS las convos de WhatsApp
    (~4.850, ~30 min, reanudable) a `scripts/data/wa_all_msgs.json`. Correr en
    segundo plano antes del 9 para tener el análisis conversacional completo.
11. `ghl_reporte_estrategia.py` — genera `estrategia-pfs-AAAA-MM-DD.html`: diagnóstico
    y playbook por segmento (esperando respuesta, calientes, negocio abierto, pipeline
    dormido, nuevos, huérfanos, en curso sin oportunidad, nutrición, descartados con
    señal, clientes/referidos). Cada segmento con botón "Ver y gestionar los leads"
    (tabla embebida con asesor, realtor, contacto, WA y CSV). Números calculados de
    los datos; texto estratégico redactado al corte 2026-07-19 — revisarlo al
    regenerar. Requiere 1 (users), 3 y 5.
12. `ghl_reporte_clientes.py` — genera `clientes-pfs-AAAA-MM-DD.html`: los ~983
    clientes para venta cruzada (segmentos: recompra declarada, post-venta roto,
    Elite, sin contacto 180+, relación viva; filtros por realtor/asesor/mercado/
    fuente/oportunidad/último contacto; distribuciones clicables; tabla + Excel).
    Último contacto calculado de las conversaciones (el campo de actividad del
    CRM está vacío para clientes). Requiere 1, 3 y 5.
13. `ghl_snapshot.py` — guarda la foto diaria de métricas clave en
    `scripts/data/historico.json` (upsert por fecha). CORRERLO SIEMPRE después de
    los fetch y ANTES de los reportes: alimenta la sección "Evolución de la
    gestión comercial" del home (resumen de impacto entre cortes + tabla con
    deltas). historico.json es acumulativo: no borrarlo.
14. `ghl_reporte_insights.py` — genera `insights-pfs-AAAA-MM-DD.html`: radiografía
    por país (prefijo del móvil, con conversión), qué quieren/desean (campos
    declarados: intención, presupuesto, zona, hobbies, visa, año + evidencia de
    conversaciones), 6 buyer personas de los clusters reales y guiones de
    persuasión por temperatura de scoring. Textos interpretativos: revisar al
    regenerar. Requiere 3 (el fetch ya trae los campos de perfil).
15. `ghl_reporte_descartes.py` — genera `descartados-pfs-AAAA-MM-DD.html`: análisis
    completo de los ~2.940 leads descartados (por qué se descartan, quién los descarta,
    tasa de descarte por fuente, gestión previa al descarte, rescatables con señal viva,
    aprendizajes dinámicos). Filtros: asesor, motivo, fuente, en curso por, realtor,
    búsqueda, fechas; KPIs clicables con recortes especiales (sin gestión / rescatables /
    sin motivo / contactables); tabla de leads ordenada por score + Excel. Requiere 1 y 3.
16. `ghl_fetch_gestion.py` — baja la gestión por lead de las carteras de asesores
    HUMANOS (excluye MARKETING PFS y sin asesor): llamadas con duración (TMO),
    emails salientes, tareas y notas → `scripts/data/gestion.json` (keyed por
    contactId, reanudable, 6 hilos, ~33k GET, ~1-1.5 h la primera vez).
    Con `--refresh N` solo re-baja contactos con actividad en los últimos N días
    (corrida diaria: minutos). Requiere 1, 3 y 5. La hoja de asesores lo usa para
    Llam./lead, TMO, Emails/lead, tareas, notas y la bitácora por lead.
17b. `ghl_gen_copykits.py` — genera los 14 kits de copy en Word
    (`netlify-pfs/docs/copy-*.doc`, formato Word-HTML): uno por segmento del plan
    de acción y uno por nivel de scoring, con mensajes de WhatsApp por etapa,
    emails y copy de landing (estructura Hormozi + insights de conversaciones y
    buyer personas). Contenido estático: revisarlo si cambian los insights.
    Enlazados desde estrategia-plan.html (sección de kits + botón en cada tarjeta).
17. `actualizar_diario.py` — ORQUESTADOR de la actualización completa: fetches
    incrementales (poda WA + gestión --refresh 3) → snapshot → dashboard gerencial
    + 7 reportes → staging estable `netlify-pfs/` (en la raíz del proyecto) → zip
    `~/Desktop/netlify-pfs-AAAA-MM-DD.zip`. `--sin-fetch` = solo reportes + zip.
18. `ghl_reporte_adquisicion.py` — genera `adquisicion-pfs-AAAA-MM-DD.html`:
    análisis de adquisición por medio — KPIs, tortas por fuente y país, llegada
    mensual apilada, tabla maestra de calidad por fuente (volumen, momentum 90d,
    conversión, descarte, calificados, 1ª atención), campañas por etiqueta no
    genérica, atribución digital (attributionSource; el embudo WA rompe UTMs/gclid)
    y tabla de leads + Excel. Requiere 1, 3 y (opcional) 10/16 para intentos.
El sitio Netlify tiene 5 pestañas: index.html (Gestión comercial),
adquisicion.html (Adquisición), asesores.html (Asesores comerciales: contenedor con 3 sub-pestañas — gestión de
asesores, análisis de conversaciones y pérdida de leads — que carga
asesores-gestion.html, conversaciones-full.html y descartados-full.html en un
iframe, generado por ghl_reporte_asesores_hub.py), estrategia.html (Estrategia
comercial: mismo patrón, carga estrategia-plan.html, insights-full.html y
recuperacion-full.html (plan de recuperación de leads en 6 segmentos con
playbook y guiones, generado por ghl_reporte_recuperacion.py; sub-pestaña
?tab=recuperacion), generado por ghl_reporte_estrategia_comercial.py) y
clientes.html (pestaña: Fidelización clientes).
insights.html, auditoria-whatsapp.html y descartados.html quedaron como
redirects (a estrategia.html?tab=insights, asesores.html?tab=conversaciones y
asesores.html?tab=descartados) para marcadores viejos.
Orden del pipeline completo: fetch (1,3,5,6,8,10) → ghl_snapshot.py → reportes
(2 opcional,4,7,9,11,12,14,15) → copiar a staging con nombres del sitio → zip.
Ejecutar siempre 1 antes de 2; y 3 antes de 4. Los HTML son autocontenidos, sin
dependencias externas, formato es-CO.
Señal clave conversaciones: lastMessageDirection=inbound = cliente esperando
respuesta (229 en WA al corte 2026-07-18; fuente "Whatsapp" orgánica 64% abandono).
Ojo: contactos (~27.900) ≠ oportunidades (~14.900): ~13.000 contactos del CRM
nunca han entrado al PIPELINE PFS.

## Regla de asesor: owner ∪ follower (solo consulta)
Desde ago-2026, en las hojas con filtro/selector de asesor (Gestión comercial,
Asesores comerciales, Fidelización clientes, Pérdida de leads) el asesor cuenta
como OWNER (assignedTo) **o** SEGUIDOR (followers) del contacto — el CRM nunca
se modifica, solo la consulta. Las filas donde solo es seguidor llevan chip
"seguidor (· owner real)". La vista agrupada del home sin filtro sigue por owner
para no duplicar totales. followers viene en el fetch de contactos
(contacts.json rec['followers']); scripts/data/followers.json es el mapa puente
del primer sondeo. En el resumen de asesores la columna Leads muestra el
desglose (owner+seguidor).

## Lead Scoring v2 (desde ago-2026)
`ghl_score_v2.py` (corre en el orquestador antes del snapshot) calcula el score
0-100 con TODA la evidencia del CRM y escribe `scripts/data/score_v2.json`
({cid: {s, d:[intención, etapa, reciprocidad, recencia], fl}}). Pilares:
① INTENCIÓN 0-35 (horizonte declarado / monto en notas-mensajes 30 / compra
declarada 20 / presupuesto 22; APLAZAMIENTO reciente ≤120d lo congela a 15);
② ETAPA 0-25 (lead status); ③ RECIPROCIDAD 0-20 (eco del lead: WA entrantes,
llamadas contestadas o notas de respuesta; gestión sin respuesta máx 4);
④ RECENCIA REAL 0-20 (mejor fecha entre lastActivity, notas, tareas, intentos y
conversaciones — los campos lastActivity suelen estar rotos). Flags: 💰M monto ·
🛒C compra · ✋R respondió · ⏸Z aplazado (chips en el drill-down del home).
Las citas de mensajes SALIENTES pegadas en notas ("PFS REALTY LLC: …") se
recortan antes de buscar evidencia (el pitch del asesor no es declaración del
lead). Los reportes cargan _SC2 y su score_of prioriza v2 con fallback a la
fórmula clásica; `ghl_reporte_clientes.py` queda EXCLUIDO (usa su propia fórmula
de recompra). Casos de calibración: Jorge Sicardo 53 MCRZ (monto real, aplazado
a octubre) y Carlos Riascos 34 sin flags (nunca respondió; su antiguo 🛒 era el
pitch de la asesora transcrito).

## Mapeo de etapas → macro-estados (clasificación excluyente, en este orden)
- **Cierres**: etapa "Cierre (Elite Club)" o status won.
- **Perdidos por no-contacto**: status lost/abandoned en Nuevo Lead, Intento de Contacto o COLD.
- **Otros descartes**: lost/abandoned en etapas posteriores.
- **Etapas avanzadas**: WARM, Llamada de Precalificación, Precalificación Financiera,
  Atención Contador, Date to Miami, Asistió Oficina Miami, Tour Miami,
  Toma Decision (HOT), Pending (Elite Club).
- **Gestión activa**: Intento de Contacto, Cita a Jornada/Evento/Webinar,
  Asistió a Jornada/Evento/Webinar, Cita Virtual, Asisitió Presencial o Virtual.
- **Base fría**: COLD. · **Sin gestionar**: Nuevo Lead.

En OPORTUNIDADES la fuente se deriva de tags (su campo `source` viene vacío en ~92%).
En CONTACTOS el campo "Fuente de contacto" (`source`) sí viene poblado (~92%) y el
reporte de contactos lo usa tal cual (solo unifica mayúsculas; vacío/<unspecified> =
"(Sin fuente)"). Mercado = país por indicativo telefónico; campaña = primer tag no genérico.

## Hallazgos vigentes (corte 2026-07-16)
48% de la base parqueada (COLD + sin gestionar) · 257 cierres sin asesor asignado ·
bolsa MARKETING PFS con 5.200+ leads · 0 motivos de pérdida configurados · solo 4
oportunidades marcadas won vs 991 en etapa Cierre · 79% de la base sin movimiento de
etapa en +90 días.

## Tareas programadas
`actualizar-dashboard-diario-pfs` (esta máquina): lunes a viernes 6:30 a.m., corre
`scripts/actualizar_diario.py` (pipeline completo incremental + zip en el Escritorio).
En otra máquina existe la antigua `actualizar-dashboard-pfs` (lunes 7:00, solo
fetch + dashboard gerencial): si se reactiva ese computador, eliminarla o
actualizarla para no duplicar trabajo. Las tareas **viven en la máquina donde se
crearon** (~/.claude/scheduled-tasks/) y corren con la app abierta (si estaba
cerrada, corren al abrirla).

## Datos personales (Habeas Data)
Los HTML generados y `scripts/data/` contienen nombres, correos y teléfonos de ~15.000
personas: son la base de datos misma. No publicarlos, no subirlos a servicios externos,
no circularlos fuera del equipo comercial autorizado de PFS.
