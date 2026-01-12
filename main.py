from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2
import os

app = Flask(__name__)

# ========================
# CONFIG
# ========================
DATABASE_URL = os.getenv("DATABASE_URL")

# Imagen placeholder (puedes cambiarla luego)
COMBO_IMAGE = "https://via.placeholder.com/600x400.png?text=Combo+Pollo+El+Buen+Sabor"

# ========================
# DB CONNECTION
# ========================
def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ========================
# HELPERS
# ========================
def normalize(text):
    return text.strip().lower()

def get_session(phone):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT state FROM sessions WHERE phone = %s", (phone,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "menu"

def set_session(phone, state):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sessions (phone, state)
        VALUES (%s, %s)
        ON CONFLICT (phone)
        DO UPDATE SET state = EXCLUDED.state
    """, (phone, state))
    conn.commit()
    cur.close()
    conn.close()

def ensure_customer(phone):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (phone)
        VALUES (%s)
        ON CONFLICT (phone) DO NOTHING
    """, (phone,))
    conn.commit()
    cur.close()
    conn.close()

def save_order(phone, order_text):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (phone, order_text)
        VALUES (%s, %s)
    """, (phone, order_text))
    conn.commit()
    cur.close()
    conn.close()

# ========================
# MAIN WEBHOOK
# ========================
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    phone = request.form.get("From")
    text = normalize(request.form.get("Body", ""))

    resp = MessagingResponse()
    msg = resp.message()

    ensure_customer(phone)
    state = get_session(phone)

    # ========================
    # GLOBAL COMMANDS
    # ========================
    if text in ["menu", "hola", "hi", "hello"]:
        set_session(phone, "menu")
        msg.body(
            "👋 *Hola, soy el asistente de Pollos El Buen Sabor 🍗*\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n"
            "4️⃣ Ver combos 📸\n\n"
            "Responde con el número de la opción."
        )
        return Response(str(resp), media_type="application/xml")

    # ========================
    # MENU STATE
    # ========================
    if state == "menu":

        if text == "1":
            msg.body(
                "💰 *Precios*\n\n"
                "🍗 Pollo entero: $10\n"
                "🍗 Medio pollo: $6\n\n"
                "Escribe *menu* para volver."
            )
            return Response(str(resp), media_type="application/xml")

        elif text == "2":
            msg.body(
                "🕐 *Horario*\n"
                "Lunes a Domingo\n"
                "11:00 AM – 10:00 PM\n\n"
                "📍 *Ubicación*\n"
                "Av. Principal #123\n\n"
                "Escribe *menu* para volver."
            )
            return Response(str(resp), media_type="application/xml")

        elif text == "3":
            set_session(phone, "ordering")
            msg.body(
                "✍️ *Perfecto.*\n\n"
                "Escribe tu pedido.\n"
                "Ejemplo:\n"
                "👉 2 pollos enteros"
            )
            return Response(str(resp), media_type="application/xml")

        elif text == "4":
            msg.body("🍗 *Nuestros combos más populares*")
            msg.media(COMBO_IMAGE)
            msg.body(
                "\n\n¿Deseas hacer un pedido?\n"
                "👉 Escribe *3* para ordenar\n"
                "👉 Escribe *menu* para volver"
            )
            return Response(str(resp), media_type="application/xml")

        else:
            msg.body("❌ Opción no válida. Escribe *menu* para ver las opciones.")
            return Response(str(resp), media_type="application/xml")

    # ========================
    # ORDERING STATE
    # ========================
    if state == "ordering":
        save_order(phone, text)
        set_session(phone, "menu")

        msg.body(
            "✅ *Pedido recibido con éxito.*\n\n"
            f"🧾 *Pedido:*\n{text}\n\n"
            "Un operador te contactará pronto.\n\n"
            "Escribe *menu* para volver."
        )
        return Response(str(resp), media_type="application/xml")

    # ========================
    # FALLBACK
    # ========================
    msg.body("❌ Ocurrió un error. Escribe *menu* para continuar.")
    return Response(str(resp), media_type="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
