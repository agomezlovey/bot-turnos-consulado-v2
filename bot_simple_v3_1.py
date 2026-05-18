#!/usr/bin/env python3
"""
Bot SIMPLE de monitoreo de turnos - Consulado Argentino en Milan
LOGICA: Si NO aparece "Sin disponibilidad" -> HAY TURNOS -> ALERTA
Version 3.1 - Compatible Windows
"""

import requests
import time
import logging
import sys
import os
from datetime import datetime

# =============================================================================
# CONFIGURACION DESDE VARIABLES DE ENTORNO
# =============================================================================

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'TU_TOKEN_AQUI')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
if TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID)

URL_TURNOS = "https://turnos.argentina.gob.ar/turnos/seleccionTurno/3354/pais/37/prov/100/loc/2911"
INTERVALO_SEGUNDOS = int(os.environ.get('INTERVALO_SEGUNDOS', '180'))

# =============================================================================
# TEXTOS QUE INDICAN "NO HAY TURNOS" (en rojo en la pagina)
# =============================================================================

TEXTOS_SIN_TURNOS = [
    "Sin disponibilidad",
    "sin turnos disponibles",
    "no hay turnos",
    "no disponible",
    "agotado",
    "no se encontraron",
    "no se hallaron",
]

# =============================================================================
# LOGS
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# TELEGRAM
# =============================================================================

def enviar_alerta(mensaje):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'TU_TOKEN_AQUI':
        logger.error('Falta TELEGRAM_BOT_TOKEN')
        return
    if not TELEGRAM_CHAT_ID:
        logger.error('Falta TELEGRAM_CHAT_ID')
        return

    url = "https://api.telegram.org/bot" + str(TELEGRAM_BOT_TOKEN) + "/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            logger.info('Alerta enviada a Telegram')
        else:
            logger.error('Error Telegram: ' + str(r.text))
    except Exception as e:
        logger.error('Error enviando alerta: ' + str(e))

# =============================================================================
# MONITOREO - LOGICA SIMPLE
# =============================================================================

def hay_turnos_disponibles():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        session = requests.Session()
        session.get("https://turnos.argentina.gob.ar/", headers=headers, timeout=30)
        response = session.get(URL_TURNOS, headers=headers, timeout=30)
        response.raise_for_status()

        html_lower = response.text.lower()

        # Buscar si aparece ALGUN texto de "sin turnos"
        for texto in TEXTOS_SIN_TURNOS:
            if texto.lower() in html_lower:
                logger.info('Texto encontrado: "' + texto + '" -> No hay turnos')
                return False

        # NINGUN texto de "sin turnos" aparece -> HAY TURNOS
        logger.info('ALERTA: NO se encontro texto de "sin turnos" -> HAY TURNOS!')
        return True

    except Exception as e:
        logger.error('Error de conexion: ' + str(e))
        return None

# =============================================================================
# MAIN
# =============================================================================

def main():
    logger.info("=" * 50)
    logger.info("BOT SIMPLE - Consulado Argentino Milan")
    logger.info("Logica: Si desaparece 'Sin disponibilidad' -> ALERTA")
    logger.info("=" * 50)

    if TELEGRAM_BOT_TOKEN == 'TU_TOKEN_AQUI':
        logger.error('Falta configurar TELEGRAM_BOT_TOKEN')
        sys.exit(1)

    if not TELEGRAM_CHAT_ID:
        logger.error('Falta configurar TELEGRAM_CHAT_ID')
        sys.exit(1)

    # Mensaje de inicio usando concatenacion simple
    mensaje_inicio = (
        "Bot iniciado\n"
        + "Monitoreando: Consulado Argentino en Milan\n"
        + "Tramite: Conversion de Licencia\n"
        + "Te avisare cuando DESAPAREZCA 'Sin disponibilidad'"
    )
    enviar_alerta(mensaje_inicio)

    ultimo_estado = "sin_turnos"
    contador = 0

    logger.info("Intervalo: " + str(INTERVALO_SEGUNDOS // 60) + " minutos")
    logger.info("Iniciando monitoreo...")

    while True:
        contador += 1
        logger.info("--- Verificacion #" + str(contador) + " ---")

        resultado = hay_turnos_disponibles()

        if resultado is None:
            logger.warning("Error en la verificacion, reintentando...")

        elif resultado is True:
            # HAY TURNOS!
            if ultimo_estado != "con_turnos":
                logger.info("TURNOS DISPONIBLES!")

                fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

                mensaje = (
                    "ALERTA: TURNOS DISPONIBLES!\n\n"
                    + "La escrita 'Sin disponibilidad' DESAPARECIO!\n"
                    + "Fecha: " + fecha_hora + "\n\n"
                    + "ENTRA YA:\n"
                    + URL_TURNOS + "\n\n"
                    + "Apurate antes de que se agoten!"
                )

                for i in range(3):
                    enviar_alerta(mensaje)
                    time.sleep(2)

                ultimo_estado = "con_turnos"
            else:
                logger.info("Turnos siguen disponibles")

        else:
            # No hay turnos
            if ultimo_estado != "sin_turnos":
                logger.info("Volvio a no haber turnos")
                enviar_alerta("Volvio a no haber turnos. Sigo monitoreando...")
                ultimo_estado = "sin_turnos"
            else:
                logger.info("Sin turnos (todo normal)")

        time.sleep(INTERVALO_SEGUNDOS)

if __name__ == "__main__":
    main()
