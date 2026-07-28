import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta
import calendar as calmod
import html as htmlmod
import plotly.express as px
import streamlit.components.v1 as components

st.set_page_config(page_title="Dashboard Personal", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"
HABITS_SHEET_ID = "1LXbi7RVzaPgot8pXQt7GZN4GqYydZXpoIbdh91zRdyA"
CALENDAR_ID = "marcoscas1508@gmail.com"

HABITOS = [
    "Ejercicio hombros", "Gym", "Leer", "No porno",
    "No azúcar", "Movilidad", "Estudiar", "Oración",
]

# ---------- Estilo visual ----------
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    .stApp {
        background-color: #0a0c12;
        background-image:
            radial-gradient(circle at 15% 10%, rgba(37,99,235,0.10) 0%, transparent 40%),
            radial-gradient(circle at 85% 90%, rgba(139,92,246,0.08) 0%, transparent 40%),
            repeating-linear-gradient(0deg, rgba(255,255,255,0.012) 0px, rgba(255,255,255,0.012) 1px, transparent 1px, transparent 3px),
            repeating-linear-gradient(90deg, rgba(255,255,255,0.012) 0px, rgba(255,255,255,0.012) 1px, transparent 1px, transparent 3px);
        background-attachment: fixed;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12151f 0%, #0d0f16 100%);
        border-right: 1px solid #20242f;
    }
    [data-testid="stSidebar"] * {
        font-family: 'Inter', sans-serif;
    }

    .card {
        background: linear-gradient(155deg, rgba(30,35,48,0.9), rgba(18,21,29,0.9));
        border: 1px solid #262b3a;
        border-radius: 16px;
        padding: 20px 22px;
        margin-bottom: 14px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.03);
        transition: border-color 0.2s ease;
    }
    .card:hover {
        border-color: #2f3650;
    }

    .card-label {
        color: #8b93a7;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
    }
    .card-value {
        color: #ffffff;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }
    .card-sub {
        color: #4ade80;
        font-size: 13px;
        margin-top: 4px;
    }

    h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, #ffffff, #b8c1d9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    h2, h3 {
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: -0.3px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #161a24;
        border-radius: 10px;
        padding: 8px 18px;
        color: #8b93a7;
        border: 1px solid #232838;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
        color: white !important;
        border: none !important;
    }

    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #2563eb, #4f46e5);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        box-shadow: 0 2px 10px rgba(37,99,235,0.35);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(37,99,235,0.45);
        color: white;
    }

    [data-testid="stRadio"] label {
        font-size: 15px;
    }

    .stDataFrame, [data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #232838 !important;
    }

    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #0a0c12; }
    ::-webkit-scrollbar-thumb { background: #262b3a; border-radius: 5px; }
    ::-webkit-scrollbar-thumb:hover { background: #333a4d; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.error("Contraseña incorrecta")
        return False
    return True


if not check_password():
    st.stop()


def tarjeta(label, valor, sub=None):
    sub_html = f'<div class="card-sub">{sub}</div>' if sub else ""
    st.markdown(f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div class="card-value">{valor}</div>
            {sub_html}
        </div>
    """, unsafe_allow_html=True)


def parsear_numero_es(valor):
    """Convierte numeros con formato español (punto=miles, coma=decimal) a float."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def conectar_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_data(ttl=300)
def cargar_datos_entrenos():
    client = conectar_gspread()
    sheet = client.open_by_key(WORKOUTS_SHEET_ID)
    hoja_raw = sheet.worksheet("Workouts_Raw")
    hoja_summary = sheet.worksheet("Workouts_Summary")
    df_raw = pd.DataFrame(hoja_raw.get_all_records(numericise_ignore=["all"]))
    df_summary = pd.DataFrame(hoja_summary.get_all_records(numericise_ignore=["all"]))
    return df_raw, df_summary


@st.cache_data(ttl=300)
def cargar_datos_habitos():
    client = conectar_gspread()
    sheet = client.open_by_key(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Habitos")
    valores = hoja.get_all_values()

    fechas = valores[0][1:]
    filas_habitos = valores[1:1 + len(HABITOS)]

    registros = []
    for fila in filas_habitos:
        nombre = fila[0]
        for i, fecha in enumerate(fechas):
            col_idx = i + 1
            valor = fila[col_idx] if col_idx < len(fila) else ""
            if valor == "":
                continue
            registros.append({"Habito": nombre, "Fecha": fecha, "Cumplido": valor == "Sí"})

    return pd.DataFrame(registros)


def calcular_racha_actual(df_habito_ordenado):
    racha = 0
    for cumplido in reversed(df_habito_ordenado["Cumplido"].tolist()):
        if cumplido:
            racha += 1
        else:
            break
    return racha


def construir_html_mapa_consistencia(df_habitos, habitos_lista):
    fechas_unicas = sorted(df_habitos["Fecha_dt"].dropna().unique())
    ancho_celda = 24

    partes = ['<div style="overflow-x:auto; padding-bottom:8px;"><div style="display:inline-block; min-width:100%;">']

    partes.append('<div style="display:flex; margin-left:130px; gap:3px; margin-bottom:6px;">')
    for f in fechas_unicas:
        etiqueta = pd.Timestamp(f).strftime("%d/%m")
        partes.append(f'<div style="width:{ancho_celda}px; font-size:9px; color:#8b93a7; text-align:center; white-space:nowrap;">{etiqueta}</div>')
    partes.append("</div>")

    for habito in habitos_lista:
        partes.append('<div style="display:flex; align-items:center; gap:3px; margin-bottom:4px;">')
        partes.append(f'<div style="width:126px; font-size:12px; color:#e5e7eb; flex-shrink:0; padding-right:6px;">{habito}</div>')
        for f in fechas_unicas:
            fila = df_habitos[(df_habitos["Habito"] == habito) & (df_habitos["Fecha_dt"] == f)]
            if len(fila) == 0:
                color = "#1a1f2b"
            elif bool(fila["Cumplido"].iloc[0]):
                color = "#10b981"
            else:
                color = "#ef4444"
            fecha_str = pd.Timestamp(f).strftime("%d/%m/%Y")
            titulo = f"{habito} - {fecha_str}"
            partes.append(f'<div title="{titulo}" style="width:{ancho_celda}px; height:20px; background:{color}; border-radius:5px; flex-shrink:0;"></div>')
        partes.append("</div>")

    partes.append("</div></div>")
    return "".join(partes)


PLOTLY_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="#c9cfdd",
    font_family="Inter, sans-serif",
)
PALETA = ["#2563eb", "#7c3aed", "#06b6d4", "#f59e0b", "#ec4899", "#10b981", "#ef4444", "#8b5cf6"]


def estilizar(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_xaxes(gridcolor="#1f2430", zerolinecolor="#1f2430")
    fig.update_yaxes(gridcolor="#1f2430", zerolinecolor="#1f2430")
    return fig



def conectar_calendar():
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build("calendar", "v3", credentials=creds)


@st.cache_data(ttl=120)
def cargar_eventos_mes(anio, mes):
    service = conectar_calendar()
    primer_dia = datetime(anio, mes, 1, tzinfo=timezone.utc)
    if mes == 12:
        siguiente_mes = datetime(anio + 1, 1, 1, tzinfo=timezone.utc)
    else:
        siguiente_mes = datetime(anio, mes + 1, 1, tzinfo=timezone.utc)
    resultado = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=primer_dia.isoformat(),
        timeMax=siguiente_mes.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute()
    return resultado.get("items", [])


def agrupar_eventos_por_dia(eventos):
    agrupado = {}
    for ev in eventos:
        inicio_raw = ev["start"].get("dateTime", ev["start"].get("date"))
        titulo = ev.get("summary", "(Sin título)")
        if "T" in inicio_raw:
            dt = datetime.fromisoformat(inicio_raw)
            dia, hora = dt.day, dt.strftime("%H:%M")
        else:
            dt = datetime.strptime(inicio_raw, "%Y-%m-%d")
            dia, hora = dt.day, ""
        agrupado.setdefault(dia, []).append((hora, titulo))
    return agrupado


def construir_html_calendario(anio, mes, eventos_por_dia):
    matriz = calmod.monthcalendar(anio, mes)
    dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    hoy = datetime.now().date()

    partes = ['<div style="display:grid; grid-template-columns: repeat(7, 1fr); gap: 6px;">']
    for d in dias_semana:
        partes.append(f'<div style="text-align:center; color:#8b93a7; font-size:12px; font-weight:600; padding-bottom:4px;">{d}</div>')

    for semana in matriz:
        for dia in semana:
            if dia == 0:
                partes.append('<div style="min-height:90px;"></div>')
                continue
            es_hoy = (anio == hoy.year and mes == hoy.month and dia == hoy.day)
            borde = "1.5px solid #2563eb" if es_hoy else "1px solid #232838"
            sombra = "box-shadow: 0 0 0 3px rgba(37,99,235,0.15);" if es_hoy else ""
            eventos_dia = eventos_por_dia.get(dia, [])
            eventos_html = ""
            for hora, titulo in eventos_dia[:3]:
                titulo_esc = htmlmod.escape(titulo)[:22]
                prefijo = f"{hora} " if hora else ""
                eventos_html += f'<div style="background:linear-gradient(135deg, rgba(37,99,235,0.25), rgba(124,58,237,0.25)); color:#c7d2fe; font-size:10px; padding:2px 4px; border-radius:4px; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{prefijo}{titulo_esc}</div>'
            if len(eventos_dia) > 3:
                eventos_html += f'<div style="color:#8b93a7; font-size:10px; margin-top:2px;">+{len(eventos_dia)-3} más</div>'

            celda = (
                f'<div style="min-height:90px; background:linear-gradient(155deg, rgba(30,35,48,0.7), rgba(18,21,29,0.7)); border:{borde}; border-radius:10px; padding:6px; {sombra}">'
                f'<div style="color:#e5e7eb; font-size:13px; font-weight:600;">{dia}</div>'
                f'{eventos_html}'
                f'</div>'
            )
            partes.append(celda)

    partes.append("</div>")
    return "".join(partes)


def crear_evento_calendar(titulo, fecha_inicio, hora_inicio, fecha_fin, hora_fin, descripcion=""):
    service = conectar_calendar()
    evento = {
        "summary": titulo,
        "description": descripcion,
        "start": {"dateTime": f"{fecha_inicio}T{hora_inicio}:00", "timeZone": "Europe/Madrid"},
        "end": {"dateTime": f"{fecha_fin}T{hora_fin}:00", "timeZone": "Europe/Madrid"},
    }
    service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()


def formatear_evento(evento):
    inicio_raw = evento["start"].get("dateTime", evento["start"].get("date"))
    titulo = evento.get("summary", "(Sin título)")
    if "T" in inicio_raw:
        dt = datetime.fromisoformat(inicio_raw)
        return titulo, dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M")
    else:
        dt = datetime.strptime(inicio_raw, "%Y-%m-%d")
        return titulo, dt.strftime("%d/%m/%Y"), "Todo el día"



@st.cache_data(ttl=300)
def cargar_citas():
    client = conectar_gspread()
    sheet = client.open_by_key(HABITS_SHEET_ID)
    hoja = sheet.worksheet("Citas")
    valores = hoja.get_all_values()
    citas = []
    for fila in valores[1:]:
        if len(fila) >= 2 and fila[1].strip():
            citas.append((fila[1].strip(), fila[0].strip()))
    return citas


def construir_widget_citas(citas):
    if not citas:
        return "<p style='color:#8b93a7; font-family:Inter,sans-serif;'>Todavía no hay citas guardadas. Manda una con /cita en Telegram.</p>"
    citas_js = json.dumps([{"frase": f, "fecha": d} for f, d in citas], ensure_ascii=False)
    html = f"""
    <div style="font-family:'Inter',sans-serif; background:linear-gradient(155deg, rgba(30,35,48,0.9), rgba(18,21,29,0.9)); border:1px solid #262b3a; border-radius:16px; padding:26px; text-align:center; min-height:110px; display:flex; flex-direction:column; justify-content:center;">
        <div id="cita-texto" style="color:#e5e7eb; font-size:17px; font-style:italic; line-height:1.5; transition:opacity 0.4s ease;">Cargando...</div>
        <div id="cita-fecha" style="color:#8b93a7; font-size:12px; margin-top:12px;"></div>
    </div>
    <script>
        const citas = {citas_js};
        let idx = 0;
        function mostrarCita() {{
            const caja = document.getElementById('cita-texto');
            caja.style.opacity = 0;
            setTimeout(() => {{
                caja.innerText = '\u201c' + citas[idx].frase + '\u201d';
                document.getElementById('cita-fecha').innerText = citas[idx].fecha;
                caja.style.opacity = 1;
                idx = (idx + 1) % citas.length;
            }}, 400);
        }}
        mostrarCita();
        setInterval(mostrarCita, 10000);
    </script>
    """
    return html


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 📊 Dashboard")
    st.caption("Marcos Castro")
    st.divider()
    seccion = st.radio(
        "Navegación",
        ["🏠 Inicio", "🏋️ Entrenos", "✅ Hábitos", "📅 Calendario"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ INICIO ============
if seccion == "🏠 Inicio":
    ahora = datetime.now()
    dias_es = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    meses_es = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_bonita = f"{dias_es[ahora.weekday()].capitalize()}, {ahora.day} de {meses_es[ahora.month-1]} de {ahora.year}"

    st.title(f"¡Buenas, Marcos! 👋")
    st.caption(fecha_bonita)

    df_habitos_home = cargar_datos_habitos()
    df_raw_home, df_summary_home = cargar_datos_entrenos()

    col_izq, col_centro, col_der = st.columns([1.1, 1.4, 1])

    # ---- Columna izquierda: Habitos diarios ----
    with col_izq:
        hoy_str = ahora.strftime("%d/%m/%Y")
        if not df_habitos_home.empty:
            df_hoy_habitos = df_habitos_home[df_habitos_home["Fecha"] == hoy_str]
            completados = int(df_hoy_habitos["Cumplido"].sum())
            total = len(HABITOS)
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <div class="card-label" style="margin-bottom:0;">HÁBITOS DIARIOS</div>
                        <div style="color:#8b93a7; font-size:13px;">{completados}/{total}</div>
                    </div>
            """, unsafe_allow_html=True)
            for habito in HABITOS:
                fila = df_hoy_habitos[df_hoy_habitos["Habito"] == habito]
                cumplido = bool(fila["Cumplido"].iloc[0]) if len(fila) > 0 else False
                icono = "✅" if cumplido else "⚪"
                st.markdown(f'<div style="padding:6px 0; border-bottom:1px solid #262b36; color:#e5e7eb; font-size:14px;">{icono} {habito}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Sin datos de hábitos todavía.")

    # ---- Columna centro: Entreno de hoy + PRs + Resumen semanal ----
    with col_centro:
        st.markdown('<div class="card-label">ENTRENAMIENTO DE HOY 💪</div>', unsafe_allow_html=True)
        if not df_raw_home.empty:
            df_raw_home["Fecha"] = pd.to_datetime(df_raw_home["Fecha"], format="%d/%m/%Y", errors="coerce")
            df_raw_home["Peso (kg)"] = df_raw_home["Peso (kg)"].apply(parsear_numero_es)
            df_raw_home["Reps"] = df_raw_home["Reps"].apply(parsear_numero_es)
            hoy_ts = pd.Timestamp(ahora.date())
            df_hoy_entreno = df_raw_home[df_raw_home["Fecha"] == hoy_ts]

            if df_hoy_entreno.empty:
                st.markdown('<div class="card">Todavía no has subido ningún entreno hoy.</div>', unsafe_allow_html=True)
            else:
                resumen_hoy = df_hoy_entreno.groupby("Ejercicio").agg(
                    Series=("Peso (kg)", "count"),
                    Peso_max=("Peso (kg)", "max"),
                ).reset_index()
                filas_html = ""
                for _, r in resumen_hoy.iterrows():
                    filas_html += f'<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #262b36; font-size:14px; color:#e5e7eb;"><span>{r["Ejercicio"]}</span><span style="color:#8b93a7;">{int(r["Series"])} series · {r["Peso_max"]:.0f} kg</span></div>'
                st.markdown(f'<div class="card">{filas_html}</div>', unsafe_allow_html=True)

            st.markdown('<div class="card-label" style="margin-top:14px;">🏆 PRs PERSONALES (peso máximo histórico)</div>', unsafe_allow_html=True)
            prs = df_raw_home.groupby("Ejercicio")["Peso (kg)"].max().reset_index().sort_values("Peso (kg)", ascending=False).head(4)
            cols_pr = st.columns(len(prs)) if len(prs) > 0 else []
            for i, (_, r) in enumerate(prs.iterrows()):
                with cols_pr[i]:
                    tarjeta(r["Ejercicio"][:16], f'{r["Peso (kg)"]:.0f} kg')
        else:
            st.info("Todavía no hay entrenos guardados.")

        st.markdown('<div class="card-label" style="margin-top:14px;">📅 RESUMEN SEMANAL</div>', unsafe_allow_html=True)
        if not df_habitos_home.empty:
            inicio_semana = ahora - timedelta(days=ahora.weekday())
            dias_cortos = ["LUN","MAR","MIÉ","JUE","VIE","SÁB","DOM"]
            cols_semana = st.columns(7)
            for i in range(7):
                fecha_dia = inicio_semana + timedelta(days=i)
                fecha_str_dia = fecha_dia.strftime("%d/%m/%Y")
                df_dia = df_habitos_home[df_habitos_home["Fecha"] == fecha_str_dia]
                todos_cumplidos = len(df_dia) > 0 and bool(df_dia["Cumplido"].all())
                hay_datos = len(df_dia) > 0
                if todos_cumplidos:
                    icono = "✅"
                elif hay_datos:
                    icono = "⚪"
                else:
                    icono = "·"
                with cols_semana[i]:
                    st.markdown(f'<div style="text-align:center;"><div style="color:#8b93a7; font-size:11px;">{dias_cortos[i]}</div><div style="font-size:20px;">{icono}</div></div>', unsafe_allow_html=True)

    # ---- Columna derecha: Progreso fisico (placeholder) + Estadisticas ----
    with col_der:
        st.markdown("""
            <div class="card" style="text-align:center; padding:30px 15px;">
                <div style="font-size:28px; margin-bottom:6px;">⚖️</div>
                <div class="card-value" style="font-size:16px;">PROGRESO FÍSICO</div>
                <div class="card-label" style="margin-top:10px;">Próximamente</div>
                <div style="color:#8b93a7; font-size:12px; margin-top:4px;">Se conectará cuando enlacemos tu báscula.</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="card-label" style="margin-top:14px;">📊 ESTADÍSTICAS</div>', unsafe_allow_html=True)
        if not df_habitos_home.empty:
            mejor_racha = 0
            for h in HABITOS:
                df_h = df_habitos_home[df_habitos_home["Habito"] == h].sort_values("Fecha_dt") if "Fecha_dt" in df_habitos_home.columns else df_habitos_home[df_habitos_home["Habito"] == h]
                mejor_racha = max(mejor_racha, calcular_racha_actual(df_h))
        else:
            mejor_racha = 0

        entrenos_este_mes = 0
        if not df_summary_home.empty:
            df_summary_home["Fecha"] = pd.to_datetime(df_summary_home["Fecha"], format="%d/%m/%Y", errors="coerce")
            entrenos_este_mes = int((df_summary_home["Fecha"].dt.month == ahora.month).sum())

        tarjeta("🔥 Racha actual", f"{mejor_racha} días")
        tarjeta("🏋️ Entrenos este mes", entrenos_este_mes)

    st.divider()

    # ---- Citas / frases guardadas ----
    st.markdown('<div class="card-label">📖 CITA DEL MOMENTO</div>', unsafe_allow_html=True)
    citas = cargar_citas()
    components.html(construir_widget_citas(citas), height=170)

    st.divider()

    # ---- Notas rapidas (placeholder, aun sin persistencia) ----
    st.markdown('<div class="card-label">📝 NOTAS RÁPIDAS</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="card">
            <div style="color:#8b93a7; font-size:13px; margin-bottom:10px;">
                🚧 Esta sección todavía no guarda datos — hay que conectarla a Google Sheets o Notion. De momento es solo el diseño.
            </div>
            <div style="display:flex; gap:24px; flex-wrap:wrap;">
                <div style="flex:1; min-width:200px;">
                    <div style="color:#e5e7eb; font-weight:600; margin-bottom:6px;">¿Qué salió bien hoy?</div>
                    <div style="color:#8b93a7; font-size:13px;">— (pendiente de conectar)</div>
                </div>
                <div style="flex:1; min-width:200px;">
                    <div style="color:#e5e7eb; font-weight:600; margin-bottom:6px;">¿Qué puedo mejorar?</div>
                    <div style="color:#8b93a7; font-size:13px;">— (pendiente de conectar)</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# ============ ENTRENOS ============
elif seccion == "🏋️ Entrenos":
    st.title("🏋️ Entrenamientos")

    df_raw, df_summary = cargar_datos_entrenos()

    if df_raw.empty:
        st.info("Todavía no hay entrenos guardados.")
    else:
        df_raw["Fecha"] = pd.to_datetime(df_raw["Fecha"], format="%d/%m/%Y", errors="coerce")
        df_raw["Peso (kg)"] = df_raw["Peso (kg)"].apply(parsear_numero_es)
        df_raw["Reps"] = df_raw["Reps"].apply(parsear_numero_es)
        df_raw["1RM Estimado"] = df_raw["1RM Estimado"].apply(parsear_numero_es)
        df_raw["Volumen Serie"] = df_raw["Volumen Serie"].apply(parsear_numero_es)

        df_summary["Fecha"] = pd.to_datetime(df_summary["Fecha"], format="%d/%m/%Y", errors="coerce")
        df_summary["Volumen Total (kg)"] = df_summary["Volumen Total (kg)"].apply(parsear_numero_es)

        c1, c2, c3 = st.columns(3)
        with c1:
            tarjeta("Entrenos totales", len(df_summary))
        with c2:
            tarjeta("Volumen acumulado", f"{df_summary['Volumen Total (kg)'].sum():,.0f} kg")
        with c3:
            tarjeta("Ejercicios distintos", df_raw["Ejercicio"].nunique())

        st.subheader("📈 Evolución de 1RM por ejercicio")
        ejercicios = sorted(df_raw["Ejercicio"].dropna().unique())
        ejercicio_sel = st.selectbox("Elige un ejercicio", ejercicios)
        df_ejercicio = df_raw[df_raw["Ejercicio"] == ejercicio_sel]
        df_max_dia = df_ejercicio.groupby("Fecha")["1RM Estimado"].max().reset_index()
        fig_1rm = px.line(df_max_dia, x="Fecha", y="1RM Estimado", markers=True,
                           title=f"1RM estimado — {ejercicio_sel}", color_discrete_sequence=[PALETA[0]])
        st.plotly_chart(estilizar(fig_1rm), use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("💪 Volumen por grupo muscular")
            df_sin_calentamiento = df_raw[df_raw["Calentamiento"] != "Sí"]
            vol_grupo = df_sin_calentamiento.groupby("Grupo_Muscular")["Volumen Serie"].sum().reset_index()
            fig_grupo = px.pie(vol_grupo, names="Grupo_Muscular", values="Volumen Serie", hole=0.55, color_discrete_sequence=PALETA)
            st.plotly_chart(estilizar(fig_grupo), use_container_width=True)

        with col_b:
            st.subheader("📊 Volumen por sesión")
            fig_vol = px.bar(df_summary.sort_values("Fecha"), x="Fecha", y="Volumen Total (kg)", color_discrete_sequence=[PALETA[0]])
            st.plotly_chart(estilizar(fig_vol), use_container_width=True)

        with st.expander("Ver tabla completa de entrenos"):
            st.dataframe(df_summary.sort_values("Fecha", ascending=False), use_container_width=True)

# ============ HABITOS ============
elif seccion == "✅ Hábitos":
    st.title("✅ Hábitos")

    df_habitos = cargar_datos_habitos()

    if df_habitos.empty:
        st.info("Todavía no hay datos de hábitos.")
    else:
        df_habitos["Fecha_dt"] = pd.to_datetime(df_habitos["Fecha"], format="%d/%m/%Y", errors="coerce")
        df_habitos = df_habitos.sort_values("Fecha_dt")

        st.subheader("🔥 Rachas activas")
        cols_racha = st.columns(4)
        for i, habito in enumerate(HABITOS):
            df_h = df_habitos[df_habitos["Habito"] == habito]
            racha = calcular_racha_actual(df_h)
            with cols_racha[i % 4]:
                tarjeta(habito, f"{racha} días", "🔥 activo" if racha > 0 else None)

        st.subheader("📊 % de cumplimiento histórico")
        resumen = df_habitos.groupby("Habito")["Cumplido"].mean().reset_index()
        resumen["Porcentaje"] = (resumen["Cumplido"] * 100).round(1)
        resumen = resumen.sort_values("Porcentaje", ascending=False)
        fig_pct = px.bar(resumen, x="Habito", y="Porcentaje", text="Porcentaje",
                          color="Porcentaje", color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#10b981"]])
        fig_pct.update_traces(texttemplate='%{text}%', textposition='outside')
        fig_pct.update_layout(coloraxis_showscale=False)
        st.plotly_chart(estilizar(fig_pct), use_container_width=True)

        st.subheader("🗓️ Mapa de consistencia")
        html_mapa = construir_html_mapa_consistencia(df_habitos, HABITOS)
        st.markdown(html_mapa, unsafe_allow_html=True)

        with st.expander("Ver tabla completa de hábitos"):
            tabla = df_habitos.pivot_table(index="Fecha_dt", columns="Habito", values="Cumplido", aggfunc="first")
            tabla = tabla.sort_index(ascending=False)
            st.dataframe(tabla, use_container_width=True)

# ============ CALENDARIO ============
else:
    st.title("📅 Calendario")

    if "cal_anio" not in st.session_state:
        hoy = datetime.now()
        st.session_state["cal_anio"] = hoy.year
        st.session_state["cal_mes"] = hoy.month

    col_prev, col_titulo, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀", use_container_width=True):
            if st.session_state["cal_mes"] == 1:
                st.session_state["cal_mes"] = 12
                st.session_state["cal_anio"] -= 1
            else:
                st.session_state["cal_mes"] -= 1
            st.rerun()
    with col_titulo:
        nombre_mes = calmod.month_name[st.session_state["cal_mes"]].capitalize()
        st.markdown(f"<h3 style='text-align:center;'>{nombre_mes} {st.session_state['cal_anio']}</h3>", unsafe_allow_html=True)
    with col_next:
        if st.button("▶", use_container_width=True):
            if st.session_state["cal_mes"] == 12:
                st.session_state["cal_mes"] = 1
                st.session_state["cal_anio"] += 1
            else:
                st.session_state["cal_mes"] += 1
            st.rerun()

    try:
        eventos_mes = cargar_eventos_mes(st.session_state["cal_anio"], st.session_state["cal_mes"])
        eventos_por_dia = agrupar_eventos_por_dia(eventos_mes)
        html_cal = construir_html_calendario(st.session_state["cal_anio"], st.session_state["cal_mes"], eventos_por_dia)
        st.markdown(html_cal, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"No se pudo conectar con Google Calendar: {e}")

    st.divider()

    with st.expander("➕ Crear evento"):
        with st.form("form_nuevo_evento", clear_on_submit=True):
            titulo_nuevo = st.text_input("Título")
            fecha_inicio = st.date_input("Fecha")
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                hora_inicio = st.time_input("Hora inicio")
            with col_h2:
                hora_fin = st.time_input("Hora fin")
            descripcion = st.text_area("Descripción (opcional)", height=80)
            enviado = st.form_submit_button("Crear evento", use_container_width=True)

            if enviado:
                if not titulo_nuevo.strip():
                    st.warning("Ponle un título al evento.")
                else:
                    try:
                        crear_evento_calendar(
                            titulo_nuevo,
                            fecha_inicio.strftime("%Y-%m-%d"),
                            hora_inicio.strftime("%H:%M"),
                            fecha_inicio.strftime("%Y-%m-%d"),
                            hora_fin.strftime("%H:%M"),
                            descripcion,
                        )
                        st.cache_data.clear()
                        st.success("Evento creado ✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo crear el evento: {e}")
