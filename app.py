"""CRM Virtualder — Aplicación web personal.

Ejecutar con:  python app.py
Abrir en el navegador: http://localhost:5000
"""
import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    jsonify, send_from_directory, abort,
)
from werkzeug.utils import secure_filename

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)

from models import (
    db, Contacto, Cliente, Proyecto, RegistroContacto, Venta, CuentaPago, Configuracion, User,
    CONFIG_DEFAULTS, DIAS_ENTREGA_FINAL,
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "virtualder-crm-secreto-local"
# SQLite local: un solo archivo portable. Para un servidor, cambiar esta URI
# por la de PostgreSQL y listo.
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{(BASE_DIR / 'crm.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

db.init_app(app)

# ===========================================================================
# Autenticación (Flask-Login)
# ===========================================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ===========================================================================
# Utilidades
# ===========================================================================
def parsear_fecha(valor):
    """Convierte strings/None/datetime a date o None."""
    if valor in (None, "", "None", "N/A", "TBD"):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    valor = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def parsear_monto(valor):
    """Convierte strings/None a float o None."""
    if valor in (None, "", "None", "N/A", "TBD"):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    valor = str(valor).replace("$", "").replace(",", "").strip()
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def parsear_bool(valor):
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("1", "true", "yes", "si", "sí", "on")


def guardar_archivo(archivo, prefijo="doc"):
    """Guarda un archivo subido y devuelve su ruta relativa o None."""
    if not archivo or not archivo.filename:
        return None
    nombre = secure_filename(archivo.filename)
    if not nombre:
        nombre = f"{prefijo}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # Prefijo para evitar colisiones.
    nombre_final = f"{prefijo}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{nombre}"
    ruta = UPLOAD_FOLDER / nombre_final
    archivo.save(str(ruta))
    return nombre_final


def get_config(clave, default=None):
    cfg = Configuracion.query.filter_by(clave=clave).first()
    if not cfg:
        return default
    try:
        return json.loads(cfg.valor)
    except (json.JSONDecodeError, TypeError):
        return cfg.valor


def set_config(clave, valor):
    """Guarda un valor de configuracion (lo serializa a JSON si hace falta)."""
    if isinstance(valor, (list, dict, bool)) or valor is None:
        valor_str = json.dumps(valor)
    else:
        valor_str = str(valor)
    cfg = Configuracion.query.filter_by(clave=clave).first()
    if cfg:
        cfg.valor = valor_str
    else:
        cfg = Configuracion(clave=clave, valor=valor_str)
        db.session.add(cfg)


def contexto_global():
    """Datos disponibles en todas las plantillas (moneda, listas)."""
    moneda = get_config("moneda", "MXN")
    simbolo = "$" if moneda in ("MXN", "USD") else ""
    return {
        "moneda": moneda,
        "simbolo_moneda": simbolo,
        "lead_status_lista": get_config("lead_status", CONFIG_DEFAULTS["lead_status"]),
        "lead_source_lista": get_config("lead_source", CONFIG_DEFAULTS["lead_source"]),
        "acciones_lista": get_config("acciones", CONFIG_DEFAULTS["acciones"]),
        "status_pago_lista": get_config("status_pago", CONFIG_DEFAULTS["status_pago"]),
        "propositos_lista": get_config("propositos_contacto", CONFIG_DEFAULTS["propositos_contacto"]),
        "metodos_lista": get_config("metodos_contacto", CONFIG_DEFAULTS["metodos_contacto"]),
        "servicios_lista": get_config("servicios", CONFIG_DEFAULTS["servicios"]),
        "anio_actual": date.today().year,
    }


@app.context_processor
def inject_globals():
    ctx = contexto_global()
    # 'hoy' disponible en todas las plantillas (para comparaciones de fecha).
    ctx["hoy"] = date.today()
    return ctx


def formatear_moneda(monto, simbolo="$"):
    if monto is None:
        monto = 0
    return f"{simbolo}{monto:,.2f}"


# ===========================================================================
# Rutas principales
# ===========================================================================
@app.route("/")
@login_required
def dashboard():
    """Panel principal con alertas, KPIs y entregas próximas."""
    hoy = date.today()

    # --- Alertas de próximos contactos (hoy, vencidos y próximos) ---
    # Excluir clientes "👎 Loss" — son ventas perdidas sin seguimiento.
    proximos = Cliente.query.filter(
        Cliente.proximo_contacto.isnot(None),
        Cliente.lead_status != "👎 Loss",
    ).all()

    def estado_contacto(c):
        if c.proximo_contacto < hoy:
            return ("vencido", c.proximo_contacto)
        elif c.proximo_contacto == hoy:
            return ("hoy", c.proximo_contacto)
        elif c.proximo_contacto <= hoy + timedelta(days=7):
            return ("proximo", c.proximo_contacto)
        return ("futuro", c.proximo_contacto)

    alertas = []
    for c in proximos:
        est, f = estado_contacto(c)
        if est in ("vencido", "hoy", "proximo"):
            alertas.append((est, c))
    alertas.sort(key=lambda x: x[1].proximo_contacto)

    # --- Oportunidades activas ---
    oportunidades = Cliente.query.filter(
        Cliente.lead_status.notin_(["👎 Loss"])
    ).all()

    # --- Saldos pendientes ---
    saldos = [v for v in Venta.query.all() if (v.saldo or 0) > 0]
    total_saldos = sum(v.saldo for v in saldos)

    # --- Entregas próximas / activas (con fecha de entrega final) ---
    entregas = []
    for c in Cliente.query.all():
        final = c.fecha_entrega_final()
        dias = c.dias_restantes()
        if final and dias is not None:
            entregas.append((c, final, dias))
    entregas.sort(key=lambda x: x[1])

    # --- KPIs ---
    kpis = {
        "oportunidades": len(oportunidades),
        "contactos_alerta": len(alertas),
        "saldos_pendientes": len(saldos),
        "total_saldos": total_saldos,
        "entregas_activas": len([e for e in entregas if e[2] >= 0]),
        "entregas_vencidas": len([e for e in entregas if e[2] < 0]),
    }

    # --- Ventas por mes (últimos 6 meses) para mini gráfica ---
    ventas = Venta.query.order_by(Venta.fecha).all()
    meses = {}
    for v in ventas:
        if v.fecha:
            clave = v.fecha.strftime("%Y-%m")
            meses[clave] = meses.get(clave, 0) + (v.monto or 0)
    # Últimos 6 meses con datos
    claves_ordenadas = sorted(meses.keys())
    ultimos = claves_ordenadas[-6:]
    labels_meses = [datetime.strptime(k, "%Y-%m").strftime("%b %Y") for k in ultimos]
    datos_meses = [meses[k] for k in ultimos]

    return render_template(
        "dashboard.html",
        alertas=alertas, kpis=kpis, entregas=entregas,
        ventas=ventas, saldos=saldos,
        labels_meses=labels_meses, datos_meses=datos_meses,
        hoy=hoy,
    )


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------
@app.route("/crm")
@login_required
def crm():
    # Multi-select filters: get all values for each parameter
    status_filter = request.args.getlist("status")
    source_filter = request.args.getlist("source")

    q = Cliente.query
    # Filter out empty string ("Todos") — treat as no filter
    active_statuses = [s for s in status_filter if s]
    active_sources = [s for s in source_filter if s]

    if active_statuses:
        q = q.filter(Cliente.lead_status.in_(active_statuses))
    if active_sources:
        q = q.filter(Cliente.lead_source.in_(active_sources))

    clientes = q.order_by(Cliente.proximo_contacto.is_(None), Cliente.proximo_contacto).all()
    return render_template("crm.html", clientes=clientes,
                           status_filtro=active_statuses, source_filtro=active_sources)


@app.route("/crm/nuevo", methods=["POST"])
@login_required
def crm_nuevo():
    c = Cliente(
        nombre=request.form.get("nombre", "").strip(),
        compania=request.form.get("compania", "").strip() or None,
        puesto=request.form.get("puesto", "").strip() or None,
        sitio_web=request.form.get("sitio_web", "").strip() or None,
        telefono=request.form.get("telefono", "").strip() or None,
        email=request.form.get("email", "").strip() or None,
        venta_estimada=parsear_monto(request.form.get("venta_estimada")),
        ultimo_contacto=parsear_fecha(request.form.get("ultimo_contacto")),
        proximo_contacto=parsear_fecha(request.form.get("proximo_contacto")),
        accion=request.form.get("accion") or None,
        lead_status=request.form.get("lead_status") or None,
        lead_source=request.form.get("lead_source") or None,
        status_pago=request.form.get("status_pago") or None,
        requiere_contrato=parsear_bool(request.form.get("requiere_contrato")),
        fecha_entrega_preliminar=parsear_fecha(request.form.get("fecha_entrega_preliminar")),
        fecha_pago=parsear_fecha(request.form.get("fecha_pago")),
        fecha_info_entregada=parsear_fecha(request.form.get("fecha_info_entregada")),
        notas=request.form.get("notas", "").strip() or None,
    )
    if not c.nombre:
        flash("El nombre del cliente es obligatorio.", "error")
        return redirect(url_for("crm"))
    # Contrato adjunto
    contrato = request.files.get("contrato")
    if contrato and contrato.filename:
        c.contrato_path = guardar_archivo(contrato, "contrato")
    db.session.add(c)
    db.session.commit()
    flash(f"Cliente '{c.nombre}' agregado correctamente.", "success")
    # Preserve filters
    filtros = request.form.get("_filtros", "")
    return redirect(url_for("crm") + ("?" + filtros if filtros else ""))


@app.route("/crm/<int:cid>/editar", methods=["POST"])
@login_required
def crm_editar(cid):
    c = Cliente.query.get_or_404(cid)
    c.nombre = request.form.get("nombre", "").strip() or c.nombre
    c.compania = request.form.get("compania", "").strip() or None
    c.puesto = request.form.get("puesto", "").strip() or None
    c.sitio_web = request.form.get("sitio_web", "").strip() or None
    c.telefono = request.form.get("telefono", "").strip() or None
    c.email = request.form.get("email", "").strip() or None
    c.venta_estimada = parsear_monto(request.form.get("venta_estimada"))
    c.ultimo_contacto = parsear_fecha(request.form.get("ultimo_contacto"))
    c.proximo_contacto = parsear_fecha(request.form.get("proximo_contacto"))
    c.accion = request.form.get("accion") or None
    c.lead_status = request.form.get("lead_status") or None
    c.lead_source = request.form.get("lead_source") or None
    c.status_pago = request.form.get("status_pago") or None
    c.requiere_contrato = parsear_bool(request.form.get("requiere_contrato"))
    c.fecha_entrega_preliminar = parsear_fecha(request.form.get("fecha_entrega_preliminar"))
    c.fecha_pago = parsear_fecha(request.form.get("fecha_pago"))
    c.fecha_info_entregada = parsear_fecha(request.form.get("fecha_info_entregada"))
    c.notas = request.form.get("notas", "").strip() or None
    # Reemplazar contrato si se sube uno nuevo
    contrato = request.files.get("contrato")
    if contrato and contrato.filename:
        c.contrato_path = guardar_archivo(contrato, "contrato")
    db.session.commit()
    flash(f"Cliente '{c.nombre}' actualizado.", "success")
    # Preserve filters from the form submission
    filtros = request.form.get("_filtros", "")
    return redirect(url_for("crm") + ("?" + filtros if filtros else ""))


@app.route("/crm/<int:cid>/eliminar", methods=["POST"])
@login_required
def crm_eliminar(cid):
    c = Cliente.query.get_or_404(cid)
    nombre = c.nombre
    db.session.delete(c)
    db.session.commit()
    flash(f"Cliente '{nombre}' eliminado.", "success")
    return redirect(url_for("crm"))


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# API: actualización rápida de notas (inline en tabla CRM)
# ---------------------------------------------------------------------------
@app.route("/api/cliente/<int:cid>/notas", methods=["POST"])
def api_cliente_notas(cid):
    """Actualiza solo las notas de un cliente (edición inline)."""
    c = Cliente.query.get_or_404(cid)
    data = request.get_json()
    if data and "notas" in data:
        c.notas = data["notas"].strip() or None
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "Falta campo 'notas'"}), 400


# ---------------------------------------------------------------------------
# API: obtener saldos pendientes de un cliente (vinculado a Ventas)
# ---------------------------------------------------------------------------
@app.route("/api/cliente/<int:cid>/saldos")
def api_cliente_saldos(cid):
    """Devuelve las ventas con saldo pendiente para un cliente."""
    c = Cliente.query.get_or_404(cid)
    ventas = Venta.query.filter(
        Venta.nombre_cliente == c.nombre,
        Venta.saldo > 0,
    ).order_by(Venta.fecha.desc()).all()
    return jsonify([{
        "id": v.id,
        "fecha": v.fecha.strftime("%Y-%m-%d") if v.fecha else "",
        "monto": v.monto or 0,
        "saldo": v.saldo or 0,
        "servicio": v.servicio or "",
    } for v in ventas])


@app.route("/api/cliente/<int:cid>")
def api_cliente(cid):
    """Devuelve los datos de un cliente en JSON para el modal de edición."""
    c = Cliente.query.get_or_404(cid)
    def fmt(f):
        return f.strftime("%Y-%m-%d") if f else ""
    return jsonify({
        "id": c.id,
        "nombre": c.nombre or "",
        "compania": c.compania or "",
        "puesto": c.puesto or "",
        "sitio_web": c.sitio_web or "",
        "telefono": c.telefono or "",
        "email": c.email or "",
        "venta_estimada": c.venta_estimada if c.venta_estimada else "",
        "ultimo_contacto": fmt(c.ultimo_contacto),
        "proximo_contacto": fmt(c.proximo_contacto),
        "accion": c.accion or "",
        "lead_status": c.lead_status or "",
        "lead_source": c.lead_source or "",
        "status_pago": c.status_pago or "",
        "requiere_contrato": c.requiere_contrato or False,
        "fecha_entrega_preliminar": fmt(c.fecha_entrega_preliminar),
        "fecha_pago": fmt(c.fecha_pago),
        "fecha_info_entregada": fmt(c.fecha_info_entregada),
        "contrato_path": c.contrato_path or "",
        "notas": c.notas or "",
    })


# ---------------------------------------------------------------------------
# Proyectos — múltiples proyectos por cliente
# ---------------------------------------------------------------------------
@app.route("/api/cliente/<int:cid>/proyectos")
def proyectos_lista(cid):
    """Devuelve los proyectos de un cliente en JSON."""
    cliente = Cliente.query.get_or_404(cid)
    proyectos = Proyecto.query.filter_by(cliente_id=cid).order_by(Proyecto.creado_en.desc()).all()
    def fmt(f):
        return f.strftime("%Y-%m-%d") if f else ""
    return jsonify([{
        "id": p.id,
        "nombre": p.nombre,
        "servicio": p.servicio or "",
        "monto": p.monto or "",
        "fecha_entrega_final": fmt(p.fecha_entrega_final),
        "status": p.status or "",
    } for p in proyectos])


@app.route("/crm/<int:cid>/proyecto/nuevo", methods=["POST"])
def proyecto_nuevo(cid):
    """Crea un nuevo proyecto para un cliente y devuelve JSON."""
    cliente = Cliente.query.get_or_404(cid)
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "El nombre del proyecto es obligatorio."}), 400
    p = Proyecto(
        cliente_id=cid,
        nombre=nombre,
        servicio=request.form.get("servicio", "").strip() or None,
        monto=parsear_monto(request.form.get("monto")) or 0,
        fecha_entrega_final=parsear_fecha(request.form.get("fecha_entrega_final")),
        status=request.form.get("status") or "En progreso",
    )
    db.session.add(p)
    db.session.commit()
    def fmt(f):
        return f.strftime("%Y-%m-%d") if f else ""
    return jsonify({
        "id": p.id,
        "nombre": p.nombre,
        "servicio": p.servicio or "",
        "monto": p.monto or "",
        "fecha_entrega_final": fmt(p.fecha_entrega_final),
        "status": p.status or "",
    })


