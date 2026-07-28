import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

st.set_page_config(page_title="Dashboard Personal", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"
HABITS_SHEET_ID = "1LXbi7RVzaPgot8pXQt7GZN4GqYydZXpoIbdh91zRdyA"

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
    df_raw = pd.DataFrame(hoja_raw.get_all_records())
    df_summary = pd.DataFrame(hoja_summary.get_all_records())
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
        df_raw["Peso (kg)"] = pd.to_numeric(df_raw["Peso (kg)"], errors="coerce")
        df_raw["Reps"] = pd.to_numeric(df_raw["Reps"], errors="coerce")
        df_raw["1RM Estimado"] = pd.to_numeric(df_raw["1RM Estimado"], errors="coerce")
        df_raw["Volumen Serie"] = pd.to_numeric(df_raw["Volumen Serie"], errors="coerce")

        df_summary["Fecha"] = pd.to_datetime(df_summary["Fecha"], format="%d/%m/%Y", errors="coerce")
        df_summary["Volumen Total (kg)"] = pd.to_numeric(df_summary["Volumen Total (kg)"], errors="coerce")

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

# ============ CALENDARIO (placeholder) ============
else:
    st.title("📅 Calendario")
    st.markdown("""
        <div class="card" style="text-align:center; padding: 60px 20px;">
            <div style="font-size: 40px; margin-bottom: 10px;">🚧</div>
            <div class="card-value" style="font-size: 20px;">Próximamente</div>
            <div class="card-label" style="margin-top: 8px;">
                Esta sección mostrará tu Google Calendar en cuanto conectemos esa integración.
            </div>
        </div>
    """, unsafe_allow_html=True)
