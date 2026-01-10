from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
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
        sslmode="require"  # 🔥 OBLIGATORIO en Railway
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(30),
                order_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cur.close()
        conn.close()

        print("✅ Tabla orders creada o ya existente")

    except Exception as e:
        print("❌ ERROR INICIALIZANDO DB:", e)

init_db()

# ======================================
# 📲 WEBHOOK WHATSAPP (TWILIO)
# ======================================
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    message = form.get("Body", "").strip().lower()
    from_number = form.get("From", "")

    reply = ""

    if message in ["hola", "menu"]:
        reply = """
👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗

1️⃣ Ver precios  
2️⃣ Horarios y ubicación  
3️⃣ Hacer un pedido  

Responde con el número de la opción.
        """

    elif message == "1":
        reply = """
💰 *Precios*

🍗 Pollo entero: $10  
🍗 Medio pollo: $6  

Escribe *menu* para volver.
        """

    elif message == "2":
        reply = """
📍 *Horario y ubicación*

🕒 Lunes a Domingo: 11am - 10pm  
📌 Centro de la ciudad  

Escribe *menu* para volver.
        """

    elif message == "3":
        reply = """
✍️ Perfecto, escribe tu pedido.
Ejemplo:
👉 1 pollo entero y 1 medio pollo
        """

    else:
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO orders (phone, order_text) VALUES (%s, %s)",
                (from_number, message)
            )

            conn.commit()
            cur.close()
            conn.close()

            reply = f"""
✅ *Pedido recibido con éxito*

🧾 Pedido:
{message}

👨‍🍳 Un operador humano te contactará pronto para confirmar.

Gracias por elegirnos ❤️  
Escribe *menu* para volver.
            """

        except Exception as e:
            print("❌ Error guardando pedido:", e)
            reply = "❌ Error al guardar tu pedido. Intenta nuevamente."

    return PlainTextResponse(
        content=f"""
<Response>
  <Message>{reply}</Message>
</Response>
        """,
        media_type="text/xml"
    )
