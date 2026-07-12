# =====================================================================
# ARCHIVO: server.py (Versión de Pruebas con Historial)
# FUNCIÓN: Servidor Backend Completo con Soporte de Usuarios e Historial
# TECNOLOGÍAS: Starlette, Uvicorn, SQLite3 y Hashlib (Encriptación)
# =====================================================================

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import sqlite3
import uvicorn
import hashlib
from datetime import datetime

async def inicio(request):
    return JSONResponse({"mensaje": "¡Servidor de Pruebas Activo!"})

# =====================================================================
# 🔐 MÓDULO: SEGURIDAD Y GESTIÓN DE USUARIOS
# =====================================================================

async def registrar_usuario(request):
    try:
        datos = await request.json()
        nombre = datos.get("nombre", "").strip()
        email = datos.get("email", "").strip().lower()
        password_plana = datos.get("password", "").strip()

        if not nombre or not email or not password_plana:
            return JSONResponse({"error": "Todos los campos son obligatorios"}, status_code=400)

        password_encriptada = hashlib.sha256(password_plana.encode('utf-8')).hexdigest()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conexion = sqlite3.connect("oposiciones.db")
        cursor = conexion.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO usuarios (nombre, email, password, fecha_registro)
                VALUES (?, ?, ?, ?)
            """, (nombre, email, password_encriptada, fecha_hoy))
            conexion.commit()
            return JSONResponse({"mensaje": "¡Usuario registrado con éxito!"})
        except sqlite3.IntegrityError:
            return JSONResponse({"error": "El correo electrónico ya está registrado"}, status_code=400)
        finally:
            conexion.close()
    except Exception as e:
        return JSONResponse({"error": f"Fallo en el servidor: {str(e)}"}, status_code=500)

async def login_usuario(request):
    try:
        datos = await request.json()
        email = datos.get("email", "").strip().lower()
        password_plana = datos.get("password", "").strip()

        if not email or not password_plana:
            return JSONResponse({"error": "Email y contraseña requeridos"}, status_code=400)

        password_encriptada = hashlib.sha256(password_plana.encode('utf-8')).hexdigest()

        conexion = sqlite3.connect("oposiciones.db")
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre, password FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()
        conexion.close()

        if usuario and usuario[2] == password_encriptada:
            return JSONResponse({
                "mensaje": "¡Login correcto!",
                "usuario": {"id": usuario[0], "nombre": usuario[1]}
            })
        else:
            return JSONResponse({"error": "Credenciales incorrectas"}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": f"Fallo en el servidor: {str(e)}"}, status_code=500)


# ---------------------------------------------------------------------
# 📊 NUEVA FUNCIÓN: guardar_historial_test
# OBJETIVO: Recibir la nota final del alumno y guardarla en la BD.
# ---------------------------------------------------------------------
async def guardar_historial_test(request):
    try:
        datos = await request.json()
        usuario_id = datos.get("usuario_id")
        tema = datos.get("tema", "").strip()
        aciertos = datos.get("aciertos")
        total_preguntas = datos.get("total_preguntas")
        nota = datos.get("nota")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if usuario_id is None or not tema or aciertos is None or total_preguntas is None or nota is None:
            return JSONResponse({"error": "Datos de historial incompletos"}, status_code=400)

        conexion = sqlite3.connect("oposiciones.db")
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO historial_tests (usuario_id, tema, aciertos, total_preguntas, nota, fecha_test)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (usuario_id, tema, aciertos, total_preguntas, nota, fecha_hoy))
        conexion.commit()
        conexion.close()

        return JSONResponse({"mensaje": "¡Nota del examen guardada en tu historial!"})
    except Exception as e:
        return JSONResponse({"error": f"Error al guardar historial: {str(e)}"}, status_code=500)


# =====================================================================
# 📚 MÓDULOS ANTERIORES (Buscador del BOIB y Banco de Preguntas)
# =====================================================================

async def obtener_procesos(request):
    params = request.query_params
    filtro_tipo = params.get("tipo", None)
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT id, puesto, ente, url, fecha_registro 
        FROM procesos 
        WHERE fecha_registro >= DATE('now', '-30 days')
        ORDER BY id DESC
    """)
    filas = cursor.fetchall()
    conexion.close()
    
    resultado = []
    for f in filas:
        ente_nombre = f[2].upper()
        if "GOVERN" in ente_nombre or "CAIB" in ente_nombre:
            tipo_institucion = "autonomica"
        elif "CONSELL" in ente_nombre:
            tipo_institucion = "insular"
        else:
            tipo_institucion = "municipal"
            
        datos_proceso = {
            "id": f[0], "puesto": f[1], "ente": f[2], "url": f[3], "fecha_registro": f[4], "tipo": tipo_institucion
        }
        if filtro_tipo and tipo_institucion != filtro_tipo:
            continue
        resultado.append(datos_proceso)
    return JSONResponse(resultado)

async def obtener_tests(request):
    conexion = sqlite3.connect("oposiciones.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT id, tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion FROM preguntas")
    filas = cursor.fetchall()
    conexion.close()
    
    resultado = []
    for f in filas:
        resultado.append({
            "id": f[0],
            "tema": f[1].strip() if f[1] else "",
            "enunciado": f[2].strip() if f[2] else "",
            "opcion_a": f[3].strip() if f[3] else "",
            "opcion_b": f[4].strip() if f[4] else "",
            "opcion_c": f[5].strip() if f[5] else "",
            "opcion_d": f[6].strip() if f[6] else "",
            "correcta": f[7].strip() if f[7] else "A",
            "justificacion": f[8].strip() if f[8] else "Fundamento jurídico no disponible."
        })
    return JSONResponse(resultado)

# Inyección de todas las rutas activas en la app (Incluyendo /historial)
rutas = [
    Route("/", endpoint=inicio),
    Route("/procesos", endpoint=obtener_procesos),
    Route("/tests", endpoint=obtener_tests),
    Route("/registro", endpoint=registrar_usuario, methods=["POST"]),
    Route("/login", endpoint=login_usuario, methods=["POST"]),
    Route("/historial", endpoint=guardar_historial_test, methods=["POST"])
]

opciones_cors = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(routes=rutas, middleware=opciones_cors)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)