import requests
from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from telegram import Bot

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

# Variables globales
last_dolar_values = {}
telegram_token = os.getenv("Telegram_Token")
chat_id = os.getenv("chat_id")
url_ambito = os.getenv("url_ambito")

# Inicializar el bot de Telegram
bot = Bot(token=telegram_token)

# Función para obtener los valores del dólar desde la API
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

        last_dolar_values[casa] = {"compra": compra, "venta": venta}

    if changes:
        # Enviar mensaje de notificación al bot
        message = "💵 *Actualización de los valores del dólar:*\n\n"
        for change in changes:
            message += f"🏠 Casa: {change['casa']}\n"
            message += f"🟢 Compra: {change['compra']} ARS\n"
            message += f"🔴 Venta: {change['venta']} ARS\n"
            message += f"📅 Fecha de actualización: {change['fecha']}\n\n"
        send_telegram_message(message)
        return changes
    else:
        return {"message": "No hay cambios en los valores del dólar"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="127.0.0.1", port=8000)
