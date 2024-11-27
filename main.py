import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext
from pymongo import MongoClient
from datetime import datetime
import threading
import asyncio
import uvicorn

# Cargar las variables de entorno
load_dotenv()

# Crear la aplicación FastAPI
APP = FastAPI()

# Variables globales
telegram_token = os.getenv("Telegram_Token")
chat_id = os.getenv("chat_id")
url_ambito = os.getenv("url_ambito")
url_backend = os.getenv("Backend_URL")
chat_id_user = os.getenv("chat_id_user")
url_inflacion = os.getenv("url_inflacion")
MONGO_URI = os.getenv("MONGO_URI")
url_riesgo_pais = os.getenv("url_riesgo_pais")

# Crear el bot de Telegram
bot = Bot(token=telegram_token)

# Conexión con la base de datos MongoDB
client = MongoClient(MONGO_URI)
db = client["cotizaciones"]
collection = db["dolar"]

# Obtener los datos de Ambito
def get_dolar_values():
    try:
        response = requests.get(f"{url_ambito}")
        response.raise_for_status()  # Verifica si la respuesta es exitosa
        data = response.json()  # Asumiendo que la respuesta está en formato JSON
        if isinstance(data, list) and all("casa" in item for item in data):
            return data
        else:
            print("⚠️ La respuesta de la API no tiene el formato esperado.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Obtener los datos de Inflación
def get_inflacion_data():
    try:
        response = requests.get(url_inflacion)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Obtener ultimo dato riesgo pais
def get_riesgo_pais():
    try:
        response = requests.get(url_riesgo_pais)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Funciones para Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"¡Hola! Soy tu bot económico. Usa /help para ver los comandos disponibles."
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n"
        " - /start: Iniciar el bot.\n"
        " - /help: Ver esta ayuda.\n"
        " - /dolar [tipo]: Consultar el precio del dólar (oficial, blue, etc.).\n"
        " - /check_dolar: Iniciar notificaciones de cambios en el dólar."
    )

# Función para almacenar los valores del dólar en la base de datos
async def update_dolar_values(data, update: Update):
    try:
        for dolar in data:
            document = {
                "_id": f"{dolar['moneda']}_{dolar['casa']}",  # Combinamos moneda y casa para crear un identificador único
                "moneda": dolar["moneda"],
                "casa": dolar["casa"],
                "nombre": dolar["nombre"],
                "compra": dolar["compra"],
                "venta": dolar["venta"],
                "fechaActualizacion": datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ")
            }

            # Intentamos actualizar o insertar el valor
            result = collection.update_one(
                {"_id": document["_id"]},
                {"$set": document},
                upsert=True
            )
            # Eliminamos la parte que requiere `update.message.reply_text` aquí
            if result.modified_count > 0:
                await update.message.reply_text(f"✅ Valor actualizado: Dólar {document['nombre']} - Compra: {document['compra']} / Venta: {document['venta']}")
    except Exception as e:
        print(f"Error al actualizar los valores del dólar: {e}")