@app.route("/crm/proyecto/<int:pid>/eliminar", methods=["POST"])
def proyecto_eliminar(pid):
    """Elimina un proyecto."""
    p = Proyecto.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Contactos (Detalles de Contacto)
# ---------------------------------------------------------------------------
@app.route("/contactos")
@login_required
def contactos():
    contactos = Contacto.query.order_by(Contacto.nombre).all()
    return render_template("contactos.html", contactos=contactos)


@app.route("/contactos/nuevo", methods=["POST"])
@login_required
def contactos_nuevo():
    c = Contacto(
        nombre=request.form.get("nombre", "").strip(),
        compania=request.form.get("compania", "").strip() or None,
        puesto=request.form.get("puesto", "").strip() or None,
        telefono=request.form.get("telefono", "").strip() or None,
        email=request.form.get("email", "").strip() or None,
        ciudad=request.form.get("ciudad", "").strip() or None,
        estado=request.form.get("estado", "").strip() or None,
        notas=request.form.get("notas", "").strip() or None,
        fecha_recepcion_lead=parsear_fecha(request.form.get("fecha_recepcion_lead")),
    )
    if not c.nombre:
        flash("El nombre del contacto es obligatorio.", "error")
        return redirect(url_for("contactos"))
    db.session.add(c)
    db.session.commit()
    flash(f"Contacto '{c.nombre}' agregado.", "success")
    return redirect(url_for("contactos"))


