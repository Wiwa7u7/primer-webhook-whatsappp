from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2
import os

app = FastAPI()

# =========================
# 🔗 CONEXIÓN A POSTGRES
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# =========================
# 🧱 CREAR TABLAS
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

print("✅ Tablas listas")

# =========================
# 📲 WEBHOOK WHATSAPP
# =========================
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body", "").strip().lower()
    phone = form.get("From")

    resp = MessagingResponse()
    msg = resp.message()

    # =========================
    # 👤 CUSTOMER
    # =========================
    cursor.execute(
        "INSERT INTO customers (phone) VALUES (%s) ON CONFLICT (phone) DO NOTHING",
        (phone,)
    )

    # =========================
    # 🧠 SESIÓN
    # =========================
    cursor.execute(
        "SELECT state FROM sessions WHERE phone = %s",
        (phone,)
    )
    row = cursor.fetchone()
    state = row[0] if row else "menu"

    # =========================
    # 🔄 RESET
    # =========================
    if incoming_msg in ["menu", "hola"]:
        cursor.execute("""
            INSERT INTO sessions (phone, state)
            VALUES (%s, 'menu')
            ON CONFLICT (phone)
            DO UPDATE SET state = 'menu'
        """, (phone,))

        msg.body(
            "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n\n"
            "Responde con el número de la opción."
        )

        return Response(content=str(resp), media_type="application/xml")

    # =========================
    # 📋 MENÚ
    # =========================
    if state == "menu":
        if incoming_msg == "1":
            msg.body(
                "💰 *Precios*\n\n"
                "🍗 Pollo entero: $10\n"
                "🍗 Medio pollo: $6\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming_msg == "2":
            msg.body(
                "🕒 *Horario*\n"
                "Lunes a Domingo\n"
                "11:00 AM – 10:00 PM\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming_msg == "3":
            cursor.execute("""
                INSERT INTO sessions (phone, state)
                VALUES (%s, 'ordering')
                ON CONFLICT (phone)
                DO UPDATE SET state = 'ordering'
            """, (phone,))

            msg.body(
                "✍️ Perfecto.\n"
                "Escribe tu pedido.\n\n"
                "Ejemplo:\n"
                "👉 2 pollos enteros"
            )

        else:
            msg.body(
                "❌ Opción no válida.\n\n"
                "1️⃣ Ver precios\n"
                "2️⃣ Horarios\n"
                "3️⃣ Hacer un pedido\n\n"
                "Escribe el número."
            )

        return Response(content=str(resp), media_type="application/xml")

    # =========================
    # 🧾 PEDIDO
    # =========================
    if state == "ordering":
        try:
            cursor.execute(
                "INSERT INTO orders (phone, order_text) VALUES (%s, %s)",
                (phone, incoming_msg)
            )

            cursor.execute(
                "UPDATE sessions SET state = 'menu' WHERE phone = %s",
                (phone,)
            )

            msg.body(
                "✅ *Pedido recibido con éxito*\n\n"
                f"🧾 Pedido:\n{incoming_msg}\n\n"
                "👨‍🍳 Un operador te contactará pronto.\n\n"
                "Escribe *menu* para volver."
            )

        except Exception as e:
            print("❌ Error guardando pedido:", e)
            msg.body("❌ Ocurrió un error. Escribe *menu* para continuar.")

        return Response(content=str(resp), media_type="application/xml")
