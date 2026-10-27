# =====================================================================
# ARCHIVO: botBuscadorOposiciones.py
# FUNCIÓN: Rastreo exclusivo de procesos NUEVOS del BOIB con discriminación de isla
# TECNOLOGÍAS: Python 3, Requests, BeautifulSoup4, SQLite3
# =====================================================================

import os
import re
import sqlite3
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_NAME = "oposiciones.db"

# Catálogo oficial de municipios de las Illes Balears
MUNICIPIOS_MALLORCA = [
    "alaro", "alaró", "alcudia", "alcúdia", "algaida", "andratx", "ariany", "arta", "artà",
    "banyalbufar", "binissalem", "buger", "búger", "bunyola", "calvia", "calvià", "campanet",
    "campos", "capdepera", "consell", "costitx", "deia", "deià", "escorca", "esporles",
    "estellencs", "felanitx", "fornalutx", "inca", "lloret", "lloseta", "llubi", "llubí",
    "llucmajor", "manacor", "mancor", "maria de la salut", "marratxi", "marratxí", "montuiri",
    "montuïri", "muro", "palma", "petra", "pollença", "pollensa", "porreres", "puigpunyent",
    "sa pobla", "sant joan", "sant llorenç", "sant llorenc", "santa eugenia", "santa eugènia",
    "santa margalida", "santa maria", "santanyi", "santanyí", "selva", "sencelles",
    "ses salines", "sineu", "soller", "sóller", "son servera", "valldemossa", "vilafranca"
]

MUNICIPIOS_MENORCA = [
    "mao", "maó", "mahon", "mahón", "ciutadella", "alaior", "es castell", "ferreries",
    "es mercadal", "mercadal", "es migjorn", "migjorn gran", "sant lluis", "sant lluís"
]

MUNICIPIOS_EIVISSA = [
    "eivissa", "ibiza", "santa eularia", "santa eulària", "santa eulalia",
    "sant antoni", "san antonio", "sant josep", "san jose", "san josé",
    "sant joan de labritja", "san juan"
]

