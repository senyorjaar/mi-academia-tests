import sqlite3
import os
import glob
import bcrypt

DB_NAME = "oposiciones.db"
CARPETA_TXT = "preguntas_txt"

def hash_password(password: str) -> str:
    # Convierte la contraseña en bytes y genera el hash seguro
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def inicializar_sistema():
    print("⏳ Conectando con la base de datos local...")
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # 1. CREACIÓN DE TABLAS
    print("⏳ Configurando estructura limpia de tablas...")
    
    # Tabla de Preguntas
    cursor.execute("DROP TABLE IF EXISTS preguntas")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema TEXT NOT NULL,
            enunciado TEXT NOT NULL,
            opcion_a TEXT NOT NULL,
            opcion_b TEXT NOT NULL,
            opcion_c TEXT NOT NULL,
            opcion_d TEXT NOT NULL,
            correcta TEXT NOT NULL,
            justificacion TEXT NOT NULL
        )
    """)
    
    # Tabla de Usuarios para el Login
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    
    # 2. CREACIÓN DE UN USUARIO DE PRUEBA
    usuario_prueba = "admin"
    pass_prueba = "12345"
    pass_encriptada = hash_password(pass_prueba)
    
    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (?, ?)", 
                       (usuario_prueba, pass_encriptada))
        print(f"👤 Usuario de prueba configurado -> Usuario: {usuario_prueba} | Contraseña: {pass_prueba}")
    except sqlite3.IntegrityError:
        pass

    # 3. IMPORTACIÓN AUTOMÁTICA DE PREGUNTAS .TXT
    if not os.path.exists(CARPETA_TXT):
        os.makedirs(CARPETA_TXT)
        print(f"📁 Se ha creado la carpeta '{CARPETA_TXT}'. Mete tus archivos .txt dentro.")
        conexion.commit()
        conexion.close()
        return

    archivos_txt = glob.glob(os.path.join(CARPETA_TXT, "*.txt"))
    if not archivos_txt:
        print(f"⚠️ No se encontraron archivos .txt en '{CARPETA_TXT}'. Tablas creadas vacías.")
        conexion.commit()
        conexion.close()
        return

    total_importado = 0
    print(f"🔍 Detectados {len(archivos_txt)} archivos listos para procesar...\n")
    
    for ruta_archivo in archivos_txt:
        nombre_archivo = os.path.basename(ruta_archivo)
        contador_local = 0
        
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as archivo:
                for num_linea, linea in enumerate(archivo, 1):
                    linea = linea.strip()
                    
                    if not linea or linea.startswith("#"): 
                        continue
                        
                    partes = linea.split("|")
                    
                    if len(partes) == 8:
                        tema, enunciado, op_a, op_b, op_c, op_d, correcta, justificacion = partes
                        
                        cursor.execute("""
                            INSERT INTO preguntas (tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            tema.strip(), 
                            enunciado.strip(), 
                            op_a.strip(), 
                            op_b.strip(), 
                            op_c.strip(), 
                            op_d.strip(), 
                            correcta.strip().upper(),
                            justificacion.strip()
                        ))
                        contador_local += 1
                        total_importado += 1
                    else:
                        print(f"⚠️ [{nombre_archivo}] Línea {num_linea} ignorada: tiene {len(partes)} campos de 8 requeridos.")
                        
            print(f"📁 {nombre_archivo}: {contador_local} preguntas procesadas con éxito.")
            
        except Exception as e:
            print(f"❌ Error crítico al leer el archivo {nombre_archivo}: {e}")
            
    conexion.commit()
    conexion.close()
    
    print("\n--------------------------------------------------")
    print(f"🚀 BASE DE DATOS LISTA. Total inyectado: {total_importado} preguntas.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    inicializar_sistema()