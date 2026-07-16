import os
import re
import json
from difflib import SequenceMatcher
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from google import genai

app = Flask(__name__)

# =========================
# Configuración Gemini
# =========================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("Error inicializando Gemini:", e)
        gemini_client = None


# =========================
# Base de conocimiento local
# =========================

def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            print(f"Base local cargada: {len(data)} registros")
            return data
    except FileNotFoundError:
        print("No se encontró knowledge_base.json")
        return []
    except json.JSONDecodeError as e:
        print("Error leyendo knowledge_base.json:", e)
        return []


KNOWLEDGE_BASE = load_knowledge_base()


# =========================
# Utilidades de texto
# =========================

STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "en", "y", "o", "que", "por", "para", "con",
    "a", "al", "se", "su", "sus", "es", "son", "fue", "ser",
    "sobre", "como", "cuando", "donde", "cuanto", "cuál", "cual",
    "venezuela", "venezolano", "venezolana", "gobierno", "pais", "país",
    "noticia", "informacion", "información", "mensaje"
}


def normalize_text(text):
    text = text.lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i")
    text = text.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_meaningful(text):
    normalized = normalize_text(text)
    tokens = normalized.split()
    return [t for t in tokens if len(t) > 3 and t not in STOPWORDS]


def detect_topic(text):
    text_n = normalize_text(text)

    topics = {
        "economía / moneda": [
            "dolar", "bcv", "bolivar", "banco", "bancos", "tipo de cambio",
            "tasa", "moneda", "economia", "inflacion", "precio"
        ],
        "sismo / emergencia": [
            "terremoto", "sismo", "temblor", "magnitud", "epicentro",
            "damnificados", "emergencia", "reliefweb"
        ],
        "política": [
            "maduro", "cilia", "delcy", "rodriguez", "rubio", "trump",
            "captura", "elecciones", "politica"
        ],
        "bonos / beneficios": [
            "bono", "beneficio", "registro", "registrate", "pago", "patria",
            "subsidio"
        ],
        "salud": [
            "cura", "medicos", "salud", "enfermedad", "milagrosa",
            "hospital", "medicina"
        ],
        "desinformación digital": [
            "whatsapp", "cadena", "reenviar", "rumor", "fake", "falsa",
            "desinformacion"
        ]
    }

    detected = []

    for topic, words in topics.items():
        for word in words:
            if normalize_text(word) in text_n:
                detected.append(topic)
                break

    if detected:
        return ", ".join(detected)

    return "tema general"


def has_question_intent(text):
    text_n = normalize_text(text)

    question_starters = [
        "que", "cual", "cuanto", "cuando", "donde", "por que",
        "es verdad", "sera verdad", "sabes", "que paso", "que ocurrio"
    ]

    if "?" in text:
        return True

    return any(text_n.startswith(q) for q in question_starters)


def is_chain_or_claim(text):
    text_n = normalize_text(text)

    chain_markers = [
        "urgente", "ultima hora", "reenviar", "reenvia", "compartelo",
        "comparte", "no lo dicen los medios", "antes de medianoche",
        "hazlo ya", "pasa este mensaje", "pásalo", "pago hoy",
        "ingresa tus datos", "enlace"
    ]

    return any(marker in text_n for marker in chain_markers)


# =========================
# Búsqueda en base local
# =========================

