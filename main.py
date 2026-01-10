from fastapi import FastAPI, Request
from fastapi.responses import Response
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            phone VARCHAR(30) UNIQUE,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            order_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

def detect_intent(message: str):
    msg = message.lower()

    if any(w in msg for w in ["hola", "buenas", "hey"]):
        return "greeting"
    if any(w in msg for w in ["precio", "cuesta"]):
        return "prices"
    if any(w in msg for w in ["horario", "abierto", "cierran"]):
        return "hours"
    if any(w in msg for w in ["pedido", "ordenar", "quiero pedir", "hacer un pedido"]):
        return "order_intent"
    return "unknown"

def is_real_order(message: str):
    keywords = ["pollo", "pollos", "entero", "medio", "1", "2", "3"]
    return any(word in message for word in keywords)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    raw_message = form.get("Body", "").strip()
    message = raw_message.lower()
    from_number = form.get("From", "")

    reply = ""
    intent = detect_intent(message)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM customers WHERE phone = %s", (from_number,))
        customer = cur.fetchone()

        if customer:
            customer_id = customer[0]
            cur.execute(
                "UPDATE customers SET last_seen = CURRENT_TIMESTAMP WHERE id = %s",
                (customer_id,)
            )
        else:
            cur.execute(
                "INSERT INTO customers (phone) VALUES (%s) RETURNING id",
                (from_number,)
            )
            customer_id = cur.fetchone()[0]

        # RESPUESTAS
        if intent == "greeting":
            reply = """👋 Hola! Bienvenido a *Pollos El Buen Sabor* 🍗
Puedes preguntarme por precios, horarios o hacer un pedido."""

        elif intent == "prices":
            reply = """💰 Pollo entero $10
🍗 Medio pollo $6"""

        elif intent == "hours":
            reply = """🕒 Lunes a Domingo
11:00 AM – 10:00 PM"""

        elif intent == "order_intent":
            reply = """✍️ Perfecto, escríbeme tu pedido.
Ejemplo: 2 pollos enteros"""

        elif is_real_order(message):
            cur.execute(
                "INSERT INTO orders (customer_id, order_text) VALUES (%s, %s)",
                (customer_id, raw_message)
            )
            reply = f"""✅ Pedido recibido:
{raw_message}
Un operador te confirmará 👨‍🍳"""

        else:
            reply = """🤔 No entendí del todo.
Puedes escribir: precios, horarios o tu pedido."""

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("ERROR:", e)
        reply = "❌ Ocurrió un error. Intenta nuevamente."

    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply}</Message></Response>',
        media_type="application/xml"
    )
