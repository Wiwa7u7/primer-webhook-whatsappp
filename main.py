import os
import re
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
# Ruta principal
# =========================
@app.route("/", methods=["GET"])
def home():
    return "VerificaIA está funcionando correctamente."


# =========================
# Funciones del bot
# =========================
def welcome_message():
    return (
        "🤖 *Bienvenido a VerificaIA*\n\n"
        "Envíame una noticia, cadena, titular, enlace o fragmento de texto "
        "y te daré una orientación preliminar sobre su confiabilidad.\n\n"
        "También puedes escribir:\n"
        "• ayuda\n"
        "• ejemplo\n\n"
        "Nota: Este sistema no determina verdades absolutas. Solo ofrece una orientación inicial."
    )


def example_message():
    return (
        "📝 *Ejemplo de uso:*\n\n"
        "Copia y envía una noticia, cadena o mensaje como este:\n\n"
        "\"Urgente: el gobierno anunció un nuevo bono y debes registrarte en este enlace antes de medianoche. Compártelo con todos tus contactos.\"\n\n"
        "VerificaIA analizará señales de alerta, nivel orientativo de confiabilidad y recomendaciones."
    )


def analyze_with_rules(text):
    text_lower = text.lower()

    warning_signals = []

    suspicious_words = [
        "urgente", "comparte", "reenviar", "reenvía", "difunde",
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
        "gobierno", "who", "oms", "onu", "unesco", "observatorio"
    ])

    if has_link:
        warning_signals.append("El mensaje contiene un enlace, por lo que conviene revisar si pertenece a una fuente confiable.")

    if not has_source:
        warning_signals.append("No se identifica claramente una fuente verificable dentro del mensaje.")

    if len(text.split()) < 12:
        warning_signals.append("El texto es muy breve, por lo que no hay suficiente contexto para evaluarlo con seguridad.")

    exclamation_count = text.count("!")
    if exclamation_count >= 2:
        warning_signals.append("El mensaje utiliza varias exclamaciones, lo cual puede indicar tono emocional o alarmista.")

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


def fallback_response(text):
    level, signals = analyze_with_rules(text)

    if not signals:
        signals = [
            "No se detectaron señales alarmistas evidentes.",
            "Aun así, se recomienda contrastar la información con fuentes confiables."
        ]

    signals_text = "\n".join([f"• {signal}" for signal in signals[:4]])

    return (
        "🤖 *VerificaIA*\n\n"
        f"*Nivel orientativo de confiabilidad:* {level}\n\n"
        "*Señales detectadas:*\n"
        f"{signals_text}\n\n"
        "*Recomendaciones:*\n"
        "• Consulta medios reconocidos o fuentes oficiales.\n"
        "• Verifica la fecha, el autor y el enlace original.\n"
        "• Evita reenviar la información si no puedes confirmarla.\n\n"
        "_Nota: Este análisis es orientativo y no sustituye una verificación profesional._"
    )


def analyze_with_gemini(text):
    if not gemini_client:
        return fallback_response(text)

    level, rule_signals = analyze_with_rules(text)
    rule_signals_text = "\n".join([f"- {s}" for s in rule_signals]) if rule_signals else "No se detectaron señales claras por reglas."

    prompt = f"""
Eres VerificaIA, un asistente académico para orientación preliminar sobre noticias falsas en medios digitales.

Analiza el siguiente contenido enviado por un usuario de WhatsApp.

IMPORTANTE:
- No afirmes que algo es 100% verdadero o 100% falso.
- No inventes fuentes.
- No digas que verificaste en internet.
- La respuesta debe ser breve, clara y útil para WhatsApp.
- Usa español.
- Mantén un tono académico pero sencillo.
- Indica que el análisis es orientativo.

Contenido enviado:
\"\"\"{text}\"\"\"

Señales detectadas por reglas básicas:
{rule_signals_text}

Responde exactamente con este formato:

🤖 *VerificaIA*

*Nivel orientativo de confiabilidad:* Bajo / Medio / Medio-Alto

*Señales de alerta detectadas:*
• Señal 1
• Señal 2
• Señal 3

*Recomendaciones:*
• Recomendación 1
• Recomendación 2
• Recomendación 3

_Nota: Este análisis es orientativo y no sustituye una verificación profesional._
"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        ai_text = response.text.strip()

        if not ai_text:
            return fallback_response(text)

        return ai_text[:1500]

    except Exception as e:
        print("Error con Gemini:", e)
        return fallback_response(text)


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

    if len(incoming_msg) < 15:
        msg.body(
            "🤖 *VerificaIA*\n\n"
            "El mensaje es muy corto para analizarlo.\n\n"
            "Envíame una noticia, cadena, enlace, titular o fragmento más completo."
        )
        return str(twilio_response)

    analysis = analyze_with_gemini(incoming_msg)
    msg.body(analysis)

    return str(twilio_response)


# =========================
# Ejecutar app
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)