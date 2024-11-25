from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
import os
import aiohttp 
import requests

# Variables de .env
load_dotenv()

# Variables globales
last_dolar_values = {}

# Token y configuración del bot
token = os.getenv("Telegram_Token")
userName = os.getenv("Telegram_Username")
backend_url = os.getenv("Backend_URL")
chat_id = os.getenv("chat_id")

# Funciones del Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"¡Hola! Soy {userName}, tu bot económico. Usa /help para ver mis comandos disponibles."
    )

async def error(update: Update, context: CallbackContext):
    await update.message.reply_text("Ocurrió un error inesperado. Intenta de nuevo más tarde.")

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

# Función para obtener los valores del dólar desde la API (usando aiohttp)
async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{backend_url}/dolares") as response:
                response.raise_for_status()
                data = await response.json()

        # Comprobar si el usuario especificó un tipo de dólar
        tipo = context.args[0].lower() if context.args else "oficial"

        # Buscar el dólar solicitado en la lista de datos
        dolar = next((item for item in data if item["casa"].lower() == tipo), None)

        if dolar:
            # Formatear la respuesta
            compra = dolar["compra"]
            venta = dolar["venta"]
            fecha = dolar["fechaActualizacion"]
            await update.message.reply_text(
                f"💵 *Dólar {dolar['casa']}*\n"
                f"🟢 Compra: {compra} ARS\n"
                f"🔴 Venta: {venta} ARS\n"
                f"📅 Última actualización: {fecha}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "No se encontró información sobre el dólar solicitado. "
                "Por favor, verifica el tipo (e.g., oficial, blue, cripto, etc.)."
            )
    except aiohttp.ClientError as e:
        await update.message.reply_text(f"⚠️ Error al consultar los datos: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ocurrió un error inesperado: {str(e)}")

        # Función para actualizar los datos del dólar cuando haya modificaciones
async def check_dolar_changes(context: CallbackContext):
    global last_dolar_values

    try:
        print("Obteniendo los valores actuales del dólar...")
        response = requests.get(f"{backend_url}/dolares")
        response.raise_for_status()
        current_dolar_values = response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error al obtener datos: {e}")
        return

    changes_detected = False
    message = "💵 *Actualización de los valores del dólar:*\n\n"

    # Comparar valores actuales con los últimos valores guardados
    for dolar in current_dolar_values:
        casa = dolar["casa"]
        compra = float(dolar["compra"])
        venta = float(dolar["venta"])

        if casa in last_dolar_values:
            last_compra = last_dolar_values[casa]["compra"]
            last_venta = last_dolar_values[casa]["venta"]

            # Detectar si hay cambios
            if last_compra != compra or last_venta != venta:
                changes_detected = True
                message += (
                    f"🏠 Casa: {casa}\n"
                    f"🟢 Compra: {compra} ARS (Antes: {last_compra})\n"
                    f"🔴 Venta: {venta} ARS (Antes: {last_venta})\n\n"
                )
        else:
            # Si no hay valores anteriores, asumir que hay cambios
            changes_detected = True
            message += (
                f"🏠 Casa: {casa}\n"
                f"🟢 Compra: {compra} ARS\n"
                f"🔴 Venta: {venta} ARS\n\n"
            )

        # Actualizar los valores guardados
        last_dolar_values[casa] = {"compra": compra, "venta": venta}

    # Enviar notificación si hay cambios
    if changes_detected:
        print("¡Detectados cambios en los valores del dólar!")
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    else:
        print("✅ Sin cambios en los valores del dólar.")

# Comando para iniciar el monitoreo
async def start_check_dolar(update: Update, context: CallbackContext):
    try:
        print("Iniciando monitoreo del dólar...")
        context.job_queue.run_repeating(check_dolar_changes, interval=60, first=5)
        await update.message.reply_text("⏳ Monitoreo del dólar iniciado. Te notificaré cuando haya cambios en los valores.")
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

    # Manejar errores
    app.add_error_handler(error)

    # Iniciar el bot
    app.run_polling()

if __name__ == "__main__":
    main()
