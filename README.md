# CRM Virtualder

CRM personal para la agencia [Virtualder](https://virtualder.mx/), diseñado como
aplicación web local con interfaz moderna y minimalista basada en los colores de marca.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-green)

## Inicio rápido

### Windows
```
Doble clic en run.bat
```

### Linux / macOS
```
chmod +x run.sh
./run.sh
```

### Manual
```
python -m pip install -r requirements.txt
python app.py
```

Abrir en el navegador: **http://localhost:5000**

## Migración de datos desde Excel

La primera vez, importa tus datos del archivo Excel:

```
python migrate.py
```

Esto lee `CRM-Virtualder.xlsx` y carga todas las hojas relevantes:
- **ContactDetails** → Libreta de contactos
- **CRM** → Pipeline de clientes
- **ContactLog** → Historial de contactos
- **SalesLog** → Registro de ventas
- **Settings** → Listas desplegables + cuentas de pago

## Secciones

| Tab | Descripción |
|-----|-------------|
| **Panel** | Dashboard con alertas de contactos, KPIs, entregas próximas, gráfica de ventas |
| **CRM** | Pipeline completo: filtros, estados, contratos adjuntos, cálculo automático de entrega final |
| **Detalles de Contacto** | Libreta maestra con registro de nuevos usuarios y fecha de recepción del lead |
| **Registro de Contacto** | Historial de seguimientos y comunicaciones |
| **Ventas e Ingresos** | Ventas con facturación, gráfica mensual y resumen de ingresos |
| **Configuración** | Listas desplegables, moneda (MXN/USD), umbrales de alertas, cuentas de pago |

## Regla de negocio: fecha de entrega final

La **fecha de entrega final** se calcula automáticamente como:

```
MAX(fecha de pago, fecha de información entregada) + 30 días
```

## Estructura del proyecto

```
CRM Virtualder/
├── app.py              # Aplicación Flask (rutas, lógica de negocio)
├── models.py           # Modelos SQLAlchemy (6 tablas)
├── migrate.py          # Importador Excel → SQLite
├── requirements.txt    # Dependencias Python
├── run.bat / run.sh    # Lanzadores
├── crm.db              # Base de datos SQLite (generado al iniciar)
├── uploads/            # Contratos y facturas adjuntos
├── static/
│   ├── css/style.css   # Tema minimalista con colores de marca
│   └── js/             # JavaScript: modales, gráficas, filtros
└── templates/          # Plantillas HTML
```

## Colores de marca

| Color | Hex | Uso |
|-------|-----|-----|
| Verde bosque | `#47704C` | Primario (sidebar, botones, badges activos) |
| Coral | `#ED9A96` | Acento (botones secundarios, detalles) |
| Crema | `#F7F1EA` | Fondo principal |

## Despliegue futuro

Para acceder desde cualquier lugar, la misma aplicación puede desplegarse en un servidor:

```bash
# Ejemplo con gunicorn
pip install gunicorn
gunicorn -w 1 -b 0.0.0.0:5000 app:app
```

Para base de datos en servidor, solo se cambia esta línea en `app.py`:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:pass@host/db"
```

## Tecnologías

- **Backend:** Flask + SQLAlchemy ORM
- **Database:** SQLite (local, portable)
- **Frontend:** HTML + CSS custom + vanilla JS
- **Gráficas:** Chart.js (100% local, sin API)
- **Python:** 3.14+
