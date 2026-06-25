"""Migración: importa los datos del Excel CRM-Virtualder.xlsx a la base SQLite.

Uso:  python migrate.py

Es idempotente: si la base ya tiene datos, pregunta antes de continuar.
Mapea las hojas así:
  ContactDetails -> Contacto (lista maestra de contactos)
  CRM            -> Cliente  (vinculado por nombre al Contacto)
  ContactLog     -> RegistroContacto
  SalesLog       -> Venta
  Settings       -> Configuracion (listas) + CuentaPago (datos de pago)
"""
import os
import sys
import warnings
from datetime import datetime, date, time
from pathlib import Path

warnings.filterwarnings("ignore")

from openpyxl import load_workbook

# Importar Flask + modelos
from app import app, db, set_config
from models import (
    Contacto, Cliente, RegistroContacto, Venta, CuentaPago,
    Configuracion, CONFIG_DEFAULTS,
)

RUTA_EXCEL = r"E:\Documentos\CRM-Virtualder.xlsx"


# ---------------------------------------------------------------------------
# Helpers de conversión
# ---------------------------------------------------------------------------
def a_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    if s in ("", "N/A", "TBD", "None"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def a_texto(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s if s and s not in ("N/A", "TBD", "None") else None


def a_numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).replace("$", "").replace(",", "").strip()
    if s in ("", "N/A", "TBD"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def a_hora(valor):
    """Convierte time/str a texto legible de hora."""
    if valor is None:
        return None
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    s = str(valor).strip()
    return s if s else None


def limpiar_status(valor):
    """Quita emojis/espacios extra del status de pago (ej. 'Anticipado 3,950')."""
    if not valor:
        return None
    s = str(valor).strip()
    # Casos como "Anticipado 3,950" -> conservar tal cual (informativo)
    return s


# ---------------------------------------------------------------------------
# Importadores por hoja
# ---------------------------------------------------------------------------
def importar_contactos(ws):
    """ContactDetails: A=Nombre B=Compañía C=Puesto D=Tel E=Email F=Ciudad G=Estado H=Notas"""
    cont = 0
    for r in range(5, ws.max_row + 1):
        nombre = a_texto(ws.cell(row=r, column=1).value)
        if not nombre:
            continue
        # Evitar duplicados por nombre
        existe = Contacto.query.filter_by(nombre=nombre).first()
        if existe:
            continue
        c = Contacto(
            nombre=nombre,
            compania=a_texto(ws.cell(row=r, column=2).value),
            puesto=a_texto(ws.cell(row=r, column=3).value),
            telefono=a_texto(ws.cell(row=r, column=4).value),
            email=a_texto(ws.cell(row=r, column=5).value),
            ciudad=a_texto(ws.cell(row=r, column=6).value),
            estado=a_texto(ws.cell(row=r, column=7).value),
            notas=a_texto(ws.cell(row=r, column=8).value),
        )
        db.session.add(c)
        cont += 1
    db.session.commit()
    return cont


def importar_clientes_crm(ws):
    """CRM: A=Nombre B=Compañía C=Puesto D=Sitio E=Tel F=Email G=VentaEst
    H=ÚltContacto I=Acción J=PróxContacto K=DíasSinContacto L=LeadStatus
    M=Fuente N=FechaEntregable O=FechaCaducidad P=StatusPago Q=Notas"""
    cont = 0
    for r in range(5, ws.max_row + 1):
        nombre = a_texto(ws.cell(row=r, column=1).value)
        if not nombre:
            continue
        if Cliente.query.filter_by(nombre=nombre).first():
            continue
        # Vincular con contacto si existe
        contacto = Contacto.query.filter_by(nombre=nombre).first()

        # Mapeo de fechas:
        #  N (Fecha de entregable) -> preliminar (hito interno de borrador)
        #  O (Fecha de caducidad)  -> fecha_pago (para que la entrega final
        #    calculada = O + 30 días siga siendo significativa en los datos
        #    migrados, ya que el Excel no tenía fecha de pago explícita)
        fecha_preliminar = a_fecha(ws.cell(row=r, column=14).value)
        fecha_caducidad = a_fecha(ws.cell(row=r, column=15).value)

        c = Cliente(
            contacto_id=contacto.id if contacto else None,
            nombre=nombre,
            compania=a_texto(ws.cell(row=r, column=2).value),
            puesto=a_texto(ws.cell(row=r, column=3).value),
            sitio_web=a_texto(ws.cell(row=r, column=4).value),
            telefono=a_texto(ws.cell(row=r, column=5).value),
            email=a_texto(ws.cell(row=r, column=6).value),
            venta_estimada=a_numero(ws.cell(row=r, column=7).value) or 0,
            ultimo_contacto=a_fecha(ws.cell(row=r, column=8).value),
            proximo_contacto=a_fecha(ws.cell(row=r, column=10).value),
            accion=a_texto(ws.cell(row=r, column=9).value),
            lead_status=a_texto(ws.cell(row=r, column=12).value),
            lead_source=a_texto(ws.cell(row=r, column=13).value),
            status_pago=limpiar_status(ws.cell(row=r, column=16).value),
            fecha_entrega_preliminar=fecha_preliminar,
            fecha_pago=fecha_caducidad,  # ver comentario arriba
            notas=a_texto(ws.cell(row=r, column=17).value),
        )
        db.session.add(c)
        cont += 1
    db.session.commit()
    return cont


def importar_contact_log(ws):
    """ContactLog: A=Fecha B=Hora C=Cliente D=Propósito E=Método F=Notas"""
    cont = 0
    for r in range(5, ws.max_row + 1):
        fecha = a_fecha(ws.cell(row=r, column=1).value)
        nombre = a_texto(ws.cell(row=r, column=3).value)
        if not fecha and not nombre:
            continue
        contacto = None
        if nombre:
            contacto = Contacto.query.filter_by(nombre=nombre).first()
        reg = RegistroContacto(
            fecha=fecha or date.today(),
            hora=a_hora(ws.cell(row=r, column=2).value),
            contacto_id=contacto.id if contacto else None,
            nombre_cliente=nombre,
            proposito=a_texto(ws.cell(row=r, column=4).value),
            metodo=a_texto(ws.cell(row=r, column=5).value),
            notas=a_texto(ws.cell(row=r, column=6).value),
        )
        db.session.add(reg)
        cont += 1
    db.session.commit()
    return cont


def importar_sales_log(ws):
    """SalesLog: A=Venta(fecha) B=Cliente C=Saldo(monto) D=Servicio E=#Factura F=Notas"""
    cont = 0
    for r in range(5, ws.max_row + 1):
        fecha = a_fecha(ws.cell(row=r, column=1).value)
        nombre = a_texto(ws.cell(row=r, column=2).value)
        # Filtrar filas de instrucciones (texto, no fecha)
        if not fecha and not nombre:
            continue
        if fecha is None and nombre and len(nombre) > 40:
            continue  # fila de instrucciones
        monto = a_numero(ws.cell(row=r, column=3).value) or 0
        notas = a_texto(ws.cell(row=r, column=6).value) or ""
        num_factura = ws.cell(row=r, column=5).value
        num_factura = str(int(num_factura)) if isinstance(num_factura, (int, float)) else a_texto(num_factura)

        # Saldo: si las notas indican "por pagar"/"pendiente", el saldo = monto
        notas_lower = notas.lower()
        saldo = monto if ("por pagar" in notas_lower or "pendiente" in notas_lower) else 0

        contacto = Contacto.query.filter_by(nombre=nombre).first() if nombre else None

        v = Venta(
            fecha=fecha or date.today(),
            contacto_id=contacto.id if contacto else None,
            nombre_cliente=nombre,
            monto=monto,
            saldo=saldo,
            servicio=a_texto(ws.cell(row=r, column=4).value),
            num_factura=num_factura,
            solicita_factura=bool(num_factura),
            notas=notas or None,
        )
        db.session.add(v)
        cont += 1
    db.session.commit()
    return cont


def importar_settings(ws):
    """Settings: listas desplegables + cuentas de pago."""
    # Listas (columnas A=LeadStatus, C=LeadSource)
    lead_status = []
    for r in range(3, 12):
        v = a_texto(ws.cell(row=r, column=1).value)
        if v:
            lead_status.append(v)
    lead_source = []
    for r in range(3, 12):
        v = a_texto(ws.cell(row=r, column=3).value)
        if v:
            lead_source.append(v)
    if lead_status:
        set_config("lead_status", lead_status)
    if lead_source:
        set_config("lead_source", lead_source)

    # Cuentas de pago: buscar bloques "Datos de pago:" en columna G
    cuentas = 0
    for r in range(1, ws.max_row + 1):
        val = ws.cell(row=r, column=7).value
        if val and "datos de pago" in str(val).lower():
            # Las 3 filas siguientes: titular, cuenta, clabe, banco (en G)
            titular = a_texto(ws.cell(row=r + 1, column=7).value)
            cuenta = ws.cell(row=r + 2, column=7).value
            clabe = ws.cell(row=r + 3, column=7).value
            banco = ws.cell(row=r + 4, column=7).value
            # Extraer valores limpios (quitar prefijos "No.de cuenta:")
            cuenta_limpia = str(cuenta).split(":")[-1].strip() if cuenta else None
            clabe_limpia = str(clabe).split(":")[-1].strip() if clabe else None
            banco_limpio = str(banco).split(":")[-1].strip() if banco else None
            if titular and banco_limpio:
                if not CuentaPago.query.filter_by(banco=banco_limpio, titular=titular).first():
                    db.session.add(CuentaPago(
                        titular=titular,
                        numero_cuenta=cuenta_limpia,
                        clabe=clabe_limpia,
                        banco=banco_limpio,
                    ))
                    cuentas += 1
    db.session.commit()
    return cuentas, lead_status, lead_source


# ---------------------------------------------------------------------------
# Rutina principal
# ---------------------------------------------------------------------------
def main():
    if not Path(RUTA_EXCEL).exists():
        print(f"ERROR: No se encontró el archivo {RUTA_EXCEL}")
        sys.exit(1)

    with app.app_context():
        db.create_all()

        # Cargar configuración por defecto si está vacía
        if Configuracion.query.count() == 0:
            for clave, valor in CONFIG_DEFAULTS.items():
                set_config(clave, valor)
            db.session.commit()

        # Verificar si ya hay datos
        total_existentes = (Contacto.query.count() + Cliente.query.count())
        if total_existentes > 0:
            print(f"La base ya contiene datos ({Contacto.query.count()} contactos, "
                  f"{Cliente.query.count()} clientes).")
            resp = input("¿Reimportar de todos modos? Esto DUPLICARÁ los registros. (s/N): ")
            if resp.strip().lower() not in ("s", "si", "sí", "y", "yes"):
                print("Migración cancelada.")
                return

        print(f"\nLeyendo: {RUTA_EXCEL}")
        wb = load_workbook(RUTA_EXCEL, data_only=True)

        print("\nImportando ContactDetails -> Contactos ...")
        n = importar_contactos(wb["ContactDetails"])
        print(f"  + {n} contactos")

        print("Importando CRM -> Clientes ...")
        n = importar_clientes_crm(wb["CRM"])
        print(f"  + {n} clientes")

        print("Importando ContactLog -> Registros de contacto ...")
        n = importar_contact_log(wb["ContactLog"])
        print(f"  + {n} registros")

        print("Importando SalesLog -> Ventas ...")
        n = importar_sales_log(wb["SalesLog"])
        print(f"  + {n} ventas")

        print("Importando Settings -> Configuración y cuentas de pago ...")
        nc, ls, src = importar_settings(wb["Settings"])
        print(f"  + {nc} cuentas de pago")
        if ls:
            print(f"  · Listas: {len(ls)} lead status, {len(src)} lead source")

        print("\n✅ Migración completada.")
        print(f"   Total: {Contacto.query.count()} contactos, "
              f"{Cliente.query.count()} clientes, "
              f"{Venta.query.count()} ventas, "
              f"{RegistroContacto.query.count()} registros de contacto.")


if __name__ == "__main__":
    main()
