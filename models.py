"""Modelos de la base de datos para el CRM de Virtualder.

El ORM (SQLAlchemy) mantiene los datos separados de la interfaz.
Para cambiar a PostgreSQL en un servidor, solo se modifica la
configuracion `SQLALCHEMY_DATABASE_URI` en app.py; estos modelos
no cambian.
"""
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Dias habiles que se agregan al pago/entrega de informacion para calcular
# la fecha de entrega final. Es una regla de negocio de la agencia.
DIAS_ENTREGA_FINAL = 30

# Feriados mexicanos fijos (no laborables) para el calculo de dias habiles.
# ponytail: lista simplificada de feriados oficiales; si se necesita precision
# extrema, reemplazar con una tabla en BD o una API como https://www.feriados.mx/
FERIADOS_MEXICO = frozenset({
    (1, 1),    # Ano Nuevo
    (2, 5),    # Constitucion (primer lunes de feb — se usa el fijo)
    (3, 21),   # Natalicio de Benito Juarez (tercer lunes de mar — fijo)
    (5, 1),    # Dia del Trabajo
    (9, 16),   # Independencia
    (11, 20),  # Revolucion (tercer lunes de nov — fijo)
    (12, 25),  # Navidad
})


# ---------------------------------------------------------------------------
# Tabla: Usuarios para autenticación
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"


# ---------------------------------------------------------------------------
# Tabla 1: Contacto (proviene de "ContactDetails")
# ---------------------------------------------------------------------------
class Contacto(db.Model):
    __tablename__ = "contactos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, index=True)
    compania = db.Column(db.String(150))
    puesto = db.Column(db.String(120))
    telefono = db.Column(db.String(40))
    email = db.Column(db.String(150))
    ciudad = db.Column(db.String(100))
    estado = db.Column(db.String(100))
    notas = db.Column(db.Text)
    # Fecha en la que se recibio el lead (lo que reflejan las notas).
    fecha_recepcion_lead = db.Column(db.Date)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Contacto {self.id} {self.nombre}>"


# ---------------------------------------------------------------------------
# Tabla 2: Cliente / CRM (proviene de "CRM")
# ---------------------------------------------------------------------------
class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    contacto_id = db.Column(db.Integer, db.ForeignKey("contactos.id"))
    nombre = db.Column(db.String(150), nullable=False, index=True)
    compania = db.Column(db.String(150))
    puesto = db.Column(db.String(120))
    sitio_web = db.Column(db.String(200))
    telefono = db.Column(db.String(40))
    email = db.Column(db.String(150))
    venta_estimada = db.Column(db.Float, default=0)
    ultimo_contacto = db.Column(db.Date)
    proximo_contacto = db.Column(db.Date, index=True)
    accion = db.Column(db.String(80))
    lead_status = db.Column(db.String(60))
    lead_source = db.Column(db.String(60))
    status_pago = db.Column(db.String(80))
    veces_contactado = db.Column(db.Integer, default=0)

    # Contrato (obligatorio en algunos casos, en otros no).
    requiere_contrato = db.Column(db.Boolean, default=False)
    contrato_path = db.Column(db.String(300))

    # Fechas de entrega.
    # Preliminar = hito interno de borrador (lo define el usuario).
    fecha_entrega_preliminar = db.Column(db.Date)
    # Fecha en la que el cliente pago y/o entrego la informacion.
    fecha_pago = db.Column(db.Date)
    fecha_info_entregada = db.Column(db.Date)

    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    contacto = db.relationship("Contacto", backref="clientes")

    @staticmethod
    def _sumar_dias_habiles(desde, n):
        """Suma `n` dias habiles a la fecha `desde` (no incluye sab/dom/feriados)."""
        actual = desde
        while n > 0:
            actual += timedelta(days=1)
            if actual.weekday() >= 5:  # sabado=5, domingo=6
                continue
            if (actual.month, actual.day) in FERIADOS_MEXICO:
                continue
            n -= 1
        return actual

    def fecha_entrega_final(self):
        """MAX(fecha_pago, fecha_info_entregada) + 30 dias habiles.

        No cuenta sabados, domingos ni feriados mexicanos oficiales.
        Devuelve None si no hay ninguna de las dos fechas o si el
        cliente ya esta entregado (lead_status = "<> Active").
        """
        if self.lead_status == "<> Active":
            return None
        fechas = [f for f in (self.fecha_pago, self.fecha_info_entregada) if f]
        if not fechas:
            return None
        base = max(fechas)
        return self._sumar_dias_habiles(base, DIAS_ENTREGA_FINAL)

    def dias_restantes(self):
        """Dias que faltan para la entrega final respecto a hoy.

        Negativo = entregas vencidas. None si no hay fecha final.
        """
        final = self.fecha_entrega_final()
        if not final:
            return None
        return (final - date.today()).days

    def dias_sin_contacto(self):
        if not self.ultimo_contacto:
            return None
        return (date.today() - self.ultimo_contacto).days

    def __repr__(self):
        return f"<Cliente {self.id} {self.nombre}>"


