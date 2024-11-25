import requests
from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from telegram import Bot
from pymongo import MongoClient
from bson import ObjectId


# Cargar las variables de entorno
load_dotenv()

# Crear la aplicación FastAPI
APP = FastAPI()

# Modelo de datos del Dólar
class Dolar(BaseModel):
    casa: str
    compra: float
    venta: float
    fecha: str

def serialize_objectid(data):
    if isinstance(data, dict):
        return {key: serialize_objectid(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_objectid(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    return data

# Variables globales
last_dolar_values = {}
telegram_token = os.getenv("Telegram_Token")
chat_id = os.getenv("chat_id")
url_ambito = os.getenv("url_ambito")
url_backend = os.getenv("Backend_URL")

# Crear el bot de Telegram
bot = Bot(token=telegram_token)

# conexión con la BD
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["cotizaciones"]  
collection = db["dolar"]  

# Función para obtener los valores del dólar desde la API o HTML
def get_dolar_values():
    try:
        response = requests.get(url_ambito)
        response.raise_for_status()  
        return response.json()  
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Función para enviar un mensaje al bot de Telegram
def send_telegram_message(message: str):
    try:
        bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

# Función para guardar los valores en MongoDB
def save_dolar_to_db(dolar_data):
    for dolar in dolar_data:
        # Verificar si ya existe el valor para esta casa
        existing_data = collection.find_one({"casa": dolar['casa']})
        if existing_data:
            # Si existe, actualizar los valores
            collection.update_one(
                {"casa": dolar['casa']},
                {"$set": {
                    "compra": dolar['compra'],
                    "venta": dolar['venta'],
                    "fecha": dolar['fecha']
                }}
            )
        else:
            # Si no existe, insertar nuevo documento
            collection.insert_one(dolar)

# Ruta de bienvenida
@APP.get("/")
def welcome():
    return {"message": "¡Bienvenido al servidor de cotizaciones!"}


# Ruta para obtener la cotización más reciente del dólar
@APP.get("/dolares")
def cotizacion_dolar():
    data = get_dolar_values()
    if not data:
        return {"error": "No se pudo obtener el valor del dólar."}
    return data

# Ruta para obtener solo los valores de dólar que han cambiado
@APP.get("/dolares/actualizados")
def read_dolar():
    global last_dolar_values

    data = get_dolar_values()
    if not data:
        return {"error": "No se pudieron obtener los valores"}

    changes = []
    for dolar in data:
        casa = dolar["casa"]
        compra = dolar["compra"]
        venta = dolar["venta"]
        
        if casa in last_dolar_values:
            if (last_dolar_values[casa]["compra"] != compra or last_dolar_values[casa]["venta"] != venta):
                changes.append({
                    "casa": casa,
                    "compra": compra,
                    "venta": venta,
                    "fecha": dolar["fechaActualizacion"]
                })
        else:
            changes.append({
                "casa": casa,
                "compra": compra,
                "venta": venta,
                "fecha": dolar["fechaActualizacion"]
            })

        # Actualizar el último valor para la próxima comparación
        last_dolar_values[casa] = {"compra": compra, "venta": venta}

    if changes:
        # Enviar mensaje de notificación al bot
        message = "💵 *Actualización de los valores del dólar:*\n\n"
        for change in changes:
            message += f"🏠 Casa: {change['casa']}\n"
            message += f"🟢 Compra: {change['compra']} ARS\n"
            message += f"🔴 Venta: {change['venta']} ARS\n"
            message += f"📅 Fecha de actualización: {change['fecha']}\n\n"
        
        # Guardar los cambios en la base de datos
        save_dolar_to_db(changes)

        # Enviar el mensaje al bot de Telegram
        send_telegram_message(message)

        # Asegúrate de serializar los cambios antes de devolverlos
        return serialize_objectid(changes)
    else:
        return {"message": "No hay cambios en los valores del dólar"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host=f"{url_backend}", port=8000)