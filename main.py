from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2
import os

app = FastAPI()

# =========================
# 🔗 POSTGRES
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# =========================
# 🧱 TABLAS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(30) UNIQUE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    phone VARCHAR(30) PRIMARY KEY,
    state VARCHAR(50)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(30),
    order_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# =========================
# 📸 IMÁGENES PLACEHOLDER
# =========================
MENU_IMAGE = "https://images.unsplash.com/photo-1600891964599-f61ba0e24092"
COMBO_IMAGE = "https://images.unsplash.com/photo-1598515213692-5f252bcb2c1c"

# =========================
# 📲 WEBHOOK
# =========================
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    text = form.get("Body", "").strip().lower()
    phone = form.get("From")

    resp = MessagingResponse()
    msg = resp.message()

    # CUSTOMER
    cursor.execute(
        "INSERT INTO customers (phone) VALUES (%s) ON CONFLICT DO NOTHING",
        (phone,)
    )

    # SESSION
    cursor.execute("SELECT state FROM sessions WHERE phone=%s", (phone,))
    row = cursor.fetchone()
    state = row[0] if row else "menu"

    # RESET
    if text in ["hola", "menu"]:
        cursor.execute("""
            INSERT INTO sessions (phone, state)
            VALUES (%s,'menu')
            ON CONFLICT (phone) DO UPDATE SET state='menu'
        """, (phone,))

        msg.body(
            "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n"
            "4️⃣ Ver combos 🍗📸\n\n"
            "Responde con el número de la opción."
        )
        return Response(content=str(resp), media_type="application/xml")

    # =========================
    # 📋 MENÚ
    # =========================
    if state == "menu":

        if text == "1":
            msg.body(
                "💰 *Precios*\n\n"
                "🍗 Pollo entero: $10\n"
                "🍗 Medio pollo: $6\n\n"
                "Escribe *menu* para volver."
            )

        elif text == "2":
            msg.body(
                "🕒 *Horario*\n"
                "Lunes a Domingo\n"
                "11:00 AM – 10:00 PM\n\n"
                "Escribe *menu* para volver."
            )

        elif text == "3":
            cursor.execute("""
                INSERT INTO sessions (phone, state)
                VALUES (%s,'ordering')
                ON CONFLICT (phone) DO UPDATE SET state='ordering'
            """, (phone,))

            msg.body(
                "✍️ Perfecto.\n"
                "Escribe tu pedido.\n\n"
                "Ejemplo:\n"
                "👉 2 pollos enteros"
            )

        elif text == "4":
            msg.body("🍗 *Nuestros combos más populares*")
            msg.media(COMBO_IMAGE)
            msg.body("\nEscribe *menu* para volver.")

        else:
            msg.body(
                "❌ Opción no válida.\n\n"
                "1️⃣ Precios\n"
                "2️⃣ Horarios\n"
                "3️⃣ Pedido\n"
                "4️⃣ Combos\n"
            )

        return Response(content=str(resp), media_type="application/xml")

    # =========================
    # 🧾 PEDIDO
    # =========================
    if state == "ordering":
        try:
            cursor.execute(
                "INSERT INTO orders (phone, order_text) VALUES (%s,%s)",
                (phone, text)
            )
            cursor.execute(
                "UPDATE sessions SET state='menu' WHERE phone=%s",
                (phone,)
            )

            msg.body(
                "✅ *Pedido recibido con éxito*\n\n"
                f"🧾 Pedido:\n{text}\n\n"
                "👨‍🍳 Un operador te contactará pronto.\n\n"
                "Escribe *menu* para volver."
            )
        except:
            msg.body("❌ Error guardando pedido. Escribe *menu*.")

        return Response(content=str(resp), media_type="application/xml")