@app.route("/contactos/<int:cid>/editar", methods=["POST"])
@login_required
def contactos_editar(cid):
    c = Contacto.query.get_or_404(cid)
    c.nombre = request.form.get("nombre", "").strip() or c.nombre
    c.compania = request.form.get("compania", "").strip() or None
    c.puesto = request.form.get("puesto", "").strip() or None
    c.telefono = request.form.get("telefono", "").strip() or None
    c.email = request.form.get("email", "").strip() or None
    c.ciudad = request.form.get("ciudad", "").strip() or None
    c.estado = request.form.get("estado", "").strip() or None
    c.notas = request.form.get("notas", "").strip() or None
    c.fecha_recepcion_lead = parsear_fecha(request.form.get("fecha_recepcion_lead"))
    db.session.commit()
    flash(f"Contacto '{c.nombre}' actualizado.", "success")
    return redirect(url_for("contactos"))


@app.route("/contactos/<int:cid>/eliminar", methods=["POST"])
@login_required
def contactos_eliminar(cid):
    c = Contacto.query.get_or_404(cid)
    nombre = c.nombre
    db.session.delete(c)
    db.session.commit()
    flash(f"Contacto '{nombre}' eliminado.", "success")
    return redirect(url_for("contactos"))


@app.route("/api/contacto/<int:cid>")
@login_required
def api_contacto(cid):
    """Devuelve los datos de un contacto en JSON para el modal de edición."""
    c = Contacto.query.get_or_404(cid)
    return jsonify({
        "id": c.id,
        "nombre": c.nombre or "",
        "compania": c.compania or "",
        "puesto": c.puesto or "",
        "telefono": c.telefono or "",
        "email": c.email or "",
        "ciudad": c.ciudad or "",
        "estado": c.estado or "",
        "fecha_recepcion_lead": c.fecha_recepcion_lead.strftime("%Y-%m-%d") if c.fecha_recepcion_lead else "",
        "notas": c.notas or "",
    })


