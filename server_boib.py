# =====================================================================
# ARCHIVO: server_boib.py
# FUNCIÓN: Servidor web central, autenticación persistente, API BOIB y motor de tests
# TECNOLOGÍAS: Python 3 (http.server nativo), SQLite3, Cookies HTTP
# =====================================================================

import os
import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http import cookies
import uuid
import datetime

try:
    import botBuscadorOposiciones
except ImportError:
    botBuscadorOposiciones = None

DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(DIRECTORIO_BASE, "oposiciones.db")
PUERTO = int(os.environ.get("PORT", 8000))

def obtener_db_conexion():
    con = sqlite3.connect(DB_NAME)
    con.row_factory = sqlite3.Row
    return con

def inicializar_tabla_sesiones():
    """Crea la tabla de sesiones persistente en SQLite para evitar caídas de login en Render."""
    with obtener_db_conexion() as con:
        cursor = con.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sesiones_activas (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                usuario TEXT NOT NULL,
                rol TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)
        con.commit()

class ServidorAcademiaHandler(SimpleHTTPRequestHandler):

    def obtener_cookie_sesion(self):
        cabecera_cookie = self.headers.get("Cookie")
        if not cabecera_cookie:
            return None
        c = cookies.SimpleCookie()
        try:
            c.load(cabecera_cookie)
            if "sesion_id" in c:
                return c["sesion_id"].value
        except Exception:
            return None
        return None

    def usuario_autenticado(self):
        token = self.obtener_cookie_sesion()
        if not token:
            return None
        try:
            with obtener_db_conexion() as con:
                cursor = con.cursor()
                cursor.execute("""
                    SELECT usuario_id, usuario, rol 
                    FROM sesiones_activas 
                    WHERE token = ?
                """, (token,))
                fila = cursor.fetchone()
                if fila:
                    return {
                        "usuario_id": fila["usuario_id"],
                        "usuario": fila["usuario"],
                        "rol": fila["rol"]
                    }
        except Exception:
            return None
        return None

    def responder_json(self, datos, codigo=200, set_cookie_header=None):
        payload = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if set_cookie_header:
            self.send_header("Set-Cookie", set_cookie_header)
        self.end_headers()
        self.wfile.write(payload)

    def redirigir(self, ruta_destino):
        self.send_response(302)
        self.send_header("Location", ruta_destino)
        self.end_headers()

    # -------------------------------------------------------------
    # CONTROL DE ACCESO Y ENDPOINTS (GET)
    # -------------------------------------------------------------
    def do_GET(self):
        url_desglosada = urllib.parse.urlparse(self.path)
        ruta = url_desglosada.path
        query = urllib.parse.parse_qs(url_desglosada.query)

        # Rutas raíz
        if ruta == "/" or ruta == "":
            if self.usuario_autenticado():
                self.redirigir("/panel.html")
            else:
                self.redirigir("/login.html")
            return

        # Rutas protegidas
        rutas_protegidas = ["/panel.html", "/quiz.html"]
        if ruta in rutas_protegidas:
            if not self.usuario_autenticado():
                self.redirigir(f"/login.html?redirect={urllib.parse.quote(ruta)}")
                return

        # API: Verificación de sesión
        if ruta == "/api/check_session":
            usuario = self.usuario_autenticado()
            if usuario:
                self.responder_json({"autenticado": True, "usuario": usuario["usuario"], "rol": usuario["rol"]})
            else:
                self.responder_json({"autenticado": False}, codigo=401)
            return

        # API: Cierre de sesión
        elif ruta == "/api/logout":
            token = self.obtener_cookie_sesion()
            if token:
                try:
                    with obtener_db_conexion() as con:
                        cursor = con.cursor()
                        cursor.execute("DELETE FROM sesiones_activas WHERE token = ?", (token,))
                        con.commit()
                except Exception:
                    pass

            cookie_expirada = "sesion_id=deleted; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax"
            self.send_response(302)
            self.send_header("Location", "/login.html")
            self.send_header("Set-Cookie", cookie_expirada)
            self.end_headers()
            return

        # API: Buscador de convocatorias BOIB
        elif ruta == "/api/buscar":
            if not self.usuario_autenticado():
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            dias = int(query.get("dias", ["30"])[0])
            ambito = query.get("ambito", ["todos"])[0].strip()
            escala = query.get("escala", ["TODAS"])[0].strip()
            texto_q = query.get("q", [""])[0].strip()

            condiciones = []
            parametros = []

            if dias <= 30:
                condiciones.append("(fecha_registro IS NULL OR julianday('now') - julianday(fecha_registro) <= ? OR fecha_registro >= date('now', '-30 days'))")
                parametros.append(dias)

            if ambito.lower() != "todos":
                condiciones.append("LOWER(COALESCE(ambito, 'Municipal')) = LOWER(?)")
                parametros.append(ambito)

            if escala.upper() != "TODAS":
                condiciones.append("LOWER(COALESCE(escala, 'S/E')) = LOWER(?)")
                parametros.append(escala)

            if texto_q:
                condiciones.append("(titulo LIKE ? OR organismo LIKE ?)")
                parametros.append(f"%{texto_q}%")
                parametros.append(f"%{texto_q}%")

            clausula_where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
            
            sql = f"""
                SELECT id, titulo, 
                       COALESCE(organismo, 'Administración Balear') as organismo, 
                       enlace, 
                       COALESCE(enlace_pdf, '') as enlace_pdf, 
                       COALESCE(escala, 'S/E') as escala, 
                       COALESCE(ambito, 'Municipal') as ambito, 
                       COALESCE(strftime('%d/%m/%Y', fecha_registro), substr(fecha_registro, 1, 10), 'Reciente') as fecha
                FROM edictos_boib
                {clausula_where}
                ORDER BY id DESC
            """

            try:
                with obtener_db_conexion() as con:
                    cursor = con.cursor()
                    cursor.execute(sql, parametros)
                    filas = [dict(r) for r in cursor.fetchall()]
                self.responder_json({"datos": filas, "total": len(filas)})
            except sqlite3.OperationalError as e:
                self.responder_json({"datos": [], "total": 0, "aviso": str(e)})
            return

        # API: Categorías y temas de tests
        elif ruta == "/api/quiz/categorias":
            if not self.usuario_autenticado():
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            with obtener_db_conexion() as con:
                cursor = con.cursor()
                cursor.execute("SELECT DISTINCT tema FROM preguntas WHERE tema IS NOT NULL ORDER BY tema ASC")
                categorias = [r["tema"] for r in cursor.fetchall()]

            self.responder_json({"categorias": categorias})
            return

        # API: Exámenes por carpeta
        elif ruta == "/api/quiz/examenes":
            if not self.usuario_autenticado():
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            tema = query.get("tema", [""])[0].strip()
            with obtener_db_conexion() as con:
                cursor = con.cursor()
                if tema:
                    cursor.execute("""
                        SELECT DISTINCT archivo_origen 
                        FROM preguntas 
                        WHERE tema = ? AND archivo_origen IS NOT NULL 
                        ORDER BY archivo_origen ASC
                    """, (tema,))
                else:
                    cursor.execute("SELECT DISTINCT archivo_origen FROM preguntas ORDER BY archivo_origen ASC")
                examenes = [r["archivo_origen"] for r in cursor.fetchall()]

            self.responder_json({"examenes": examenes})
            return

        # API: Banco de preguntas aleatorio
        elif ruta == "/api/quiz/preguntas":
            if not self.usuario_autenticado():
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            tema = query.get("tema", [""])[0].strip()
            examen = query.get("examen", [""])[0].strip()
            cantidad = query.get("cantidad", ["10"])[0].strip()

            condiciones = []
            parametros = []

            if tema:
                condiciones.append("tema = ?")
                parametros.append(tema)
            if examen:
                condiciones.append("archivo_origen = ?")
                parametros.append(examen)

            where_str = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
            limit_str = ""
            if cantidad.isdigit():
                limit_str = f" LIMIT {int(cantidad)}"

            sql = f"""
                SELECT id, tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion, archivo_origen
                FROM preguntas
                {where_str}
                ORDER BY RANDOM()
                {limit_str}
            """

            with obtener_db_conexion() as con:
                cursor = con.cursor()
                cursor.execute(sql, parametros)
                preguntas = [dict(r) for r in cursor.fetchall()]

            self.responder_json({"preguntas": preguntas, "total": len(preguntas)})
            return

        # Servir estáticos HTML, CSS, JS
        return super().do_GET()

    # -------------------------------------------------------------
    # ENDPOINTS DE ESCRITURA (POST)
    # -------------------------------------------------------------
    def do_POST(self):
        url_desglosada = urllib.parse.urlparse(self.path)
        ruta = url_desglosada.path

        longitud_contenido = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(longitud_contenido).decode("utf-8") if longitud_contenido > 0 else ""

        datos_json = {}
        if cuerpo:
            try:
                datos_json = json.loads(cuerpo)
            except Exception:
                pass

        if ruta == "/api/login":
            usuario_in = str(datos_json.get("usuario", "")).strip()
            password_in = str(datos_json.get("password", "")).strip()

            if not usuario_in or not password_in:
                self.responder_json({"exito": False, "mensaje": "Usuario y contraseña requeridos."}, codigo=400)
                return

            with obtener_db_conexion() as con:
                cursor = con.cursor()
                cursor.execute("""
                    SELECT id, usuario, password, rol 
                    FROM usuarios 
                    WHERE (LOWER(usuario) = LOWER(?) OR LOWER(COALESCE(email, '')) = LOWER(?))
                """, (usuario_in, usuario_in))
                usuario_db = cursor.fetchone()

                if usuario_db and usuario_db["password"] == password_in:
                    token_sesion = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO sesiones_activas (token, usuario_id, usuario, rol)
                        VALUES (?, ?, ?, ?)
                    """, (token_sesion, usuario_db["id"], usuario_db["usuario"], usuario_db["rol"]))
                    con.commit()

                    cookie_header = f"sesion_id={token_sesion}; Path=/; HttpOnly; SameSite=Lax"
                    self.responder_json({"exito": True, "mensaje": "Acceso autorizado."}, set_cookie_header=cookie_header)
                else:
                    self.responder_json({"exito": False, "mensaje": "Credenciales inválidas."}, codigo=401)
            return

        elif ruta == "/api/actualizar_boib":
            if not self.usuario_autenticado():
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            if botBuscadorOposiciones and hasattr(botBuscadorOposiciones, "buscar_novedades_reales_boib"):
                try:
                    total = botBuscadorOposiciones.buscar_novedades_reales_boib()
                    self.responder_json({"exito": True, "mensaje": f"Sincronización completada. Se procesaron {total} convocatorias."})
                except Exception as e:
                    self.responder_json({"exito": False, "mensaje": f"Error durante la sincronización: {e}"}, codigo=500)
            else:
                self.responder_json({"exito": False, "mensaje": "Módulo escaneador BOIB no disponible."}, codigo=503)
            return

        elif ruta == "/api/quiz/guardar_resultado":
            usuario = self.usuario_autenticado()
            if not usuario:
                self.responder_json({"error": "No autorizado"}, codigo=401)
                return

            tema = str(datos_json.get("tema", "General")).strip()
            aciertos = int(datos_json.get("aciertos", 0))
            total = int(datos_json.get("total_preguntas", 0))
            nota = float(datos_json.get("nota", 0.0))

            with obtener_db_conexion() as con:
                cursor = con.cursor()
                cursor.execute("""
                    INSERT INTO historial_tests (usuario_id, tema, aciertos, total_preguntas, nota, fecha_test)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (usuario["usuario_id"], tema, aciertos, total, nota))
                con.commit()

            self.responder_json({"exito": True, "mensaje": "Resultado del test registrado en el historial."})
            return

        self.responder_json({"error": "Ruta no encontrada"}, codigo=404)

def iniciar_servidor():
    os.chdir(DIRECTORIO_BASE)
    inicializar_tabla_sesiones()
    servidor = HTTPServer(("0.0.0.0", PUERTO), ServidorAcademiaHandler)
    print(f"🚀 Servidor en ejecución en el puerto {PUERTO}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido de forma segura.")
        servidor.server_close()

if __name__ == "__main__":
    iniciar_servidor()