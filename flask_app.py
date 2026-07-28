import os
import re
import json
import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HABITS_SHEET_ID = "1LXbi7RVzaPgot8pXQt7GZN4GqYydZXpoIbdh91zRdyA"
WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"

DINERO_OBJETIVO = 5000
ENTRENOS_OBJETIVO = 200

HABITOS = [
    "Ejercicio hombros",
    "Gym",
    "Leer",
    "No porno",
    "No azucar",
    "Movilidad",
    "Estudiar",
    "Oracion",
]

HABITOS_RECORDATORIO = ["Leer", "Movilidad", "Oracion"]
HABITOS_CRITICOS = ["Gym", "Leer"]
FRASE_MOTIVACIONAL = (
    "«Si el sufrimiento es inevitable, si nuestros problemas en la vida son ineludibles, "
    "entonces la pregunta que nos deberíamos plantear no es '¿cómo dejo de sufrir?' "
    "sino '¿por qué estoy sufriendo, con qué propósito?'»"
)

MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

GRUPOS_MUSCULARES = {
    "Pecho": ["pecho", "banca", "aperturas", "pec deck", "fondos de pecho"],
    "Espalda": ["espalda", "remo", "dominada", "jalón", "jalon", "pulldown"],
    "Piernas": ["pierna", "sentadilla", "prensa", "zancada", "femoral", "cuádriceps", "cuadriceps", "gemelo"],
    "Hombros": ["hombro", "militar", "elevaciones laterales"],
    "Biceps": ["biceps", "bíceps", "curl de biceps", "curl biceps"],
    "Triceps": ["triceps", "tríceps"],
    "Core": ["abdomen", "plancha", "crunch", "core"],
}

PATRON_SERIE = re.compile(
    r"^Serie (\d+):\s*([\d.,]+)\s*kg\s*x\s*(\d+)(?:\s*\[(.+?)\])?$",
    re.IGNORECASE
)
PATRON_FECHA = re.compile(
    r"(\w+),\s*(\w+)\s*(\d{1,2}),\s*(\d{4})\s*a las\s*(\d{1,2}):(\d{2})\s*(am|pm)",
    re.IGNORECASE
)

# ---------- Telegram ----------

