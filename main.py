from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters
import requests
from multiprocessing import Process
from dotenv import load_dotenv 
import os 
import aiohttp


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

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu bot económico. Puedes consultar:\n"
        " - /bot_status: Verificar el estado del bot.\n"
        " - /dolar : Para consultar por el precio del dólar oficial.\n"
        " - /dolar [tipo]: Consultar el precio del dólar.\n"
        " - /reservas_internacionales: Datos de las reservas internacionales.\n"
        " - /inflacion: Datos de la inflación.\n"
        " - /base_monetaria: Datos de la base monetaria.\n"
        " - /graficar_base: Gráfico de la base monetaria.\n"
        " - /graficar_inflacion: Gráfico de la inflación.\n"
        " - /web: Sitio web de datos económicos."
    )


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

# Sitio inicial bot
async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Usando aiohttp en lugar de requests para hacer una solicitud asincrónica
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{backend_url}/dolares") as response:
                response.raise_for_status()
                data = await response.json()

        # Comprobar si el usuario especificó un tipo de dólar
        if context.args:
            tipo = context.args[0].lower()  # Tomar el argumento como tipo de dólar
        else:
            tipo = "oficial"  # Predeterminado

        # Buscar el dólar solicitado en la lista de datos
        dolar = next((item for item in data if item['casa'].lower() == tipo), None)

        if dolar:
            # Formatear la respuesta
            compra = dolar['compra']
            venta = dolar['venta']
            fecha = dolar['fechaActualizacion']
            await update.message.reply_text(
                f"💵 *Dólar {dolar['casa']}*\n"
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
    app.add_handler(CommandHandler("help", help))

    # Manejar mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & filters.TEXT, handle_message))

    # Manejar errores
    app.add_error_handler(error)

    print("¡Bot de Telegram iniciado!")
    app.run_polling(poll_interval=1, timeout=5)