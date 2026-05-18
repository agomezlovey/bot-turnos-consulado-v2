#!/usr/bin/env python3
"""
Bot de monitoreo de turnos - Consulado Argentino en Milan
VERSION CORREGIDA - Detecta "Sin disponibilidad" (texto real de la pagina)
"""

import requests
import time
import json
import logging
import sys
import os
from datetime import datetime
from bs4 import BeautifulSoup

# =============================================================================
# CONFIGURACION DESDE VARIABLES DE ENTORNO (Railway, Render, etc.)
# =============================================================================

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TELEGRAM_BOT_TOKEN:
    TELEGRAM_BOT_TOKEN = "TU_TOKEN_AQUI"
if not TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = None
else:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID)

URL_TURNOS = "https://turnos.argentina.gob.ar/turnos/seleccionTurno/3354/pais/37/prov/100/loc/2911"
INTERVALO_SEGUNDOS = int(os.environ.get('INTERVALO_SEGUNDOS', '180'))

# =============================================================================
# TEXTO CLAVE - ACTUALIZADO SEGUN PAGINA REAL
# =============================================================================
# La pagina muestra "Sin disponibilidad" en rojo cuando no hay turnos
MENSAJE_SIN_TURNOS = "Sin disponibilidad"

# Textos alternativos por si cambian en el futuro
MENSAJES_SIN_TURNOS_ALTERNATIVOS = [
    "Sin disponibilidad",
    "Sin turnos disponibles",
    "No hay turnos",
    "Sin disponibilidad",
    "No disponible",
    "Agotado",
    "No se encontraron",
]

# =============================================================================
# CONFIGURACION DE LOGS
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# FUNCIONES DE TELEGRAM
# =============================================================================

def enviar_mensaje_telegram(mensaje, token=None, chat_id=None):
    if token is None:
        token = TELEGRAM_BOT_TOKEN
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID

    if not token or token == "TU_TOKEN_AQUI":
        logger.error("ERROR: No configuraste el TOKEN de Telegram!")
        return False

    if not chat_id:
        logger.error("ERROR: No configuraste el CHAT_ID.")
        return False

    url = "https://api.telegram.org/bot" + str(token) + "/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Mensaje enviado a Telegram")
            return True
        else:
            logger.error("Error al enviar mensaje: " + str(response.text))
            return False
    except Exception as e:
        logger.error("Excepcion al enviar mensaje: " + str(e))
        return False


def obtener_chat_id(token):
    logger.info("Obteniendo actualizaciones de Telegram para detectar tu chat ID...")
    logger.info("Por favor, enviale un mensaje a tu bot en Telegram ahora...")

    url = "https://api.telegram.org/bot" + str(token) + "/getUpdates"

    for intento in range(30):
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if data.get("result"):
                ultimo = data["result"][-1]
                chat_id = ultimo["message"]["chat"]["id"]
                username = ultimo["message"]["chat"].get("username", "Desconocido")

                logger.info("Chat ID encontrado: " + str(chat_id) + " (Usuario: " + str(username) + ")")
                return chat_id
        except Exception as e:
            logger.error("Error obteniendo updates: " + str(e))

        time.sleep(10)

    logger.error("No se pudo obtener el chat ID.")
    return None


# =============================================================================
# FUNCIONES DE MONITOREO
# =============================================================================

def verificar_turnos():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-AR,es;q=0.9,it;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    }

    try:
        logger.info("Consultando disponibilidad... [" + datetime.now().strftime('%H:%M:%S') + "]")

        session = requests.Session()

        logger.info("Conectando al servidor...")
        home_response = session.get(
            "https://turnos.argentina.gob.ar/",
            headers=headers,
            timeout=30,
            allow_redirects=True
        )
        logger.info("Home status: " + str(home_response.status_code))

        response = session.get(
            URL_TURNOS,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )

        response.raise_for_status()
        logger.info("Turnos status: " + str(response.status_code))

        html_content = response.text
        html_lower = html_content.lower()
        logger.info("HTML recibido: " + str(len(html_content)) + " caracteres")

        # =================================================================
        # DETECCION PRINCIPAL - "Sin disponibilidad"
        # =================================================================
        sin_turnos_detectado = False
        texto_detectado = ""

        for texto in MENSAJES_SIN_TURNOS_ALTERNATIVOS:
            if texto.lower() in html_lower:
                sin_turnos_detectado = True
                texto_detectado = texto
                logger.info("Detectado texto de SIN TURNOS: '" + texto + "'")
                break

        if sin_turnos_detectado:
            return False, "Sin turnos disponibles (texto: " + texto_detectado + ")", {"status": "no_disponible", "texto": texto_detectado}

        # =================================================================
        # SI NO ESTA "Sin disponibilidad", ANALIZAR SI HAY TURNOS
        # =================================================================
        soup = BeautifulSoup(html_content, 'html.parser')

        selectores_fecha = soup.find_all('select', {'name': lambda x: x and 'fecha' in x.lower()})
        selectores_hora = soup.find_all('select', {'name': lambda x: x and 'hora' in x.lower()})
        botones_confirmar = soup.find_all('button', {'type': 'submit'})
        inputs_fecha = soup.find_all('input', {'name': lambda x: x and 'fecha' in x.lower()})

        textos_disponibilidad = [
            "seleccionar fecha", "seleccionar hora", "confirmar turno",
            "disponible", "cupos", "proximos turnos", "reservar", "agendar",
            "turno disponible", "fecha disponible", "horario disponible"
        ]

        hay_indicadores = False
        texto_encontrado = ""

        for texto in textos_disponibilidad:
            if texto.lower() in html_lower:
                hay_indicadores = True
                texto_encontrado = texto
                break

        # Si hay selectores de fecha/hora o botones de confirmar -> HAY TURNOS
        if selectores_fecha or selectores_hora or inputs_fecha or (botones_confirmar and hay_indicadores):
            detalles = {
                "status": "disponible",
                "selectores_fecha": len(selectores_fecha),
                "selectores_hora": len(selectores_hora),
                "inputs_fecha": len(inputs_fecha),
                "botones": len(botones_confirmar),
                "texto_detectado": texto_encontrado
            }
            logger.info("INDICADORES DE TURNOS DETECTADOS!")
            return True, "TURNOS DISPONIBLES!", detalles

        # Si no hay nada claro, asumir que no hay turnos (por seguridad)
        logger.info("No se detectaron indicadores claros de turnos ni de sin turnos")
        return False, "Sin turnos (analisis por defecto)", {"status": "no_disponible", "html_length": len(html_content)}

    except requests.exceptions.RequestException as e:
        logger.error("Error de red: " + str(e))
        return None, "Error de red: " + str(e), {"error": str(e)}
    except Exception as e:
        logger.error("Error inesperado: " + str(e))
        return None, "Error: " + str(e), {"error": str(e)}


