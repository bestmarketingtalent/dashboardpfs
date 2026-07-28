#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera la hoja unificada "Estrategia comercial": un contenedor con dos
sub-pestañas que carga estrategia-plan.html (plan de acción por segmentos) e
insights-full.html (insights y buyer personas) en un iframe del mismo sitio,
ocultando el encabezado interno de cada una. Así los dos reportes conviven en
una sola hoja sin mezclar sus motores de JavaScript.
También genera el redirect insights-redirect-*.html → estrategia.html?tab=insights
para no romper marcadores viejos de insights.html."""
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_hoy = datetime.now()
MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
CORTE = f'{_hoy.day} de {MESES[_hoy.month-1]} de {_hoy.year}'

HTML = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estrategia comercial</title>
<style>
:root{{--azul:#2C4356;--azul-oscuro:#072031;--azul-suave:#EAF0F6;--amarillo:#C4B284;--naranja:#AA9664;
--tinta:#152238;--gris:#5B6B85;--gris-linea:#E4E9F2;--gris-fondo:#F7F9FC}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;color:var(--tinta);background:#fff}}
.wrap{{max-width:1280px;margin:0 auto;padding:0 20px}}
header{{background:var(--azul-oscuro);color:#fff;padding:20px 0}}
header .wrap{{display:flex;align-items:center;gap:16px}}
.logo{{background:var(--amarillo);color:var(--azul-oscuro);font-weight:900;font-size:21px;letter-spacing:1px;padding:11px 13px;border-radius:9px}}
header h1{{font-size:18.5px;font-weight:800}}
header p{{color:#C9D6E4;font-size:12.5px;margin-top:2px}}
.mainnav{{background:var(--azul-oscuro);border-top:1px solid #ffffff14}}
.mainnav .mnwrap{{max-width:1280px;margin:0 auto;padding:0 14px;display:flex;gap:2px;overflow-x:auto}}
.mainnav a{{color:#9FB3C6;text-decoration:none;font-size:13px;font-weight:700;padding:11px 16px 9px;
border-bottom:3px solid transparent;white-space:nowrap;display:flex;gap:7px;align-items:center;
letter-spacing:.2px;transition:color .15s,border-color .15s}}
.mainnav a:hover{{color:#fff}}
.mainnav a.act{{color:var(--amarillo);border-bottom-color:var(--amarillo)}}
.mainnav a .ic{{font-size:15px}}
.strip{{height:6px;background:linear-gradient(90deg,var(--amarillo) 55%,var(--naranja) 55% 78%,var(--azul) 78%)}}
.subtabs{{max-width:1280px;margin:0 auto;padding:12px 20px 0;display:flex;gap:8px;flex-wrap:wrap}}
.subtab{{border:1.5px solid var(--gris-linea);background:var(--gris-fondo);color:var(--gris);border-radius:11px 11px 0 0;
padding:10px 20px;font-size:13.5px;font-weight:800;cursor:pointer;display:flex;gap:8px;align-items:center}}
.subtab.on{{background:#fff;color:var(--azul-oscuro);border-color:var(--azul);border-bottom-color:#fff;position:relative;top:1px}}
.subtab:hover{{color:var(--azul-oscuro)}}
.frwrap{{border-top:1.5px solid var(--gris-linea)}}
iframe{{display:block;width:100%;height:calc(100vh - 208px);min-height:640px;border:0}}
.cargando{{text-align:center;color:var(--gris);font-size:13px;padding:30px}}
</style></head><body>
<header><div class="wrap"><div class="logo">GC</div>
<div><h1>Estrategia comercial</h1>
<p>CRM comercial (solo lectura) · Plan de acción + insights + recuperación de leads · Corte: {CORTE}</p></div>
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
<div class="subtabs">
<button class="subtab on" id="t-ins" data-src="insights-full.html">🧠 Insights y buyer personas</button>
<button class="subtab" id="t-plan" data-src="estrategia-plan.html">🎯 Plan de acción por segmentos</button>
<button class="subtab" id="t-rec" data-src="recuperacion-full.html">🚑 Recuperación de leads</button>
</div>
<div class="frwrap"><iframe id="fr" src="insights-full.html" title="Contenido de estrategia comercial"></iframe></div>
<script>
const fr = document.getElementById('fr');
const tabs = [...document.querySelectorAll('.subtab')];
function abrir(tab) {{
  tabs.forEach(t => t.classList.toggle('on', t === tab));
  /* location.replace: cambia el contenido SIN crear entradas de historial en la
     pestaña (cambiar fr.src ensucia el historial y el navegador lo restaura mal) */
  try {{ fr.contentWindow.location.replace(tab.dataset.src); }}
  catch (e) {{ fr.src = tab.dataset.src; }}
}}
tabs.forEach(t => t.addEventListener('click', () => abrir(t)));
/* dentro del iframe (mismo sitio) se oculta el encabezado propio de cada reporte
   para que no se dupliquen la cabecera y la navegación; además se sincroniza la
   sub-pestaña activa con lo que el navegador haya restaurado realmente */
fr.addEventListener('load', () => {{
  try {{
    const d = fr.contentDocument;
    ['header', '.mainnav', '.strip'].forEach(sel => {{
      const el = d.querySelector(sel);
      if (el) el.style.display = 'none';
    }});
    const path = fr.contentWindow.location.pathname;
    tabs.forEach(t => t.classList.toggle('on', path.endsWith(t.dataset.src)));
  }} catch (e) {{ /* si el navegador bloquea el acceso (file://), se ve el encabezado interno: solo estético */ }}
}});
const _tab2 = new URLSearchParams(location.search).get('tab');
if (_tab2 === 'insights') abrir(document.getElementById('t-ins'));
if (_tab2 === 'plan') abrir(document.getElementById('t-plan'));
if (_tab2 === 'recuperacion') abrir(document.getElementById('t-rec'));
</script>
</body></html>'''

out = ROOT / f'estrategia-comercial-pfs-{_hoy:%Y-%m-%d}.html'
out.write_text(HTML, encoding='utf-8')

REDIR = '''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0;url=estrategia.html?tab=insights">
<title>Insights</title></head>
<body style="font-family:system-ui;padding:30px;color:#152238">Los insights ahora viven en la hoja
<a href="estrategia.html?tab=insights">Estrategia comercial</a>. Redirigiendo…</body></html>'''
red = ROOT / f'insights-redirect-pfs-{_hoy:%Y-%m-%d}.html'
red.write_text(REDIR, encoding='utf-8')
print('OK ->', out)
print('OK ->', red)
