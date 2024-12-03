import os
import requests
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext
from pymongo import MongoClient
from datetime import datetime
import threading
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Cargar las variables de entorno
load_dotenv()

# Variables globales
telegram_token = os.getenv("Telegram_Token")
chat_id = os.getenv("chat_id")
url_ambito = os.getenv("url_ambito")
url_backend = os.getenv("Backend_URL")
chat_id_user = os.getenv("chat_id_user")
url_inflacion = os.getenv("url_inflacion")
MONGO_URI = os.getenv("MONGO_URI")
url_riesgo_pais = os.getenv("url_riesgo_pais")

# Verificar que todas las variables estén definidas
if not all([telegram_token, chat_id, url_ambito, chat_id_user, url_inflacion, MONGO_URI, url_riesgo_pais]):
    raise RuntimeError("Faltan variables de entorno obligatorias.")

# Crear el bot de Telegram
bot = Bot(token=telegram_token)

# Conexión con la base de datos MongoDB
client = MongoClient(MONGO_URI)
db = client["cotizaciones"]
collection = db["dolar"]
collection_diario = db["dolar_diario"]

# Obtener los datos de Ambito
def get_dolar_values():
    try:
        response = requests.get(f"{url_ambito}")
        response.raise_for_status()  # Verifica si la respuesta es exitosa
        data = response.json()  
        if isinstance(data, list) and all("casa" in item for item in data):
            return data
        else:
            print("⚠️ La respuesta de la API no tiene el formato esperado.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos: {e}")
        return None

# Obtener los datos de Inflación
def get_inflation_data():
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
    
async def enviar_inflacion(update: Update, context: CallbackContext):
    # Recupera los argumentos de fecha enviados por el usuario
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Por favor, proporciona dos fechas en el formato 'YYYY-MM YYYY-MM'.")
        return

    start_date = args[0]
    end_date = args[1]

    # Validar las fechas en formato 'YYYY-MM'
    try:
        datetime.strptime(start_date, '%Y-%m')
        datetime.strptime(end_date, '%Y-%m')
    except ValueError:
        await update.message.reply_text("Las fechas deben estar en el formato 'YYYY-MM'.")
        return

    # Convertir las fechas a objetos datetime, estableciendo el día como el primer día del mes
    start_date_obj = datetime.strptime(start_date, '%Y-%m').replace(day=1)
    end_date_obj = datetime.strptime(end_date, '%Y-%m').replace(day=1)

    # Obtener los datos de inflación
    data = get_inflation_data()
    if not data:
        await update.message.reply_text("No se pudieron obtener los datos de inflación.")
        return

    # Filtrar los datos en el rango de fechas
    filtered_data = [entry for entry in data if start_date_obj <= datetime.strptime(entry['fecha'], '%Y-%m-%d') < end_date_obj]

    if not filtered_data:
        await update.message.reply_text("No hay datos disponibles para el rango de fechas especificado.")
        return

    # Generar el gráfico de inflación en el rango de fechas
    imagen_buffer = plot_inflation(filtered_data, start_date_obj, end_date_obj)
    
    if imagen_buffer:
        await update.message.reply_photo(photo=imagen_buffer, caption=f"Gráfico de la inflación desde {start_date} hasta {end_date}.")
    else:
        await update.message.reply_text("No se pudo generar el gráfico de inflación.")

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
            # Si se actualizó el valor, notificarlo
            if result.modified_count > 0:
                # Enviar mensaje al chat
                await update.message.reply_text(f"✅ Valor actualizado: Dólar {document['nombre']} - Compra: {document['compra']} / Venta: {document['venta']}")
    except Exception as e:
        print(f"Error al actualizar los valores del dólar: {e}")


