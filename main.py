import os
from flask import Flask, request, Response
import psycopg

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

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
            return row[0] if row else None

def set_state(phone, state):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (phone, state)
                VALUES (%s, %s)
                ON CONFLICT (phone)
                DO UPDATE SET state = EXCLUDED.state
            """, (phone, state))
        conn.commit()

@app.route("/webhook", methods=["POST"])
def whatsapp():
    incoming = request.form.get("Body", "").strip().lower()
    phone = request.form.get("From")

    print("📩 Mensaje recibido:", incoming)

    state = get_state(phone)

    if not state:
        set_state(phone, "menu")
        return Response(
            "👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗\n\n"
            "1️⃣ Ver precios\n"
            "2️⃣ Horarios y ubicación\n"
            "3️⃣ Hacer un pedido\n"
            "4️⃣ Ver combos\n\n"
            "Responde con el número de la opción.",
            mimetype="text/plain"
        )

    if state == "menu":
        if incoming == "1":
            return Response("🍗 Pollo entero: $10\n🍗 Medio pollo: $6", mimetype="text/plain")
        elif incoming == "2":
            return Response("📍 Abierto todos los días de 12pm a 10pm", mimetype="text/plain")
        elif incoming == "3":
            set_state(phone, "pedido")
            return Response("✍️ Escribe tu pedido (ej: 2 pollos enteros)", mimetype="text/plain")
        elif incoming == "4":
            return Response("🔥 Combo familiar: $18", mimetype="text/plain")
        else:
            return Response("❌ Opción no válida. Responde 1, 2, 3 o 4.", mimetype="text/plain")

    if state == "pedido":
        set_state(phone, "menu")
        return Response(f"✅ Pedido recibido: {incoming}\nGracias 🙌", mimetype="text/plain")

    return Response("⚠️ Error inesperado", mimetype="text/plain")
