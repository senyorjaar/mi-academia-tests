import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -------------------------------------------------------------
# CONFIGURACIÓN INICIAL DEL SERVIDOR
# -------------------------------------------------------------
app = FastAPI(title="API Academia de Oposiciones y Buscador BOIB")

# Permitir conexiones desde cualquier origen (esencial para movilidad)
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
# SECCIÓN 2: MÓDULO DE PROCESOS (CON Mapeo Dinámico Antierrores)
# -------------------------------------------------------------

@app.get("/buscar-convocatorias")
def buscar_convocatorias(termino: str = "", tipo: str = "todos"):
    """
    MANTENIMIENTO: Módulo adaptativo. Trae todas las columnas disponibles de la tabla
    e intenta mapear dinámicamente los campos al formato que tu 'panel.html' necesita
    para evitar que la app lance un error fatal si la estructura varía ligeramente.
    """
    conn = sqlite3.connect("oposiciones.db")
    # Configuramos el conector para leer las filas como diccionarios usando los nombres reales de las columnas
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Seleccionamos todo para evitar fallos si una columna específica cambió de nombre
        query = "SELECT * FROM convocatorias WHERE 1=1"
        parametros = []
        
        # Filtro por ámbito (Si tu base de datos usa la columna 'type' o 'ambito')
        if tipo != "todos":
            # Intentamos filtrar por 'type'. Si da error, el bloque 'except' lo gestionará de forma segura.
            query += " AND (type = ? OR ambito = ?)"
            parametros.extend([tipo, tipo])
            
        query += " ORDER BY id DESC"
        
        cursor.execute(query, parametros)
        filas = cursor.fetchall()
        
        resultados = []
        for fila in filas:
            # Convertimos la fila en un diccionario estándar de Python
            datos_fila = dict(fila)
            
            # Mapeo Inteligente: Buscamos alternativas por si las columnas se llaman diferente en SQLite
            puesto = datos_fila.get('puesto') or datos_fila.get('titulo') or "Puesto sin especificar"
            ente = datos_fila.get('ente') or datos_fila.get('organismo') or "Organismo local"
            ambito_tipo = datos_fila.get('type') or datos_fila.get('ambito') or "municipal"
            url_boib = datos_fila.get('url') or datos_fila.get('enlace') or "#"
            
            # Añadimos al JSON de salida con las claves exactas que tu tabla de 'panel.html' lee
            resultados.append({
                "puesto": puesto,
                "ente": ente,
                "type": ambito_tipo,
                "url": url_boib
            })
            
        return {"estado": "ok", "datos": resultados}
        
    except sqlite3.Error as error_sqlite:
        # Si la tabla no existe o las columnas fallan en el filtrado, devolvemos un JSON limpio avisando del problema
        return {
            "estado": "error", 
            "mensaje": f"Aviso de estructura: {str(error_sqlite)}. Asegúrate de que la tabla 'convocatorias' tenga datos cargados."
        }
    finally:
        conn.close()

# -------------------------------------------------------------
# ARRANQUE LOCAL DEL SERVIDOR
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)