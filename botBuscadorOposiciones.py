# =====================================================================
# ARCHIVO: botBuscadorOposiciones.py
# FUNCIÓN: Extractor Automatizado de Edictos y Plazas del BOIB (Scraper)
# TECNOLOGÍAS: requests (Peticiones Web), BeautifulSoup (Minería de Datos)
# =====================================================================

import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime

def ejecutar_rastreador_boib():
    # 1. Configuración de la URL de portada del boletín oficial (BOIB)
    url_boib = "https://boib.caib.es/es" 
    
    # User-Agent: Simula que somos un navegador Chrome común en Windows para evitar bloqueos
    cabeceras_navegador = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] Conectando al boletín oficial BOIB...")
    
    try:
        # 2. Lanzamos la petición de descarga a la web del Govern/BOIB
        respuesta = requests.get(url_boib, headers=cabeceras_navegador, timeout=15)
        
        if respuesta.status_code != 200:
            print(f"❌ Error de acceso al BOIB. Código de estado del servidor: {respuesta.status_code}")
            print("💡 Nota: Es posible que la web oficial del BOIB esté en mantenimiento o haya cambiado de estructura.")
            return
            
        # 3. Analizamos el código HTML descargado usando BeautifulSoup
        html_analizable = BeautifulSoup(respuesta.text, "html.parser")
        
        # Conectamos a la base de datos para almacenar lo que encontremos
        conexion = sqlite3.connect("oposiciones.db")
        cursor = conexion.cursor()
        
        # Nos aseguramos de que la tabla 'procesos' del BOIB existe y tiene sus columnas correctas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procesos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                puesto TEXT NOT NULL,
                ente TEXT NOT NULL,
                url TEXT NOT NULL,
                fecha_registro TEXT NOT NULL
            )
        """)
        
        # 4. 🧠 ALGORITMO DE EXTRACCIÓN
        # Buscamos los enlaces (etiquetas 'a') que apunten a edictos o boletines recientes
        enlaces = html_analizable.find_all("a") 
        
        print(f"🔍 Analizando elementos HTML en busca de plazas para Marratxí y personal...")
        nuevos_edictos_guardados = 0
        
        for enlace in enlaces:
            texto_enlace = enlace.text.strip() if enlace.text else ""
            enlace_relativo = enlace.get("href", "")
            
            # Filtramos si el texto del enlace o la URL contienen palabras clave importantes
            texto_en_mayusculas = texto_enlace.upper()
            
            if "MARRATXÍ" in texto_en_mayusculas or "AJUNTAMENT" in texto_en_mayusculas or "BORSES" in texto_en_mayusculas or "OPOSIC" in texto_en_mayusculas:
                
                # Reconstruimos la URL absoluta en caso de que venga compactada
                url_completa_boib = enlace_relativo if enlace_relativo.startswith("http") else f"https://boib.caib.es{enlace_relativo}"
                
                # Verificación de duplicados: Comprobamos si ya teníamos guardada esa URL exacta
                cursor.execute("SELECT id FROM procesos WHERE url = ?", (url_completa_boib,))
                existe = cursor.fetchone()
                
                if not existe:
                    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                    
                    # Asignamos valores por defecto si no podemos separar el ente del puesto en la portada
                    ente_identificado = "Ajuntament de Marratxí" if "MARRATXÍ" in texto_en_mayusculas else "BOIB General"
                    
                    # Insertamos el edicto en la tabla de procesos
                    cursor.execute("""
                        INSERT INTO procesos (puesto, ente, url, fecha_registro)
                        VALUES (?, ?, ?, ?)
                    """, (texto_enlace, ente_identificado, url_completa_boib, fecha_hoy))
                    
                    print(f"   ✨ ¡Nueva plaza detectada!: {texto_enlace}")
                    nuevos_edictos_guardados += 1
                    
        # 6. Guardamos los cambios de manera permanente y cerramos
        conexion.commit()
        conexion.close()
        
        print(f"\n🚀 Rastreo finalizado. Se han añadido {nuevos_edictos_guardados} nuevas ofertas al panel web.")
        
    except Exception as e:
        print(f"❌ Error crítico durante la ejecución del bot raspador del BOIB: {e}")

# Ejecución automática al arrancar el script
if __name__ == "__main__":
    ejecutar_rastreador_boib()