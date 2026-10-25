# =====================================================================
# ARCHIVO: crear_usuarios_root.py
# FUNCIÓN: Registrar o actualizar cuentas de administración en oposiciones.db
# TECNOLOGÍAS: SQLite3
# =====================================================================

import sqlite3

DB_NAME = "oposiciones.db"

USUARIOS_ROOT = [
    {
        "usuario": "root",
        "nombre": "Administrador Principal",
        "email": "root@academia.com",
        "password": "root1234",
        "rol": "admin"
    },
    {
        "usuario": "root2",
        "nombre": "Administrador Secundario",
        "email": "root2@academia.com",
        "password": "root1234",
        "rol": "admin"
    }
]

def registrar_usuarios_root():
    print("⏳ Conectando con la base de datos...")
    
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()

        # Asegurar estructura
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                nombre TEXT,
                email TEXT UNIQUE,
                password TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'admin',
                fecha_registro TEXT
            )
        """)

        cursor.execute("PRAGMA table_info(usuarios)")
        columnas_actuales = [col[1] for col in cursor.fetchall()]
        if "fecha_registro" not in columnas_actuales:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN fecha_registro TEXT")

        print("⏳ Registrando cuentas administrativas...")

        for u in USUARIOS_ROOT:
            cursor.execute("""
                SELECT id FROM usuarios 
                WHERE usuario = ? OR email = ?
            """, (u["usuario"], u["email"]))
            
            registro = cursor.fetchone()

            if registro:
                cursor.execute("""
                    UPDATE usuarios 
                    SET usuario = ?, nombre = ?, email = ?, password = ?, rol = ?, 
                        fecha_registro = COALESCE(fecha_registro, datetime('now'))
                    WHERE id = ?
                """, (u["usuario"], u["nombre"], u["email"], u["password"], u["rol"], registro[0]))
                print(f"🔄 Actualizado: Usuario '{u['usuario']}' | Correo '{u['email']}'")
            else:
                cursor.execute("""
                    INSERT INTO usuarios (usuario, nombre, email, password, rol, fecha_registro)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (u["usuario"], u["nombre"], u["email"], u["password"], u["rol"]))
                print(f"✅ Creado: Usuario '{u['usuario']}' | Correo '{u['email']}'")

        conexion.commit()

        print("\n📋 Cuentas activas en oposiciones.db:")
        cursor.execute("""
            SELECT id, usuario, nombre, email, password, rol, fecha_registro 
            FROM usuarios 
            WHERE usuario IN ('root', 'root2')
        """)
        for fila in cursor.fetchall():
            print(f"   • ID: {fila[0]} | User: {fila[1]} | Nombre: {fila[2]} | Correo: {fila[3]} | Clave: {fila[4]} | Rol: {fila[5]}")

    print("\n✨ Cuentas listas.")

if __name__ == "__main__":
    registrar_usuarios_root()