# ---------------------------------------------------------------------------
# Registro de Contacto (log de seguimientos)
# ---------------------------------------------------------------------------
@app.route("/registro")
@login_required
def registro():
    registros = RegistroContacto.query.order_by(RegistroContacto.fecha.desc()).all()
    contactos_lista = Contacto.query.order_by(Contacto.nombre).all()
    return render_template("registro.html", registros=registros,
                           contactos_lista=contactos_lista)


@app.route("/registro/nuevo", methods=["POST"])
@login_required
def registro_nuevo():
    contacto_id = request.form.get("contacto_id") or None
    nombre = request.form.get("nombre_cliente", "").strip()
    # Si se eligió un contacto de la lista, usar su nombre
    if contacto_id:
        cont = Contacto.query.get(contacto_id)
        if cont:
            nombre = cont.nombre
    r = RegistroContacto(
        fecha=parsear_fecha(request.form.get("fecha")) or date.today(),
        hora=request.form.get("hora", "").strip() or None,
        contacto_id=contacto_id if contacto_id else None,
        nombre_cliente=nombre or None,
        proposito=request.form.get("proposito") or None,
        metodo=request.form.get("metodo") or None,
        notas=request.form.get("notas", "").strip() or None,
    )
    db.session.add(r)
    db.session.commit()
    flash("Registro de contacto agregado.", "success")
    return redirect(url_for("registro"))


