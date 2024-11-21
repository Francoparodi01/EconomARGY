from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters
import requests
from multiprocessing import Process
from dotenv import load_dotenv 
import os 

# Variables de .env
load_dotenv()

# Token y nombre de usuario del bot
token = os.getenv("Telegram_Token")
userName = os.getenv("Telegram_Username")
backend_url = os.getenv("Backend_URL")

# Funciones del Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hello! My name is {userName}. How can I help you?")

async def error(update: Update, context: CallbackContext):
    await update.message.reply_text("An error has occurred.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    print(f"Received message: {text}")

    if "hello" in text:
        response = "Hello!"
    elif "bye" in text:
        response = "Goodbye!"
    else:
        response = "I don't understand you."

    await update.message.reply_text(response)

async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Solicitar los datos de la API local de FastAPI
        response = requests.get(f"{backend_url}/dolares")
        response.raise_for_status()
        data = response.json()

        # Comprobar si el usuario especificó un tipo de dólar
        if context.args:
            tipo = context.args[0].lower()  # Tomar el argumento como tipo de dólar
        else:
            tipo = "oficial"  # Predeterminado

        # Buscar el dólar solicitado en la lista de datos
        dolar = next((item for item in data if item['casa'] == tipo), None)

        if dolar:
            # Formatear la respuesta
            nombre = dolar['nombre']
            compra = dolar['compra']
            venta = dolar['venta']
            fecha = dolar['fechaActualizacion']
            await update.message.reply_text(
                f"💵 *Dólar {nombre}*\n"
                f"🟢 Compra: {compra} ARS\n"
                f"🔴 Venta: {venta} ARS\n"
                f"📅 Última actualización: {fecha}",
                parse_mode="Markdown"
            )
        else:
            # Mensaje de error si no se encuentra el tipo de dólar
            await update.message.reply_text(
                "No se encontró información sobre el dólar solicitado. "
                "Por favor, verifica el tipo (e.g., oficial, blue, cripto, etc.)."
            )
    except Exception as e:
        await update.message.reply_text(f"Ocurrió un error: {e}")



# Main
if __name__ == '__main__':
    print("Iniciando el bot de Telegram...")
    app = Application.builder().token(token).build()

    # Manejar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dolar", get_dolar))

    # Manejar mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & filters.TEXT, handle_message))

    # Manejar errores
    app.add_error_handler(error)

    print("¡Bot de Telegram iniciado!")
    app.run_polling(poll_interval=1, timeout=5)