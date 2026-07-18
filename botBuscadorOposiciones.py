import requests
from bs4 import BeautifulSoup
import sqlite3
import time

DB_NAME = "oposiciones.db"

def inicializar_base_datos():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edictos_boib (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            enlace TEXT UNIQUE NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conexion.commit()
    conexion.close()

def es_edicto_nuevo(enlace):
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT 1 FROM edictos_boib WHERE enlace = ?", (enlace,))
    resultado = cursor.fetchone()
    conexion.close()
    return resultado is None

def guardar_edicto(titulo, enlace):
    try:
        conexion = sqlite3.connect(DB_NAME)
        cursor = conexion.cursor()
        cursor.execute("INSERT INTO edictos_boib (titulo, enlace) VALUES (?, ?)", (titulo, enlace))
        conexion.commit()
        conexion.close()
    except sqlite3.IntegrityError:
        pass

def buscar_novedades_reales_boib():
    inicializar_base_datos()
    url_base = "https://boib.caib.es"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print("\n🛡️ [ESCANER BOIB DE NUEVAS CONVOCATORIAS] Buscando procesos limpios...")
    
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            print(f"❌ Error al acceder a la portada del BOIB: {respuesta.status_code}")
            return
            
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        # Extracción adaptativa de la ruta del año actual
        enlace_referencia = None
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href and "/2026/" in href:
                enlace_referencia = href
                break

        if not enlace_referencia:
            print("❌ No se detectó la estructura de boletines del año en curso.")
            return

        partes = [p for p in enlace_referencia.split("/") if p]
        prefijo_raiz = partes[0] if partes else "eboibfront"
        
        # Capturamos los sumarios de los boletines oficiales reales de la portada
        boletines_validos = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href and prefijo_raiz in href and "/2026/" in href and not "/mes/" in href:
                url_completa = href if href.startswith("http") else f"{url_base}{href}"
                if url_completa not in boletines_validos:
                    boletines_validos.append(url_completa)
                    
        # Revisamos los últimos 4 boletines publicados
        ultimos_boletines = boletines_validos[:4]
        print(f"📋 Analizando los edictos de los {len(ultimos_boletines)} últimos boletines del BOIB...")
        print("------------------------------------------------------------------------")
        
        # Raíces clave basadas en los enunciados tipo EBAP/CAIB
        patrones_empleo = ["procés", "proces", "selectiu", "oposici", "borsa", "bolsa", "convocat"]
        nuevos_descubiertos = 0
        
        for idx, url_b in enumerate(ultimos_boletines):
            try:
                res_b = requests.get(url_b, headers=headers, timeout=10)
                if res_b.status_code != 200:
                    continue
                    
                soup_b = BeautifulSoup(res_b.text, "html.parser")
                
                # Buscamos todos los enlaces del sumario diario
                for enlace in soup_b.find_all("a"):
                    # Extraemos tanto el texto del enlace como el atributo 'title' si existe (a veces el BOIB mete el texto largo ahí)
                    texto_nodo = enlace.text.strip()
                    texto_title = enlace.get("title", "").strip()
                    texto_completo = f"{texto_nodo} {texto_title}"
                    texto_min = texto_completo.lower()
                    
                    href_edicto = enlace.get("href", "")
                    
                    # Evitamos enlaces del sistema, idiomas vacíos o PDFs repetidos cortos
                    if len(texto_min) < 20 or "lang=" in href_edicto and not "pdf" in texto_min:
                        continue
                        
                    # Validamos si encaja con enunciados de convocatorias públicas
                    if any(patron in texto_min for patron in patrones_empleo):
                        url_edicto_completa = href_edicto if href_edicto.startswith("http") else f"{url_base}{href_edicto}"
                        
                        # Control estricto de duplicados (Procesos nuevos vs ya en marcha)
                        if es_edicto_nuevo(url_edicto_completa):
                            # Limpieza estética del enunciado
                            enunciado_limpio = " ".join(texto_completo.split())
                            
                            print(f"🆕 [NUEVO PROCESO DETECTADO EN EL BOIB]")
                            print(f"   📋 Enunciado: {enunciado_limpio[:120]}...")
                            print(f"   🔗 Enlace: {url_edicto_completa}")
                            print("------------------------------------------------------------------------")
                            
                            guardar_edicto(enunciado_limpio, url_edicto_completa)
                            nuevos_descubiertos += 1
                            
            except Exception:
                pass
                
            time.sleep(0.5)
            
        print(f"\n🏁 Análsis completado. Nuevos procesos agregados al registro: {nuevos_descubiertos}\n")
        
    except Exception as e:
        print(f"❌ Error en el motor de búsqueda: {e}")

if __name__ == "__main__":
    buscar_novedades_reales_boib()