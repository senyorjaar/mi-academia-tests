# =====================================================================
# ARCHIVO: leer_base_datos.py
# FUNCIÓN: Inspector Técnico de Verificación de la Base de Datos
# TECNOLOGÍAS: SQLite3 (Consola de comandos integrada)
# =====================================================================

import sqlite3

def inspeccionar_base_datos():
    # 1. Establecemos la conexión con el archivo de base de datos de la academia
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    
    print("==================================================")
    print("🔍 INICIANDO INSPECCIÓN DE OPOSICIONES.DB")
    print("==================================================\n")
    
    try:
        # 2. CONSULTA 1: Contamos cuántas preguntas totales hay en el banco de datos
        cursor.execute("SELECT COUNT(*) FROM preguntas")
        total_preguntas = cursor.fetchone()[0]
        print(f"📊 TOTAL DE PREGUNTAS INYECTADAS: {total_preguntas}\n")
        
        # 3. CONSULTA 2: Agrupamos las preguntas por ley/materia para ver el reparto
        cursor.execute("SELECT tema, COUNT(*) FROM preguntas GROUP BY tema")
        reparto_temas = cursor.fetchall()
        
        print("📋 REPARTO DE PREGUNTAS POR MATERIA / LEY:")
        for tema, cantidad in reparto_temas:
            # El campo .strip() asegura que veamos el nombre real sin espacios invisibles
            print(f"   • {tema.strip()}: {cantidad} preguntas.")
        print("\n--------------------------------------------------")
        
        # 4. CONSULTA 3: Extraemos una muestra de las 3 últimas preguntas para verificar el Fundamento Jurídico
        print("👀 VERIFICACIÓN DE MUESTRA (Últimos 3 registros cargados):")
        cursor.execute("""
            SELECT id, tema, enunciado, correcta, justificacion 
            FROM preguntas 
            ORDER BY id DESC LIMIT 3
        """)
        muestra = cursor.fetchall()
        
        for p in muestra:
            print(f"\n   🆔 ID: {p[0]} | 📚 Ley: {p[1].strip()}")
            print(f"   ❓ Enunciado: {p[2].strip()}")
            print(f"   ✅ Respuesta Correcta guardada: {p[3].strip()}")
            print(f"   ⚖️ Fundamento Jurídico: {p[4].strip()}")
            print("   " + "-"*40)
            
    except sqlite3.OperationalError as e:
        # Control de errores: Si la tabla aún no existe o el archivo .db está vacío
        print(f"❌ Error operacional: La tabla 'preguntas' no existe o está dañada. Razón: {e}")
        print("💡 Solución: Ejecuta 'python crear_tabla_tests.py' e 'importar_preguntas.py' primero.")
        
    finally:
        # 5. Cerramos la conexión de forma segura para no bloquear el archivo .db
        conexion.close()
        print("\n==================================================")
        print("✅ INSPECCIÓN FINALIZADA CON ÉXITO")
        print("==================================================")

# Punto de entrada para ejecutar el script desde la terminal de VS Code
if __name__ == "__main__":
    inspeccionar_base_datos()