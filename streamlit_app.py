import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone
import plotly.express as px

st.set_page_config(page_title="Dashboard Personal", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"
HABITS_SHEET_ID = "1LXbi7RVzaPgot8pXQt7GZN4GqYydZXpoIbdh91zRdyA"
CALENDAR_ID = "marcoscas1508@gmail.com"

HABITOS = [
    "Ejercicio hombros", "Gym", "Leer", "No porno",
    "No azucar", "Movilidad", "Estudiar", "Oracion",
]

# ---------- Estilo visual ----------
CSS = """
<style>
    .stApp {
        background-color: #0e1117;
    }
    [data-testid="stSidebar"] {
        background-color: #161a23;
        border-right: 1px solid #262b36;
    }
    .card {
        background: linear-gradient(145deg, #1a1f2b, #151920);
        border: 1px solid #262b36;
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }
    .card-label {
        color: #8b93a7;
        font-size: 13px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .card-value {
        color: #ffffff;
        font-size: 28px;
        font-weight: 700;
    }
    .card-sub {
        color: #4caf50;
        font-size: 13px;
        margin-top: 4px;
    }
    h1, h2, h3 {
        color: #ffffff !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1f2b;
        border-radius: 8px;
        padding: 8px 18px;
        color: #8b93a7;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
    }
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


PLOTLY_LAYOUT = dict(
    plot_bgcolor="#0e1117",
    paper_bgcolor="#0e1117",
    font_color="#e5e7eb",
)


def estilizar(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig



def conectar_calendar():
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build("calendar", "v3", credentials=creds)


@st.cache_data(ttl=120)
def cargar_proximos_eventos():
    service = conectar_calendar()
    ahora = datetime.now(timezone.utc).isoformat()
    resultado = service.events().list(
        calendarId=CALENDAR_ID, timeMin=ahora, maxResults=15,
        singleEvents=True, orderBy="startTime"
    ).execute()
    return resultado.get("items", [])


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


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 📊 Dashboard")
    st.caption("Marcos Castro")
    st.divider()
    seccion = st.radio(
        "Navegación",
        ["🏋️ Entrenos", "✅ Hábitos", "📅 Calendario"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============ ENTRENOS ============
if seccion == "🏋️ Entrenos":
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
                           title=f"1RM estimado — {ejercicio_sel}")
        st.plotly_chart(estilizar(fig_1rm), use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("💪 Volumen por grupo muscular")
            df_sin_calentamiento = df_raw[df_raw["Calentamiento"] != "Sí"]
            vol_grupo = df_sin_calentamiento.groupby("Grupo_Muscular")["Volumen Serie"].sum().reset_index()
            fig_grupo = px.pie(vol_grupo, names="Grupo_Muscular", values="Volumen Serie", hole=0.5)
            st.plotly_chart(estilizar(fig_grupo), use_container_width=True)

        with col_b:
            st.subheader("📊 Volumen por sesión")
            fig_vol = px.bar(df_summary.sort_values("Fecha"), x="Fecha", y="Volumen Total (kg)")
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
                          color="Porcentaje", color_continuous_scale=[[0, "#e57373"], [1, "#66bb6a"]])
        fig_pct.update_traces(texttemplate='%{text}%', textposition='outside')
        fig_pct.update_layout(coloraxis_showscale=False)
        st.plotly_chart(estilizar(fig_pct), use_container_width=True)

        st.subheader("🗓️ Mapa de consistencia")
        df_pivot = df_habitos.pivot_table(index="Habito", columns="Fecha_dt", values="Cumplido", aggfunc="first")
        df_pivot = df_pivot.reindex(HABITOS)
        fig_heatmap = px.imshow(
            df_pivot.astype(float),
            labels=dict(x="Fecha", y="Hábito", color="Cumplido"),
            color_continuous_scale=[[0, "#e57373"], [1, "#66bb6a"]],
            aspect="auto",
        )
        fig_heatmap.update_layout(coloraxis_showscale=False)
        st.plotly_chart(estilizar(fig_heatmap), use_container_width=True)

        with st.expander("Ver tabla completa de hábitos"):
            tabla = df_habitos.pivot_table(index="Fecha_dt", columns="Habito", values="Cumplido", aggfunc="first")
            tabla = tabla.sort_index(ascending=False)
            st.dataframe(tabla, use_container_width=True)

# ============ CALENDARIO ============
else:
    st.title("📅 Calendario")

    col_izq, col_der = st.columns([3, 2])

    with col_izq:
        st.subheader("Próximos eventos")
        try:
            eventos = cargar_proximos_eventos()
        except Exception as e:
            eventos = []
            st.error(f"No se pudo conectar con Google Calendar: {e}")

        if not eventos:
            st.info("No tienes eventos próximos, o el calendario está vacío.")
        else:
            for evento in eventos:
                titulo, fecha_str, hora_str = formatear_evento(evento)
                st.markdown(f"""
                    <div class="card">
                        <div class="card-label">{fecha_str} — {hora_str}</div>
                        <div class="card-value" style="font-size: 18px;">{titulo}</div>
                    </div>
                """, unsafe_allow_html=True)

    with col_der:
        st.subheader("➕ Crear evento")
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