def search_knowledge_base(user_text):
    """
    Búsqueda más prudente:
    - Evita coincidencias falsas por palabras genéricas.
    - Exige coincidencias fuertes o varias coincidencias significativas.
    - Devuelve estado: strong_match, weak_match o no_match.
    """

    if not KNOWLEDGE_BASE:
        return {
            "status": "no_match",
            "score": 0,
            "item": None,
            "reason": "La base local no está disponible."
        }

    user_n = normalize_text(user_text)
    user_tokens = set(tokenize_meaningful(user_text))

    best_item = None
    best_score = 0
    best_keyword_hits = 0
    best_strong_hits = 0
    best_reason = ""

    for item in KNOWLEDGE_BASE:
        title = item.get("titulo", "")
        content = item.get("contenido", "")
        keywords = item.get("palabras_clave", [])

        # Permite usar palabras_clave_fuertes en el futuro sin romper el JSON actual.
        strong_keywords = item.get("palabras_clave_fuertes", [])

        title_n = normalize_text(title)
        content_n = normalize_text(content)
        combined_n = f"{title_n} {content_n}"

        item_tokens = set(tokenize_meaningful(f"{title} {content} {' '.join(keywords)}"))

        # Similitud textual general
        text_similarity = SequenceMatcher(None, user_n, combined_n).ratio()

        # Coincidencia por tokens significativos
        overlap = user_tokens.intersection(item_tokens)
        token_score = len(overlap) / max(len(user_tokens), 1)

        # Coincidencia por palabras clave normales
        keyword_hits = 0
        for keyword in keywords:
            kw = normalize_text(keyword)
            if kw and kw in user_n:
                keyword_hits += 1

        keyword_score = keyword_hits / max(len(keywords), 1)

        # Coincidencia por palabras clave fuertes
        strong_hits = 0
        for keyword in strong_keywords:
            kw = normalize_text(keyword)
            if kw and kw in user_n:
                strong_hits += 1

        # Coincidencia directa con título
        title_similarity = SequenceMatcher(None, user_n, title_n).ratio()

        final_score = (
            text_similarity * 0.25
            + token_score * 0.30
            + keyword_score * 0.25
            + title_similarity * 0.20
        )

        # Bonus si hay palabra clave fuerte
        if strong_hits > 0:
            final_score += 0.25

        if final_score > best_score:
            best_score = final_score
            best_item = item
            best_keyword_hits = keyword_hits
            best_strong_hits = strong_hits
            best_reason = (
                f"score={round(final_score, 2)}, "
                f"keywords={keyword_hits}, "
                f"strong_keywords={strong_hits}, "
                f"overlap={len(overlap)}"
            )

    # Reglas de aceptación más estrictas
    if not best_item:
        return {
            "status": "no_match",
            "score": 0,
            "item": None,
            "reason": "No se encontró coincidencia."
        }

    score = round(best_score, 2)

    # Coincidencia fuerte:
    # - score alto, o
    # - palabras clave fuertes, o
    # - varias palabras clave específicas.
    # Coincidencia fuerte:
# Solo se acepta si hay palabras clave fuertes,
# o si hay varias palabras clave específicas y un puntaje alto.
    if best_strong_hits >= 1 or (score >= 0.50 and best_keyword_hits >= 3):
        return {
        "status": "strong_match",
        "score": score,
        "item": best_item,
        "reason": best_reason
    }

# Coincidencia débil:
# Hay tema parecido, pero no suficiente para verificar.
    if score >= 0.30 and best_keyword_hits >= 2:
        return {
        "status": "weak_match",
        "score": score,
        "item": best_item,
        "reason": best_reason
    }


# =========================
# Clasificación
# =========================

def map_status_to_classification(estado):
    estado = estado.lower().strip()

    if estado == "confiable":
        return "Confiable", "Alto"
    elif estado == "referencial":
        return "Referencial / parcialmente confiable", "Medio"
    elif estado == "sospechoso":
        return "Sospechoso", "Bajo"
    elif estado == "no_verificable":
        return "No verificable", "Bajo"
    elif estado == "falso":
        return "Falso o desmentido", "Muy bajo"
    elif estado == "pendiente_revision":
        return "Pendiente de revisión", "No verificable"
    elif estado == "sin_coincidencia":
        return "Sin coincidencia en base local", "No verificable"
    else:
        return "No verificable", "No verificable"


# =========================
# Ruta principal
# =========================

@app.route("/", methods=["GET"])
def home():
    return "VerificaIA está funcionando correctamente."


# =========================
# Mensajes del bot
# =========================

def welcome_message():
    return (
        "🤖 *Bienvenido a VerificaIA*\n\n"
        "Envíame una noticia, cadena, titular, enlace o fragmento de texto "
        "y te daré una orientación preliminar sobre su confiabilidad.\n\n"
        "*Puedes escribir:*\n"
        "• ayuda\n"
        "• ejemplo\n"
        "• criterios\n"
        "• demo\n"
        "• acerca\n\n"
        "El sistema utiliza reglas básicas, una base local de referencia e Inteligencia Artificial.\n\n"
        "_Nota: Este sistema no determina verdades absolutas. Solo ofrece una orientación inicial._"
    )


def example_message():
    return (
        "📝 *Ejemplo de uso:*\n\n"
        "Puedes enviar una noticia o cadena como:\n\n"
        "“Urgente: el gobierno anunció un nuevo bono y debes registrarte en este enlace antes de medianoche. Compártelo con todos tus contactos.”\n\n"
        "VerificaIA analizará coincidencias en la base local, señales de alerta, nivel orientativo de confiabilidad y recomendaciones."
    )


