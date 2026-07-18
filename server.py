import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -------------------------------------------------------------
# CONFIGURACIÓN INICIAL DEL SERVIDOR
# -------------------------------------------------------------
app = FastAPI(title="API Academia de Oposiciones y Buscador BOIB")

# Permitir conexiones desde cualquier origen (esencial para que el frontend del móvil funcione)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# MODELOS DE DATOS (VALIDACIÓN DE ENTRADAS CON PYDANTIC)
# -------------------------------------------------------------
class UsuarioRegistro(BaseModel):
    """Estructura de datos requerida para registrar un nuevo usuario"""
    usuario: str
    contrasena: str

# -------------------------------------------------------------
# SECCIÓN 1: RUTAS DE AUTENTICACIÓN (LOGIN Y REGISTRO)
# -------------------------------------------------------------

@app.post("/registro")
def registrar_usuario(datos: UsuarioRegistro):
    conn = sqlite3.connect("oposiciones.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            contrasena TEXT
        )
    """)
    
    try:
        cursor.execute(
            "INSERT INTO usuarios (usuario, contrasena) VALUES (?, ?)", 
            (datos.usuario, datos.contrasena)
        )
        conn.commit()
        return {"estado": "ok", "mensaje": "Usuario registrado con éxito"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado")
    finally:
        conn.close()

@app.post("/login")
def iniciar_sesion(datos: UsuarioRegistro):
    conn = sqlite3.connect("oposiciones.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            contrasena TEXT
        )
    """)
    
    cursor.execute(
        "SELECT * FROM usuarios WHERE usuario = ? AND contrasena = ?", 
        (datos.usuario, datos.contrasena)
    )
    usuario_encontrado = cursor.fetchone()
    conn.close()
    
    if usuario_encontrado:
        return {"estado": "ok", "mensaje": "Acceso concedido"}
    else:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

# -------------------------------------------------------------
# SECCIÓN 2: MÓDULO DE PROCESOS (CORREGIDO PARA TU TABLA ORIGINAL)
# -------------------------------------------------------------

@app.get("/buscar-convocatorias")
def buscar_convocatorias(termino: str = "", tipo: str = "todos"):
    """
    MANTENIMIENTO: Módulo unificado que filtra por ámbito (tipo) y por palabra clave.
    Devuelve los nombres exactos esperados por el frontend: puesto, ente, type, url.
    """
    conn = sqlite3.connect("oposiciones.db")
    cursor = conn.cursor()
    
    try:
        # Consulta base
        query = "SELECT puesto, ente, type, url FROM convocatorias WHERE 1=1"
        parametros = []
        
        # Filtro 1: Por palabra clave (Buscador por texto)
        if termino:
            query += " AND (LOWER(puesto) LIKE ? OR LOWER(ente) LIKE ?)"
            termino_busqueda = f"%{termino.lower()}%"
            parametros.extend([termino_busqueda, termino_busqueda])
            
        # Filtro 2: Por ámbito administrativo (Botones de Ver todo, Municipales...)
        if tipo != "todos":
            query += " AND type = ?"
            parametros.append(tipo)
            
        # Ordenamos para ver siempre los últimos publicados primero
        query += " ORDER BY id DESC"
        
        cursor.execute(query, parametros)
        filas = cursor.fetchall()
        
        # MANTENIMIENTO: Formateamos la respuesta JSON usando las claves exactas de tu panel original
        resultados = []
        for fila in filas:
            resultados.append({
                "puesto": fila[0],
                "ente": fila[1],
                "type": fila[2],
                "url": fila[3]
            })
            
        return {"estado": "ok", "datos": resultados}
        
    except sqlite3.OperationalError:
        # Control por si la tabla del bot rastreador no se ha creado en Render
        return {
            "estado": "error", 
            "mensaje": "La tabla 'convocatorias' no existe en la base de datos de Render. Ejecuta el scraping."
        }
    finally:
        conn.close()

# -------------------------------------------------------------
# ARRANQUE LOCAL DEL SERVIDOR
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)