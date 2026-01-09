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

    return PlainTextResponse ("👋 Hola, soy el asistente virtual de *Pollos El Buen Sabor* 🐔\n\n"
    "Puedo ayudarte con:\n"
    "1️⃣ Ver precios\n"
    "2️⃣ Horarios y ubicación\n"
    "3️⃣ Hacer un pedido\n\n"
    "Responde con el número de la opción que desees.")
