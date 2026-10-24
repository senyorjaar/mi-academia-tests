import os
import glob
import json
import sqlite3

DB_NAME = "oposiciones.db"

def asegurar_columnas(cursor):
    """Asegura que la tabla preguntas tenga la columna archivo_origen sin borrar datos."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema TEXT,
            enunciado TEXT,
            opcion_a TEXT,
            opcion_b TEXT,
            opcion_c TEXT,
            opcion_d TEXT,
            correcta TEXT,
            justificacion TEXT,
            archivo_origen TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(preguntas)")
    columnas = [col[1] for col in cursor.fetchall()]
    if "archivo_origen" not in columnas:
        cursor.execute("ALTER TABLE preguntas ADD COLUMN archivo_origen TEXT")

def insertar_pregunta(cursor, tema, enunciado, op_a, op_b, op_c, op_d, correcta, justificacion, archivo_origen=""):
    cursor.execute("""
        INSERT INTO preguntas (tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion, archivo_origen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tema.strip(),
        enunciado.strip(),
        op_a.strip(),
        op_b.strip(),
        op_c.strip(),
        op_d.strip(),
        correcta.strip().upper(),
        justificacion.strip(),
        archivo_origen.strip()
    ))

def importar_desde_txt(cursor):
    total_txt = 0
    archivos_txt = glob.glob("preguntas_txt/**/*.txt", recursive=True)
    archivos_txt = [f for f in archivos_txt if os.path.basename(f) not in ["requirements.txt", "runtime.txt"]]

    for ruta in archivos_txt:
        nombre = os.path.basename(ruta)
        # Nombre del contenedor (carpeta)
        contenedor = os.path.basename(os.path.dirname(ruta))
        contador = 0
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#"):
                        continue
                    partes = linea.split("|")
                    if len(partes) == 8:
                        _, enun, a, b, c, d, corr, just = partes
                        # Usamos ÚNICAMENTE el nombre de la carpeta contenedora
                        insertar_pregunta(cursor, contenedor, enun, a, b, c, d, corr, just, nombre)
                        contador += 1
                        total_txt += 1
            if contador > 0:
                print(f"📄 [TXT] ({contenedor}) -> {nombre}: {contador} preguntas.")
        except Exception as e:
            print(f"❌ Error al leer TXT {nombre}: {e}")
    return total_txt

def importar_desde_json(cursor):
    total_json = 0
    # Busca exclusivamente en tu carpeta preguntas_txt
    archivos_json = glob.glob("preguntas_txt/**/*.json", recursive=True)

    for ruta in archivos_json:
        nombre = os.path.basename(ruta)
        # Nombre del contenedor (Notificador, OficialElectricista, PeoEspexitlizat, etc.)
        contenedor = os.path.basename(os.path.dirname(ruta))
        contador = 0
        try:
            with open(ruta, "r", encoding="utf-8-sig") as f:
                contenido = f.read().strip()

            if not contenido:
                continue

            # Tu lógica original que descarta comentarios /* ... */
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
                    # TEMA: Únicamente el nombre de la carpeta contenedora
                    tema = contenedor
                    enunciado = item.get("enunciado", "")
                    opciones = item.get("opciones", {})
                    op_a = opciones.get("A", "")
                    op_b = opciones.get("B", "")
                    op_c = opciones.get("C", "")
                    op_d = opciones.get("D", "")
                    correcta = item.get("respuesta_correcta", "")
                    justificacion = item.get("justificacion", "Convocatoria Oficial Marratxí")

                    if enunciado and op_a and correcta:
                        insertar_pregunta(cursor, tema, enunciado, op_a, op_b, op_c, op_d, correcta, justificacion, nombre)
                        contador += 1
                        total_json += 1

            if contador > 0:
                print(f"📦 [JSON] ({contenedor}) -> {nombre}: {contador} preguntas.")
        except Exception as e:
            print(f"❌ Error al leer JSON {nombre}: {e}")
            
    return total_json

def ejecutar_importacion_completa():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()

    asegurar_columnas(cursor)

    # Limpia preguntas anteriores para que no se mezclen las materias viejas
    cursor.execute("DELETE FROM preguntas")
    conexion.commit()

    print("🚀 Importando preguntas clasificadas únicamente por CARPETA CONTENEDORA...\n")
    n_txt = importar_desde_txt(cursor)
    n_json = importar_desde_json(cursor)

    conexion.commit()
    conexion.close()

    print("\n--------------------------------------------------")
    print(f"✅ Proceso terminado:")
    print(f"   • Desde TXT:  {n_txt}")
    print(f"   • Desde JSON: {n_json}")
    print(f"   • Total:      {n_txt + n_json}\n")

if __name__ == "__main__":
    ejecutar_importacion_completa()