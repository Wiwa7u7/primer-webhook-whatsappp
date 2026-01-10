from fastapi import FastAPI, Request
from fastapi.responses import Response
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")

# ======================================
# 🔗 CONEXIÓN A POSTGRES (RAILWAY)
# ======================================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

# ======================================
# 🧱 INICIALIZAR BASE DE DATOS
# ======================================
def init_db():
    try:
        print("⏳ Conectando a PostgreSQL...")
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1;")
        print("✅ Conexión a PostgreSQL OK")

        # Tabla clientes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(30) UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tabla pedidos
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

        print("✅ Tablas customers y orders listas")

    except Exception as e:
        print("❌ ERROR INICIALIZANDO DB:", e)

init_db()

# ======================================
# 🧠 DETECCIÓN INTELIGENTE DE INTENCIÓN
# ======================================
def detect_intent(message: str):
    msg = message.lower()

    if any(word in msg for word in ["hola", "buenas", "hey"]):
        return "greeting"

    if any(word in msg for word in ["precio", "cuesta", "vale"]):
        return "prices"

    if any(word in msg for word in ["horario", "abierto", "cierran"]):
        return "hours"

    if any(word in msg for word in ["donde", "ubicacion", "dirección"]):
        return "location"

    if any(word in msg for word in ["pollo", "pedido", "ordenar", "quiero"]):
        return "order"

    if any(word in msg for word in ["gracias", "ok", "perfecto"]):
        return "thanks"

    return "unknown"

# ======================================
# 📲 WEBHOOK WHATSAPP (TWILIO)
# ======================================
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    raw_message = form.get("Body", "").strip()
    message = raw_message.lower()
    from_number = form.get("From", "")

    print("📩 Mensaje recibido:", raw_message)

    reply = ""
    intent = detect_intent(message)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Buscar o crear cliente
        cur.execute(
            "SELECT id FROM customers WHERE phone = %s",
            (from_number,)
        )
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

        # =========================
        # RESPUESTAS SEGÚN INTENCIÓN
        # =========================
        if intent == "greeting":
            reply = """
👋 Hola! Bienvenido a *Pollos El Buen Sabor* 🍗

Puedes preguntarme por:
• precios
• horarios
• hacer un pedido
            """

        elif intent == "prices":
            reply = """
💰 *Nuestros precios*

🍗 Pollo entero: $10  
🍗 Medio pollo: $6  

¿Deseas hacer un pedido?
            """

        elif intent == "hours":
            reply = """
🕒 *Horario*

Lunes a Domingo  
11:00 AM – 10:00 PM
            """

        elif intent == "location":
            reply = """
📍 *Ubicación*

Estamos en el centro de la ciudad.
            """

        elif intent == "order":
            cur.execute(
                "INSERT INTO orders (customer_id, order_text) VALUES (%s, %s)",
                (customer_id, raw_message)
            )

            reply = f"""
✅ *Pedido recibido*

🧾 Pedido:
{raw_message}

Un operador humano te contactará para confirmar 👨‍🍳
            """

        elif intent == "thanks":
            reply = "🙏 ¡Gracias por escribirnos! Estamos para ayudarte."

        else:
            reply = """
🤔 Puedo ayudarte con:
• precios
• horarios
• ubicación
• pedidos

Solo dime qué necesitas 😊
            """

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("❌ Error procesando mensaje:", e)
        reply = "❌ Ocurrió un error. Intenta nuevamente."

    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply}</Message></Response>',
        media_type="application/xml"
    )
