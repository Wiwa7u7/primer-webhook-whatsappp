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
            return json.load(file)
    except FileNotFoundError:
        print("No se encontró knowledge_base.json")
        return []
    except json.JSONDecodeError as e:
        print("Error leyendo knowledge_base.json:", e)
        return []


KNOWLEDGE_BASE = load_knowledge_base()


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñü]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_knowledge_base(user_text):
    """
    Busca coincidencias entre el mensaje del usuario y la base local.
    Usa palabras clave + similitud textual básica.
    """
    if not KNOWLEDGE_BASE:
        return None

    user_normalized = normalize_text(user_text)
    best_match = None
    best_score = 0

    for item in KNOWLEDGE_BASE:
        title = normalize_text(item.get("titulo", ""))
        content = normalize_text(item.get("contenido", ""))
        keywords = item.get("palabras_clave", [])

        combined_text = f"{title} {content}"

        text_similarity = SequenceMatcher(None, user_normalized, combined_text).ratio()

        keyword_hits = 0
        for keyword in keywords:
            keyword_normalized = normalize_text(keyword)
            if keyword_normalized and keyword_normalized in user_normalized:
                keyword_hits += 1

        keyword_score = keyword_hits / max(len(keywords), 1)

        final_score = (text_similarity * 0.55) + (keyword_score * 0.45)

        if final_score > best_score:
            best_score = final_score
            best_match = item

    # Umbral mínimo para considerar coincidencia
    if best_score >= 0.18:
        return {
            "score": round(best_score, 2),
            "item": best_match
        }

    return None


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
        "• acerca\n\n"
        "El sistema utiliza reglas básicas, una base local de referencia e Inteligencia Artificial.\n\n"
        "_Nota: Este sistema no determina verdades absolutas. Solo ofrece una orientación inicial._"
    )


def example_message():
    return (
        "📝 *Ejemplo de uso:*\n\n"
        "Copia y envía una noticia, cadena o mensaje como este:\n\n"
        "\"Urgente: el gobierno anunció un nuevo bono y debes registrarte en este enlace antes de medianoche. Compártelo con todos tus contactos.\"\n\n"
        "VerificaIA analizará señales de alerta, coincidencias en la base local, nivel orientativo de confiabilidad y recomendaciones."
    )


def criteria_message():
    return (
        "📌 *Criterios de análisis de VerificaIA*\n\n"
        "El prototipo evalúa:\n"
        "• Fuente identificable.\n"
        "• Presencia de fecha, contexto o autor.\n"
        "• Lenguaje alarmista o emocional.\n"
        "• Solicitud de reenvío masivo.\n"
        "• Presencia de enlaces sospechosos.\n"
        "• Coincidencia con una base local de contenidos clasificados.\n\n"
        "_La ausencia de coincidencia en la base local no significa que la noticia sea falsa._"
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
        "antes de medianoche", "hazlo ya", "pásalo", "pásalo a todos"
    ]

    for word in suspicious_words:
        if word in text_lower:
            warning_signals.append(f"Uso de expresión posiblemente alarmista o persuasiva: “{word}”.")

    has_link = bool(re.search(r"https?://|www\.", text_lower))

    has_source = any(source in text_lower for source in [
        "bbc", "cnn", "reuters", "ap", "efe", "el país", "ministerio",
        "gobierno", "who", "oms", "onu", "unesco", "reliefweb",
        "bcv", "banco central", "new york times", "rpp", "wikipedia"
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


def format_kb_context(kb_result):
    if not kb_result:
        return (
            "No se encontró coincidencia suficiente en la base local. "
            "Esto no significa que la noticia sea falsa; solo indica que esta versión del prototipo "
            "no cuenta con información suficiente para verificarla mediante su base interna."
        )

    item = kb_result["item"]
    score = kb_result["score"]

    return (
        f"Se encontró una coincidencia aproximada en la base local.\n"
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
# Respuesta sin IA
# =========================
def fallback_response(text, kb_result=None):
    level, signals = analyze_with_rules(text)

    kb_text = ""

    if kb_result:
        item = kb_result["item"]
        kb_text = (
            f"*Coincidencia en base local:*\n"
            f"• Se encontró un registro relacionado.\n"
            f"• Título: {item.get('titulo', 'N/A')}\n"
            f"• Estado registrado: {item.get('estado', 'N/A')}\n"
            f"• Fuente: {item.get('fuente', 'N/A')}\n\n"
        )
    else:
        kb_text = (
            "*Coincidencia en base local:*\n"
            "• No se encontró coincidencia suficiente.\n"
            "• Esto no significa que la noticia sea falsa.\n\n"
        )

    if not signals:
        signals = [
            "No se detectaron señales alarmistas evidentes.",
            "Aun así, se recomienda contrastar la información con fuentes confiables."
        ]

    signals_text = "\n".join([f"• {signal}" for signal in signals[:4]])

    return (
        "🤖 *VerificaIA*\n\n"
        f"*Nivel orientativo de confiabilidad:* {level}\n\n"
        f"{kb_text}"
        "*Indicadores detectados:*\n"
        f"{signals_text}\n\n"
        "*Recomendaciones:*\n"
        "• Consulta medios reconocidos o fuentes oficiales.\n"
        "• Verifica la fecha, el autor y el enlace original.\n"
        "• Evita reenviar la información si no puedes confirmarla.\n\n"
        "_Nota: Este análisis es orientativo y no sustituye una verificación profesional._"
    )


# =========================
# Análisis con Gemini
# =========================
def analyze_with_gemini(text, kb_result=None):
    if not gemini_client:
        return fallback_response(text, kb_result)

    level, rule_signals = analyze_with_rules(text)
    rule_signals_text = "\n".join([f"- {s}" for s in rule_signals]) if rule_signals else "No se detectaron señales claras por reglas."
    kb_context = format_kb_context(kb_result)

    prompt = f"""
Eres VerificaIA, un asistente académico para orientación preliminar sobre noticias falsas en medios digitales.

Analiza el contenido enviado por un usuario de WhatsApp usando tres elementos:
1. Reglas básicas de análisis textual.
2. Base de conocimiento local.
3. Criterio orientativo de Inteligencia Artificial.

IMPORTANTE:
- No afirmes que algo es 100% verdadero o 100% falso.
- No inventes fuentes.
- No digas que verificaste en internet.
- Si no hay coincidencia en la base local, aclara que eso NO significa que la noticia sea falsa.
- La respuesta debe ser breve, clara y útil para WhatsApp.
- Usa español.
- Mantén un tono académico pero sencillo.
- No uses párrafos demasiado largos.

Contenido enviado por el usuario:
\"\"\"{text}\"\"\"

Nivel preliminar por reglas:
{level}

Señales detectadas por reglas básicas:
{rule_signals_text}

Resultado de búsqueda en base local:
{kb_context}

Responde exactamente con este formato:

🤖 *VerificaIA*

*Resultado del análisis preliminar:*
Nivel orientativo de confiabilidad: Bajo / Medio / Medio-Alto / No verificable con base local

*Coincidencia en base local:*
Explica si hubo coincidencia o no. Si hubo, menciona el estado registrado, fuente y fecha.

*Indicadores evaluados:*
• Indicador 1
• Indicador 2
• Indicador 3

*Recomendaciones:*
• Recomendación 1
• Recomendación 2
• Recomendación 3

*Conclusión:*
Una conclusión breve y prudente.

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
    analysis = analyze_with_gemini(incoming_msg, kb_result)
    msg.body(analysis)

    return str(twilio_response)


# =========================
# Ejecutar app
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)