async def obtener_todos_los_dolares(update: Update, context: CallbackContext):
    try:
        # Obtener todos los documentos de la colección de la base de datos
        documentos = list(collection.find().sort("fechaActualizacion", -1))  # Ordenar por fecha descendente
        
        if not documentos:
            await update.message.reply_text("⚠️ No se encontraron datos de la base de datos.")
            return

        # Crear un mensaje con todos los datos de todos los tipos de dólar
        mensaje = "📊 Datos completos del dólar:\n\n"
        for doc in documentos:
            # Extraer los valores del documento
            moneda = doc.get("moneda", "Desconocido")
            casa = doc.get("casa", "Desconocida")
            nombre = doc.get("nombre", "Desconocido")
            compra = doc.get("compra", 0)
            venta = doc.get("venta", 0)
            fecha_actualizacion = doc.get("fechaActualizacion")

            # Verificar si la fecha es un objeto datetime y formatear adecuadamente
            if isinstance(fecha_actualizacion, datetime):
                fecha_formateada = fecha_actualizacion.strftime("%d/%m/%Y %H:%M:%S")
            else:
                fecha_formateada = "Desconocida"

            # Construir el mensaje
            mensaje += f"🏠 Dolar: {nombre} \n"
            mensaje += f"💰 Compra: {compra:.2f} ARS\n"
            mensaje += f"💸 Venta: {venta:.2f} ARS\n\n"
            mensaje += f"📅 última actualización: {fecha_formateada}\n"

        # Verificar el límite de caracteres de Telegram y enviar el mensaje
        if len(mensaje) > 4096:
            # Dividir el mensaje en partes y enviarlas
            for i in range(0, len(mensaje), 4096):
                await update.message.reply_text(mensaje[i:i + 4096], parse_mode="Markdown")
        else:
            # Enviar el mensaje completo
            await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        print(f"Error en obtener_todos_los_dolares: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al obtener los datos del dólar.")




# Función para obtener el valor del dólar desde la base de datos
async def get_dolar_from_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = context.args[0].lower() if context.args else "oficial"
    dolar = collection.find_one({"moneda": "USD", "casa": tipo})

    # Si se encontraron datos, enviar el mensaje
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
async def store_dolar_values(update: Update):
    try:
        # Obtener los valores del dólar
        data = get_dolar_values()
        if data:
            print("ℹ️ Datos obtenidos correctamente para almacenar en la base de datos.")
            # Procesar y almacenar los datos
            for dolar in data:
                document = {
                    "_id": f"{dolar['moneda']}_{dolar['casa']}",
                    "moneda": dolar["moneda"],
                    "casa": dolar["casa"],
                    "nombre": dolar["nombre"],
                    "compra": dolar["compra"],
                    "venta": dolar["venta"],
                    "fechaActualizacion": datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ"),
                }

                # Insertar o actualizar el documento en la base de datos
                result = collection.update_one({"_id": document["_id"]}, {"$set": document}, upsert=True)

                # Informar al usuario de la actualización
                if result.upserted_id or result.modified_count > 0:
                    await update.message.reply_text(
                        f"✅ Valor actualizado: Dólar {document['nombre']} - "
                        f"Compra: {document['compra']} / Venta: {document['venta']}"
                    )
        else:
            await update.message.reply_text("⚠️ No se pudieron obtener los valores del dólar.")
    except Exception as e:
        print(f"Error al almacenar valores del dólar: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al almacenar los valores del dólar.")


# Función para verificar y notificar cambios en los valores del dólar
async def check_and_notify_changes(context: CallbackContext):
    try:
        # Obtener datos de la API
        data = get_dolar_values()
        if data:
            # Reutilizar la lógica de almacenamiento
            for dolar in data:
                document = {
                    "_id": f"{dolar['moneda']}_{dolar['casa']}",
                    "moneda": dolar["moneda"],
                    "casa": dolar["casa"],
                    "nombre": dolar["nombre"],
                    "compra": dolar["compra"],
                    "venta": dolar["venta"],
                    "fechaActualizacion": datetime.strptime(dolar["fechaActualizacion"], "%Y-%m-%dT%H:%M:%S.%fZ"),
                }

                # Verificar si existe en la base de datos
                existing_doc = collection.find_one({"_id": document["_id"]})
                if existing_doc and (
                    existing_doc["compra"] != document["compra"] or existing_doc["venta"] != document["venta"]
                ):
                    # Notificar cambios
                    await context.bot.send_message(
                        chat_id=context.job.data["chat_id"],
                        text=(f"🔔 *Actualización de Dólar {document['nombre']}*\n"
                              f"🟢 Compra: {document['compra']} ARS\n"
                              f"🔴 Venta: {document['venta']} ARS\n"
                              f"📅 Última actualización: {document['fechaActualizacion']:%Y-%m-%d %H:%M}"),
                        parse_mode="Markdown",
                    )

                # Almacenar o actualizar en la base de datos
                collection.update_one({"_id": document["_id"]}, {"$set": document}, upsert=True)
    except Exception as e:
        print(f"Error en check_and_notify_changes: {e}")


