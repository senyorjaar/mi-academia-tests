import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
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

def ejecutar_escaneo_boib():
    inicializar_base_datos()
    url_base = "https://boib.caib.es"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    nuevos_procesos = []
    
    try:
        # 1. Analizar la portada para aprender la estructura dinámica actual
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return {"error": f"Error al acceder a la portada del BOIB: {respuesta.status_code}"}, []
            
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        enlace_referencia = None
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href and "/2026/" in href:
                enlace_referencia = href
                break

        if not enlace_referencia:
            return {"error": "No se pudo mapear la estructura del año actual en la portada."}, []

        partes = [p for p in enlace_referencia.split("/") if p]
        prefijo_raiz = partes[0] if partes else "eboibfront"
        
        # 2. Capturar los últimos boletines del sumario
        boletines_validos = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href and prefijo_raiz in href and "/2026/" in href and not "/mes/" in href:
                url_completa = href if href.startswith("http") else f"{url_base}{href}"
                if url_completa not in boletines_validos:
                    boletines_validos.append(url_completa)
                    
        ultimos_boletines = boletines_validos[:4]
        
        # Filtros amplios y agresivos
        patrones_empleo = ["procés", "proces", "selectiu", "oposici", "borsa", "bolsa", "convocat"]
        
        # 3. Escaneo profundo de edictos
        for url_b in ultimos_boletines:
            try:
                res_b = requests.get(url_b, headers=headers, timeout=10)
                if res_b.status_code != 200:
                    continue
                    
                soup_b = BeautifulSoup(res_b.text, "html.parser")
                for enlace in soup_b.find_all("a"):
                    texto_nodo = enlace.text.strip()
                    texto_title = enlace.get("title", "").strip()
                    texto_completo = f"{texto_nodo} {texto_title}"
                    texto_min = texto_completo.lower()
                    href_edicto = enlace.get("href", "")
                    
                    if len(texto_min) < 20 or ("lang=" in href_edicto and not "pdf" in texto_min):
                        continue
                        
                    if any(patron in texto_min for patron in patrones_empleo):
                        url_edicto_completa = href_edicto if href_edicto.startswith("http") else f"{url_base}{href_edicto}"
                        
                        if es_edicto_nuevo(url_edicto_completa):
                            enunciado_limpio = " ".join(texto_completo.split())
                            guardar_edicto(enunciado_limpio, url_edicto_completa)
                            nuevos_procesos.append({
                                "titulo": enunciado_limpio,
                                "enlace": url_edicto_completa
                            })
            except Exception:
                pass
            time.sleep(0.3)
            
        return None, nuevos_procesos
    except Exception as e:
        return {"error": str(e)}, []

# 🎛️ PANEL VISUAL PARA EL USUARIO
@app.route('/')
def home():
    html_panel = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Panel de Control BOIB</title>
        <meta charset="utf-8">
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; text-align: center; background: #0d1117; color: #c9d1d9; padding: 50px; }
            .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 30px; max-width: 700px; margin: 0 auto; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            h1 { color: #58a6ff; margin-bottom: 10px; }
            p { color: #8b949e; font-size: 16px; }
            .btn { background: #238636; color: white; padding: 12px 24px; border: 1px solid rgba(240,246,252,0.1); border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
            .btn:hover { background: #2ea043; }
            #resultado { margin-top: 30px; text-align: left; background: #0d1117; padding: 20px; border-radius: 6px; border: 1px solid #30363d; min-height: 50px; }
            ul { padding-left: 20px; }
            li { margin-bottom: 12px; }
            a { color: #58a6ff; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
        <script>
            async function activarBuscador() {
                const resDiv = document.getElementById('resultado');
                resDiv.innerHTML = "<span style='color: #8b949e;'>🔍 Conectando con el BOIB y cruzando datos... Por favor, espera unos segundos.</span>";
                try {
                    const response = await fetch('/ejecutar-secreto');
                    const data = await response.json();
                    if(data.status === "ok") {
                        if(data.nuevos.length === 0) {
                            resDiv.innerHTML = "<span style='color: #7ee787;'>✅ Análisis completado con éxito. No se han encontrado nuevas convocatorias en los últimos boletines inspeccionados (0 nuevos).</span>";
                        } else {
                            let lista = "<h3 style='color: #ff7b72; margin-top:0;'>🎉 ¡Nuevas Convocatorias Detectadas!</h3><ul>";
                            data.nuevos.forEach(item => {
                                lista += `<li><a href="${item.enlace}" target="_blank">${item.titulo}</a></li>`;
                            });
                            lista += "</ul>";
                            resDiv.innerHTML = lista;
                        }
                    } else {
                        resDiv.innerHTML = "<span style='color: #f85149;'>❌ Error en el motor: " + data.mensaje + "</span>";
                    }
                } catch(e) {
                    resDiv.innerHTML = "<span style='color: #f85149;'>❌ Error de comunicación con el servidor de Render.</span>";
                }
            }
        </script>
    </head>
    <body>
        <div class="card">
            <h1>Buscador BOIB - Modo Servidor</h1>
            <p>Ejecución bajo demanda para optimizar recursos en la nube.</p>
            <hr style="border-color: #30363d; margin: 20px 0;">
            <button class="btn" onclick="activarBuscador()">🚀 Activar Escáner Secreto</button>
            <div id="resultado"><span style="color: #8b949e;">Esperando activación...</span></div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_panel)

# 🔗 EL ENLACE DE PETICIÓN EXTERNA (EL ENPOINT DE RENDER)
@app.route('/ejecutar-secreto', methods=['GET'])
def endpoint_secreto():
    error, nuevos = ejecutar_escaneo_boib()
    if error:
        return jsonify({"status": "error", "mensaje": error["error"]}), 500
    return jsonify({"status": "ok", "nuevos": nuevos}), 200

# 🌐 CONEXIÓN DEL ENLACE DINÁMICO DE RENDER
if __name__ == '__main__':
    # Aquí es donde mapeamos el puerto que Render nos exige de forma obligatoria
    puerto_render = int(os.environ.get("PORT", 5000))
    # Escuchamos en 0.0.0.0 para que sea accesible públicamente en internet
    app.run(host='0.0.0.0', port=puerto_render)