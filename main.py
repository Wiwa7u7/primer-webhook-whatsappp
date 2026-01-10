from fastapi import FastAPI, Request
from fastapi.responses import Response
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")

# ======================================
# 🔗 DB
# ======================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ======================================
# 🧱 INIT DB
# ======================================
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
        CREATE TABLE IF NOT EXISTS sessions (
            phone VARCHAR(30) PRIMARY KEY,
            state VARCHAR(30) NOT NULL
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
    print("✅ DB lista")

init_db()

# ======================================
# 📲 WEBHOOK
# ======================================
@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    message = form.get("Body", "").strip().lower()
    raw_message = form.get("Body", "").strip()
    phone = form.get("From", "")

    reply = ""

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # ---------- CUSTOMER ----------
        cur.execute("SELECT id FROM customers WHERE phone = %s", (phone,))
        row = cur.fetchone()

        if row:
            customer_id = row[0]
            cur.execute(
                "UPDATE customers SET last_seen = CURRENT_TIMESTAMP WHERE phone = %s",
                (phone,)
            )
        else:
            cur.execute(
                "INSERT INTO customers (phone) VALUES (%s) RETURNING id",
                (phone,)
            )
            customer_id = cur.fetchone()[0]

        # ---------- SESSION (UPSERT) ----------
        cur.execute("""
            INSERT INTO sessions (phone, state)
            VALUES (%s, 'menu')
            ON CONFLICT (phone) DO NOTHING
        """, (phone,))

        cur.execute("SELECT state FROM sessions WHERE phone = %s", (phone,))
        state = cur.fetchone()[0]

        # ---------- MENU ----------
        if state == "menu":

            if message in ["hola", "menu", "hi"]:
                reply = """👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗

1️⃣ Ver precios  
2️⃣ Horarios y ubicación  
3️⃣ Hacer un pedido  

Responde con el número de la opción.
                """

            elif message == "1":
                reply = """💰 *Precios*
🍗 Pollo entero: $10
🍗 Medio pollo: $6

Escribe *menu* para volver.
                """

            elif message == "2":
                reply = """📍 *Horario*
🕒 Lunes a Domingo
11:00 AM – 10:00 PM

Escribe *menu* para volver.
                """

            elif message == "3":
                cur.execute(
                    "UPDATE sessions SET state = 'waiting_order' WHERE phone = %s",
                    (phone,)
                )
                reply = """✍️ Perfecto.
Escribe tu pedido.

Ejemplo:
👉 2 pollos enteros
                """

            else:
                reply = """❓ Opción inválida.
Responde 1, 2 o 3.
                """

        # ---------- WAITING ORDER ----------
        elif state == "waiting_order":

            cur.execute(
                "INSERT INTO orders (customer_id, order_text) VALUES (%s, %s)",
                (customer_id, raw_message)
            )

            cur.execute(
                "UPDATE sessions SET state = 'menu' WHERE phone = %s",
                (phone,)
            )

            reply = f"""✅ *Pedido recibido*

🧾 Pedido:
{raw_message}

👨‍🍳 Un operador te contactará pronto.
Escribe *menu* para volver.
            """

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("❌ ERROR REAL:", e)

        # 🔴 RESET DE EMERGENCIA
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE sessions SET state = 'menu' WHERE phone = %s",
                (phone,)
            )
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass

        reply = "❌ Ocurrió un error. Escribe *menu* para continuar."

    return Response(
        content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Message>{reply}</Message>
</Response>""",
        media_type="application/xml"
    )