def criteria_message():
    return (
        "📌 *Criterios de análisis de VerificaIA*\n\n"
        "El prototipo evalúa:\n"
        "• Fuente identificable.\n"
        "• Presencia de fecha, contexto o autor.\n"
        "• Lenguaje alarmista o emocional.\n"
        "• Solicitud de reenvío masivo.\n"
        "• Presencia de enlaces o solicitudes de datos.\n"
        "• Coincidencia con una base local de contenidos clasificados.\n\n"
        "_La ausencia de coincidencia en la base local no significa que la noticia sea falsa._"
    )


def demo_message():
    return (
        "🧪 *Casos de prueba para la demostración*\n\n"
        "Puedes probar con:\n\n"
        "1. ¿Cuál fue el dólar BCV del 13 de julio de 2026 en Venezuela?\n"
        "2. Terremotos de Venezuela de 2026\n"
        "3. Bono de contingencia por terremoto\n"
        "4. Cura milagrosa que elimina enfermedades\n"
        "5. Mañana cerrarán todos los bancos del país\n"
        "6. Venezuela cambiará el bolívar por el dólar\n\n"
        "El último ejemplo permite mostrar qué ocurre cuando no hay coincidencia suficiente en la base local."
    )


def about_message():
    return (
        "ℹ️ *Acerca de VerificaIA*\n\n"
        "VerificaIA es un prototipo académico desarrollado para apoyar la verificación preliminar "
        "de noticias falsas en medios digitales mediante WhatsApp.\n\n"
        "El sistema combina:\n"
        "• Reglas básicas de análisis textual.\n"
        "• Base de conocimiento local.\n"
        "• Inteligencia Artificial generativa.\n\n"
        "No sustituye periodistas, verificadores profesionales ni fuentes oficiales."
    )


# =========================
# Análisis por reglas
# =========================

def analyze_with_rules(text):
    text_lower = text.lower()
    warning_signals = []

    suspicious_words = [
        "urgente", "comparte", "compártelo", "reenviar", "reenvía", "difunde",
        "última hora", "no lo dicen los medios", "100% confirmado",
        "secreto", "alerta", "cura milagrosa", "bono", "regístrate",
        "antes de medianoche", "hazlo ya", "pásalo", "pásalo a todos",
        "ingresa tus datos", "retira tu dinero"
    ]

    for word in suspicious_words:
        if word in text_lower:
            warning_signals.append(f"Uso de expresión posiblemente alarmista o persuasiva: “{word}”.")

    has_link = bool(re.search(r"https?://|www\.", text_lower))

    has_source = any(source in text_lower for source in [
        "bbc", "cnn", "reuters", "ap", "efe", "el país", "ministerio",
        "gobierno", "who", "oms", "onu", "unesco", "reliefweb",
        "bcv", "banco central", "new york times", "rpp", "wikipedia",
        "funvisis"
    ])

    if has_link:
        warning_signals.append("El mensaje contiene un enlace, por lo que conviene revisar si pertenece a una fuente confiable.")

    if not has_source:
        warning_signals.append("No se identifica claramente una fuente verificable dentro del mensaje.")

    if len(text.split()) < 12:
        warning_signals.append("El texto es breve, por lo que puede faltar contexto para evaluarlo con seguridad.")

    if text.count("!") >= 2:
        warning_signals.append("El mensaje utiliza varias exclamaciones, posible señal de tono emocional o alarmista.")

    uppercase_words = [word for word in text.split() if len(word) > 4 and word.isupper()]
    if len(uppercase_words) >= 2:
        warning_signals.append("El mensaje contiene varias palabras en mayúsculas, posible señal de énfasis alarmista.")

    score = len(warning_signals)

    if score <= 1:
        level = "Medio-Alto"
    elif score <= 3:
        level = "Medio"
    else:
        level = "Bajo"

    return level, warning_signals


# =========================
# Respuestas
# =========================

def no_match_response(text, kb_result=None):
    topic = detect_topic(text)
    level, signals = analyze_with_rules(text)

    if not signals:
        signals = [
            "No se detectaron señales alarmistas evidentes.",
            "Sin embargo, la base local no contiene información suficiente para verificar esta consulta."
        ]

    signals_text = "\n".join([f"• {signal}" for signal in signals[:4]])

    return (
        "🤖 *VerificaIA*\n\n"
        "*Clasificación del contenido:* No verificable\n"
        "*Nivel orientativo de confiabilidad:* No verificable con la base local\n\n"
        "*Coincidencia en base local:*\n"
        "No se encontró un registro suficientemente relacionado con esta afirmación.\n\n"
        f"*Tema detectado:* {topic}\n\n"
        "*Análisis preliminar:*\n"
        "La base local del prototipo no contiene una noticia verificada sobre este hecho específico. "
        "Por esa razón, el sistema no debe clasificar el contenido como verdadero o falso.\n\n"
        "*Indicadores evaluados:*\n"
        f"{signals_text}\n\n"
        "*Recomendación:*\n"
        "Consulta fuentes oficiales, medios reconocidos o instituciones relacionadas con el tema antes de compartir la información.\n\n"
        "_Nota: La ausencia de coincidencia en la base local no significa que la noticia sea falsa._"
    )


