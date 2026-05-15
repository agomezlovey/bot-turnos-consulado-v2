#!/usr/bin/env python3
"""
Bot de monitoreo de turnos - Consulado Argentino en Milán
VERSIÓN PARA RAILWAY / SERVIDOR EN LA NUBE

Lee TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID desde variables de entorno.
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
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO (Railway, Render, etc.)
# =============================================================================

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Si no están en variables de entorno, usar valores hardcodeados (para pruebas locales)
if not TELEGRAM_BOT_TOKEN:
    TELEGRAM_BOT_TOKEN = "TU_TOKEN_AQUI"
if not TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = None  # Auto-detectar en primera ejecución
else:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID)

# URL del trámite de conversión de licencia en Milán
URL_TURNOS = "https://turnos.argentina.gob.ar/turnos/seleccionTurno/3354/pais/37/prov/100/loc/2911"

# Intervalo de monitoreo en segundos
INTERVALO_SEGUNDOS = int(os.environ.get('INTERVALO_SEGUNDOS', '180'))

# Mensaje clave que indica SIN turnos disponibles
MENSAJE_SIN_TURNOS = "Sin turnos disponibles"

# =============================================================================
# CONFIGURACIÓN DE LOGS
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
    """Envía un mensaje por Telegram."""
    if token is None:
        token = TELEGRAM_BOT_TOKEN
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID

    if not token or token == "TU_TOKEN_AQUI":
        logger.error("❌ ERROR: No configuraste el TOKEN de Telegram!")
        return False

    if not chat_id:
        logger.error("❌ ERROR: No configuraste el CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Mensaje enviado a Telegram")
            return True
        else:
            logger.error(f"❌ Error al enviar mensaje: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Excepción al enviar mensaje: {e}")
        return False


def obtener_chat_id(token):
    """Obtiene el chat ID enviando primero un mensaje al bot."""
    logger.info("🔍 Obteniendo actualizaciones de Telegram para detectar tu chat ID...")
    logger.info("📱 Por favor, enviale un mensaje a tu bot en Telegram ahora...")

    url = f"https://api.telegram.org/bot{token}/getUpdates"

    for intento in range(30):
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if data.get("result"):
                ultimo = data["result"][-1]
                chat_id = ultimo["message"]["chat"]["id"]
                username = ultimo["message"]["chat"].get("username", "Desconocido")

                logger.info(f"✅ Chat ID encontrado: {chat_id} (Usuario: {username})")
                return chat_id
        except Exception as e:
            logger.error(f"Error obteniendo updates: {e}")

        time.sleep(10)

    logger.error("❌ No se pudo obtener el chat ID.")
    return None


# =============================================================================
# FUNCIONES DE MONITOREO
# =============================================================================

def verificar_turnos():
    """Verifica si hay turnos disponibles."""
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
        logger.info(f"🔍 Consultando disponibilidad... [{datetime.now().strftime('%H:%M:%S')}]")

        session = requests.Session()

        logger.info("🌐 Conectando al servidor...")
        home_response = session.get(
            "https://turnos.argentina.gob.ar/",
            headers=headers,
            timeout=30,
            allow_redirects=True
        )
        logger.info(f"📊 Home status: {home_response.status_code}")

        response = session.get(
            URL_TURNOS,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )

        response.raise_for_status()
        logger.info(f"📊 Turnos status: {response.status_code}")

        html_content = response.text
        logger.info(f"📄 HTML recibido: {len(html_content)} caracteres")

        if MENSAJE_SIN_TURNOS.lower() in html_content.lower():
            return False, "Sin turnos disponibles", {"status": "no_disponible"}

        soup = BeautifulSoup(html_content, 'html.parser')

        selectores_fecha = soup.find_all('select', {'name': lambda x: x and 'fecha' in x.lower()})
        selectores_hora = soup.find_all('select', {'name': lambda x: x and 'hora' in x.lower()})
        botones_confirmar = soup.find_all('button', {'type': 'submit'})

        textos_disponibilidad = [
            "seleccionar fecha", "seleccionar hora", "confirmar turno",
            "disponible", "cupos", "próximos turnos", "reservar", "agendar"
        ]

        hay_indicadores = False
        texto_encontrado = ""

        for texto in textos_disponibilidad:
            if texto.lower() in html_content.lower():
                hay_indicadores = True
                texto_encontrado = texto
                break

        if selectores_fecha or selectores_hora or (botones_confirmar and hay_indicadores):
            detalles = {
                "status": "disponible",
                "selectores_fecha": len(selectores_fecha),
                "selectores_hora": len(selectores_hora),
                "botones": len(botones_confirmar),
                "texto_detectado": texto_encontrado
            }
            return True, "¡TURNOS DISPONIBLES!", detalles

        return False, "Sin turnos disponibles (por defecto)", {"status": "no_disponible", "html_length": len(html_content)}

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error de red: {e}")
        return None, f"Error de red: {e}", {"error": str(e)}
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return None, f"Error: {e}", {"error": str(e)}


# =============================================================================
# BUCLE PRINCIPAL
# =============================================================================

def main():
    """Función principal del bot."""
    global TELEGRAM_CHAT_ID

    logger.info("=" * 60)
    logger.info("🤖 BOT DE MONITOREO DE TURNOS - CONSULADO ARGENTINO MILÁN")
    logger.info("📝 Trámite: Conversión Licencia Argentina → Italiana")
    logger.info("☁️  Versión Railway - Cloud")
    logger.info("=" * 60)

    if TELEGRAM_BOT_TOKEN == "TU_TOKEN_AQUI":
        logger.error("❌ ERROR CRÍTICO: No configuraste el TELEGRAM_BOT_TOKEN")
        logger.error("   Agregá la variable de entorno TELEGRAM_BOT_TOKEN en Railway.")
        sys.exit(1)

    if TELEGRAM_CHAT_ID is None:
        logger.info("⚠️  TELEGRAM_CHAT_ID no configurado. Iniciando auto-detección...")
        TELEGRAM_CHAT_ID = obtener_chat_id(TELEGRAM_BOT_TOKEN)

        if TELEGRAM_CHAT_ID:
            logger.info(f"📋 Chat ID detectado: {TELEGRAM_CHAT_ID}")
            logger.info("   Agregá esta variable en Railway: TELEGRAM_CHAT_ID")
            enviar_mensaje_telegram(
                f"✅ <b>Bot configurado!</b>\n"
                f"Chat ID: <code>{TELEGRAM_CHAT_ID}</code>\n"
                f"Agregá esta variable en Railway y redeployá."
            )
        else:
            logger.error("❌ No se pudo obtener el chat ID.")
        sys.exit(0)

    enviar_mensaje_telegram(
        f"🚀 <b>Bot iniciado en Railway</b>\n"
        f"📍 Trámite: Conversión Licencia Argentina → Italiana\n"
        f"🏛️ Consulado Argentino en Milán\n"
        f"⏱️ Intervalo: cada {INTERVALO_SEGUNDOS // 60} minutos\n"
        f"🔔 Te avisaré cuando haya turnos!"
    )

    ultimo_estado = None
    contador_verificaciones = 0
    errores_consecutivos = 0

    logger.info(f"⏱️  Intervalo: {INTERVALO_SEGUNDOS} segundos")
    logger.info("🟢 Iniciando monitoreo...\n")

    try:
        while True:
            contador_verificaciones += 1
            hay_turnos, mensaje, detalles = verificar_turnos()

            if hay_turnos is None:
                errores_consecutivos += 1
                logger.warning(f"⚠️  Error #{errores_consecutivos}: {mensaje}")
                if errores_consecutivos % 5 == 0:
                    enviar_mensaje_telegram(f"⚠️ <b>Error #{errores_consecutivos}</b>: {mensaje}")

            elif hay_turnos:
                errores_consecutivos = 0
                if ultimo_estado != "disponible":
                    logger.info("🎉🎉🎉 ¡TURNOS DISPONIBLES! 🎉🎉🎉")
                    mensaje_alerta = (
                        f"🚨🚨🚨 <b>¡TURNOS DISPONIBLES!</b> 🚨🚨🚨\n\n"
                        f"📍 <b>Trámite:</b> Conversión Licencia Argentina → Italiana\n"
                        f"🏛️ <b>Consulado:</b> Milán, Italia\n"
                        f"⏰ <b>Detectado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                        f"🔗 <b>Reservá AHORA:</b>\n"
                        f"{URL_TURNOS}\n\n"
                        f"⚡ <b>¡Apurate! Los turnos se agotan rápido.</b>"
                    )
                    for _ in range(3):
                        enviar_mensaje_telegram(mensaje_alerta)
                        time.sleep(2)
                    ultimo_estado = "disponible"
                else:
                    logger.info("✅ Turnos siguen disponibles")

            else:
                errores_consecutivos = 0
                if ultimo_estado != "no_disponible":
                    logger.info(f"📭 {mensaje}")
                    enviar_mensaje_telegram(f"📭 <b>Sin turnos</b>. Sigo monitoreando...")
                    ultimo_estado = "no_disponible"
                else:
                    logger.info(f"📭 Intento {contador_verificaciones}: Sin turnos")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido.")
        enviar_mensaje_telegram(f"🛑 <b>Bot detenido</b>. Verificaciones: {contador_verificaciones}")


if __name__ == "__main__":
    main()
