"""
Tool: yoko_procesar_archivos

Procesa un lote de comprobantes peruanos (factura, boleta, NC, ND, RH, ticket,
boleto aéreo) y devuelve los datos contables estructurados. Lo ejecuta el
orquestador llamando a `POST /api/facturas?action=procesar-chat`.
"""

TOOL_DEFINITION: dict = {
    "name": "yoko_procesar_archivos",
    "description": (
        "Procesa comprobantes de pago peruanos (factura, boleta, NC, ND, RH, "
        "ticket, boleto aéreo) en formato PDF/JPG/PNG/WEBP. Acepta hasta 50 "
        "archivos por lote. Devuelve datos estructurados: proveedor, RUC, "
        "serie, monto, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo": {
                "type": "string",
                "enum": ["compra", "venta"],
                "description": "Si los comprobantes son de compras o de ventas.",
            },
            "mes": {
                "type": "string",
                "pattern": r"^\d{4}-\d{2}$",
                "description": "Mes contable de los comprobantes en formato YYYY-MM.",
            },
        },
        "required": ["tipo", "mes"],
    },
}
