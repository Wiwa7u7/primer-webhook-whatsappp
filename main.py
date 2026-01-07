from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    mensaje = form.get("Body")
    numero = form.get("From")

    print("Mensaje recibido:", mensaje)
    print("Número:", numero)

    return PlainTextResponse("Hola 👋 Soy el asistente virtual de la pollera 🐔\n\n"
        "Puedo ayudarte con:\n"
        "1️⃣ Precios\n"
        "2️⃣ Horarios\n"
        "3️⃣ Pedidos\n\n"
        "Escribe cualquier cosa para probar.")