# =============================================================================
# BUCLE PRINCIPAL
# =============================================================================

def main():
    global TELEGRAM_CHAT_ID

    logger.info("=" * 60)
    logger.info("BOT DE MONITOREO DE TURNOS - CONSULADO ARGENTINO MILAN")
    logger.info("Tramite: Conversion Licencia Argentina -> Italiana")
    logger.info("VERSION CORREGIDA - Detecta 'Sin disponibilidad'")
    logger.info("=" * 60)

    if TELEGRAM_BOT_TOKEN == "TU_TOKEN_AQUI":
        logger.error("ERROR CRITICO: No configuraste el TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    if TELEGRAM_CHAT_ID is None:
        logger.info("TELEGRAM_CHAT_ID no configurado. Iniciando auto-deteccion...")
        TELEGRAM_CHAT_ID = obtener_chat_id(TELEGRAM_BOT_TOKEN)

        if TELEGRAM_CHAT_ID:
            logger.info("Chat ID detectado: " + str(TELEGRAM_CHAT_ID))
            logger.info("Agrega esta variable en Railway: TELEGRAM_CHAT_ID")
            enviar_mensaje_telegram(
                "Bot configurado! Chat ID: " + str(TELEGRAM_CHAT_ID) + ". Agrega esta variable en Railway y redeploya."
            )
        else:
            logger.error("No se pudo obtener el chat ID.")
        sys.exit(0)

    enviar_mensaje_telegram(
        "Bot iniciado en Railway (v2.1 - Corregido)\n"
        "Tramite: Conversion Licencia Argentina -> Italiana\n"
        "Consulado Argentino en Milan\n"
        "Intervalo: cada " + str(INTERVALO_SEGUNDOS // 60) + " minutos\n"
        "Detectando: 'Sin disponibilidad'\n"
        "Te avisare cuando haya turnos!"
    )

    ultimo_estado = None
    contador_verificaciones = 0
    errores_consecutivos = 0

    logger.info("Intervalo: " + str(INTERVALO_SEGUNDOS) + " segundos")
    logger.info("Iniciando monitoreo...")

    try:
        while True:
            contador_verificaciones += 1
            hay_turnos, mensaje, detalles = verificar_turnos()

            if hay_turnos is None:
                errores_consecutivos += 1
                logger.warning("Intento " + str(contador_verificaciones) + ": Error (" + str(errores_consecutivos) + " errores seguidos)")
                if errores_consecutivos % 5 == 0:
                    enviar_mensaje_telegram("Error persistente #" + str(errores_consecutivos) + ": " + mensaje)

            elif hay_turnos:
                errores_consecutivos = 0
                if ultimo_estado != "disponible":
                    logger.info("TURNOS DISPONIBLES!")
                    mensaje_alerta = (
                        "ALERTA: TURNOS DISPONIBLES!\n\n"
                        "Tramite: Conversion Licencia Argentina -> Italiana\n"
                        "Consulado: Milan, Italia\n"
                        "Detectado: " + datetime.now().strftime('%d/%m/%Y %H:%M:%S') + "\n\n"
                        "Reserva AHORA:\n"
                        + URL_TURNOS + "\n\n"
                        "Apurate! Los turnos se agotan rapido."
                    )
                    for _ in range(3):
                        enviar_mensaje_telegram(mensaje_alerta)
                        time.sleep(2)
                    ultimo_estado = "disponible"
                else:
                    logger.info("Turnos siguen disponibles")

            else:
                errores_consecutivos = 0
                if ultimo_estado != "no_disponible":
                    logger.info(mensaje)
                    enviar_mensaje_telegram("Estado actual: Sin turnos disponibles. Sigo monitoreando...")
                    ultimo_estado = "no_disponible"
                else:
                    logger.info("Intento " + str(contador_verificaciones) + ": Sin turnos")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        logger.info("Bot detenido.")
        enviar_mensaje_telegram("Bot detenido. Verificaciones: " + str(contador_verificaciones))


if __name__ == "__main__":
    main()