@app.route("/registro/<int:rid>/eliminar", methods=["POST"])
@login_required
def registro_eliminar(rid):
    r = RegistroContacto.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    flash("Registro eliminado.", "success")
    return redirect(url_for("registro"))


# ---------------------------------------------------------------------------
# Ventas e Ingresos
# ---------------------------------------------------------------------------
@app.route("/ventas")
@login_required
def ventas():
    todas = Venta.query.order_by(Venta.fecha.desc()).all()
    contactos_lista = Contacto.query.order_by(Contacto.nombre).all()

    # --- Resumen mensual ---
    resumen = {}
    for v in todas:
        if v.fecha:
            clave = v.fecha.strftime("%Y-%m")
            d = resumen.setdefault(clave, {"mes": clave, "ventas": 0,
                                          "ingresos": 0, "facturas": 0, "count": 0})
            d["count"] += 1
            d["ventas"] += v.monto or 0
            if (v.monto or 0) > 0:
                d["ingresos"] += v.monto or 0
            if v.solicita_factura:
                d["facturas"] += 1
    resumen_lista = sorted(resumen.values(), key=lambda x: x["mes"], reverse=True)

    total_anio = sum(v.monto or 0 for v in todas
                     if v.fecha and v.fecha.year == date.today().year)
    total_saldos = sum(v.saldo or 0 for v in todas if (v.saldo or 0) > 0)

    # Datos para la gráfica (todos los meses con datos)
    claves = sorted(resumen.keys())
    labels = [datetime.strptime(k, "%Y-%m").strftime("%b %Y") for k in claves]
    datos = [resumen[k]["ingresos"] for k in claves]

    return render_template(
        "ventas.html", ventas=todas, contactos_lista=contactos_lista,
        resumen=resumen_lista, total_anio=total_anio, total_saldos=total_saldos,
        labels=labels, datos=datos,
    )


