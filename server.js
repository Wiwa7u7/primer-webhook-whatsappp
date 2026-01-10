const express = require("express");
const bodyParser = require("body-parser");
const { Pool } = require("pg");

const app = express();
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// ======================================
// 🔗 CONEXIÓN A POSTGRES (RAILWAY)
// ======================================
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false, // 🔥 OBLIGATORIO en Railway
  },
});

// ======================================
// 🧱 INICIALIZAR BASE DE DATOS
// ======================================
async function initDB() {
  try {
    console.log("⏳ Conectando a PostgreSQL...");

    // Test REAL de conexión
    await pool.query("SELECT 1");
    console.log("✅ Conexión a PostgreSQL OK");

    // Crear tabla si no existe
    await pool.query(`
      CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        phone VARCHAR(30),
        order_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    console.log("✅ Tabla orders creada o ya existente");

  } catch (error) {
    console.error("❌ ERROR INICIALIZANDO DB:", error);
  }
}

// Ejecutar al iniciar el servidor
initDB();

// ======================================
// 📲 WEBHOOK WHATSAPP (TWILIO)
// ======================================
app.post("/whatsapp", async (req, res) => {
  const message = req.body.Body?.trim().toLowerCase();
  const from = req.body.From;

  let reply = "";

  if (message === "hola" || message === "menu") {
    reply = `
👋 Hola, soy el asistente de *Pollos El Buen Sabor* 🍗

1️⃣ Ver precios  
2️⃣ Horarios y ubicación  
3️⃣ Hacer un pedido  

Responde con el número de la opción.
    `;
  }

  else if (message === "1") {
    reply = `
💰 *Precios*

🍗 Pollo entero: $10  
🍗 Medio pollo: $6  

Escribe *menu* para volver.
    `;
  }

  else if (message === "2") {
    reply = `
📍 *Horario y ubicación*

🕒 Lunes a Domingo: 11am - 10pm  
📌 Centro de la ciudad  

Escribe *menu* para volver.
    `;
  }

  else if (message === "3") {
    reply = `
✍️ Perfecto, escribe tu pedido.
Ejemplo:
👉 1 pollo entero y 1 medio pollo
    `;
  }

  else {
    // ======================================
    // 🧾 GUARDAR PEDIDO EN POSTGRES
    // ======================================
    try {
      await pool.query(
        "INSERT INTO orders (phone, order_text) VALUES ($1, $2)",
        [from, message]
      );

      reply = `
✅ *Pedido recibido con éxito*

🧾 Pedido:
${message}

👨‍🍳 Un operador humano te contactará pronto para confirmar.

Gracias por elegirnos ❤️  
Escribe *menu* para volver.
      `;
    } catch (error) {
      console.error("❌ Error guardando pedido:", error);
      reply = "❌ Hubo un error al guardar tu pedido. Intenta nuevamente.";
    }
  }

  res.set("Content-Type", "text/xml");
  res.send(`
<Response>
  <Message>${reply}</Message>
</Response>
  `);
});

// ======================================
// 🚀 INICIAR SERVIDOR
// ======================================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("🚀 Servidor corriendo en puerto", PORT);
});