def weak_match_response(text, kb_result):
    item = kb_result.get("item")
    topic = detect_topic(text)

    possible_title = item.get("titulo", "N/A") if item else "N/A"
    possible_category = item.get("categoria", "N/A") if item else "N/A"

    return (
        "🤖 *VerificaIA*\n\n"
        "*Clasificación del contenido:* No verificable\n"
        "*Nivel orientativo de confiabilidad:* No verificable con la base local\n\n"
        "*Coincidencia en base local:*\n"
        "Se detectó un tema parecido, pero no una coincidencia suficientemente fuerte para usarla como verificación.\n\n"
        f"*Tema detectado:* {topic}\n"
        f"*Registro parecido encontrado:* {possible_title}\n"
        f"*Categoría relacionada:* {possible_category}\n\n"
        "*Análisis preliminar:*\n"
        "El contenido enviado parece estar relacionado con un tema presente en la base local, "
        "pero no coincide de forma suficiente con una noticia o cadena registrada. "
        "Por prudencia, el sistema no lo clasifica como verdadero, falso o confiable.\n\n"
        "*Recomendación:*\n"
        "Verifica la información en fuentes oficiales o medios reconocidos antes de compartirla.\n\n"
        "_Nota: Una coincidencia débil no debe tomarse como confirmación de la noticia._"
    )


def strong_match_response(text, kb_result):
    item = kb_result["item"]

    estado = item.get("estado", "no_verificable")
    clasificacion, nivel = map_status_to_classification(estado)

    contenido = item.get("contenido", "No disponible")
    fuente = item.get("fuente", "N/A")
    fecha = item.get("fecha", "N/A")
    categoria = item.get("categoria", "N/A")
    explicacion = item.get("explicacion", "No disponible")
    recomendacion = item.get("recomendacion", "Contrastar con fuentes oficiales o medios reconocidos.")

    return (
        "🤖 *VerificaIA*\n\n"
        f"*Clasificación del contenido:* {clasificacion}\n"
        f"*Nivel orientativo de confiabilidad:* {nivel}\n\n"
        "*Respuesta basada en la base local:*\n"
        f"{contenido}\n\n"
        "*Registro consultado:*\n"
        f"• Fuente: {fuente}\n"
        f"• Fecha: {fecha}\n"
        f"• Categoría: {categoria}\n\n"
        "*¿Por qué se clasifica así?*\n"
        f"{explicacion}\n\n"
        "*Recomendación:*\n"
        f"{recomendacion}\n\n"
        "_Nota: Este análisis es orientativo y no sustituye una verificación profesional._"
    )

def fallback_response(text, kb_result=None):
    if kb_result:
        status = kb_result.get("status")

        if status == "strong_match":
            return strong_match_response(text, kb_result)

        if status == "weak_match":
            return weak_match_response(text, kb_result)

    return no_match_response(text, kb_result)


# =========================
# Contexto para Gemini
# =========================

def format_kb_context(kb_result):
    if not kb_result or kb_result.get("status") == "no_match":
        return (
            "No se encontró coincidencia suficiente en la base local. "
            "Esto no significa que la noticia sea falsa; solo indica que esta versión del prototipo "
            "no cuenta con información suficiente para verificarla mediante su base interna."
        )

    if kb_result.get("status") == "weak_match":
        item = kb_result.get("item")
        return (
            "Se encontró una coincidencia débil o temática, pero no suficientemente fuerte para verificar el contenido.\n"
            f"Registro parecido: {item.get('titulo', 'N/A') if item else 'N/A'}\n"
            "Debe responderse como no verificable, aclarando que el registro parecido no confirma la afirmación del usuario."
        )

    item = kb_result["item"]
    score = kb_result["score"]

    return (
        f"Se encontró una coincidencia fuerte en la base local.\n"
        f"Coincidencia: {score}\n"
        f"ID: {item.get('id', 'N/A')}\n"
        f"Título registrado: {item.get('titulo', 'N/A')}\n"
        f"Estado registrado: {item.get('estado', 'N/A')}\n"
        f"Categoría: {item.get('categoria', 'N/A')}\n"
        f"Fecha: {item.get('fecha', 'N/A')}\n"
        f"Fuente: {item.get('fuente', 'N/A')}\n"
        f"Tipo de fuente: {item.get('tipo_fuente', 'N/A')}\n"
        f"URL: {item.get('url_fuente', 'N/A')}\n"
        f"Explicación registrada: {item.get('explicacion', 'N/A')}\n"
        f"Recomendación registrada: {item.get('recomendacion', 'N/A')}"
    )


