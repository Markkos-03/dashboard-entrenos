import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

st.set_page_config(page_title="Dashboard Personal", page_icon="📊", layout="wide")

WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"
HABITS_SHEET_ID = "1LXbi7RVzaPgot8pXQt7GZN4GqYydZXpoIbdh91zRdyA"

HABITOS = [
    "Ejercicio hombros", "Gym", "Leer", "No porno",
    "No azucar", "Movilidad", "Estudiar", "Oracion",
]


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

    df_habitos = pd.DataFrame(registros)
    return df_habitos


def calcular_racha_actual(df_habito_ordenado):
    racha = 0
    for cumplido in reversed(df_habito_ordenado["Cumplido"].tolist()):
        if cumplido:
            racha += 1
        else:
            break
    return racha


st.title("📊 Dashboard Personal")

tab_entrenos, tab_habitos = st.tabs(["🏋️ Entrenos", "✅ Hábitos"])

# ============ TAB ENTRENOS ============
with tab_entrenos:
    col_titulo, col_boton = st.columns([4, 1])
    with col_boton:
        if st.button("🔄 Actualizar", key="refresh_entrenos"):
            st.cache_data.clear()
            st.rerun()

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

        m1, m2, m3 = st.columns(3)
        m1.metric("Entrenos totales", len(df_summary))
        m2.metric("Volumen total acumulado (kg)", f"{df_summary['Volumen Total (kg)'].sum():,.0f}")
        m3.metric("Ejercicios distintos", df_raw["Ejercicio"].nunique())

        st.divider()

        st.subheader("📈 Evolución de 1RM por ejercicio")
        ejercicios = sorted(df_raw["Ejercicio"].dropna().unique())
        ejercicio_sel = st.selectbox("Elige un ejercicio", ejercicios)
        df_ejercicio = df_raw[df_raw["Ejercicio"] == ejercicio_sel]
        df_max_dia = df_ejercicio.groupby("Fecha")["1RM Estimado"].max().reset_index()
        fig_1rm = px.line(df_max_dia, x="Fecha", y="1RM Estimado", markers=True,
                           title=f"1RM estimado — {ejercicio_sel}")
        st.plotly_chart(fig_1rm, use_container_width=True)

        st.subheader("💪 Volumen por grupo muscular")
        df_sin_calentamiento = df_raw[df_raw["Calentamiento"] != "Sí"]
        vol_grupo = df_sin_calentamiento.groupby("Grupo_Muscular")["Volumen Serie"].sum().reset_index()
        fig_grupo = px.pie(vol_grupo, names="Grupo_Muscular", values="Volumen Serie",
                            title="Distribución de volumen por grupo muscular")
        st.plotly_chart(fig_grupo, use_container_width=True)

        st.subheader("📊 Volumen total por sesión")
        fig_vol = px.bar(df_summary.sort_values("Fecha"), x="Fecha", y="Volumen Total (kg)",
                          title="Volumen total por entreno")
        st.plotly_chart(fig_vol, use_container_width=True)

        with st.expander("Ver tabla completa de entrenos"):
            st.dataframe(df_summary.sort_values("Fecha", ascending=False), use_container_width=True)

# ============ TAB HABITOS ============
with tab_habitos:
    col_titulo2, col_boton2 = st.columns([4, 1])
    with col_boton2:
        if st.button("🔄 Actualizar", key="refresh_habitos"):
            st.cache_data.clear()
            st.rerun()

    df_habitos = cargar_datos_habitos()

    if df_habitos.empty:
        st.info("Todavía no hay datos de hábitos.")
    else:
        df_habitos["Fecha_dt"] = pd.to_datetime(df_habitos["Fecha"], format="%d/%m/%Y", errors="coerce")
        df_habitos = df_habitos.sort_values("Fecha_dt")

        st.subheader("🔥 Racha actual por hábito")
        cols_racha = st.columns(4)
        for i, habito in enumerate(HABITOS):
            df_h = df_habitos[df_habitos["Habito"] == habito]
            racha = calcular_racha_actual(df_h)
            with cols_racha[i % 4]:
                st.metric(habito, f"{racha} días 🔥")

        st.divider()

        st.subheader("📊 % de cumplimiento total por hábito")
        resumen = df_habitos.groupby("Habito")["Cumplido"].mean().reset_index()
        resumen["Porcentaje"] = (resumen["Cumplido"] * 100).round(1)
        resumen = resumen.sort_values("Porcentaje", ascending=False)
        fig_pct = px.bar(resumen, x="Habito", y="Porcentaje",
                          title="Porcentaje de cumplimiento por hábito (histórico)",
                          text="Porcentaje")
        fig_pct.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig_pct, use_container_width=True)

        st.subheader("🗓️ Mapa de consistencia")
        df_pivot = df_habitos.pivot_table(index="Habito", columns="Fecha_dt", values="Cumplido", aggfunc="first")
        df_pivot = df_pivot.reindex(HABITOS)
        fig_heatmap = px.imshow(
            df_pivot.astype(float),
            labels=dict(x="Fecha", y="Hábito", color="Cumplido"),
            color_continuous_scale=["#f4433622", "#4caf5099"],
            aspect="auto",
        )
        fig_heatmap.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        with st.expander("Ver tabla completa de hábitos"):
            tabla = df_habitos.pivot_table(index="Fecha_dt", columns="Habito", values="Cumplido", aggfunc="first")
            tabla = tabla.sort_index(ascending=False)
            st.dataframe(tabla, use_container_width=True)