# Función para obtener el valor del dólar desde la base de datos
async def get_dolar_from_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = context.args[0].lower() if context.args else "oficial"
    dolar = collection.find_one({"moneda": "USD", "casa": tipo})

    if dolar:
        fecha_actualizacion = dolar['fechaActualizacion']
        fecha_formateada = fecha_actualizacion.strftime("%Y-%m-%d %H:%M")
        await update.message.reply_text(
            f"💵 *Dólar {dolar['nombre']}*\n"
            f"🟢 Compra: {dolar['compra']} ARS\n"
            f"🔴 Venta: {dolar['venta']} ARS\n"
            f"📅 Última actualización: {fecha_formateada}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("No se encontraron datos para el tipo de dólar solicitado.")


# Función para almacenar los valores del dólar en la base de datos
async def store_dolar_values(update):
    data = get_dolar_values()
    if data:
        await update_dolar_values(data, update) 

# Función para verificar y notificar cambios en los valores del dólar        
async def check_and_notify_changes(context: CallbackContext):
    try:
        # Obtener los valores actuales desde la API
        data = get_dolar_values()

        if not data:
            print("⚠️ No se pudo obtener los datos del dólar.")
            return

        for dolar in data:
            # Crear el documento esperado
            document = {
                "_id": f"{dolar['moneda']}_{dolar['casa']}",  # Identificador único
                "moneda": dolar["moneda"],
                "casa": dolar["casa"],
                "nombre": dolar["nombre"],
                "compra": dolar["compra"],
                "venta": dolar["venta"],
                "fechaActualizacion": datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ"),
            }

            # Buscar el documento existente en la base de datos
            existing_doc = collection.find_one({"_id": document["_id"]})

            # Compara los valores de compra y venta
            if existing_doc:
                if (
                    existing_doc["compra"] != document["compra"]
                    or existing_doc["venta"] != document["venta"]
                ):
                    # Si los valores cambiaron, enviar notificación
                    chat_id = context.job.data["chat_id"]  # Obtener el chat_id desde `data`
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🔔 *Actualización de Dólar {document['nombre']}*\n"
                            f"🟢 Compra: {document['compra']} ARS\n"
                            f"🔴 Venta: {document['venta']} ARS\n"
                            f"📅 Última actualización: {document['fechaActualizacion']:%Y-%m-%d %H:%M}" 
                        ), 
                        parse_mode="Markdown", # Formato Markdown para negritas
                    )

            # Actualizar o insertar el documento en la base de datos
            collection.update_one({"_id": document["_id"]}, {"$set": document}, upsert=True)

    except Exception as e:
        print(f"⚠️ Error al verificar y notificar cambios: {e}")

async def start_periodic_check(update: Update, context: CallbackContext):
    try:
        # Inicia el trabajo periódico
        context.job_queue.run_repeating(
            check_and_notify_changes,
            interval=60,  # Intervalo de 60 segundos
            first=5,  # Primera ejecución después de 5 segundos
            data={"chat_id": update.effective_chat.id},  # Pasar el chat_id como datos
        )
        await update.message.reply_text("🔄 El bot notificará actualizaciones en los valores del dólar.")
    except Exception as e:
        print(f"⚠️ Error al iniciar la verificación periódica: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al iniciar la verificación periódica.")



# Rutas de FastAPI
@APP.get("/")
def welcome():
    return {"message": "¡Bienvenido al servidor de cotizaciones!"}

@APP.get("/dolares")
def cotizacion_dolar():
    data = get_dolar_values()
    if not data:
        return {"error": "No se pudo obtener el valor del dólar."}
    return {"data": data}

@APP.get("/inflacion")
def obtener_inflacion():
    fecha_inicio = '2023-12-10'
    fecha_hoy_str = datetime.now().strftime('%Y-%m-%d')
    data = get_inflacion_data()
    if data and 'results' in data:
        return [{"fecha": item['fecha'], "valor": item['valor']} for item in data['results']]
    return {"error": "No se pudo obtener los datos de inflación."}

@APP.get("/riesgo_pais")
def obtener_riesgo_pais():
    data = get_riesgo_pais()
    if data:
        return {"data": data}
    return {"error": "No se pudo obtener el riesgo país."}

async def start_services():
    bot_task = asyncio.create_task(APP.run_polling())
    fastapi_task = asyncio.create_task(uvicorn.run(APP, host="127.0.0.1", port=8000))
    await asyncio.gather(bot_task, fastapi_task)


# Función principal de Telegram
def main():
    print("Iniciando el bot de Telegram...")

    app = Application.builder().token(telegram_token).build()

    # Comandos de Telegram 
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("dolar", get_dolar_from_db))
    app.add_handler(CommandHandler("check_dolar", start_periodic_check))
    

    # Ejecutar el bot
    app.run_polling()

if __name__ == "__main__":
    main()
    asyncio.run(start_services())