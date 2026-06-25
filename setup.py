"""Utilidad para gestionar el usuario administrador del CRM.

Uso:
  python setup.py create      Crea usuario admin (si no existe)
  python setup.py change      Cambia contraseña del admin
  python setup.py list        Lista usuarios existentes
"""
import sys
from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def crear_admin():
    with app.app_context():
        if User.query.filter_by(username="admin").first():
            print("✓ El usuario 'admin' ya existe.")
            return
        password = input("Contraseña para admin (Enter = 'virtualder2026'): ").strip()
        if not password:
            password = "virtualder2026"
        user = User(username="admin", password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print(f"\n✓ Usuario 'admin' creado con contraseña: {password}")
        print("  Cambia la contraseña con: python setup.py change")

def cambiar_password():
    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        if not user:
            print("✗ El usuario 'admin' no existe. Crealo con: python setup.py create")
            return
        p1 = input("Nueva contraseña: ").strip()
        if not p1:
            print("✗ La contraseña no puede estar vacía.")
            return
        p2 = input("Confirmar contraseña: ").strip()
        if p1 != p2:
            print("✗ Las contraseñas no coinciden.")
            return
        user.password_hash = generate_password_hash(p1)
        db.session.commit()
        print(f"✓ Contraseña actualizada.")

def listar_usuarios():
    with app.app_context():
        users = User.query.all()
        if not users:
            print("No hay usuarios registrados.")
            return
        print(f"Usuarios ({len(users)}):")
        for u in users:
            print(f"  - {u.username} (ID: {u.id})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "create":
        crear_admin()
    elif cmd == "change":
        cambiar_password()
    elif cmd == "list":
        listar_usuarios()
    else:
        print(f"Comando desconocido: {cmd}")
        print(__doc__)