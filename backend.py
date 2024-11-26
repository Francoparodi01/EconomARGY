import requests
from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from telegram import Bot
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime


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
chat_id_user = os.getenv("chat_id_user")
url_inflacion = os.getenv("url_inflacion")

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
        response.raise_for_status()  # Verifica errores HTTP
        data = response.json()  # Intenta cargar el JSON
        if isinstance(data, list) and all("casa" in item for item in data):
            return data
        else:
            print("⚠️ La respuesta de la API no tiene el formato esperado.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None


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
    return {"data": data}

def get_inflacion_data():
    try:
        response = requests.get(url_inflacion)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None



@APP.get("/inflacion")
def obtener_inflacion():
    fecha_inicio = '2023-12-10'
    fecha_hoy_str = datetime.now().strftime('%Y-%m-%d')
    dataInflacion_url = f'{url_inflacion}/{fecha_inicio}/{fecha_hoy_str}'

    data = get_inflacion_data()
    if data and 'results' in data:
        return [{"fecha": item['fecha'], "valor": item['valor']} for item in data['results']]
    
    return {"error": "No se pudo obtener los datos de inflación."}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="0.0.0.0", port=8000)