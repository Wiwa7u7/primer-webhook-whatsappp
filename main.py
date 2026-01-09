from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

user_state = {}


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body" , "").strip()
    from_number = form.get("From")

     # Estado actual del usuario
    state = user_state.get(from_number, "menu")

    # MENÚ PRINCIPAL
    if state == "menu":
        if incoming_msg == "1":
            user_state[from_number] = "precios"
            return PlainTextResponse(
                "💰 *Precios de nuestros pollos*\n\n"
                "🐔 Pollo entero: $10\n"
                "🍗 Medio pollo: $6\n\n"
                "Escribe *menu* para volver al inicio."
            )

        elif incoming_msg == "2":
            user_state[from_number] = "horarios"
            return PlainTextResponse(
                "📍 *Horarios y ubicación*\n\n"
                "🕘 Lunes a Domingo: 9am – 8pm\n"
                "📌 Av. Principal, frente a la plaza\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming_msg == "3":
            user_state[from_number] = "pedido"
            return PlainTextResponse(
                "📝 *Hacer un pedido*\n\n"
                "¿Qué deseas ordenar?\n"
                "Ejemplo: '1 pollo entero'\n\n"
                "Escribe *menu* para volver."
            )

        else:
            return PlainTextResponse(
                "👋 Hola, soy el asistente virtual de *Pollos El Buen Sabor* 🐔\n\n"
                "1️⃣ Ver precios\n"
                "2️⃣ Horarios y ubicación\n"
                "3️⃣ Hacer un pedido\n\n"
                "Responde con el número de la opción."
            )

    # VOLVER AL MENÚ
    if incoming_msg.lower() == "menu":
        user_state[from_number] = "menu"
        return PlainTextResponse(
            "🔙 *Menú principal*\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido"
        )

    # PEDIDO SIMPLE
    if state == "pedido":
        return PlainTextResponse(
            f"✅ *Pedido recibido*\n\n"
            f"🧾 Pedido: {incoming_msg}\n\n"
            "En breve un operador humano te contactará 📞\n\n"
            "Escribe *menu* para volver."
        )

    # FALLBACK
    return PlainTextResponse(
        "No entendí tu mensaje 😅\n"
        "Escribe *menu* para volver al inicio."
    )