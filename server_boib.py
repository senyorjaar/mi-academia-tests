import os
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory

try:
    from botBuscadorOposiciones import buscar_novedades_reales_boib, detectar_escala
except ImportError:
    buscar_novedades_reales_boib = None
    detectar_escala = lambda t: "S/E"

app = Flask(__name__, static_folder='.', static_url_path='')
DB_NAME = "oposiciones.db"

def obtener_conexion():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    return conexion

def normalizar(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    forma_nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in forma_nfkd if not unicodedata.combining(c)])

# -------------------------------------------------------------
# RUTAS DE PÁGINAS Y VISTAS
# -------------------------------------------------------------
@app.route('/')
def index():
    if os.path.exists('login.html'):
        return send_from_directory('.', 'login.html')
    return "<h1>Bienvenido al Servidor de Oposiciones</h1>"

@app.route('/<path:archivo>')
def servir_archivos(archivo):
    if archivo.startswith('static/'):
        archivo = archivo.replace('static/', '', 1)
    if os.path.exists(archivo):
        return send_from_directory('.', archivo)
    return "<h3>Error 404: Archivo no encontrado</h3>", 404

# -------------------------------------------------------------
# EJECUTAR ESCANER DESDE LA WEB
# -------------------------------------------------------------
@app.route('/ejecutar-escaner', methods=['POST', 'GET'])
def ejecutar_escaner():
    if buscar_novedades_reales_boib:
        try:
            total = buscar_novedades_reales_boib()
            return jsonify({"estado": "ok", "mensaje": f"Escaneo completado. Convocatorias analizadas y clasificadas por Escalas TREBEP."})
        except Exception as e:
            return jsonify({"estado": "error", "mensaje": str(e)}), 500
    return jsonify({"estado": "error", "mensaje": "Módulo de búsqueda no disponible"}), 500

