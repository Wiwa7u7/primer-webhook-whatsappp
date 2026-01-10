from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

def clean_text(text: str) -> str:
    return (
        text.replace("&", "y")
            .replace("<", "")
            .replace(">", "")
            .replace("*", "")
    )

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    phone = form.get("From")
    message = form.get("Body", "").strip().lower()

    resp = MessagingResponse()
    msg = resp.message()

    conn = get_db()
    cur = conn.cursor()

    # --- CUSTOMER ---
    cur.execute(
        "SELECT id FROM customers WHERE phone = %s",
        (phone,)
    )
    customer = cur.fetchone()

    if not customer:
        cur.execute(
            "INSERT INTO customers (phone) VALUES (%s)",
            (phone,)
        )
        conn.commit()

    # --- SESSION ---
    cur.execute(
        "SELECT state FROM sessions WHERE phone = %s",
        (phone,)
    )
    session = cur.fetchone()

    if not session:
        cur.execute(
            "INSERT INTO sessions (phone, state) VALUES (%s, %s)",
            (phone, "menu")
        )
        conn.commit()
        state = "menu"
    else:
        state = session[0]

    # --- GLOBAL MENU ---
    if message in ["menu", "hola", "hi", "hello"]:
        cur.execute(
            "UPDATE sessions SET state = %s WHERE phone = %s",
            ("menu", phone)
        )
        conn.commit()

        msg.body(
            "👋 Hola, soy el asistente de Pollos El Buen Sabor 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n\n"
            "Responde con el número de la opción."
        )
        return PlainTextResponse(str(resp))

    # --- MENU OPTIONS ---
    if state == "menu":
        if message == "1":
            msg.body(
                "💲 Precios\n"
                "🍗 Pollo entero: $10\n"
                "🍗 Medio pollo: $6\n\n"
                "Escribe *menu* para volver."
            )

        elif message == "2":
            msg.body(
                "🕒 Horario\n"
                "Lunes a Domingo\n"
                "11:00 AM – 10:00 PM\n\n"
                "Escribe *menu* para volver."
            )

        elif message == "3":
            cur.execute(
                "UPDATE sessions SET state = %s WHERE phone = %s",
                ("waiting_order", phone)
            )
            conn.commit()

            msg.body(
                "✍️ Escribe tu pedido.\n"
                "Ejemplo:\n"
                "2 pollos enteros"
            )

        else:
            msg.body("❌ Opción inválida. Escribe *menu*.")

        return PlainTextResponse(str(resp))

    # --- ORDER FLOW ---
    if state == "waiting_order":
        safe_order = clean_text(message)

        # 🔥 AQUÍ SE GUARDA SÍ O SÍ
        cur.execute(
            "INSERT INTO orders (phone, order_text) VALUES (%s, %s)",
            (phone, safe_order)
        )

        cur.execute(
            "UPDATE sessions SET state = %s WHERE phone = %s",
            ("menu", phone)
        )

        conn.commit()

        msg.body(
            "✅ Pedido recibido con éxito.\n\n"
            f"🧾 Pedido:\n{safe_order}\n\n"
            "Un operador te contactará pronto.\n"
            "Escribe *menu* para volver."
        )

        return PlainTextResponse(str(resp))

    msg.body("❌ Ocurrió un error. Escribe *menu*.")
    return PlainTextResponse(str(resp))
