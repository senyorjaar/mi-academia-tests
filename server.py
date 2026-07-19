import sqlite3
import datetime
import re
import jwt
import bcrypt
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Depends, Security, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Backend Oposiciones")

# CONFIGURACIONES DE SEGURIDAD (JWT)
SECRET_KEY = "MI_CLAVE_SECRETA_SUPER_SEGURA_CAMBIAME_EN_RENDER"
ALGORITHM = "HS256"
security_bearer = HTTPBearer()

DB_NAME = "oposiciones.db"
U_CALENDARIO = "https://www.caib.es/eboibfront/ES"

# Modelos de datos para recibir el Login
class LoginRequest(BaseModel):
    username: str
    password: str

# Montar la carpeta 'static' para servir tus páginas HTML de la interfaz
app.mount("/static", StaticFiles(directory="static"), name="static")


# =====================================================================
# 🛠️ FUNCIONES AUXILIARES Y DE SEGURIDAD (Siempre arriba)
# =====================================================================

def hash_password(password: str) -> str:
    """Convierte una contraseña en texto plano en un hash seguro encriptado."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verificar_token(credentials: HTTPAuthorizationCredentials = Security(security_bearer)):
    """Valida el token JWT que envía el frontend en la cabecera."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha expirado. Inicia sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido. Acceso denegado.")

def limpiar_titulo(texto):
    """Limpia el contenido extraído del BOIB devolviendo el enunciado largo y completo."""
    # Convertimos a mayúsculas y limpiamos múltiples espacios/saltos de línea internos para no romper la tabla
    texto_limpio = " ".join(texto.split()).strip().upper()
    return texto_limpio


# =====================================================================
# 🌐 ENDPOINTS Y RUTAS WEB
# =====================================================================

# Ruta raíz por defecto redirige al login/panel
@app.get("/")
def leer_raiz():
    return FileResponse("static/index.html")

@app.post("/register")
def registrar_usuario(datos: LoginRequest):
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # Comprobar si el nombre de usuario ya está cogido
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (datos.username,))
    if cursor.fetchone():
        conexion.close()
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")
    
    # Encriptar e insertar el nuevo usuario
    pass_encriptada = hash_password(datos.password)
    cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (?, ?)", (datos.username, pass_encriptada))
    
    conexion.commit()
    conexion.close()
    return {"message": "Usuario creado con éxito. Ya puedes iniciar sesión."}

