# =====================================================================
# ARCHIVO: importar_preguntas.py
# FUNCIÓN: Ingesta masiva y estructurada de tests (JSON y TXT) en oposiciones.db
# TECNOLOGÍAS: Python 3, JSON, Glob, SQLite3
# =====================================================================

import os
import glob
import json
import sqlite3

DB_NAME = "oposiciones.db"

def preparar_tabla_preguntas(cursor):
    """Crea la estructura definitiva de la tabla preguntas con índices."""
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
            justificacion TEXT NOT NULL,
            archivo_origen TEXT NOT NULL
        )
    """)
    # Índice para acelerar el filtrado por oficio/carpeta y archivo
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preguntas_tema ON preguntas (tema)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_preguntas_origen ON preguntas (archivo_origen)")

def extraer_desde_txt(archivos_txt):
    """Lee y estructura preguntas desde ficheros delimitados por tubería (|)."""
    registros = []
    
    for ruta in archivos_txt:
        nombre_archivo = os.path.basename(ruta)
        contenedor = os.path.basename(os.path.dirname(ruta))
        contador_archivo = 0
        
        try:
            with open(ruta, "r", encoding="utf-8-sig", errors="replace") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#"):
                        continue
                    
                    partes = linea.split("|")
                    if len(partes) >= 8:
                        # Estructura esperada: ID|Enunciado|A|B|C|D|Correcta|Justificacion
                        enun = partes[1].strip()
                        op_a = partes[2].strip()
                        op_b = partes[3].strip()
                        op_c = partes[4].strip()
                        op_d = partes[5].strip()
                        corr = partes[6].strip().upper()
                        just = partes[7].strip() if len(partes) > 7 else "Convocatoria Oficial Marratxí"
                        
                        if enun and op_a and corr:
                            registros.append((contenedor, enun, op_a, op_b, op_c, op_d, corr, just, nombre_archivo))
                            contador_archivo += 1
                            
            if contador_archivo > 0:
                print(f"📄 [TXT] ({contenedor}) -> {nombre_archivo}: {contador_archivo} preguntas.")
        except Exception as e:
            print(f"❌ Error al leer TXT '{nombre_archivo}': {e}")
            
    return registros

def extraer_desde_json(archivos_json):
    """Lee y estructura preguntas desde ficheros JSON de convocatorias."""
    registros = []
    
    for ruta in archivos_json:
        nombre_archivo = os.path.basename(ruta)
        contenedor = os.path.basename(os.path.dirname(ruta))
        contador_archivo = 0
        
        try:
            with open(ruta, "r", encoding="utf-8-sig", errors="replace") as f:
                contenido = f.read().strip()

            if not contenido:
                continue

            # Limpieza de posibles comentarios o encabezados previos al JSON
            pos_inicio = contenido.find("[")
            if pos_inicio == -1:
                pos_inicio = contenido.find("{")

            if pos_inicio != -1:
                contenido = contenido[pos_inicio:]

            datos = json.loads(contenido)
            if isinstance(datos, dict):
                datos = [datos]

            if isinstance(datos, list):
                for item in datos:
                    enun = str(item.get("enunciado", "")).strip()
                    opciones = item.get("opciones", {})
                    op_a = str(opciones.get("A", "")).strip()
                    op_b = str(opciones.get("B", "")).strip()
                    op_c = str(opciones.get("C", "")).strip()
                    op_d = str(opciones.get("D", "")).strip()
                    corr = str(item.get("respuesta_correcta", "")).strip().upper()
                    just = str(item.get("justificacion", "Convocatoria Oficial Marratxí")).strip()

                    if enun and op_a and corr:
                        registros.append((contenedor, enun, op_a, op_b, op_c, op_d, corr, just, nombre_archivo))
                        contador_archivo += 1

            if contador_archivo > 0:
                print(f"📦 [JSON] ({contenedor}) -> {nombre_archivo}: {contador_archivo} preguntas.")
        except Exception as e:
            print(f"❌ Error al leer JSON '{nombre_archivo}': {e}")
            
    return registros

def ejecutar_importacion_completa():
    print("==================================================")
    print("🚀 INICIANDO IMPORTACIÓN DE PREGUNTAS")
    print("==================================================\n")

    archivos_txt = [
        f for f in glob.glob("preguntas_txt/**/*.txt", recursive=True)
        if os.path.basename(f) not in ["requirements.txt", "runtime.txt"]
    ]
    archivos_json = glob.glob("preguntas_txt/**/*.json", recursive=True)

    lista_txt = extraer_desde_txt(archivos_txt)
    lista_json = extraer_desde_json(archivos_json)
    todas_las_preguntas = lista_txt + lista_json

    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        preparar_tabla_preguntas(cursor)

        # Limpiar preguntas anteriores para evitar mezclas o datos desactualizados
        cursor.execute("DELETE FROM preguntas")

        # Inserción atómica en bloque
        cursor.executemany("""
            INSERT INTO preguntas (
                tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion, archivo_origen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, todas_las_preguntas)
        
        conexion.commit()

    print("\n--------------------------------------------------")
    print("✅ PROCESO FINALIZADO CON ÉXITO:")
    print(f"   • Preguntas desde TXT:  {len(lista_txt)}")
    print(f"   • Preguntas desde JSON: {len(lista_json)}")
    print(f"   • Total insertadas:     {len(todas_las_preguntas)}")
    print("--------------------------------------------------\n")

if __name__ == "__main__":
    ejecutar_importacion_completa()