@app.route("/ventas/nuevo", methods=["POST"])
@login_required
def ventas_nuevo():
    contacto_id = request.form.get("contacto_id") or None
    nombre = request.form.get("nombre_cliente", "").strip()
    if contacto_id:
        cont = Contacto.query.get(contacto_id)
        if cont:
            nombre = cont.nombre
    v = Venta(
        fecha=parsear_fecha(request.form.get("fecha")) or date.today(),
        contacto_id=contacto_id if contacto_id else None,
        nombre_cliente=nombre or None,
        monto=parsear_monto(request.form.get("monto")) or 0,
        saldo=parsear_monto(request.form.get("saldo")) or 0,
        servicio=request.form.get("servicio") or None,
        num_factura=request.form.get("num_factura", "").strip() or None,
        solicita_factura=parsear_bool(request.form.get("solicita_factura")),
        notas=request.form.get("notas", "").strip() or None,
    )
    factura = request.files.get("factura")
    if factura and factura.filename:
        v.factura_path = guardar_archivo(factura, "factura")
    db.session.add(v)
    db.session.commit()
    flash("Venta registrada.", "success")
    return redirect(url_for("ventas"))


@app.route("/ventas/<int:vid>/editar", methods=["POST"])
@login_required
def ventas_editar(vid):
    v = Venta.query.get_or_404(vid)
    contacto_id = request.form.get("contacto_id") or None
    v.contacto_id = contacto_id if contacto_id else None
    if contacto_id:
        cont = Contacto.query.get(contacto_id)
        if cont:
            v.nombre_cliente = cont.nombre
    else:
        v.nombre_cliente = request.form.get("nombre_cliente", "").strip() or None
    v.fecha = parsear_fecha(request.form.get("fecha")) or v.fecha
    v.monto = parsear_monto(request.form.get("monto")) or 0
    v.saldo = parsear_monto(request.form.get("saldo")) or 0
    v.servicio = request.form.get("servicio") or None
    v.num_factura = request.form.get("num_factura", "").strip() or None
    v.solicita_factura = parsear_bool(request.form.get("solicita_factura"))
    v.notas = request.form.get("notas", "").strip() or None
    factura = request.files.get("factura")
    if factura and factura.filename:
        v.factura_path = guardar_archivo(factura, "factura")
    db.session.commit()
    flash("Venta actualizada.", "success")
    return redirect(url_for("ventas"))


