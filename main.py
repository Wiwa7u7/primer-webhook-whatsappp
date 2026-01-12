import os
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import psycopg

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg.connect(DATABASE_URL)

# ======================
# DB HELPERS
# ======================

def get_state(phone):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM sessions WHERE phone = %s",
                (phone,)
            )
            row = cur.fetchone()
            return row[0] if row else "new"

def set_state(phone, state):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (phone, state)
                VALUES (%s, %s)
                ON CONFLICT (phone)
                DO UPDATE SET state = EXCLUDED.state
                """,
                (phone, state)
            )
            conn.commit()

def save_order(phone, order_text):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (phone, order_text)
                VALUES (%s, %s)
                """,
                (phone, order_text)
            )
            conn.commit()

# ======================
# MENUS
# ======================

def main_menu():
    return (
        "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
        "1️⃣ Ver precios\n"
        "2️⃣ Horarios y ubicación\n"
        "3️⃣ Hacer un pedido\n"
        "4️⃣ Ver combos 📸\n\n"
        "Responde con el número de la opción."
    )

# ======================
# WEBHOOK
# ======================

@app.route("/webhook", methods=["POST"])
def whatsapp():
    incoming = request.form.get("Body", "").strip().lower()
    phone = request.form.get("From")

    print("📩 Mensaje recibido:", incoming)

    resp = MessagingResponse()
    msg = resp.message()

    # 🔁 RESET GLOBAL
    if incoming in ["hola", "menu", "inicio"]:
        set_state(phone, "new")
        msg.body(main_menu())
        return Response(str(resp), mimetype="application/xml")

    state = get_state(phone)

    # ======================
    # NEW STATE
    # ======================
    if state == "new":
        if incoming == "1":
            msg.body("🍗 Pollo entero: $10\n🍗 Medio pollo: $6")
        elif incoming == "2":
            msg.body("📍 Abierto todos los días de 12pm a 10pm")
        elif incoming == "3":
            set_state(phone, "ordering")
            msg.body("✍️ Escribe tu pedido (ej: 2 pollos enteros)")
        elif incoming == "4":
            msg.body(
                "🔥 Combos disponibles:\n\n"
                "🍗 Combo Familiar - $18\n"
                "Incluye 2 pollos + acompañantes\n\n"
                "📸 Imágenes próximamente"
            )
        else:
            msg.body("❌ Opción no válida. Responde 1, 2, 3 o 4.")
        return Response(str(resp), mimetype="application/xml")

    # ======================
    # ORDERING STATE
    # ======================
    if state == "ordering":
        save_order(phone, incoming)
        set_state(phone, "new")
        msg.body(
            f"✅ Pedido recibido: *{incoming}*\n\n"
            "Gracias 🙌\n"
            "Escribe *menu* para volver."
        )
        return Response(str(resp), mimetype="application/xml")

    # Fallback
    msg.body(main_menu())
    return Response(str(resp), mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
