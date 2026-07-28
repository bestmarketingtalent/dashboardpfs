#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualización diaria COMPLETA del dashboard PFS (solo lectura sobre GHL).

Corre en orden: fetches (oportunidades/usuarios, contactos, conversaciones,
mensajes WA incrementales, cola pendiente, gestión incremental) → snapshot
histórico → los 7 reportes + dashboard gerencial → staging → zip en el Escritorio.

Incremental: los mensajes de WhatsApp y la gestión (llamadas/tareas/notas) solo
se re-descargan para los contactos con actividad en los últimos REFRESH_DIAS días,
así la corrida diaria tarda ~10-20 min en vez de horas.

Uso: python3 scripts/actualizar_diario.py [--sin-fetch]  (--sin-fetch: solo reportes+zip)
"""
import json, shutil, subprocess, sys, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / 'scripts'
DATA = S / 'data'
PY = sys.executable
REFRESH_DIAS = 3
HOY = datetime.now().strftime('%Y-%m-%d')
T0 = datetime.now()

def run(script, *args, timeout=5400):
    print(f'\n== {script} {" ".join(args)}', flush=True)
    r = subprocess.run([PY, str(S / script), *args], cwd=ROOT, timeout=timeout)
    if r.returncode:
        raise SystemExit(f'FALLO en {script} (código {r.returncode})')

if '--sin-fetch' not in sys.argv:
    # 1) fetches base
    run('ghl_fetch.py')             # oportunidades + usuarios + pipelines
    run('ghl_fetch_contactos.py')   # contactos con campos personalizados
    run('ghl_fetch_convos.py')      # metadata de todas las conversaciones

    # 2) poda incremental de mensajes WA: re-bajar solo convos con actividad reciente
    # lastDate viene en epoch milisegundos
    corte_ms = (datetime.now(timezone.utc) - timedelta(days=REFRESH_DIAS)).timestamp() * 1000
    convos = json.load(open(DATA / 'convos.json'))
    recientes = {c['id'] for c in convos
                 if c['lastType'] == 'TYPE_WHATSAPP' and (c.get('lastDate') or 0) >= corte_ms}
    wa_path = DATA / 'wa_all_msgs.json'
    if wa_path.exists() and recientes:
        wa = json.load(open(wa_path))
        antes = len(wa)
        wa = [r for r in wa if r['id'] not in recientes]
        json.dump(wa, open(wa_path, 'w'), ensure_ascii=False)
        print(f'poda WA: {antes - len(wa)} convos con actividad reciente se re-bajarán', flush=True)
    run('ghl_fetch_wa_all.py')      # reanudable: solo baja lo podado + lo nuevo
    run('ghl_fetch_pend_msgs.py')   # cola de clientes esperando + workflows
    run('ghl_fetch_gestion.py', '--refresh', str(REFRESH_DIAS))  # llamadas/TMO, emails, tareas, notas

# 3) snapshot histórico — SIEMPRE después de los fetch y antes de los reportes
run('ghl_snapshot.py')

# 4) reportes (7 páginas del sitio + dashboard gerencial de oportunidades)
for rep in ['ghl_build_dashboard.py', 'ghl_reporte_contactos.py', 'ghl_reporte_descartes.py',
            'ghl_reporte_wa.py', 'ghl_reporte_asesores.py', 'ghl_reporte_estrategia.py',
            'ghl_reporte_clientes.py', 'ghl_reporte_insights.py', 'ghl_reporte_adquisicion.py',
            'ghl_reporte_estrategia_comercial.py', 'ghl_reporte_asesores_hub.py', 'ghl_reporte_recuperacion.py',
            'ghl_reporte_lineas.py']:
    run(rep)

# 4b) kits de copy en Word (estáticos, van al staging docs/)
run('ghl_gen_copykits.py')

# 5) staging con los nombres del sitio + zip para Netlify en el Escritorio
MAPA = {
    f'reporte-contactos-pfs-{HOY}.html':   'index.html',
    f'descartados-pfs-{HOY}.html':         'descartados-full.html',
    f'desc-redirect-pfs-{HOY}.html':       'descartados.html',
    f'asesores-hub-pfs-{HOY}.html':        'asesores.html',
    f'auditoria-asesores-pfs-{HOY}.html':  'asesores-gestion.html',
    f'auditoria-whatsapp-pfs-{HOY}.html':  'conversaciones-full.html',
    f'wa-redirect-pfs-{HOY}.html':         'auditoria-whatsapp.html',
    f'estrategia-comercial-pfs-{HOY}.html': 'estrategia.html',
    f'estrategia-pfs-{HOY}.html':          'estrategia-plan.html',
    f'clientes-pfs-{HOY}.html':            'clientes.html',
    f'adquisicion-pfs-{HOY}.html':         'adquisicion.html',
    f'lineas-pfs-{HOY}.html':              'lineas.html',
    f'insights-pfs-{HOY}.html':            'insights-full.html',
    f'recuperacion-pfs-{HOY}.html':        'recuperacion-full.html',
    f'insights-redirect-pfs-{HOY}.html':   'insights.html',
}
stage = ROOT / 'netlify-pfs'
stage.mkdir(exist_ok=True)
for src, dst in MAPA.items():
    if not (ROOT / src).exists():
        raise SystemExit(f'FALTA el reporte {src}')
    shutil.copy(ROOT / src, stage / dst)

zip_path = Path.home() / 'Desktop' / f'netlify-pfs-{HOY}.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for dst in MAPA.values():
        z.write(stage / dst, dst)
    for doc in sorted((stage / 'docs').glob('*.doc')):
        z.write(doc, f'docs/{doc.name}')

# 6) resumen
contacts = json.load(open(DATA / 'contacts.json'))
gestion = json.load(open(DATA / 'gestion.json')) if (DATA / 'gestion.json').exists() else {}
desc = sum(1 for c in contacts if (c.get('leadStatus') or '').strip() == 'Descartado')
cli = sum(1 for c in contacts if (c.get('leadStatus') or '').strip() == 'Cliente')
print(f'''
LISTO en {int((datetime.now() - T0).total_seconds() / 60)} min · corte {HOY}
  contactos {len(contacts):,} | clientes {cli:,} | descartados {desc:,} | gestión descargada {len(gestion):,} leads
  staging: {stage}
  zip:     {zip_path}
Sube el zip a Netlify (deploy manual) — contiene datos personales: no publicar fuera del equipo autorizado.'''.replace(',', '.'), flush=True)
