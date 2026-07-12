# =====================================================================
# ARCHIVO: importar_preguntas.py
# FUNCIÓN: Importador Automático Masivo y Multiarchivo de Preguntas
# TECNOLOGÍAS: Python Integrado, Módulos 'os' y 'glob' (Gestión de Archivos)
# =====================================================================

import sqlite3
import os
import glob

def importar_multiples_txt():
    # 1. Definimos el nombre de la carpeta donde guardas tus blocs de notas (.txt)
    carpeta_origen = "preguntas_txt"
    
    # Verificación de seguridad: Si la carpeta no existe, avisamos y paramos el script
    if not os.path.exists(carpeta_origen):
        print(f"❌ Error: No existe la carpeta '{carpeta_origen}'. Créala y mete tus archivos dentro.")
        return
        
    # 2. El comando 'glob' busca de forma automática todos los archivos que terminen en .txt dentro de esa carpeta
    archivos_txt = glob.glob(os.path.join(carpeta_origen, "*.txt"))
    
    # Verificación de seguridad: Si la carpeta está vacía, avisamos y paramos
    if not archivos_txt:
        print(f"⚠️ No se encontró ningún archivo .txt dentro de la carpeta '{carpeta_origen}'.")
        return
        
    # 3. Conectamos a la base de datos local
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    
    total_importado = 0  # Contador global para saber cuántas preguntas metemos en total
    
    print(f"🔍 Detectados {len(archivos_txt)} archivos listos para procesar...\n")
    
    # 4. 🔄 BUCLE PRINCIPAL: Procesamos los archivos uno por uno
    for ruta_archivo in archivos_txt:
        nombre_archivo = os.path.basename(ruta_archivo)  # Extrae solo el nombre (Ej: constitucionAP.txt)
        contador_local = 0                             # Contador individual para este archivo
        
        try:
            # Abrimos el archivo con codificación UTF-8 para que lea bien los acentos, la ñ y caracteres en catalán
            with open(ruta_archivo, "r", encoding="utf-8") as archivo:
                for num_linea, linea in enumerate(archivo, 1):
                    linea = linea.strip()  # Limpia espacios vacíos sueltos al inicio o final de la línea
                    
                    # Si la línea está vacía o es un comentario (empieza por #), la ignoramos y seguimos
                    if not linea or linea.startswith("#"): 
                        continue
                        
                    # Rompemos la línea en trozos usando la barra vertical '|' como cuchillo
                    partes = linea.split("|")
                    
                    # REGLA DE VALIDACIÓN: Cada pregunta debe tener exactamente 8 campos
                    if len(partes) == 8:
                        tema, enunciado, op_a, op_b, op_c, op_d, correcta, justificacion = partes
                        
                        # Inyectamos de forma segura los 8 campos en la base de datos usando marcadores '?'
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
                            correcta.strip().upper(),  # Aseguramos la letra de la respuesta en mayúscula (A)
                            justificacion.strip()       # Texto completo del comentario/artículo legal
                        ))
                        
                        contador_local += 1
                        total_importado += 1
                    else:
                        # Si una línea está rota o mal estructurada, avisamos sin detener el resto del archivo
                        print(f"⚠️ [{nombre_archivo}] Línea {num_linea} ignorada: tiene {len(partes)} campos de 8 requeridos.")
                        
            print(f"📁 {nombre_archivo}: {contador_local} preguntas procesadas con éxito.")
            
        except Exception as e:
            # Si el archivo tiene un fallo grave de lectura, capturamos el error para que el programa no se caiga
            print(f"❌ Error crítico al leer el archivo {nombre_archivo}: {e}")
            
    # 5. Guardamos permanentemente todos los cambios en la base de datos y cerramos
    conexion.commit()
    conexion.close()
    
    print("\n--------------------------------------------------")
    print(f"🚀 ¡PASO 2 COMPLETADO! Total global inyectado: {total_importado} preguntas.")
    print("--------------------------------------------------")

# Punto de entrada para ejecutar la función al lanzar el script
if __name__ == "__main__":
    importar_multiples_txt()