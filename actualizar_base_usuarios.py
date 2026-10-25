# =====================================================================
# ARCHIVO: actualizar_base_usuarios.py
# FUNCIÓN: Crear o sincronizar tablas de Usuarios e Historial en oposiciones.db
# TECNOLOGÍAS: SQLite3
# =====================================================================

import sqlite3

DB_NAME = "oposiciones.db"

def expandir_base_datos():
    print("⏳ Conectando con la base de datos...")
    
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        
        # 1. Crear tabla usuarios si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE,
                nombre TEXT,
                email TEXT UNIQUE,
                password TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'admin',
                fecha_registro TEXT
            )
        """)
        
        # 2. Asegurar columnas faltantes sin DEFAULT dinámico (restricción estricta de SQLite en ALTER TABLE)
        cursor.execute("PRAGMA table_info(usuarios)")
        columnas_actuales = [col[1] for col in cursor.fetchall()]
        
        columnas_a_verificar = {
            "usuario": "TEXT",
            "nombre": "TEXT",
            "email": "TEXT",
            "password": "TEXT NOT NULL DEFAULT ''",
            "rol": "TEXT NOT NULL DEFAULT 'admin'",
            "fecha_registro": "TEXT"
        }
        
        for col, tipo in columnas_a_verificar.items():
            if col not in columnas_actuales:
                cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
                print(f"➕ Columna '{col}' agregada a la tabla 'usuarios'.")

        # Rellenar fecha_registro si quedó nula
        cursor.execute("""
            UPDATE usuarios 
            SET fecha_registro = datetime('now') 
            WHERE fecha_registro IS NULL OR fecha_registro = ''
        """)
        
        # 3. Tabla de historial de tests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                tema TEXT NOT NULL,
                aciertos INTEGER NOT NULL,
                total_preguntas INTEGER NOT NULL,
                nota REAL NOT NULL,
                fecha_test TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historial_usuario 
            ON historial_tests (usuario_id)
        """)

        conexion.commit()

    print("✅ Tablas 'usuarios' e 'historial_tests' configuradas y sincronizadas con éxito.")

if __name__ == "__main__":
    expandir_base_datos()