# ---------------------------------------------------------------------------
# Tabla 3: Registro de Contacto (proviene de "ContactLog")
# ---------------------------------------------------------------------------
class RegistroContacto(db.Model):
    __tablename__ = "registros_contacto"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, index=True)
    hora = db.Column(db.String(20))
    contacto_id = db.Column(db.Integer, db.ForeignKey("contactos.id"))
    nombre_cliente = db.Column(db.String(150))
    proposito = db.Column(db.String(80))
    metodo = db.Column(db.String(60))
    notas = db.Column(db.Text)

    contacto = db.relationship("Contacto", backref="registros")

    def __repr__(self):
        return f"<RegistroContacto {self.id} {self.nombre_cliente}>"


# ---------------------------------------------------------------------------
# Tabla 4: Venta (proviene de "SalesLog")
# ---------------------------------------------------------------------------
class Venta(db.Model):
    __tablename__ = "ventas"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, index=True)
    contacto_id = db.Column(db.Integer, db.ForeignKey("contactos.id"))
    nombre_cliente = db.Column(db.String(150))
    monto = db.Column(db.Float, default=0)
    saldo = db.Column(db.Float, default=0)
    servicio = db.Column(db.String(150))
    num_factura = db.Column(db.String(40))
    # Algunos clientes solicitan factura.
    solicita_factura = db.Column(db.Boolean, default=False)
    factura_path = db.Column(db.String(300))
    notas = db.Column(db.Text)

    contacto = db.relationship("Contacto", backref="ventas")

    def __repr__(self):
        return f"<Venta {self.id} {self.nombre_cliente}>"


# ---------------------------------------------------------------------------
# Tabla 5: Proyecto — múltiples proyectos por cliente
# ---------------------------------------------------------------------------
class Proyecto(db.Model):
    __tablename__ = "proyectos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    servicio = db.Column(db.String(150))
    monto = db.Column(db.Float, default=0)
    fecha_entrega_final = db.Column(db.Date)
    status = db.Column(db.String(60), default="En progreso")
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Cliente", backref=db.backref("proyectos", lazy="dynamic", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<Proyecto {self.id} {self.nombre} (cliente {self.cliente_id})>"


# ---------------------------------------------------------------------------
# Tabla 6: Cuenta de Pago (proviene de "Settings" -> datos de pago)
# ---------------------------------------------------------------------------
class CuentaPago(db.Model):
    __tablename__ = "cuentas_pago"

    id = db.Column(db.Integer, primary_key=True)
    titular = db.Column(db.String(150))
    numero_cuenta = db.Column(db.String(40))
    clabe = db.Column(db.String(40))
    banco = db.Column(db.String(60))

    def __repr__(self):
        return f"<CuentaPago {self.id} {self.banco}>"


# ---------------------------------------------------------------------------
# Tabla 6: Configuracion (clave-valor)
#    Almacena las listas desplegables, moneda y umbrales.
# ---------------------------------------------------------------------------
class Configuracion(db.Model):
    __tablename__ = "configuracion"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(60), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)  # JSON para listas

    def __repr__(self):
        return f"<Config {self.clave}>"


# ---------------------------------------------------------------------------
# Claves de configuracion por defecto (usadas en la migracion y settings)
# ---------------------------------------------------------------------------
CONFIG_DEFAULTS = {
    # Listas para los menús desplegables del CRM.
    "lead_status": [
        "<> Active",
        "👍 Won",
        "👎 Loss",
        "❄ Cold",
        "♨ Warm",
        "🔥 Hot",
        "🌐︎ Development",
    ],
    "lead_source": ["Email", "Referido", "Website", "Google Ads", "Social"],
    "acciones": [
        "Approach",
        "Contacto",
        "Seguimiento",
        "Cierre",
        "Monitoreo",
        "Pendiente",
    ],
    "status_pago": ["Pendiente", "Pagado", "Anticipado", "Por pagar"],
    "propositos_contacto": [
        "Follow-Up",
        "Approaching",
        "Closing",
        "Monitoring",
        "Introduction",
    ],
    "metodos_contacto": ["WhatsApp", "Email", "Teléfono", "Reunión", "Otro"],
    "servicios": [
        "Landing Page Básica",
        "Landing Page Premium",
        "E-Commerce",
        "Sitio Web",
        "Redes Sociales",
        "Otro",
    ],
    # Moneda configurable desde Configuración.
    "moneda": "MXN",
    # Umbrales de días para formato condicional (como en Excel).
    "dias_desde_ultimo_contacto": 5,
    "dias_hasta_proximo_contacto": 5,
}
