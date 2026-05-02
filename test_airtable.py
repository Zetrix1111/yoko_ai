import json, urllib.request

env = {}
with open('.env.local') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v

url = f"https://api.airtable.com/v0/{env['AIRTABLE_BASE_ID']}/solicitudes_caja"
headers = {
    'Authorization': f"Bearer {env['AIRTABLE_TOKEN']}",
    'Content-Type': 'application/json'
}

fields = {
    'NOMBRE': 'Test User',
    'PLAZO': '10 dias',
    'MOTIVO': 'Test motivo',
    'MONEDA': 'PEN',
    'OBRA': 'Test Obra',
    'TOTAL_GENERAL': 100.0,
    'TIPO_GASTO': 'CAJA CHICA',
    'DETALLE_GASTO': 'Test detalle',
    'ESTADO': 'PENDIENTE_APROBACION_RESIDENTE'
}

req = urllib.request.Request(url, data=json.dumps({'fields': fields}).encode('utf-8'), headers=headers, method='POST')
try:
    with urllib.request.urlopen(req) as response:
        print('SUCCESS:', response.read().decode())
except urllib.error.HTTPError as e:
    print('ERROR:', e.code, e.read().decode())
