from telegram import Update
from telegram.ext import Application, Updater, CommandHandler, CallbackContext, filters, ContextTypes, MessageHandler
import requests
from fastapi import FastAPI


# Variables de .env
token = '7854598944:AAFaTWosQnasErlclPxlmZQrE0IwyYscUl0' 

userName = "Economargy_bot"

# Inicialización de FastAPI

APP = FastAPI()

# Tomamos valores de la api de Dolares

url_ambito = 'https://dolarapi.com/v1/ambito' # Url de la api USD



APP.get("/dolares")
def read_item(requests):
    response = requests.get(url_ambito)
    data = response.json()
    print(data)
    return data










# Comandos del bot 
async def start(update: Update, context: ContextTypes):
    await update.message.reply_text(f"Hello! My name is {userName} . How can I help you?")

async def error(update: Update, context: CallbackContext):
    await update.message.reply_text("An error has occurred.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()  # Procesar texto del mensaje
    print(f"Received message: {text}")

    if "hello" in text:
        response = "Hello!"
    elif "bye" in text:
        response = "Goodbye!"
    else:
        response = "I don't understand you."

    await update.message.reply_text(response)

if __name__ == '__main__':
    print("Bot starting...")
    app = Application.builder().token(token).build()

    # Manejar comandos
    app.add_handler(CommandHandler("start", start))

    # Manejar mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & filters.TEXT, handle_message))
    
    # Manejar errores
    app.add_error_handler(error)
    
    print("Bot started!")
    app.run_polling(poll_interval=1, timeout=5)