@app.post("/login")
def login(datos: LoginRequest):
    # =====================================================================
    # 👑 CONFIGURACIÓN DEL USUARIO MAESTRO
    # =====================================================================
    USUARIO_MAESTRO = "root"
    PASSWORD_MAESTRA = "root1234"  # <-- Cambia esta contraseña por la que quieras
    
    if datos.username == USUARIO_MAESTRO and datos.password == PASSWORD_MAESTRA:
        # Emitir token directamente sin tocar la base de datos
        expiracion = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
        token = jwt.encode({"sub": USUARIO_MAESTRO, "role": "maestro", "exp": expiracion}, SECRET_KEY, algorithm=ALGORITHM)
        return {"token": token, "username": USUARIO_MAESTRO}
    # =====================================================================

    # Si no es el usuario maestro, procedemos con la validación normal en la BD
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT password_hash FROM usuarios WHERE username = ?", (datos.username,))
    resultado = cursor.fetchone()
    conexion.close()
    
    if not resultado:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        
    password_hash = resultado[0]
    
    # Comprobar si la contraseña introducida coincide con el hash encriptado
    if not bcrypt.checkpw(datos.password.encode('utf-8'), password_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        
    # Crear token de acceso normal válido por 12 horas
    expiracion = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    token = jwt.encode({"sub": datos.username, "exp": expiracion}, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"token": token, "username": datos.username}

@app.get("/procesos")
def buscar_ofertas(tipo: str = Query("todos")):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    resultados_json = []
    
    try:
        res_cal = requests.get(U_CALENDARIO, headers=headers, timeout=20)
        soup_cal = BeautifulSoup(res_cal.text, 'html.parser')
        enlaces_boletines = [ "https://www.caib.es" + l['href'] for l in soup_cal.find_all('a', href=True) if "/eboibfront/es/2026/" in l['href'].lower() ]
        
        ultimos_4 = enlaces_boletines[-4:]
        if not ultimos_4: 
            return []

        municipios = [
            "palma", "calvià", "calvia", "eivissa", "manacor", "llucmajor", "marratxí", "marratxi", 
            "inca", "alcúdia", "alcudia", "felanitx", "pollença", "sóller", "soller", 
            "sa pobla", "santanyí", "santanyi", "son servera", "andratx", "capdepera", "santa margalida",
            "alaró", "alaro", "artà", "arta", "porreres", "valldemossa", "sant llorenç", "caib", "govern", "consell"
        ]
        
        # Ajuste de filtros: Buscamos únicamente inicios de convocatorias y bases de plazas nuevas
        si_quiero = ["bases", "convocatoria", "convocatòria", "constitución", "constitució", "creación", "creació", "selecti", "proves"]
        
        # Lista ampliada de exclusión de trámites intermedios y administrativos irrelevantes
        no_quiero = [
            "designación", "designació", "nombramiento", "nomenament", "lista", "llista", 
            "admitidos", "admesos", "puntuación", "puntuació", "corrección", "esmena", 
            "adjudica", "adjudicación", "adjudicacio", "emplazamiento", "audiencia", 
            "recurso", "reposición", "reposició", "notificación", "notificació", 
            "exposición pública", "exposició pública"
        ]

        for url_boletin in ultimos_4:
            try:
                res_dia = requests.get(url_boletin, headers=headers, timeout=15)
                soup_dia = BeautifulSoup(res_dia.text, 'html.parser')
                url_sec2 = next(( "https://www.caib.es" + l['href'] for l in soup_dia.find_all('a', href=True) if "sección ii" in l.get_text().lower() or "autoridades y personal" in l.get_text().lower()), None)
                
                if not url_sec2: 
                    continue
                res_sec = requests.get(url_sec2, headers=headers, timeout=15)
                soup_sec = BeautifulSoup(res_sec.text, 'html.parser')

                for bloque in soup_sec.find_all(['div', 'tr', 'td']):
                    full_text = bloque.get_text(separator=" ").strip().lower()
                    
                    if any(m in full_text for m in municipios) and any(sq in full_text for sq in si_quiero):
                        if not any(nq in full_text for nq in no_quiero):
                            link_pdf = bloque.find('a', href=True)
                            if link_pdf:
                                url_f = "https://www.caib.es" + link_pdf['href'] if link_pdf['href'].startswith('/') else link_pdf['href']
                                puesto = limpiar_titulo(full_text)
                                
                                ente = next((m.upper() for m in municipios if m in full_text), "MALLORCA")
                                ambito = "municipal"
                                if "CONSELL" in ente:
                                    ambito = "insular"
                                elif "GOVERN" in ente or "CAIB" in ente:
                                    ambito = "autonomica"
                                
                                item = {"puesto": puesto, "ente": ente, "type": ambito, "url": url_f}
                                
                                if item not in resultados_json:
                                    resultados_json.append(item)
            except: 
                continue

    except Exception as e: 
        print(f"Error en Scraper: {e}")

    if tipo != "todos":
        resultados_json = [r for r in resultados_json if r["type"] == tipo]

    return resultados_json

@app.get("/tests")
def obtener_banco_preguntas(usuario_actual: dict = Depends(verificar_token)):
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row  
    cursor = conexion.cursor()
    
    cursor.execute("SELECT id, tema, enunciado, opcion_a, opcion_b, opcion_c, opcion_d, correcta, justificacion FROM preguntas")
    filas = cursor.fetchall()
    conexion.close()
    
    preguntas_json = []
    for f in filas:
        preguntas_json.append({
            "id": f["id"],
            "tema": f["tema"],
            "enunciado": f["enunciado"],
            "opcion_a": f["opcion_a"],
            "opcion_b": f["opcion_b"],
            "opcion_c": f["opcion_c"],
            "opcion_d": f["opcion_d"],
            "correcta": f["correcta"],
            "justificacion": f["justificacion"]
        })
        
    return preguntas_json