# =====================================================================
# ARCHIVO: actualizar_base_usuarios.py
# FUNCIÓN: Añadir tablas de Usuarios e Historial a oposiciones.db
# TECNOLOGÍAS: SQLite3
# =====================================================================

import sqlite3

def expandir_base_datos():
    # Conectamos a tu base de datos actual en esta carpeta
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    
    print("⏳ Creando tablas para el sistema de usuarios...")
    
    # 1. Tabla de usuarios (Guardará las cuentas de tus alumnos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, -- Aquí irá la contraseña encriptada por seguridad
            fecha_registro TEXT NOT NULL
        )
    """)
    
    # 2. Tabla de historial (Guardará los resultados de los exámenes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tema TEXT NOT NULL,
            aciertos INTEGER NOT NULL,
            total_preguntas INTEGER NOT NULL,
            nota REAL NOT NULL,
            fecha_test TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    conexion.commit()
    conexion.close()
    print("✅ Tablas 'usuarios' e 'historial_tests' creadas con éxito sin tocar tus preguntas.")

if __name__ == "__main__":
    expandir_base_datos()