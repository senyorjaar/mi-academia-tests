import sqlite3

DB_NAME = "oposiciones.db"

# Credenciales exactas solicitadas
USUARIOS_ROOT = [
    {
        "nombre": "root",
        "email": "root@academia.com",
        "password": "root1234"
    },
    {
        "nombre": "root2",
        "email": "root2@academia.com",
        "password": "root1234"
    }
]

def registrar_usuarios_root():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()

    # Asegura la existencia de la tabla usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    """)

    print("⏳ Registrando cuentas root...")

    for u in USUARIOS_ROOT:
        try:
            cursor.execute("""
                INSERT INTO usuarios (nombre, email, password, fecha_registro)
                VALUES (?, ?, ?, datetime('now'))
            """, (u["nombre"], u["email"], u["password"]))
            print(f"✅ Creado: Usuario '{u['nombre']}' | Correo '{u['email']}'")
        except sqlite3.IntegrityError:
            # Si el correo ya existía en la base de datos, actualiza nombre y contraseña
            cursor.execute("""
                UPDATE usuarios 
                SET nombre = ?, password = ?
                WHERE email = ?
            """, (u["nombre"], u["password"], u["email"]))
            print(f"🔄 Actualizado: Usuario '{u['nombre']}' | Correo '{u['email']}'")

    conexion.commit()

    print("\n📋 Cuentas activas en oposiciones.db:")
    cursor.execute("SELECT id, nombre, email, password FROM usuarios WHERE email IN ('root@academia.com', 'root2@academia.com')")
    for fila in cursor.fetchall():
        print(f"   • ID: {fila[0]} | Nombre: {fila[1]} | Correo: {fila[2]} | Clave: {fila[3]}")

    conexion.close()
    print("\n✨ Base de datos lista.")

if __name__ == "__main__":
    registrar_usuarios_root()