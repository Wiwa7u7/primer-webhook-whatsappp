from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

# =========================
# CONFIGURACIÓN GENERAL
# =========================

BUSINESS_NAME = "Pollos El Buen Sabor"
USE_AI = False  # luego lo activamos
HUMAN_OPERATOR_MSG = (
    "👨‍💼 Un operador humano te contactará en breve para confirmar tu pedido.\n\n"
    "Gracias por elegirnos ❤️"
)

MENU_TEXT = (
    "👋 *¡Hola! Bienvenido a Pollos El Buen Sabor* 🐔🔥\n\n"
    "Estoy aquí para ayudarte 😊\n\n"
    "¿Qué deseas hacer?\n"
    "1️⃣ Ver precios\n"
    "2️⃣ Horarios y ubicación\n"
    "3️⃣ Hacer un pedido\n\n"
    "Responde con el *número* de la opción."
)

PRICES_TEXT = (
    "💰 *Precios de nuestros pollos*\n\n"
    "🐔 Pollo entero: $10\n"
    "🍗 Medio pollo: $6\n\n"
    "Escribe *menu* para volver al inicio."
)

SCHEDULE_TEXT = (
    "📍 *Horarios y ubicación*\n\n"
    "🕒 Lunes a Domingo\n"
    "⏰ 11:00 AM – 9:00 PM\n\n"
    "📌 Dirección: Av. Principal, frente a la plaza.\n\n"
    "Escribe *menu* para volver al inicio."
)

UNKNOWN_TEXT = (
    "😅 Disculpa, no entendí tu mensaje.\n\n"
    "Por favor responde con:\n"
    "1️⃣ Precios\n"
    "2️⃣ Horarios\n"
    "3️⃣ Pedido\n\n"
    "O escribe *menu* para volver."
)

# =========================
# WEBHOOK WHATSAPP
# =========================

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    incoming_msg = form_data.get("Body", "")
    incoming_msg = incoming_msg.strip().lower()

    # =========================
    # MENÚ PRINCIPAL
    # =========================
    if incoming_msg in ["hola", "menu", "menú", "inicio"]:
        return PlainTextResponse(MENU_TEXT)

    # =========================
    # OPCIÓN 1 - PRECIOS
    # =========================
    if incoming_msg == "1":
        return PlainTextResponse(PRICES_TEXT)

    # =========================
    # OPCIÓN 2 - HORARIOS
    # =========================
    if incoming_msg == "2":
        return PlainTextResponse(SCHEDULE_TEXT)

    # =========================
    # OPCIÓN 3 - PEDIDO
    # =========================
    if incoming_msg == "3":
        return PlainTextResponse(
            "📝 *Perfecto, vamos a tomar tu pedido* 🍗🔥\n\n"
            "Por favor escribe qué deseas ordenar.\n"
            "Ejemplo:\n"
            "👉 1 pollo entero y 1 medio pollo"
        )

    # =========================
    # MENSAJE DESPUÉS DEL PEDIDO
    # =========================
    if "pollo" in incoming_msg or "pedido" in incoming_msg:
        return PlainTextResponse(
            "✅ *Pedido recibido con éxito*\n\n"
            f"📦 Pedido: {incoming_msg}\n\n"
            f"{HUMAN_OPERATOR_MSG}\n\n"
            "Escribe *menu* para volver al inicio."
        )

    # =========================
    # RESPUESTA IA (FUTURO)
    # =========================
    if USE_AI:
        return PlainTextResponse("🤖 (Aquí responderá la IA en el futuro)")

    # =========================
    # MENSAJE NO ENTENDIDO
    # =========================
    return PlainTextResponse(UNKNOWN_TEXT)