# =========================
# Análisis con Gemini
# =========================

def analyze_with_gemini(text, kb_result=None):
    # Por seguridad, si Gemini falla, el fallback ya está bien diseñado.
    if not gemini_client:
        return fallback_response(text, kb_result)

    level, rule_signals = analyze_with_rules(text)
    rule_signals_text = "\n".join([f"- {s}" for s in rule_signals]) if rule_signals else "No se detectaron señales claras por reglas."
    kb_context = format_kb_context(kb_result)
    topic = detect_topic(text)

    prompt = f"""
Eres VerificaIA, un asistente académico para orientación preliminar sobre noticias falsas en medios digitales.

Tu objetivo es responder de forma prudente y útil a usuarios de WhatsApp.

Debes usar tres elementos:
1. Reglas básicas de análisis textual.
2. Base de conocimiento local.
3. Criterio orientativo de Inteligencia Artificial.

IMPORTANTE:
- No afirmes que algo es 100% verdadero o 100% falso.
- No inventes fuentes.
- No digas que verificaste en internet.
- Si la coincidencia en la base local es débil, responde como "No verificable".
- Si no hay coincidencia en la base local, aclara que eso NO significa que la noticia sea falsa.
- Si hay coincidencia fuerte, usa el estado registrado en la base local.
- La respuesta debe ser clara, breve y útil para WhatsApp.
- Usa español.
- No uses párrafos demasiado largos.

Contenido enviado por el usuario:
\"\"\"{text}\"\"\"

Tema detectado:
{topic}

Nivel preliminar por reglas:
{level}

Señales detectadas por reglas básicas:
{rule_signals_text}

Resultado de búsqueda en base local:
{kb_context}

Responde exactamente con este formato:

🤖 *VerificaIA*

*Clasificación del contenido:* Confiable / Referencial / Sospechoso / No verificable / Falso o desmentido
*Nivel orientativo de confiabilidad:* Alto / Medio / Bajo / Muy bajo / No verificable

*Respuesta basada en el análisis:*
Responde directamente la consulta del usuario o resume el contenido encontrado.

*Coincidencia en base local:*
Explica si hubo coincidencia fuerte, coincidencia débil o ninguna coincidencia.

*¿Por qué se clasifica así?*
Explica brevemente los motivos.

*Recomendación:*
Da una recomendación práctica.

_Nota: Este análisis es orientativo y no sustituye una verificación profesional._
"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        ai_text = response.text.strip()

        if not ai_text:
            return fallback_response(text, kb_result)

        return ai_text[:1600]

    except Exception as e:
        print("Error con Gemini:", e)
        return fallback_response(text, kb_result)


# =========================
# Webhook de Twilio
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    print(f"Mensaje recibido de {sender}: {incoming_msg}")

    twilio_response = MessagingResponse()
    msg = twilio_response.message()

    if not incoming_msg:
        msg.body("No recibí ningún texto. Envíame una noticia, titular, enlace o cadena para analizar.")
        return str(twilio_response)

    normalized = incoming_msg.lower().strip()

    if normalized in ["hola", "buenas", "menu", "menú", "inicio", "start"]:
        msg.body(welcome_message())
        return str(twilio_response)

    if normalized in ["ayuda", "help"]:
        msg.body(welcome_message())
        return str(twilio_response)

    if normalized in ["ejemplo", "example"]:
        msg.body(example_message())
        return str(twilio_response)

    if normalized in ["criterios", "criterio"]:
        msg.body(criteria_message())
        return str(twilio_response)

    if normalized in ["demo", "pruebas", "probar"]:
        msg.body(demo_message())
        return str(twilio_response)

    if normalized in ["acerca", "info", "informacion", "información"]:
        msg.body(about_message())
        return str(twilio_response)

    if len(incoming_msg) < 15:
        msg.body(
            "🤖 *VerificaIA*\n\n"
            "El mensaje es muy corto para analizarlo.\n\n"
            "Envíame una noticia, cadena, enlace, titular o fragmento más completo."
        )
        return str(twilio_response)

    kb_result = search_knowledge_base(incoming_msg)

    # Si Gemini está funcionando, lo usa.
    # Si falla, cae en respuestas controladas.
    analysis = analyze_with_gemini(incoming_msg, kb_result)

    msg.body(analysis)
    return str(twilio_response)


# =========================
# Ejecutar app
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)