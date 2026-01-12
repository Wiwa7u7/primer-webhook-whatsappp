import os
import psycopg
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# =========================
# DATABASE HELPERS
# =========================

def get_conn():
    return psycopg.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    phone TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
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
        conn.commit()

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
            cur.execute("""
                INSERT INTO sessions (phone, state)
                VALUES (%s, %s)
                ON CONFLICT (phone)
                DO UPDATE SET state = EXCLUDED.state,
            """, (phone, state))
        conn.commit()

def save_order(phone, order_text):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (phone, order_text)
                VALUES (%s, %s)
            """, (phone, order_text))
        conn.commit()

# =========================
# WEBHOOK
# =========================

@app.route("/webhook", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip().lower()
    phone = request.values.get("From")

    print("📩 Mensaje recibido:", incoming)

    resp = MessagingResponse()
    msg = resp.message()

    state = get_state(phone)

    # =========================
    # MENU / NEW
    # =========================
    if incoming in ["hola", "menu"]:
        set_state(phone, "new")
        msg.body(
            "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n"
            "4️⃣ Ver combos\n\n"
            "Responde con el número de la opción."
        )
        return Response(str(resp), mimetype="application/xml")

    # =========================
    # STATE: NEW
    # =========================
    if state == "new":
        if incoming == "1":
            msg.body("🍗 Pollo entero: $10\n🍗 Medio pollo: $6")

        elif incoming == "2":
            msg.body("📍 Abierto todos los días de 12pm a 10pm")

        elif incoming == "3":
            set_state(phone, "ordering")
            msg.body("✍️ Escribe tu pedido (ej: 2 pollos enteros)")

        elif incoming == "4":
            msg = resp.message(
                "🔥 *Combo Familiar*\n\n"
                "🍗 2 pollos enteros\n"
                "🥤 Bebida grande\n"
                "💲 Precio: $18\n\n"
                "Escribe *menu* para volver o *3* para hacer un pedido."
            )
            msg.media(
                "https://www.freepik.es/fotos-vectores-gratis/dibujos-animados-pollo"
            )
            set_state(phone, "menu")

        else:
            msg.body("❌ Opción no válida. Responde 1, 2, 3 o 4.")

        return Response(str(resp), mimetype="application/xml")

    # =========================
    # STATE: ORDERING
    # =========================
    if state == "ordering":
        save_order(phone, incoming)
        set_state(phone, "menu")
        msg.body(
            f"✅ Pedido recibido: {incoming}\n\n"
            "Gracias 🙌\n"
            "Escribe *menu* para volver."
        )
        return Response(str(resp), mimetype="application/xml")

    # =========================
    # FALLBACK
    # =========================
    msg.body("Escribe *menu* para comenzar.")
    return Response(str(resp), mimetype="application/xml")


# =========================
# STARTUP
# =========================
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