@app.route("/ventas/<int:vid>/eliminar", methods=["POST"])
@login_required
def ventas_eliminar(vid):
    v = Venta.query.get_or_404(vid)
    db.session.delete(v)
    db.session.commit()
    flash("Venta eliminada.", "success")
    return redirect(url_for("ventas"))


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
@app.route("/configuracion")
@login_required
def configuracion():
    cuentas = CuentaPago.query.order_by(CuentaPago.id).all()
    return render_template(
        "configuracion.html",
        cuentas=cuentas,
        dias_ultimo_contacto=get_config("dias_desde_ultimo_contacto", 5),
        dias_proximo_contacto=get_config("dias_hasta_proximo_contacto", 5),
    )


@app.route("/configuracion/guardar", methods=["POST"])
@login_required
def configuracion_guardar():
    for clave in ["lead_status", "lead_source", "acciones", "status_pago",
                  "propositos_contacto", "metodos_contacto", "servicios"]:
        # Las listas vienen de textareas (una opción por línea).
        raw = request.form.get(clave + "[]", "")
        lineas = raw.splitlines()
        limpios = []
        for v in lineas:
            v = v.strip()
            if v and v not in limpios:
                limpios.append(v)
        set_config(clave, limpios)
    # Moneda
    set_config("moneda", request.form.get("moneda", "MXN"))
    # Umbrales
    set_config("dias_desde_ultimo_contacto",
               parsear_monto(request.form.get("dias_desde_ultimo_contacto")) or 5)
    set_config("dias_hasta_proximo_contacto",
               parsear_monto(request.form.get("dias_hasta_proximo_contacto")) or 5)
    db.session.commit()
    flash("Configuración guardada.", "success")
    return redirect(url_for("configuracion"))


@app.route("/configuracion/cuenta/nuevo", methods=["POST"])
@login_required
def cuenta_nuevo():
    c = CuentaPago(
        titular=request.form.get("titular", "").strip() or None,
        numero_cuenta=request.form.get("numero_cuenta", "").strip() or None,
        clabe=request.form.get("clabe", "").strip() or None,
        banco=request.form.get("banco", "").strip() or None,
    )
    db.session.add(c)
    db.session.commit()
    flash("Cuenta de pago agregada.", "success")
    return redirect(url_for("configuracion"))


@app.route("/configuracion/cuenta/<int:cid>/eliminar", methods=["POST"])
@login_required
def cuenta_eliminar(cid):
    c = CuentaPago.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash("Cuenta eliminada.", "success")
    return redirect(url_for("configuracion"))


# ---------------------------------------------------------------------------
# Descarga de archivos (contratos y facturas)
# ---------------------------------------------------------------------------
@app.route("/uploads/<path:filename>")
def descargar_archivo(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Inicialización de la base de datos y configuración por defecto
# ---------------------------------------------------------------------------
def init_db():
    """Crea las tablas y carga la configuración por defecto si están vacías."""
    with app.app_context():
        db.create_all()
        if Configuracion.query.count() == 0:
            for clave, valor in CONFIG_DEFAULTS.items():
                set_config(clave, valor)
            db.session.commit()
            print("Configuración por defecto cargada.")
        # Crear usuario admin por defecto si no existe
        if User.query.count() == 0:
            admin = User(
                username="admin",
                password_hash=generate_password_hash("virtualder2026"),
            )
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado (contraseña: virtualder2026)")


with app.app_context():
    db.create_all()
    if Configuracion.query.count() == 0:
        for clave, valor in CONFIG_DEFAULTS.items():
            set_config(clave, valor)
        db.session.commit()
    # Crear usuario admin por defecto si no existe
    if User.query.count() == 0:
        admin = User(
            username="admin",
            password_hash=generate_password_hash("virtualder2026"),
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado (contraseña: virtualder2026)")


if __name__ == "__main__":
    init_db()
    print("\n" + "=" * 50)
    print("  CRM Virtualder")
    print("  Abre en tu navegador: http://localhost:5000")
    print("=" * 50 + "\n")
    # debug=False para uso personal estable; usa 127.0.0.1 (local)
    app.run(host="127.0.0.1", port=5000, debug=True)
