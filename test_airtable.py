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

# 1. Simulate login for a DNI (e.g. 41683585 or 72682425 as seen in screenshot)
url_empleados = f"https://api.airtable.com/v0/{env['AIRTABLE_BASE_ID']}/Empleados?filterByFormula=NOT({{APROBADORES}}%3D'')"
req_empleados = urllib.request.Request(url_empleados, headers=headers, method='GET')
try:
    with urllib.request.urlopen(req_empleados) as res:
        data = json.loads(res.read().decode())
        print("Empleados con APROBADORES:")
        for r in data.get('records', []):
            f = r['fields']
            print(r['id'], f.get('NOMBRE CORTO'), f.get('APROBADORES'))
except Exception as e:
    print('ERROR:', e)