# -------------------------------------------------------------
# AUTENTICACIÓN (LOGIN Y REGISTRO)
# -------------------------------------------------------------
@app.route('/registro', methods=['POST'])
def registro():
    datos = request.get_json() or {}
    nombre = datos.get('nombre', '').strip()
    email = datos.get('email', '').strip()
    password = datos.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Correo y contraseña requeridos"}), 400

    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO usuarios (nombre, email, password, fecha_registro) 
            VALUES (?, ?, ?, datetime('now'))
        """, (nombre, email, password))
        con.commit()
        con.close()
        return jsonify({"mensaje": "Registro completado con éxito."})
    except sqlite3.IntegrityError:
        return jsonify({"error": "El correo electrónico ya está registrado."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    datos = request.get_json() or {}
    identificador = (datos.get('email') or datos.get('usuario') or datos.get('identificador') or '').strip()
    password = datos.get('password', '').strip()

    if not identificador or not password:
        return jsonify({"error": "Indica tu usuario/correo y contraseña"}), 400

    con = obtener_conexion()
    cur = con.cursor()
    cur.execute("""
        SELECT id, nombre, email 
        FROM usuarios 
        WHERE (email = ? OR nombre = ?) AND password = ?
    """, (identificador, identificador, password))
    usuario = cur.fetchone()
    con.close()

    if usuario:
        return jsonify({
            "mensaje": f"Bienvenido, {usuario['nombre']}",
            "usuario": dict(usuario)
        })
    return jsonify({"error": "Credenciales inválidas"}), 401

# -------------------------------------------------------------
# BANCO DE TESTS: EXCLUSIVAMENTE POR NOMBRE DE CARPETA Y ARCHIVO
# -------------------------------------------------------------
@app.route('/temas', methods=['GET'])
def listar_temas():
    con = obtener_conexion()
    cur = con.cursor()

    cur.execute("PRAGMA table_info(preguntas)")
    cols = [c[1] for c in cur.fetchall()]

    carpetas = []
    archivos = []

    if "tema" in cols:
        cur.execute("SELECT DISTINCT tema FROM preguntas WHERE tema IS NOT NULL AND tema != '' ORDER BY tema ASC")
        carpetas = [f[0] for f in cur.fetchall()]

    if "archivo_origen" in cols:
        cur.execute("SELECT DISTINCT archivo_origen FROM preguntas WHERE archivo_origen IS NOT NULL AND archivo_origen != '' ORDER BY archivo_origen ASC")
        archivos = [f[0] for f in cur.fetchall()]

    con.close()

    return jsonify({
        "carpetas": carpetas,
        "archivos": archivos
    })

@app.route('/obtener-preguntas', methods=['GET'])
def obtener_preguntas():
    selector = request.args.get('tema', 'todos').strip()
    limite = int(request.args.get('limite', 20))

    con = obtener_conexion()
    cur = con.cursor()

    cur.execute("PRAGMA table_info(preguntas)")
    cols = [c[1] for c in cur.fetchall()]

    col_id = "id" if "id" in cols else cols[0]
    col_preg = "pregunta" if "pregunta" in cols else "enunciado"
    col_tema = "tema" if "tema" in cols else "NULL as tema"
    col_archivo = "archivo_origen" if "archivo_origen" in cols else "NULL as archivo_origen"
    col_exp = "explicacion" if "explicacion" in cols else "NULL as explicacion"
    col_cor = "correcta" if "correcta" in cols else "respuesta_correcta"

    consulta = f"SELECT {col_id}, {col_preg}, {col_tema}, {col_archivo}, {col_exp}, {col_cor}, opcion_a, opcion_b, opcion_c, opcion_d FROM preguntas"
    parametros = []

    if selector != 'todos' and selector != '':
        # Filtra bien por carpeta o bien por archivo de origen exacto
        consulta += f" WHERE {col_tema} = ? OR {col_archivo} = ?"
        parametros.extend([selector, selector])

    consulta += " ORDER BY RANDOM() LIMIT ?"
    parametros.append(limite)

    cur.execute(consulta, parametros)
    filas = cur.fetchall()
    con.close()

    preguntas_formateadas = []
    for f in filas:
        dict_f = dict(f)
        opciones = [
            dict_f.get('opcion_a', ''),
            dict_f.get('opcion_b', ''),
            dict_f.get('opcion_c', ''),
            dict_f.get('opcion_d', '')
        ]

        resp_correcta = str(dict_f.get(col_cor, '')).strip().upper()
        indice_correcto = 0
        if resp_correcta in ['0', '1', '2', '3']:
            indice_correcto = int(resp_correcta)
        elif resp_correcta in ['A', 'B', 'C', 'D']:
            indice_correcto = ord(resp_correcta) - ord('A')
        else:
            for idx, opc in enumerate(opciones):
                if normalizar(resp_correcta) == normalizar(opc):
                    indice_correcto = idx
                    break

        preguntas_formateadas.append({
            "id": dict_f.get(col_id),
            "pregunta": dict_f.get(col_preg),
            "carpeta": dict_f.get(col_tema, "General"),
            "archivo": dict_f.get(col_archivo, ""),
            "opciones": opciones,
            "correcta": indice_correcto,
            "explicacion": dict_f.get(col_exp, "") or "Respuesta oficial según plantilla."
        })

    return jsonify({"preguntas": preguntas_formateadas})

# -------------------------------------------------------------
# CONSULTA Y FILTRADO DEL BUSCADOR BOIB
# -------------------------------------------------------------
@app.route('/buscar-convocatorias', methods=['GET'])
def buscar_convocatorias():
    termino = normalizar(request.args.get('termino', ''))
    tipo_ambito = request.args.get('tipo', 'todos').lower().strip()
    filtro_escala = request.args.get('escala', 'todos').upper().strip()
    ver_historico = request.args.get('historico', 'false').lower() == 'true'

    con = obtener_conexion()
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tablas = [r['name'] for r in cur.fetchall()]

    registros_raw = []

    for tabla_nombre in ['edictos_detectados', 'edictos_boib', 'procesos']:
        if tabla_nombre in tablas:
            cur.execute(f"PRAGMA table_info({tabla_nombre})")
            cols = [c[1] for c in cur.fetchall()]

            campo_tit = "titulo" if "titulo" in cols else "puesto"
            campo_url = "enlace" if "enlace" in cols else "url"
            campo_pdf = "enlace_pdf" if "enlace_pdf" in cols else "NULL"
            campo_esc = "escala" if "escala" in cols else "NULL"
            campo_fec = "fecha_registro" if "fecha_registro" in cols else "CURRENT_TIMESTAMP"

            try:
                cur.execute(f"""
                    SELECT id, {campo_tit}, {campo_url}, {campo_fec}, {campo_pdf}, {campo_esc} 
                    FROM {tabla_nombre} 
                    ORDER BY id DESC
                """)
                for f in cur.fetchall():
                    registros_raw.append((f[0], f[1], f[2], f[3], f[4], f[5]))
            except Exception:
                pass

    con.close()

    vistos = set()
    elementos_unicos = []
    for id_reg, tit, enl, fecha, pdf, esc in registros_raw:
        if enl and enl not in vistos and tit:
            vistos.add(enl)
            elementos_unicos.append((id_reg, tit.strip(), enl.strip(), fecha, pdf, esc))

    fecha_limite = datetime.now() - timedelta(days=35)
    lista_final = []

    for id_reg, titulo, enlace, fecha_str, enlace_pdf, escala in elementos_unicos:
        es_antigua = False
        if fecha_str:
            try:
                f_texto = str(fecha_str).split('.')[0].strip()
                if '-' in f_texto and len(f_texto) >= 10:
                    f_obj = datetime.strptime(f_texto[:10], "%Y-%m-%d")
                    if f_obj < fecha_limite:
                        es_antigua = True
            except Exception:
                es_antigua = False

        if ver_historico:
            if not es_antigua:
                continue
        else:
            if es_antigua:
                continue

        escala_def = escala if (escala and str(escala).strip() not in ['NULL', 'S/E', 'None']) else detectar_escala(titulo)

        if filtro_escala and filtro_escala != 'TODOS':
            if escala_def.upper() != filtro_escala:
                continue

        t_norm = normalizar(titulo)

        if any(k in t_norm for k in ["consell", "insular", "formentera", "menorca", "eivissa", "mallorca"]):
            ambito = "insular"
            ente = "Consell Insular"
        elif any(k in t_norm for k in ["ajuntament", "ayuntamiento", "alcudia", "marratxi", "palma", "calvia", "andratx", "binissalem", "castell", "manacor", "alaro", "inca"]):
            ambito = "municipal"
            ente = "Ayuntamiento"
        else:
            ambito = "autonomica"
            ente = "Govern de les Illes Balears"

        if tipo_ambito and tipo_ambito != 'todos' and tipo_ambito != ambito:
            continue

        if termino:
            e_norm = normalizar(ente)
            if (termino not in t_norm) and (termino not in e_norm):
                continue

        pdf_final = enlace_pdf if (enlace_pdf and str(enlace_pdf) not in ['NULL', 'None']) else ""
        if not pdf_final and "/eboibfront/" in enlace:
            pdf_final = enlace.replace("/versio-html/", "/pdf/").replace(".html", ".pdf")

        lista_final.append({
            "id": id_reg,
            "puesto": titulo,
            "ente": ente,
            "ambito": ambito,
            "escala": escala_def,
            "url": enlace,
            "url_pdf": pdf_final,
            "fecha": str(fecha_str)[:10] if fecha_str else "Reciente"
        })

    return jsonify({"estado": "ok", "datos": lista_final})

if __name__ == '__main__':
    puerto = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=puerto, debug=True)