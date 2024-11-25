from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    filters,
    JobQueue,
)
from dotenv import load_dotenv
import os
import aiohttp 
import requests
from pymongo import MongoClient

# Variables de .env
load_dotenv()

# Token y configuración del bot
token = os.getenv("Telegram_Token")
userName = os.getenv("Telegram_Username")
backend_url = os.getenv("Backend_URL")
chat_id_user = os.getenv("chat_id_user")

# Funciones del Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"¡Hola! Soy {userName}, tu bot económico. Usa /help para ver mis comandos disponibles."
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n"
        " - /start: Iniciar el bot.\n"
        " - /help: Ver esta ayuda.\n"
        " - /dolar [tipo]: Consultar el precio del dólar (oficial, blue, etc.).\n"
        " - /check_dolar: Inicia el monitoreo de cambios en el precio del dólar.\n"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    print(f"Received message: {text}")

    if "hello" in text:
        response = "¡Hola!"
    elif "bye" in text:
        response = "¡Adiós!"
    else:
        response = "No entiendo el mensaje. Usa /help para ver los comandos disponibles."

    await update.message.reply_text(response)

# Funciones para el manejo de la base de datos 

# conexión con la BD
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["cotizaciones"]  
collection = db["dolar"]  


async def get_dolar_values():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{backend_url}/dolares") as response:
            response.raise_for_status()
            return await response.json()



# Función para guardar los valores en MongoDB
def save_dolar_to_db(changes):
    for change in changes:
        collection.update_one(
            {"_id": change["casa"]},  # Buscar por el identificador único
            {"$set": {  # Actualizar valores y timestamp
                "compra": change["compra"],
                "venta": change["venta"],
                "ultimaActualizacion": change["fecha"]
            }},
            upsert=True  # Crear un documento si no existe
        )

# Función para obtener los valores del dólar desde la API 
async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await get_dolar_values()
        tipo = context.args[0].lower() if context.args else "oficial"
        dolar = next((item for item in data if item["casa"].lower() == tipo), None)
        if dolar:
            await update.message.reply_text(
                f"💵 *Dólar {dolar['casa']}*\n"
                f"🟢 Compra: {dolar['compra']} ARS\n"
                f"🔴 Venta: {dolar['venta']} ARS\n"
                f"📅 Última actualización: {dolar['fechaActualizacion']}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "No se encontró información sobre el dólar solicitado. Verifica el tipo (e.g., oficial, blue, etc.)."
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error al consultar los datos: {str(e)}")
def detect_changes(new_data):
    changes = []
    for dolar in new_data:
        casa = dolar["casa"]
        compra = float(dolar["compra"])
        venta = float(dolar["venta"])

        # Consultar el último valor en la base de datos
        last_dolar = collection.find_one({"_id": casa})

        if last_dolar:
            # Comprobar si hay cambios
            if (
                last_dolar["compra"] != compra
                or last_dolar["venta"] != venta
                or not last_dolar.get("notificado", False)
            ):
                changes.append({
                    "casa": casa,
                    "compra": compra,
                    "venta": venta,
                    "fecha": dolar["fechaActualizacion"],
                })
        else:
            # Si no existe en la BD, lo consideramos como un cambio
            changes.append({
                "casa": casa,
                "compra": compra,
                "venta": venta,
                "fecha": dolar["fechaActualizacion"],
            })
    return changes


def save_dolar_to_db(changes):
    for change in changes:
        collection.update_one(
            {"_id": change["casa"]},  # Buscar por el identificador único
            {"$set": {  # Actualizar valores y timestamp
                "compra": change["compra"],
                "venta": change["venta"],
                "ultimaActualizacion": change["fecha"],
                "notificado": True  # Marcar como notificado
            }},
            upsert=True  # Crear un documento si no existe
        )


async def check_dolar_changes(context: CallbackContext):
    try:
        current_dolar_values = await get_dolar_values()
        changes = detect_changes(current_dolar_values)
        if changes:
            message = "💵 *Actualización de los valores del dólar:*\n\n"
            for change in changes:
                message += (
                    f"🏠 Casa: {change['casa']}\n"
                    f"🟢 Compra: {change['compra']} ARS\n"
                    f"🔴 Venta: {change['venta']} ARS\n"
                    f"📅 Fecha: {change['fecha']}\n\n"
                )
            save_dolar_to_db(changes)
            await context.bot.send_message(chat_id=chat_id_user, text=message, parse_mode="Markdown")
        else:
            print("No hay cambios detectados.")
    except Exception as e:
        print(f"⚠️ Error en la detección de cambios: {e}")

        
# Comando para iniciar el monitoreo
async def start_check_dolar(update: Update, context: CallbackContext):
    try: 
        context.job_queue.run_repeating(check_dolar_changes, interval=60, first=5)
        await update.message.reply_text("⏳ Monitoreo del dólar iniciado. Te notificaré si hay cambios.")
    except Exception as e:
        print(f"Error al iniciar el monitoreo del dólar: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al intentar iniciar el monitoreo del dólar.")

def main():
    print("Iniciando el bot de Telegram...")

    # Iniciar el bot de Telegram
    app = Application.builder().token(token).build()

    # Manejar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("dolar", get_dolar))
    app.add_handler(CommandHandler("check_dolar", start_check_dolar))

    # Manejar mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Iniciar el bot
    app.run_polling()

if __name__ == "__main__":
    main()