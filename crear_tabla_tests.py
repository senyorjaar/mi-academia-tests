import sqlite3

def crear_sistema_tests():
    # 1. Establecer conexión con el archivo de base de datos local
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    
    print("⏳ Eliminando tabla de preguntas antigua (si existía) para evitar conflictos...")
    # 2. Borrar la tabla antigua. Esto elimina datos corruptos o columnas desalineadas
    cursor.execute("DROP TABLE IF EXISTS preguntas")
    
    print("⏳ Creando nueva estructura limpia para la tabla 'preguntas'...")
    # 3. Crear la tabla definitiva con las 9 columnas exactas necesarias para el proyecto
    # NOTA: Dentro de las comillas triples de SQL, los comentarios se hacen con -- y no con #
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Identificador único numérico automático
            tema TEXT NOT NULL,                    -- Nombre o etiqueta de la ley/materia
            enunciado TEXT NOT NULL,               -- El texto de la pregunta del examen
            opcion_a TEXT NOT NULL,                -- Respuesta alternativa A
            opcion_b TEXT NOT NULL,                -- Respuesta alternativa B
            opcion_c TEXT NOT NULL,                -- Respuesta alternativa C
            opcion_d TEXT NOT NULL,                -- Respuesta alternativa D
            correcta TEXT NOT NULL,                -- Letra de la respuesta verdadera (A, B, C o D)
            justificacion TEXT NOT NULL            -- Comentario explicativo con el artículo literal
        )
    """)
    
    # 4. Guardar los cambios de manera permanente en el archivo .db y cerrar conexión
    conexion.commit()
    conexion.close()
    print("✅ Paso 1 completado con éxito: Tabla 'preguntas' creada y lista en oposiciones.db")

# Si el script se ejecuta directamente desde la terminal, lanza la función
if __name__ == "__main__":
    crear_sistema_tests()