import os
import sqlite3
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_NAME = "oposiciones.db"

def obtener_conexion_db():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    return conexion

# 🏠 RUTA PRINCIPAL: CARGA EL CUESTIONARIO (QUIZ)
@app.route('/')
def home():
    try:
        with open("quiz.html", "r", encoding="utf-8") as f:
            contenido = f.read()
        return render_template_string(contenido)
    except FileNotFoundError:
        return "❌ Error: No se encontró el archivo quiz.html en el servidor.", 404

# ⚙️ RUTA DEL PANEL DE CONTROL
@app.route('/panel')
def panel():
    try:
        with open("panel.html", "r", encoding="utf-8") as f:
            contenido = f.read()
        return render_template_string(contenido)
    except FileNotFoundError:
        return "❌ Error: No se encontró el archivo panel.html en el servidor.", 404

# 📊 API: OBTENER TODAS LAS PREGUNTAS (CON FILTRO DE TEMAS)
@app.route('/api/preguntas', methods=['GET'])
def obtener_preguntas():
    tema = request.args.get('tema')
    conexion = obtener_conexion_db()
    cursor = conexion.cursor()
    
    if tema:
        cursor.execute("SELECT * FROM preguntas WHERE tema = ?", (tema,))
    else:
        cursor.execute("SELECT * FROM preguntas")
        
    filas = cursor.fetchall()
    conexion.close()
    
    preguntas = []
    for fila in filas:
        preguntas.append({
            "id": fila["id"],
            "tema": fila["tema"],
            "pregunta": fila["pregunta"],
            "opcion_a": fila["opcion_a"],
            "opcion_b": fila["opcion_b"],
            "opcion_c": fila["opcion_c"],
            "opcion_d": fila["opcion_d"],
            "respuesta_correcta": fila["respuesta_correcta"]
        })
    return jsonify(preguntas)

# 📝 API: OBTENER LISTA DE TEMAS DISPONIBLES
@app.route('/api/temas', methods=['GET'])
def obtener_temas():
    conexion = obtener_conexion_db()
    cursor = conexion.cursor()
    cursor.execute("SELECT DISTINCT tema FROM preguntas")
    temas = [fila["tema"] for fila in cursor.fetchall() if fila["tema"]]
    conexion.close()
    return jsonify(temas)

# 📈 API: OBTENER ESTADÍSTICAS GENERALES
@app.route('/api/estadisticas', methods=['GET'])
def obtener_estadisticas():
    conexion = obtener_conexion_db()
    cursor = conexion.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    total_preguntas = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT tema) FROM preguntas")
    total_temas = cursor.fetchone()[0]
    
    conexion.close()
    return jsonify({
        "total_preguntas": total_preguntas,
        "total_temas": total_temas
    })

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)