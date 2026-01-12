from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import psycopg
import os

app = Flask(__name__)

# ==========================
# 🔗 DATABASE CONNECTION
# ==========================
DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg.connect(DATABASE_URL)
conn.autocommit = True

# ==========================
# 🧱 INIT DATABASE
# ==========================
def init_db():
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            phone TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            phone TEXT PRIMARY KEY,
            state TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            phone TEXT,
            order_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

init_db()

# ==========================
# 🧠 SESSION HELPERS
# ==========================
def get_state(phone):
    with conn.cursor() as cur:
        cur.execute("SELECT state FROM sessions WHERE phone = %s", (phone,))
        row = cur.fetchone()
        return row[0] if row else None

def set_state(phone, state):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO sessions (phone, state)
        VALUES (%s, %s)
        ON CONFLICT (phone)
        DO UPDATE SET state = EXCLUDED.state, updated_at = CURRENT_TIMESTAMP
        """, (phone, state))

def ensure_customer(phone):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO customers (phone)
        VALUES (%s)
        ON CONFLICT DO NOTHING
        """, (phone,))

# ==========================
# 📲 WHATSAPP WEBHOOK
# ==========================
@app.route("/webhook", methods=["POST"])
def whatsapp():
    print("📩 Webhook recibido")
    print(request.form)

    incoming_msg = request.form.get("Body", "").strip().lower()
    phone = request.form.get("From")

    ensure_customer(phone)
    state = get_state(phone)

    resp = MessagingResponse()
    msg = resp.message()

    # ===== GLOBAL COMMANDS =====
    if incoming_msg in ["menu", "hola", "hi", "hello"]:
        set_state(phone, "menu")
        msg.body(
            "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n\n"
            "Responde con el número de la opción."
        )
        return Response(str(resp), mimetype="text/xml")

    # ===== MENU STATE =====
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
                "📍 *Horario y ubicación*\n\n"
                "🕒 Lunes a Domingo\n"
                "11:00 AM – 10:00 PM\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming_msg == "3":
            set_state(phone, "ordering")
            msg.body(
                "✍️ Perfecto.\n"
                "Escribe tu pedido.\n\n"
                "Ejemplo:\n"
                "👉 2 pollos enteros"
            )

        else:
            msg.body("❌ Opción no válida. Escribe *menu* para continuar.")

        return Response(str(resp), mimetype="text/xml")

    # ===== ORDERING STATE =====
    if state == "ordering":
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (phone, order_text) VALUES (%s, %s)",
                (phone, incoming_msg)
            )

        set_state(phone, "menu")

        msg.body(
            "✅ *Pedido recibido con éxito*\n\n"
            f"🧾 Pedido:\n{incoming_msg}\n\n"
            "👨‍🍳 Un operador te contactará pronto.\n\n"
            "Escribe *menu* para volver."
        )

        return Response(str(resp), mimetype="text/xml")

    # ===== FALLBACK =====
    set_state(phone, "menu")
    msg.body("⚠️ Algo no salió bien. Escribe *menu* para continuar.")
    return Response(str(resp), mimetype="text/xml")


# ==========================
# 🚀 LOCAL RUN (ignored in Railway)
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
