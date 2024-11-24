from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv 
import os 
import requests
import aiohttp
import schedule


# Variables de .env
load_dotenv()

# Variables globales
last_dolar_values = {}

# Token y nombre de usuario del bot
token = os.getenv("Telegram_Token")
userName = os.getenv("Telegram_Username")
backend_url = os.getenv("Backend_URL")
chat_id = os.getenv("chat_id")

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

# Función para obtener los valores del dólar desde la API
def get_dolar_values():
    try:
        response = requests.get(f"{backend_url}/dolares")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Función para verificar cambios y enviar mensajes
async def check_dolar_changes(context: ContextTypes.DEFAULT_TYPE):
    global last_dolar_values

    # Obtener los valores actuales
    current_dolar_values = get_dolar_values()
    if not current_dolar_values:
        print("⚠️ No se pudieron obtener los valores.")
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
        await context.bot.send_message(chat_id=context.job.chat_id, text=message, parse_mode="Markdown")
    else:
        await context.bot.send_message("✅ Sin cambios en los valores del dólar.")

# Programar la verificación de cambios cada 1 minuto
def schedule_dolar():
    schedule.every(1).minutes.do(check_dolar_changes)

# Sitio inicial bot
async def get_dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{backend_url}/dolares") as response:
                response.raise_for_status()
                data = await response.json()

        # Comprobar si el usuario especificó un tipo de dólar
        if context.args:
            tipo = context.args[0].lower()  
        else:
            tipo = "oficial"  

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

async def check_dolar_changes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Monitoreo del dólar iniciado. Te notificaré cuando haya cambios en los valores.")

    # Programar el monitoreo cada 1 minuto
    chat_id = update.effective_chat.id
    context.job_queue.run_repeating(check_dolar_changes, interval=60, first=0, chat_id=chat_id)
        

def main():

    print("Iniciando el bot de Telegram...")
    
    # Iniciar el bot de Telegram
    app = Application.builder().token(token).build()
    print("¡Bot de Telegram iniciado!")

    # Manejar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dolar", get_dolar))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("check_dolar", check_dolar_changes))

    # Manejar mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & filters.TEXT, handle_message))

    # Manejar errores
    app.add_error_handler(error)

    # Iniciar el bot
    app.run_polling(poll_interval=1, timeout=5)

# Main
if __name__ == '__main__':
    main()