def enviar_mensaje(texto, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        res = requests.post(url, data=payload, timeout=5)
        return res.json()
    except Exception as e:
        print(f"Error al enviar mensaje por Telegram: {e}")
        return None

def editar_mensaje(message_id, texto, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        payload = {
            "chat_id": CHAT_ID,
            "message_id": message_id,
            "text": texto,
            "parse_mode": "Markdown"
        }
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Error al editar mensaje en Telegram: {e}")

def responder_callback(callback_query_id, texto=""):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
        requests.post(url, data={"callback_query_id": callback_query_id, "text": texto}, timeout=5)
    except Exception as e:
        print(f"Error al responder callback en Telegram: {e}")

# ---------- Google Sheets ----------

def conectar_sheets(sheet_id=HABITS_SHEET_ID):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("/home/Markkos03/mysite/credenciales.json", scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)

def obtener_estado_examenes():
    try:
        sheet = conectar_sheets(HABITS_SHEET_ID)
        hoja = sheet.worksheet("Metas")
        val = hoja.acell("Z2").value
        return val == "ON"
    except Exception as e:
        print(f"Error al obtener estado de exámenes: {e}")
        return False

def cambiar_estado_examenes(estado_bool):
    try:
        sheet = conectar_sheets(HABITS_SHEET_ID)
        hoja = sheet.worksheet("Metas")
        hoja.update_cell(2, 26, "ON" if estado_bool else "OFF")
        return True
    except Exception as e:
        print(f"Error al cambiar estado de exámenes: {e}")
        return False

def marcar_habito_en_sheet(nombre_habito):
    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")

    if hoy_str not in fechas:
        return

    col_hoy = fechas.index(hoy_str) + 1

    for idx, fila in enumerate(valores[1:], start=2):
        if fila and fila[0] == nombre_habito:
            hoja.update_cell(idx, col_hoy, "Sí")
            break

# ---------- Habitos: progreso, hoy, rachas ----------

def calcular_progreso():
    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")
    col_hoy = fechas.index(hoy_str) if hoy_str in fechas else len(fechas) - 1

    primer_dia_mes = 1
    for i in range(col_hoy, 0, -1):
        dia = fechas[i].split("/")[0]
        if dia == "01":
            primer_dia_mes = i
            break

    dia_actual = int(fechas[col_hoy].split("/")[0])
    mes_actual = int(fechas[col_hoy].split("/")[1])
    anio_actual = int(fechas[col_hoy].split("/")[2])
    dias_en_mes = calendar.monthrange(anio_actual, mes_actual)[1]
    dias_restantes = max(0, dias_en_mes - dia_actual)

    filas_habitos = valores[1:1 + len(HABITOS)]

    texto = "📊 *BALANCE MENSUAL*\n"
    texto += f"🗓️ _Mes actual_ | ⏳ Quedan *{dias_restantes}* días\n"
    texto += "───────────────────\n\n"

    for fila in filas_habitos:
        nombre = fila[0]
        dias_del_mes = fila[primer_dia_mes:col_hoy + 1]
        veces_cumplido = dias_del_mes.count("Sí")
        pct = round((veces_cumplido / dias_en_mes) * 100)

        barra = "🔥" if pct >= 80 else ("⚡" if pct >= 50 else "🌱")
        texto += f"{barra} *{nombre}*\n└ `{veces_cumplido}/{dias_en_mes} días` — *{pct}%*\n\n"

    return texto

def calcular_hoy():
    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")
    col_hoy = fechas.index(hoy_str) if hoy_str in fechas else len(fechas) - 1

    filas_habitos = valores[1:1 + len(HABITOS)]

    texto = "✨ *ESTADO DE HOY* ✨\n"
    if obtener_estado_examenes():
        texto += "📚 *[Modo Exámenes / Pausa Activado]*\n"

    texto += "───────────────────\n\n"

    botones = []
    for fila in filas_habitos:
        nombre = fila[0]
        valor_hoy = fila[col_hoy] if col_hoy < len(fila) else ""
        if valor_hoy == "Sí":
            texto += f"🟢 *{nombre}*\n"
        else:
            texto += f"⚪ {nombre}\n"
            botones.append([{"text": f"⚡ Marcar {nombre}", "callback_data": f"marcar_{nombre}"}])

    entrenos_totales = 0
    for fila in filas_habitos:
        if fila[0] == "Gym":
            entrenos_totales = fila[1:col_hoy + 1].count("Sí")

    hoja_metas = sheet.worksheet("Metas")
    valores_metas = hoja_metas.get_all_values()

    dinero_actual = 0
    for fila_meta in valores_metas:
        if fila_meta and fila_meta[0].replace("€", "").strip().isdigit() and len(fila_meta) > 1 and fila_meta[1] == "Sí":
            hito_valor = int(fila_meta[0].replace("€", "").strip())
            dinero_actual = max(dinero_actual, hito_valor)

    libros_leidos = 0
    for fila_libro in valores_metas[4:19]:
        if len(fila_libro) > 6 and fila_libro[6] == "Sí":
            libros_leidos += 1
    objetivo_libros = 15

    texto += "\n🏆 *OBJETIVOS DEL AÑO*\n"
    texto += f"🏋️‍♂️ *Entrenos:* `{entrenos_totales} / {ENTRENOS_OBJETIVO}`\n"
    texto += f"💸 *Ingresos:* `{dinero_actual} / {DINERO_OBJETIVO} €`\n"
    texto += f"📖 *Lectura:* `{libros_leidos} / {objetivo_libros} libros`\n"

    reply_markup = {"inline_keyboard": botones} if botones else None

    return texto, reply_markup

def calcular_rachas():
    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")
    col_hoy = fechas.index(hoy_str) if hoy_str in fechas else len(fechas) - 1

    def calcular_racha(fila_habito, columna_inicio):
        racha = 0
        col = columna_inicio
        while col >= 1 and fila_habito[col] == "Sí":
            racha += 1
            col -= 1
        return racha

    filas_habitos = valores[1:1 + len(HABITOS)]

    texto = "🔥 *TUS RACHAS ACTIVAS* 🔥\n"
    texto += "¡Mantén la inercia, no rompas la cadena!\n"
    texto += "───────────────────\n\n"

    hay_rachas = False
    for fila in filas_habitos:
        nombre = fila[0]
        racha = calcular_racha(fila, col_hoy)
        if racha > 0:
            hay_rachas = True
            texto += f"⚡ *{nombre}:* `{racha}` días seguidos\n"

    if not hay_rachas:
        texto = "❄️ *Sin rachas activas hoy.*\n¡Es un buen día para empezar una nueva!"

    return texto.strip()

def comprobar_recordatorio_2000():
    if obtener_estado_examenes():
        return

    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")

    if hoy_str not in fechas:
        return

    col_hoy = fechas.index(hoy_str)
    filas_habitos = valores[1:1 + len(HABITOS)]

    pendientes = []
    for fila in filas_habitos:
        nombre = fila[0]
        if nombre in HABITOS_RECORDATORIO:
            valor_hoy = fila[col_hoy] if col_hoy < len(fila) else ""
            if valor_hoy != "Sí":
                pendientes.append(nombre)

    if pendientes:
        texto = "⏰ *RECORDATORIO NOCTURNO*\n\n"
        texto += "Todavía tienes tareas pendientes para hoy:\n\n"
        botones = []
        for habito in pendientes:
            texto += f"⚪ {habito}\n"
            botones.append([{"text": f"⚡ Marcar {habito}", "callback_data": f"marcar_{habito}"}])

        reply_markup = {"inline_keyboard": botones}
        enviar_mensaje(texto, reply_markup=reply_markup)

def comprobar_alerta_inactividad():
    if obtener_estado_examenes():
        return

    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_str = ahora_madrid.strftime("%d/%m/%Y")

    if hoy_str not in fechas:
        return

    col_hoy = fechas.index(hoy_str)
    if col_hoy < 2:
        return

    col_ayer = col_hoy - 1
    filas_habitos = valores[1:1 + len(HABITOS)]

    habitos_fallados_2dias = []
    for fila in filas_habitos:
        nombre = fila[0]
        if nombre in HABITOS_CRITICOS:
            valor_hoy = fila[col_hoy] if col_hoy < len(fila) else ""
            valor_ayer = fila[col_ayer] if col_ayer < len(fila) else ""

            if valor_hoy != "Sí" and valor_ayer != "Sí":
                habitos_fallados_2dias.append(nombre)

    if habitos_fallados_2dias:
        lista_habitos = " y ".join(habitos_fallados_2dias)
        mensaje = (
            f"🚨 *ALERTA DE INACTIVIDAD* 🚨\n\n"
            f"Llevas 2 días seguidos sin cumplir con *{lista_habitos}*.\n\n"
            f"💬 _{FRASE_MOTIVACIONAL}_"
        )
        enviar_mensaje(mensaje)

def generar_resumen_semanal():
    sheet = conectar_sheets(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0]
    ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid"))

    hoy = ahora_madrid.date()
    lunes_pasado = hoy - timedelta(days=hoy.weekday() + 7)
    domingo_pasado = lunes_pasado + timedelta(days=6)

    lunes_str = lunes_pasado.strftime("%d/%m/%Y")
    domingo_str = domingo_pasado.strftime("%d/%m/%Y")

    if lunes_str not in fechas or domingo_str not in fechas:
        enviar_mensaje("⚠️ No se encontraron las fechas de la semana pasada en la hoja de cálculo.")
        return

    col_inicio = fechas.index(lunes_str)
    col_fin = fechas.index(domingo_str)

    filas_habitos = valores[1:1 + len(HABITOS)]

    total_posibles = len(filas_habitos) * 7
    total_cumplidos = 0

    resumen_habitos = {}
    for fila in filas_habitos:
        nombre = fila[0]
        dias_semana = fila[col_inicio:col_fin + 1]
        cumplidos = dias_semana.count("Sí")
        resumen_habitos[nombre] = cumplidos
        total_cumplidos += cumplidos

    pct_global = round((total_cumplidos / total_posibles) * 100) if total_posibles > 0 else 0

    max_val = max(resumen_habitos.values()) if resumen_habitos else 0
    min_val = min(resumen_habitos.values()) if resumen_habitos else 0

    estrellas = [k for k, v in resumen_habitos.items() if v == max_val]
    debiles = [k for k, v in resumen_habitos.items() if v == min_val]

    mensaje = f"🏆 *REPORTE SEMANAL*\n"
    mensaje += f"📅 `{lunes_str}` ➔ `{domingo_str}`\n"
    mensaje += "───────────────────\n\n"
    mensaje += f"🎯 *Rendimiento Global:* `{pct_global}%`\n\n"
    mensaje += f"🌟 *Hábito Estrella:* {', '.join(estrellas)} (`{max_val}/7`)\n"
    mensaje += f"🎯 *Punto a Mejorar:* {', '.join(debiles)} (`{min_val}/7`)\n\n"
    mensaje += "📋 *Detalle semanal:*\n"

    for nombre, c in resumen_habitos.items():
        mensaje += f"• *{nombre}:* `{c}/7` días\n"

    mensaje += "\n───\n💪 _«La disciplina es el puente entre metas y logros.»_\n¡A romperla esta semana!"
    enviar_mensaje(mensaje)

def marcar_habito_hoy(nombre_habito):
    marcar_habito_en_sheet(nombre_habito)

# ---------- Hevy: parsing y guardado ----------

def clasificar_musculo(nombre_ejercicio):
    nombre_lower = nombre_ejercicio.lower()
    for grupo, palabras in GRUPOS_MUSCULARES.items():
        for palabra in palabras:
            if palabra in nombre_lower:
                return grupo
    return "Otros"

def calcular_1rm(peso, reps):
    if reps <= 0:
        return 0
    return round(peso * (1 + reps / 30), 1)

def parsear_fecha_hevy(linea_fecha):
    m = PATRON_FECHA.search(linea_fecha)
    if not m:
        return None
    _dia_semana, mes_abrev, dia, anio, hora, minuto, ampm = m.groups()
    mes = MESES_ES.get(mes_abrev.lower()[:3], 1)
    hora = int(hora)
    minuto = int(minuto)
    if ampm.lower() == "pm" and hora != 12:
        hora += 12
    if ampm.lower() == "am" and hora == 12:
        hora = 0
    fecha_str = f"{int(dia):02d}/{mes:02d}/{anio}"
    hora_str = f"{hora:02d}:{minuto:02d}"
    return fecha_str, hora_str

def parsear_entreno_hevy(texto_crudo):
    lineas = [l.strip() for l in texto_crudo.split("\n") if l.strip() != ""]

    idx_fecha = None
    fecha_str = hora_str = None
    for i, linea in enumerate(lineas):
        resultado = parsear_fecha_hevy(linea)
        if resultado:
            fecha_str, hora_str = resultado
            idx_fecha = i
            break

    if fecha_str is None:
        return None, None, None, "No se encontro la linea de fecha"

    hevy_id = None
    for linea in lineas:
        m = re.search(r"hevy\.com/workout/([A-Za-z0-9]+)", linea)
        if m:
            hevy_id = m.group(1)
            break
    if hevy_id is None:
        hevy_id = f"{fecha_str.replace('/', '')}_{hora_str.replace(':', '')}"

    titulo_entreno = lineas[0] if idx_fecha > 0 else "Entreno"

    filas_raw = []
    ejercicio_actual = None
    volumen_total = 0.0
    num_series = 0

    for linea in lineas[idx_fecha + 1:]:
        if linea.startswith("@") or "hevy.com" in linea:
            continue

        m_serie = PATRON_SERIE.match(linea)
        if m_serie:
            if ejercicio_actual is None:
                continue
            serie_num, peso_str, reps_str, tag = m_serie.groups()
            peso = float(peso_str.replace(",", "."))
            reps = int(reps_str)
            es_calentamiento = "Sí" if (tag and "calent" in tag.lower()) else "No"
            rm_estimado = calcular_1rm(peso, reps)
            volumen_serie = round(peso * reps, 1)
            grupo = clasificar_musculo(ejercicio_actual)

            filas_raw.append([
                hevy_id, fecha_str, hora_str, titulo_entreno, ejercicio_actual,
                serie_num, peso, reps, rm_estimado, volumen_serie, grupo, es_calentamiento
            ])
            num_series += 1
            if es_calentamiento == "No":
                volumen_total += volumen_serie
        else:
            ejercicio_actual = linea

    if not filas_raw:
        return None, None, None, "No se reconocio ninguna serie en el texto"

    num_ejercicios = len(set(f[4] for f in filas_raw))
    resumen = [
        hevy_id, fecha_str, hora_str, titulo_entreno, "",
        round(volumen_total, 1), num_series, ""
    ]

    return hevy_id, resumen, filas_raw, None

def registrar_fallback_hevy(texto_crudo, motivo):
    try:
        sheet = conectar_sheets(WORKOUTS_SHEET_ID)
        hoja = sheet.worksheet("Fallback_Log")
        ahora = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")
        hoja.append_row([ahora, texto_crudo[:500], motivo])
    except Exception as e:
        print(f"Error registrando fallback: {e}")

def entreno_ya_existe(hevy_id):
    try:
        sheet = conectar_sheets(WORKOUTS_SHEET_ID)
        hoja = sheet.worksheet("Workouts_Summary")
        columna_ids = hoja.col_values(1)
        return hevy_id in columna_ids
    except Exception as e:
        print(f"Error comprobando duplicado: {e}")
        return False

def guardar_entreno_hevy(resumen, filas_raw):
    sheet = conectar_sheets(WORKOUTS_SHEET_ID)
    hoja_summary = sheet.worksheet("Workouts_Summary")
    hoja_raw = sheet.worksheet("Workouts_Raw")
    hoja_summary.append_row(resumen, value_input_option="USER_ENTERED")
    hoja_raw.append_rows(filas_raw, value_input_option="USER_ENTERED")

# ---------- Rutas ----------

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data:
            return "ok"

        if "message" in data and "text" in data["message"]:
            texto_recibido = data["message"]["text"].strip()

            if texto_recibido == "/progreso":
                respuesta = calcular_progreso()
                enviar_mensaje(respuesta)
            elif texto_recibido == "/hoy":
                texto_hoy, reply_markup = calcular_hoy()
                enviar_mensaje(texto_hoy, reply_markup=reply_markup)
            elif texto_recibido == "/racha":
                respuesta = calcular_rachas()
                enviar_mensaje(respuesta)
            elif texto_recibido == "/resumen":
                generar_resumen_semanal()
            elif texto_recibido == "/examenes on":
                cambiar_estado_examenes(True)
                enviar_mensaje("📚 *Modo exámenes activado.*\nSe han pausado los recordatorios de las 20:00 y las alertas para que te concentres en estudiar.")
            elif texto_recibido == "/examenes off":
                cambiar_estado_examenes(False)
                enviar_mensaje("🟢 *Modo exámenes desactivado.*\nLos recordatorios y alertas vuelven a estar activos.")

        elif "callback_query" in data:
            callback = data["callback_query"]
            callback_id = callback["id"]
            callback_data = callback["data"]
            message_id = callback["message"]["message_id"]

            if callback_data.startswith("marcar_"):
                habito_a_marcar = callback_data.replace("marcar_", "")
                marcar_habito_en_sheet(habito_a_marcar)
                responder_callback(callback_id, f"¡{habito_a_marcar} marcado como cumplido!")
                nuevo_texto, nuevo_reply_markup = calcular_hoy()
                editar_mensaje(message_id, nuevo_texto, reply_markup=nuevo_reply_markup)

        return "ok"
    except Exception as e:
        print(f"Error en webhook de Telegram: {e}")
        return "ok", 200

@app.route("/webhook/hevy", methods=["POST"])
def webhook_hevy():
    try:
        texto_crudo = request.get_data(as_text=True)
        if not texto_crudo or texto_crudo.strip() == "":
            return "sin contenido", 200

        hevy_id, resumen, filas_raw, error = parsear_entreno_hevy(texto_crudo)

        if error:
            registrar_fallback_hevy(texto_crudo, error)
            return "guardado en fallback", 200

        if entreno_ya_existe(hevy_id):
            return "duplicado, ignorado", 200

        guardar_entreno_hevy(resumen, filas_raw)
        marcar_habito_en_sheet("Gym")

        ejercicios_unicos = sorted(set(f[4] for f in filas_raw))
        volumen_total = resumen[5]
        num_series = resumen[6]

        mensaje = "🏋️‍♂️ *ENTRENO GUARDADO*\n"
        mensaje += f"📅 {resumen[1]} a las {resumen[2]}\n"
        mensaje += f"💪 {len(ejercicios_unicos)} ejercicios, {num_series} series\n"
        mensaje += f"📦 Volumen total: {volumen_total} kg\n\n"
        mensaje += "✅ Hábito 'Gym' marcado automáticamente."
        enviar_mensaje(mensaje)

        return "ok", 200
    except Exception as e:
        print(f"Error en webhook hevy: {e}")
        return "ok", 200

@app.route("/cron/recordatorio", methods=["GET", "POST"])
def cron_recordatorio():
    comprobar_recordatorio_2000()
    comprobar_alerta_inactividad()
    return "Recordatorios y alertas procesados"

@app.route("/cron/resumen-semanal", methods=["GET", "POST"])
def cron_resumen_semanal():
    generar_resumen_semanal()
    return "Resumen semanal procesado"

@app.route("/")
def home():
    return "Bot activo"
