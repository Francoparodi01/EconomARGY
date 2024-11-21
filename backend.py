import requests
from fastapi import FastAPI
from pydantic import BaseModel
import os
import uvicorn
from dotenv import load_dotenv

APP = FastAPI()

class Dolar(BaseModel):
    casa: str
    compra: float
    venta: float
    fecha: str

last_dolar_values = {}

#URL de Ambito

load_dotenv()

url_ambito = os.getenv("url_ambito")




def get_dolar_values():
    try:
        response = requests.get(url_ambito)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(e)
        return None
    

@APP.get("/dolares")
def cotizacion_dolar():
    try:
        response = requests.get(url_ambito)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(e)
        return {"error": "No se pudo obtener el valor del dólar."}

    
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
        return changes
    else:
        return {"message": "No hay cambios en los valores del dólar"}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="127.0.0.1", port=8000)