def inicializar_base_datos():
    """Crea la tabla canónica edictos_boib con soporte para ámbito e isla."""
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edictos_boib (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                organismo TEXT DEFAULT 'Administración Balear',
                enlace TEXT UNIQUE NOT NULL,
                enlace_pdf TEXT,
                escala TEXT DEFAULT 'S/E',
                ambito TEXT DEFAULT 'Municipal',
                isla TEXT DEFAULT 'Mallorca',
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("PRAGMA table_info(edictos_boib)")
        columnas_actuales = [info[1] for info in cursor.fetchall()]
        
        columnas_requeridas = {
            "organismo": "TEXT DEFAULT 'Administración Balear'",
            "enlace_pdf": "TEXT",
            "escala": "TEXT DEFAULT 'S/E'",
            "ambito": "TEXT DEFAULT 'Municipal'",
            "isla": "TEXT DEFAULT 'Mallorca'"
        }
        for col, definicion in columnas_requeridas.items():
            if col not in columnas_actuales:
                cursor.execute(f"ALTER TABLE edictos_boib ADD COLUMN {col} {definicion}")
                
        conexion.commit()

def detectar_escala(texto):
    """
    Clasificación según el TREBEP:
    - AP: Sin titulación, Peones, Operarios, Limpieza, Subalternos, Conserjes.
    - C2: Graduado ESO, Oficiales de oficios (paleta, fontanero, pintor, electricista), Auxiliares.
    - C1: Bachiller / FP Medio, Policía Local, Bomberos, Administrativos.
    - B:  Técnico Superior FP, Delineantes, Proyectistas.
    - A2: Grado / Diplomatura, Arquitectos Técnicos, Aparejadores, Trabajadores Sociales, Maestros.
    - A1: Licenciatura, Máster, TAG, Letrados, Arquitectos, Ingenieros, Médicos.
    - Laboral: Expresamente personal laboral.
    """
    if not texto:
        return "S/E"
    
    t = str(texto).lower()

    # 1. Agrupaciones Profesionales (AP)
    palabras_ap = [
        "agrupacio professional", "agrupacion profesional", "grup e", "grupo e",
        "peó", "peon", "peons", "peones", "conserge", "conserje", "operari", "operario",
        "neteja", "limpieza", "vigilant", "vigilante", "subaltern", "subalterno", "celador"
    ]
    for p in palabras_ap:
        if p in t and not ("oficial" in t or "auxiliar" in t or "arquitect" in t or "enginyer" in t):
            return "AP"

    # 2. Subgrupo C2 (ESO - Oficiales de oficios y Auxiliares)
    palabras_c2 = [
        "c2", "subgrup c2", "subgrupo c2", "oficial", "oficials", "paleta", "albañil",
        "electricista", "fontaner", "fontanero", "pintor", "jardiner", "jardinero",
        "conductor", "auxiliar"
    ]
    for p in palabras_c2:
        if p in t and not ("c1" in t or ("administratiu" in t and "auxiliar" not in t)):
            return "C2"

    # 3. Subgrupo C1 (Bachiller / FP Medio - Policía Local, Bomberos, Administrativos)
    palabras_c1 = [
        "c1", "subgrup c1", "subgrupo c1", "policia", "policía", "bomber", "bombero",
        "administratiu", "administrativo", "agent de policia"
    ]
    for p in palabras_c1:
        if p in t and "auxiliar" not in t:
            return "C1"

    # 4. Grupo B (Técnico Superior FP)
    palabras_b = [
        "grup b", "grupo b", "subgrup b", "subgrupo b", "delineant", "delineante",
        "projectista", "proyectista", "tecnic superior", "tècnic superior", "técnico superior"
    ]
    for p in palabras_b:
        if p in t and not ("a1" in t or "a2" in t):
            return "B"

    # 5. Subgrupo A2 (Grado / Diplomatura)
    palabras_a2 = [
        "a2", "subgrup a2", "subgrupo a2", "arquitecte tecnic", "arquitecte tècnic",
        "arquitecto tecnico", "arquitecto técnico", "aparellador", "aparejador",
        "enginyer tecnic", "enginyer tècnic", "treballador social", "trabajador social",
        "educador", "mestre", "maestro", "infermer", "enfermer"
    ]
    for p in palabras_a2:
        if p in t:
            return "A2"

    # 6. Subgrupo A1 (Licenciatura / Máster / TAG / Letrados)
    palabras_a1 = [
        "a1", "subgrup a1", "subgrupo a1", "tag", "administracio general", "administración general",
        "lletrat", "letrado", "advocat", "abogado", "interventor", "secretari", "secretario",
        "economista", "arquitecte", "arquitecto", "enginyer", "ingeniero", "metge", "médico"
    ]
    for p in palabras_a1:
        if p in t:
            return "A1"

    # 7. Laboral
    if "laboral" in t or "contracte laboral" in t:
        return "Laboral"

    return "S/E"

def detectar_ambito_organismo_e_isla(texto):
    """
    Identifica con precisión el ámbito institucional, el organismo convocante
    y la isla en la que se convoca la plaza.
    """
    t = texto.lower()

    # 1. ÁMBITO INSULAR
    if "consell insular" in t or "consell de mallorca" in t or "consell de menorca" in t or "consell d'eivissa" in t or "consell de formentera" in t or "imas" in t or "agència de defensa del territori" in t:
        if "menorca" in t:
            return "Insular", "Consell de Menorca · Menorca", "Menorca"
        elif "eivissa" in t or "ibiza" in t:
            return "Insular", "Consell d'Eivissa · Eivissa", "Eivissa"
        elif "formentera" in t:
            return "Insular", "Consell de Formentera · Formentera", "Formentera"
        else:
            return "Insular", "Consell de Mallorca · Mallorca", "Mallorca"

    # 2. ÁMBITO AUTONÓMICO (Govern Balear)
    elif "govern" in t or "conselleria" in t or "ib-salut" in t or "servei de salut" in t or "irfap" in t or "soib" in t or "comunitat autònoma" in t:
        # Discriminar si la plaza autonómica tiene asignación territorial explícita
        if "menorca" in t or any(m in t for m in MUNICIPIOS_MENORCA):
            isla_auto = "Menorca"
        elif "eivissa" in t or "ibiza" in t or any(m in t for m in MUNICIPIOS_EIVISSA):
            isla_auto = "Eivissa"
        elif "formentera" in t:
            isla_auto = "Formentera"
        else:
            isla_auto = "Mallorca"
            
        nombre_ente = "Govern de les Illes Balears"
        if "ib-salut" in t or "servei de salut" in t:
            nombre_ente = "Servei de Salut (Ib-Salut)"
        elif "soib" in t:
            nombre_ente = "SOIB"
            
        return "Autonómica", f"{nombre_ente} · {isla_auto}", isla_auto

    # 3. ÁMBITO MUNICIPAL (Ayuntamientos)
    elif "ajuntament" in t or "ayuntamiento" in t:
        # Búsqueda en Menorca
        for mun in MUNICIPIOS_MENORCA:
            if mun in t:
                nombre = mun.capitalize()
                if mun in ["mao", "maó", "mahon", "mahón"]:
                    nombre = "Maó"
                elif mun == "ciutadella":
                    nombre = "Ciutadella de Menorca"
                return "Municipal", f"Ajuntament de {nombre} · Menorca", "Menorca"

        # Búsqueda en Eivissa
        for mun in MUNICIPIOS_EIVISSA:
            if mun in t:
                nombre = mun.capitalize()
                if mun in ["eivissa", "ibiza"]:
                    nombre = "Eivissa"
                elif mun in ["santa eularia", "santa eulària", "santa eulalia"]:
                    nombre = "Santa Eulària des Riu"
                elif mun in ["sant antoni", "san antonio"]:
                    nombre = "Sant Antoni de Portmany"
                return "Municipal", f"Ajuntament d'{nombre} · Eivissa", "Eivissa"

        # Búsqueda en Formentera
        if "formentera" in t:
            return "Municipal", "Ajuntament / Consell de Formentera · Formentera", "Formentera"

        # Búsqueda en Mallorca
        for mun in MUNICIPIOS_MALLORCA:
            if mun in t:
                nombre = mun.capitalize()
                if mun in ["calvia", "calvià"]:
                    nombre = "Calvià"
                elif mun in ["alaro", "alaró"]:
                    nombre = "Alaró"
                elif mun in ["alcudia", "alcúdia"]:
                    nombre = "Alcúdia"
                elif mun in ["marratxi", "marratxí"]:
                    nombre = "Marratxí"
                return "Municipal", f"Ajuntament de {nombre} · Mallorca", "Mallorca"

        # Extracción genérica si no está en la lista estándar
        coincidencia = re.search(r"(?:ajuntament|ayuntamiento)\s+(?:de\s+|d['’]\s*)([A-Za-zÀ-ÿ\s]+?)(?:,|\.|\s+per|\s+número|\s+mitjançant|$)", texto, re.IGNORECASE)
        org = f"Ajuntament de {coincidencia.group(1).strip()}" if coincidencia else "Ajuntament"
        return "Municipal", f"{org} · Mallorca", "Mallorca"

    return "Municipal", "Administración Local · Mallorca", "Mallorca"

def limpiar_espacios(texto):
    return " ".join(texto.split()) if texto else ""

def purgar_procesos_no_nuevos():
    """Elimina de la base de datos registros antiguos que sean de seguimiento o trámites internos."""
    terminos_borrado = [
        "%llista%", "%llistat%", "%admesos%", "%exclosos%", "%admitidos%",
        "%tribunal%", "%designació%", "%designacio%", "%constitució de la borsa%",
        "%constitucio de la borsa%", "%comissió de serveis%", "%comissio de serveis%",
        "%modificació de l'annex%", "%modificacio de l'annex%", "%promoció interna%",
        "%promocio interna%", "%es constitueix la borsa%", "%rectificació llistat%"
    ]
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        for patron in terminos_borrado:
            cursor.execute("DELETE FROM edictos_boib WHERE LOWER(titulo) LIKE ?", (patron,))
        conexion.commit()

def buscar_novedades_reales_boib():
    inicializar_base_datos()
    purgar_procesos_no_nuevos()
    
    url_base = "https://www.caib.es"
    anio_actual = datetime.datetime.now().year
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ca,es;q=0.9"
    }

    print("\n=======================================================")
    print("🔍 [ESCANER BOIB] Rastreo exclusivo de PROCESOS NUEVOS (Filtro estricto)")
    print("=======================================================")

    try:
        resp = requests.get(f"{url_base}/eboibfront/ca/", headers=headers, timeout=20, verify=False)
        if resp.status_code != 200:
            resp = requests.get("https://boib.caib.es", headers=headers, timeout=20, verify=False)
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return 0

    soup_portada = BeautifulSoup(resp.text, "html.parser")
    enlaces_boletines = set()
    patron_id = re.compile(r'/eboibfront/(?:ca|es)/\d{4}/(\d+)', re.IGNORECASE)

    for a in soup_portada.find_all("a", href=True):
        match = patron_id.search(a["href"])
        if match:
            enlaces_boletines.add(match.group(1))

    ids_ordenados = sorted(list(enlaces_boletines), key=lambda x: int(x), reverse=True)

    if ids_ordenados:
        ultimo_id = int(ids_ordenados[0])
        ultimos_ids = [str(ultimo_id - i) for i in range(14) if (ultimo_id - i) > 0]
    else:
        ultimos_ids = [str(12347 - i) for i in range(14)]

    print(f"📋 Se escanearán los últimos 14 boletines: {ultimos_ids[0]} hasta {ultimos_ids[-1]}")

    # Solo términos que definen apertura de un nuevo proceso
    terminos_inicio = [
        "convocat", "bases", "procés selectiu", "proceso selectivo",
        "borsa", "bolsa", "oposició", "oposicion", "concurs", "concurso",
        "oferta pública", "oferta publica", "places vacants", "plazas vacantes",
        "cobertura"
    ]

    # Filtro exhaustivo: descarta seguimiento, tribunales, bolsas ya cerradas y trámites internos
    terminos_descarte = [
        # Listas y admitidos/excluidos
        "llista", "llistat", "lista", "listado", "admes", "admitid", "exclos", "excloid", "excluid",
        # Tribunales y designaciones
        "tribunal", "designaci", "designación", "comissió qualificadora", "comissio qualificadora",
        # Bolsas ya constituidas o cerradas
        "constitució", "constitucio", "constitucion", "constitución", "es constitueix", "es constitueixi",
        # Notas, resultados y actas
        "nomenament", "nombramiento", "acta", "resultat", "resultado", "qualificaci", "calificaci",
        "aprovats", "aprobados", "aspirants que han superat", "desert", "desierto",
        # Rectificaciones, subsanaciones y modificaciones
        "rectificaci", "rectificación", "modificaci", "modificación", "esmena", "subsanaci", 
        "al·legaci", "alegaci", "revocaci", "revocación", "barem",
        # Trámites internos (no nuevo acceso libre)
        "comissió de serveis", "comissio de serveis", "comisión de servicios", "comision de servicios",
        "promoció interna", "promocio interna", "promoción interna", "promocion interna",
        "mobilitat", "movilidad", "trasllat", "traslado"
    ]

    lote_guardado = []

    for id_b in ultimos_ids:
        url_seccion2 = f"{url_base}/eboibfront/ca/{anio_actual}/{id_b}/seccio-ii-autoritats-i-personal"

        try:
            r_sec = requests.get(url_seccion2, headers=headers, timeout=12, verify=False)
            if r_sec.status_code != 200:
                url_sec_alt = f"{url_base}/eboibfront/ca/{anio_actual}/{id_b}/seccio-ii-autoritats-i-personal/473"
                r_sec = requests.get(url_sec_alt, headers=headers, timeout=12, verify=False)

            if r_sec.status_code != 200:
                continue

            soup_sec = BeautifulSoup(r_sec.text, "html.parser")
            enlaces_html = soup_sec.find_all("a", string=re.compile(r'Versió HTML|Versión HTML', re.IGNORECASE))
            if not enlaces_html:
                enlaces_html = [a for a in soup_sec.find_all("a", href=True) if "altres-formats" in a["href"] or "versio-html" in a["href"].lower()]

            for enlace_version in enlaces_html:
                href_documento = enlace_version.get("href", "").strip()
                if not href_documento:
                    continue

                url_edicto = href_documento if href_documento.startswith("http") else f"{url_base}{href_documento}"
                tarjeta = enlace_version.find_parent(["div", "li", "section", "article"])
                
                if tarjeta and len(tarjeta.get_text()) < 60:
                    tarjeta = tarjeta.find_parent(["div", "li", "section", "article"])

                if not tarjeta:
                    continue

                enlace_pdf_nodo = tarjeta.find("a", string=re.compile(r'Versió PDF|Versión PDF', re.IGNORECASE))
                if enlace_pdf_nodo and enlace_pdf_nodo.get("href"):
                    href_pdf = enlace_pdf_nodo["href"].strip()
                    url_pdf = href_pdf if href_pdf.startswith("http") else f"{url_base}{href_pdf}"
                else:
                    url_pdf = url_edicto.replace("/versio-html/", "/pdf/").replace(".html", ".pdf")

                texto_completo = limpiar_espacios(tarjeta.get_text(separator=" ", strip=True))
                for frase in ["Versió PDF", "Versió HTML", "Versió XML", "Contingut, oficial i autèntic, de la disposició:"]:
                    texto_completo = texto_completo.replace(frase, "")
                texto_completo = limpiar_espacios(texto_completo)

                t_lower = texto_completo.lower()
                es_convocatoria = any(ter in t_lower for ter in terminos_inicio)
                es_seguimiento_o_descarte = any(desc in t_lower for desc in terminos_descarte)

                # Solo procesar convocatorias NUEVAS
                if es_convocatoria and not es_seguimiento_o_descarte and len(texto_completo) > 30:
                    escala_detectada = detectar_escala(texto_completo)
                    ambito_det, organismo_det, isla_det = detectar_ambito_organismo_e_isla(texto_completo)
                    lote_guardado.append((texto_completo, organismo_det, url_edicto, url_pdf, escala_detectada, ambito_det, isla_det))

        except Exception:
            pass

    # Guardado atómico en SQLite
    total_procesadas = len(lote_guardado)
    if lote_guardado:
        with sqlite3.connect(DB_NAME) as conexion:
            cursor = conexion.cursor()
            cursor.executemany("""
                INSERT INTO edictos_boib (titulo, organismo, enlace, enlace_pdf, escala, ambito, isla)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(enlace) DO UPDATE SET
                    organismo = excluded.organismo,
                    enlace_pdf = COALESCE(excluded.enlace_pdf, edictos_boib.enlace_pdf),
                    escala = excluded.escala,
                    ambito = excluded.ambito,
                    isla = excluded.isla
            """, lote_guardado)
            conexion.commit()

    print("\n=======================================================")
    print(f"🏁 Escaneo finalizado. Procesos NUEVOS guardados: {total_procesadas}")
    print("=======================================================\n")
    return total_procesadas

if __name__ == "__main__":
    buscar_novedades_reales_boib()