import os
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, redirect, session

try:
    from botBuscadorOposiciones import buscar_novedades_reales_boib, detectar_escala
except ImportError:
    buscar_novedades_reales_boib = None
    detectar_escala = lambda t: "S/E"

# -------------------------------------------------------------
# CONFIGURACIÓN GENERAL Y RUTAS ABSOLUTAS
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
app.secret_key = "clave_secreta_oposiciones_balears_segura"
DB_NAME = os.path.join(BASE_DIR, "oposiciones.db")

def obtener_conexion():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    return conexion

def inicializar_sistema():
    """Garantiza la estructura correcta de la tabla usuarios y crea la cuenta root."""
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS usuarios")
        cursor.execute("""
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'admin'
            )
        """)
        
        cursor.execute("""
            INSERT INTO usuarios (usuario, password, rol)
            VALUES ('root', 'root', 'admin')
        """)
        
        conexion.commit()
        conexion.close()
        print("Sistema y credenciales inicializados.")
    except Exception as e:
        print(f"Error inicializando tabla usuarios: {e}")

inicializar_sistema()

def normalizar(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    forma_nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in forma_nfkd if not unicodedata.combining(c)])

# -------------------------------------------------------------
# RUTAS DE ACCESO Y PROTECCIÓN DE VISTAS
# -------------------------------------------------------------
@app.route('/')
def index():
    if session.get('autenticado'):
        return redirect('/panel.html')
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/login.html')
def servir_login():
    if session.get('autenticado'):
        return redirect('/panel.html')
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/panel.html')
def servir_panel():
    if not session.get('autenticado'):
        return redirect('/login.html')
    return send_from_directory(BASE_DIR, 'panel.html')

@app.route('/quiz.html')
def servir_quiz():
    if not session.get('autenticado'):
        return redirect('/login.html')
    return send_from_directory(BASE_DIR, 'quiz.html')

# -------------------------------------------------------------
# API DE AUTENTICACIÓN Y SESIONES
# -------------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    datos = request.get_json(silent=True) or {}
    usuario = datos.get('usuario', '').strip()
    password = datos.get('password', '').strip()

    if not usuario or not password:
        return jsonify({"exito": False, "mensaje": "Ingresa usuario y contraseña."}), 400

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, usuario, rol FROM usuarios WHERE usuario = ? AND password = ?", (usuario, password))
        user = cursor.fetchone()
        conexion.close()

        if user:
            session['autenticado'] = True
            session['usuario'] = user['usuario']
            session['rol'] = user['rol']
            return jsonify({
                "exito": True,
                "usuario": user["usuario"],
                "rol": user["rol"]
            })
        return jsonify({"exito": False, "mensaje": "Usuario o contraseña incorrectos."}), 401
    except Exception as e:
        return jsonify({"exito": False, "mensaje": f"Error interno: {str(e)}"}), 500

@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.clear()
    return redirect('/login.html')

# -------------------------------------------------------------
# API DEL BUSCADOR DE OPOSICIONES (BOIB)
# -------------------------------------------------------------
@app.route('/api/buscar', methods=['GET'])
def api_buscar():
    if not session.get('autenticado'):
        return jsonify({"exito": False, "error": "Acceso no autorizado"}), 401

    filtro_escala = request.args.get('escala', '').strip().upper()
    filtro_isla = normalizar(request.args.get('isla', ''))
    filtro_termino = normalizar(request.args.get('q', ''))

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Obtenemos las convocatorias más recientes sin filtrar fecha por texto
        cursor.execute("""
            SELECT id, titulo, organismo, fecha, url, escala, isla, num_plazas 
            FROM convocatorias 
            ORDER BY id DESC LIMIT 300
        """)
        filas = cursor.fetchall()
        conexion.close()

        resultados = []
        for fila in filas:
            fila_dict = dict(fila)
            titulo_norm = normalizar(fila_dict.get('titulo', ''))
            org_norm = normalizar(fila_dict.get('organismo', ''))
            isla_norm = normalizar(fila_dict.get('isla', ''))
            escala_row = str(fila_dict.get('escala', '')).strip().upper()

            # Filtro por Escala TREBEP
            if filtro_escala and filtro_escala not in ["TODAS", "TODOS"]:
                if filtro_escala not in escala_row:
                    continue

            # Filtro por Ámbito / Isla
            if filtro_isla and filtro_isla not in ["todas", "todos"]:
                if filtro_isla not in isla_norm and filtro_isla not in org_norm:
                    continue

            # Filtro por término libre
            if filtro_termino:
                if filtro_termino not in titulo_norm and filtro_termino not in org_norm:
                    continue

            resultados.append(fila_dict)

        return jsonify({
            "exito": True,
            "total": len(resultados),
            "datos": resultados
        })

    except Exception as e:
        return jsonify({"exito": False, "error": str(e)}), 500

