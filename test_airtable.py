import json, urllib.request, sys

env = {}
with open('.env.local') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v

BASE = f"https://api.airtable.com/v0/{env['AIRTABLE_BASE_ID']}"
headers = {
    'Authorization': f"Bearer {env['AIRTABLE_TOKEN']}",
    'Content-Type': 'application/json'
}

def get(url):
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def post(table, fields):
    url = f"{BASE}/{table}"
    data = json.dumps({'fields': fields}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print('ERROR:', e.code, e.read().decode())
        return None

# ── 1. Simular login con DNI ──────────────────────────────────────────────
dni = '41683585'
print(f"\n[1] Simulando login para DNI {dni}...")
data = get(f"{BASE}/Empleados?filterByFormula={{DNI}}='{dni}'&maxRecords=1")
if not data.get('records'):
    print("DNI no encontrado"); sys.exit(1)
solicitante_record_id = data['records'][0]['id']
nombre_solicitante = data['records'][0]['fields'].get('NOMBRE CORTO', 'N/A')
print(f"    OK → {nombre_solicitante} (record_id: {solicitante_record_id})")

# ── 2. Cargar lista APROBADOR_1 (Residentes) ─────────────────────────────
print("\n[2] Obteniendo lista de RESIDENTES (APROBADOR_1)...")
data = get(f"{BASE}/Empleados?filterByFormula={{APROBADORES}}='APROBADOR_1'")
residentes = [{'id': r['id'], 'nombre': r['fields'].get('NOMBRE CORTO', '?')} for r in data.get('records', [])]
for r in residentes:
    print(f"    • {r['nombre']}  →  {r['id']}")
if not residentes:
    print("    (ninguno encontrado)")

# ── 3. Cargar lista APROBADOR_2 (Aprobadores) ────────────────────────────
print("\n[3] Obteniendo lista de APROBADORES (APROBADOR_2)...")
data = get(f"{BASE}/Empleados?filterByFormula={{APROBADORES}}='APROBADOR_2'")
aprobadores = [{'id': r['id'], 'nombre': r['fields'].get('NOMBRE CORTO', '?')} for r in data.get('records', [])]
for a in aprobadores:
    print(f"    • {a['nombre']}  →  {a['id']}")
if not aprobadores:
    print("    (ninguno encontrado)"); sys.exit(1)

# ── 4. Simular elección del usuario ──────────────────────────────────────
residente_elegido  = residentes[0] if residentes else None
aprobador_elegido  = aprobadores[0]
print(f"\n[4] Usuario elige:")
print(f"    RESIDENTE  → {residente_elegido['nombre'] if residente_elegido else 'No aplica'}")
print(f"    APROBADOR  → {aprobador_elegido['nombre']}")

# ── 5. Crear solicitud en Airtable ───────────────────────────────────────
print("\n[5] Creando solicitud en solicitudes_caja...")
fields = {
    'NOMBRE':        nombre_solicitante,
    'PLAZO':         'Del 01/05 al 31/05',
    'MOTIVO':        'Prueba automatizada con RESIDENTE y APROBADOR',
    'MONEDA':        'PEN',
    'OBRA':          'Test Obra',
    'TOTAL_GENERAL': 500.0,
    'TIPO_GASTO':    'CAJA CHICA',
    'DETALLE_GASTO': 'Verificacion del flujo completo de campos',
    'SOLICITANTE':   [solicitante_record_id],
    'APROBADOR':     [aprobador_elegido['id']],
}
if residente_elegido:
    fields['RESIDENTE'] = [residente_elegido['id']]

result = post('solicitudes_caja', fields)
if result:
    print(f"\n✅ SOLICITUD CREADA EXITOSAMENTE")
    print(f"   ID Airtable   : {result['id']}")
    print(f"   NOMBRE        : {result['fields'].get('NOMBRE')}")
    print(f"   SOLICITANTE   : {result['fields'].get('DNI (from SOLICITANTE)', 'N/A')}")
    print(f"   RESIDENTE     : {result['fields'].get('NOMBRE CORTO (from RESIDENTE)', 'N/A')}")
    print(f"   APROBADOR     : {result['fields'].get('NOMBRE CORTO (from APROBADOR)', 'N/A')}")
    print(f"   LINK          : {result['fields'].get('LINK', '')}")
