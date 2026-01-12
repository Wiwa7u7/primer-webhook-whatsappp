import os
import psycopg
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from datetime import datetime
import pytz

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# =========================
# Twilio config
# =========================
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"  # Sandbox
OPERADOR_NUMBER = "whatsapp:+584243761325"       # Tu número verificado


# =========================
# DB helpers
# =========================
def get_conn():
    return psycopg.connect(DATABASE_URL)


def get_state(phone):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM sessions WHERE phone = %s",
                (phone,)
            )
            row = cur.fetchone()
            return row[0] if row else "menu"


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


# =========================
# Notify operator
# =========================
def notify_operator(cliente_phone, pedido):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    vzla_tz = pytz.timezone("America/Caracas")
    hora = datetime.now(vzla_tz).strftime("%d/%m/%Y %H:%M")

    mensaje = (
        "📢 *Nuevo pedido recibido*\n\n"
        f"📞 Cliente: {cliente_phone}\n"
        f"📝 Pedido: {pedido}\n"
        f"⏰ Hora: {hora}\n\n"
        "👉 Contactar al cliente."
    )

    client.messages.create(
        from_=TWILIO_WHATSAPP_NUMBER,
        to=OPERADOR_NUMBER,
        body=mensaje
    )


# =========================
# WhatsApp webhook
# =========================
@app.route("/webhook", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip().lower()
    phone = request.values.get("From")

    resp = MessagingResponse()
    msg = resp.message()

    # comandos globales
    if incoming == "menu":
        set_state(phone, "menu")

    state = get_state(phone)

    # =========================
    # MENU PRINCIPAL
    # =========================
    if state == "menu":
        if incoming in ("hola", "menu", ""):
            msg.body(
                "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
                "1️⃣ Ver precios\n"
                "2️⃣ Horarios y ubicación\n"
                "3️⃣ Hacer un pedido\n"
                "4️⃣ Ver combos\n\n"
                "Responde con el número de la opción."
            )

        elif incoming == "1":
            msg.body(
                "🍗 *Precios*\n\n"
                "• Pollo entero: $10\n"
                "• Medio pollo: $6\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming == "2":
            msg.body(
                "📍 *Horario y ubicación*\n\n"
                "🕛 Todos los días de 12pm a 10pm\n"
                "📌 Centro de la ciudad\n\n"
                "Escribe *menu* para volver."
            )

        elif incoming == "3":
            set_state(phone, "ordering")
            msg.body("✍️ Escribe tu pedido (ej: 2 pollos enteros)")

        elif incoming == "4":
            msg.body(
                "🔥 *Combo Familiar*\n\n"
                "🍗 2 pollos enteros\n"
                "🥤 Bebida grande\n"
                "💲 *Precio: $18*\n\n"
                "Escribe *menu* para volver o *3* para hacer un pedido."
            )
            msg.media(
                "https://i.blogs.es/abc649/mejores-recetas-pollo/650_1200.jpg"
            )
            set_state(phone, "menu")

        else:
            msg.body("❌ Opción no válida. Responde 1, 2, 3 o 4.")

    # =========================
    # TOMANDO PEDIDO
    # =========================
    elif state == "ordering":
        save_order(phone, incoming)
        notify_operator(phone, incoming)

        msg.body(
            f"✅ Pedido recibido: *{incoming}*\n\n"
            "Gracias 🙌\n"
            "Escribe *menu* para volver."
        )
        set_state(phone, "menu")

    return str(resp)