async def start_periodic_check(update: Update, context: CallbackContext):
    try:
        # Inicia el trabajo periódico
        context.job_queue.run_repeating(
            check_and_notify_changes,
            interval=10, 
            first=5,  
            data={"chat_id": update.effective_chat.id},  # Pasar el chat_id como datos
        )
        await update.message.reply_text("🔄 El bot notificará actualizaciones en los valores del dólar.")
    except Exception as e:
        print(f"⚠️ Error al iniciar la verificación periódica: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al iniciar la verificación periódica.")

async def analisis_semanal_dolar(update: Update):
    try:
        # Obtener la fecha de hoy y la fecha hace 7 días
        hoy = datetime.now().date()
        hace_7_dias = hoy - timedelta(days=7)

        # Buscar los valores de la semana en la colección
        documentos_semanales = collection_diario.find({"fecha": {"$gte": hace_7_dias, "$lte": hoy}})
        
        if not documentos_semanales:
            await update.message.reply_text("⚠️ No se encontraron datos de la semana para el análisis.")
            return

        # Crear listas para los datos de compra y venta
        fechas = []
        compras = []
        ventas = []

        for doc in documentos_semanales:
            fechas.append(doc["fecha"])
            compras.append(doc["compra"])
            ventas.append(doc["venta"])

        # Calcular las variaciones
        variacion_compra = compras[-1] - compras[0]
        variacion_venta = ventas[-1] - ventas[0]

        # Generar gráfico
        plt.figure(figsize=(10, 5))
        plt.plot(fechas, compras, label="Compra (ARS)", marker='o')
        plt.plot(fechas, ventas, label="Venta (ARS)", marker='o')
        plt.xlabel("Fecha")
        plt.ylabel("Valor (ARS)")
        plt.title("Análisis Semanal del Dólar")
        plt.legend()
        plt.grid(True)

        # Guardar la imagen del gráfico en un buffer de memoria
        imagen_buffer = io.BytesIO()
        plt.savefig(imagen_buffer, format='png')
        imagen_buffer.seek(0)

        # Enviar el gráfico por Telegram
        await update.message.reply_photo(photo=imagen_buffer, caption=(
            f"📈 Análisis semanal del dólar:\n"
            f"Variación de la compra: {variacion_compra:.2f} ARS\n"
            f"Variación de la venta: {variacion_venta:.2f} ARS"
        ))

    except Exception as e:
        print(f"Error en analisis_semanal_dolar: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al generar el análisis semanal del dólar.")
        


# --------------------------- GRÁFICOS MATPLOTLIB ------------------------------
def plot_inflation(data, start_date, end_date):
    # Filtra los datos para incluir solo los que están en el rango de fecha proporcionado
    filtered_data = [entry for entry in data if start_date <= datetime.strptime(entry['fecha'], '%Y-%m-%d').replace(day=1) < end_date]

    if not filtered_data:
        print("No hay datos para el rango de fechas especificado.")
        return None

    # Generar gráfico
    fechas = [datetime.strptime(entry['fecha'], '%Y-%m-%d').replace(day=1) for entry in filtered_data]
    valores = [entry['valor'] for entry in filtered_data]

    plt.figure(figsize=(12, 6))
    plt.plot(fechas, valores, marker='o', linestyle='-', color='b')
    plt.title(f'Inflación de {start_date.strftime("%B %Y")} a {end_date.strftime("%B %Y")}')
    plt.xlabel('Fecha')
    plt.ylabel('Inflación (%)')
    plt.grid(True)
    
    # Guardar en un buffer de memoria
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return buf


# Función principal de Telegram
def main():
    print("Iniciando el bot de Telegram...")

    app = Application.builder().token(telegram_token).build()

    # Comandos de Telegram 
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("dolar", get_dolar_from_db))
    app.add_handler(CommandHandler("dolares", obtener_todos_los_dolares))
    app.add_handler(CommandHandler("check_dolar", start_periodic_check))
    app.add_handler(CommandHandler("inflacion", enviar_inflacion))

    
    app.run_polling()

if __name__ == "__main__":
    main()