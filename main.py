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
from datetime import datetime

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
            data = await response.json()
            return data["data"]  # Acceder a la lista "data" que contiene los valores


# Función para guardar los valores en MongoDB
def save_dolar_to_db(new_data):
    """Guardar nuevos datos en la base de datos."""
    for dolar in new_data:
        collection.update_one(
            {"_id": dolar["casa"]},  # Buscar por identificador único (nombre de la casa)
            {"$set": {
                "compra": dolar["compra"],
                "venta": dolar["venta"],
                "ultimaActualizacion": dolar["fechaActualizacion"]
            }},
            upsert=True  # Crear un nuevo documento si no existe
        )

# Función para obtener los valores del dólar desde la API 
async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await get_dolar_values()
        tipo = context.args[0].lower() if context.args else "oficial"
        dolar = next((item for item in data if item["casa"].lower() == tipo), None)
        if dolar:
            await update.message.reply_text(
                f"💵 *Dólar {dolar['nombre']} ({dolar['casa']})*\n"
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


# Función para detectar cambios en los valores
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


def save_dolar_to_db(new_data):
    """Guardar nuevos datos en la base de datos."""
    for dolar in new_data:
        collection.update_one(
            {"_id": dolar["casa"]},  # Buscar por identificador único
            {"$set": {
                "compra": dolar["compra"],
                "venta": dolar["venta"],
                "ultimaActualizacion": dolar["fechaActualizacion"]
            }},
            upsert=True  # Crear un nuevo documento si no existe
        )


# Variable para guardar la última fecha procesada
last_notified_time = None

async def check_dolar_changes(context: CallbackContext):
    global last_notified_time  # Usamos la variable global para rastrear la última fecha procesada

    try:
        # Obtener valores actuales desde la API
        current_dolar_values = await get_dolar_values()

        # Si no hay valores previos registrados en la variable global, obtener el último registro de la BD
        if not last_notified_time:
            last_entry = collection.find_one(sort=[("ultimaActualizacion", -1)])  # Obtener el registro más reciente
            if last_entry:
                last_notified_time = datetime.strptime(last_entry["ultimaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ")

        # Procesar nuevos datos
        new_data = []
        for dolar in current_dolar_values:
            # Convertir fecha de actualización
            dolar_datetime = datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ")

            # Agregar a la lista de nuevos datos solo si es más reciente que la última notificación
            if not last_notified_time or dolar_datetime > last_notified_time:
                new_data.append(dolar)

        if new_data:
            # Generar mensaje de notificación
            message = "💵 *Actualización de los valores del dólar:*\n\n"
            for dolar in new_data:
                message += (
                    f"🏠 Casa: {dolar['nombre']} ({dolar['casa']})\n"
                    f"🟢 Compra: {dolar['compra']} ARS\n"
                    f"🔴 Venta: {dolar['venta']} ARS\n"
                    f"📅 Fecha: {dolar['fechaActualizacion']}\n\n"
                )

            # Guardar los datos nuevos en la base de datos
            save_dolar_to_db(new_data)

            # Actualizar la última fecha procesada
            last_notified_time = max(
                datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ")
                for dolar in new_data
            )

            # Enviar notificación al usuario
            await context.bot.send_message(chat_id=chat_id_user, text=message, parse_mode="Markdown")
        else:
            print("No hay nuevos datos.")
    except Exception as e:
        print(f"⚠️ Error en la detección de cambios: {e}")


# Función para obtener la última hora de actualización guardada en la base de datos
def get_last_update_time():
    """Obtener la última hora de actualización guardada en la base de datos."""
    last_entry = collection.find_one(sort=[("ultimaActualizacion", -1)])  # Ordenar por el campo más reciente
    if last_entry:
        return datetime.strptime(last_entry["ultimaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ")
    return None
        
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