@app.route('/api/actualizar_boib', methods=['POST'])
def api_actualizar_boib():
    if not session.get('autenticado'):
        return jsonify({"exito": False, "error": "No autorizado"}), 401

    if not buscar_novedades_reales_boib:
        return jsonify({"exito": False, "mensaje": "Módulo botBuscadorOposiciones no disponible"}), 500

    try:
        novedades = buscar_novedades_reales_boib()
        return jsonify({
            "exito": True,
            "mensaje": f"Sincronización completada. Nuevos registros: {novedades}"
        })
    except Exception as e:
        return jsonify({"exito": False, "error": str(e)}), 500

# -------------------------------------------------------------
# API DEL SIMULADOR DE TESTS / QUIZ
# -------------------------------------------------------------
@app.route('/api/carpetas', methods=['GET'])
def api_carpetas():
    if not session.get('autenticado'):
        return jsonify({"exito": False, "error": "No autorizado"}), 401

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT DISTINCT categoria 
            FROM preguntas 
            WHERE categoria IS NOT NULL AND categoria != ''
            ORDER BY categoria ASC
        """)
        filas = cursor.fetchall()
        conexion.close()

        carpetas = [fila["categoria"] for fila in filas]
        return jsonify({"exito": True, "carpetas": carpetas})
    except Exception as e:
        return jsonify({"exito": False, "error": str(e)}), 500

@app.route('/api/archivos', methods=['GET'])
def api_archivos():
    if not session.get('autenticado'):
        return jsonify({"exito": False, "error": "No autorizado"}), 401

    carpeta = request.args.get('carpeta', '').strip()
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        if carpeta:
            cursor.execute("""
                SELECT DISTINCT archivo_origen 
                FROM preguntas 
                WHERE categoria = ? AND archivo_origen IS NOT NULL AND archivo_origen != ''
                ORDER BY archivo_origen ASC
            """, (carpeta,))
        else:
            cursor.execute("""
                SELECT DISTINCT archivo_origen 
                FROM preguntas 
                WHERE archivo_origen IS NOT NULL AND archivo_origen != ''
                ORDER BY archivo_origen ASC
            """)
        filas = cursor.fetchall()
        conexion.close()

        archivos = [fila["archivo_origen"] for fila in filas]
        return jsonify({"exito": True, "archivos": archivos})
    except Exception as e:
        return jsonify({"exito": False, "error": str(e)}), 500

@app.route('/api/preguntas', methods=['GET'])
def api_preguntas():
    if not session.get('autenticado'):
        return jsonify({"exito": False, "error": "No autorizado"}), 401

    carpeta = request.args.get('carpeta', '').strip()
    archivo = request.args.get('archivo', '').strip()
    limite = request.args.get('limite', default=20, type=int)

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        query = "SELECT id, pregunta, opcion_a, opcion_b, opcion_c, opcion_d, respuesta_correcta, explicacion, categoria, archivo_origen FROM preguntas WHERE 1=1"
        parametros = []

        if carpeta:
            query += " AND categoria = ?"
            parametros.append(carpeta)

        if archivo:
            query += " AND archivo_origen = ?"
            parametros.append(archivo)

        query += " ORDER BY RANDOM() LIMIT ?"
        parametros.append(limite)

        cursor.execute(query, parametros)
        filas = cursor.fetchall()
        conexion.close()

        lista_preguntas = [dict(fila) for fila in filas]
        return jsonify({
            "exito": True,
            "total": len(lista_preguntas),
            "preguntas": lista_preguntas
        })
    except Exception as e:
        return jsonify({"exito": False, "error": str(e)}), 500

# -------------------------------------------------------------
# ARCHIVOS ESTÁTICOS
# -------------------------------------------------------------
@app.route('/<path:archivo>')
def servir_archivos(archivo):
    if archivo.startswith('static/'):
        archivo = archivo.replace('static/', '', 1)

    ruta_completa = os.path.join(BASE_DIR, archivo)
    if os.path.exists(ruta_completa) and os.path.isfile(ruta_completa):
        return send_from_directory(BASE_DIR, archivo)

    return f"<h3>Error 404: El archivo '{archivo}' no existe en el servidor</h3>", 404

# -------------------------------------------------------------
# ARRANQUE
# -------------------------------------------------------------
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto, debug=True)