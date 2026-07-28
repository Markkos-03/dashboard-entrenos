import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

st.set_page_config(page_title="Dashboard Entrenos", page_icon="🏋️", layout="wide")

WORKOUTS_SHEET_ID = "1AFwTKUF89S3sNhcjc1KZ5l6NqjSb1Z3VL11FwLz-mTo"


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


@st.cache_data(ttl=300)
def cargar_datos():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(WORKOUTS_SHEET_ID)

    hoja_raw = sheet.worksheet("Workouts_Raw")
    hoja_summary = sheet.worksheet("Workouts_Summary")

    df_raw = pd.DataFrame(hoja_raw.get_all_records())
    df_summary = pd.DataFrame(hoja_summary.get_all_records())
    return df_raw, df_summary


st.title("🏋️ Dashboard de Entrenamientos")

col_titulo, col_boton = st.columns([4, 1])
with col_boton:
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

df_raw, df_summary = cargar_datos()

if df_raw.empty:
    st.info("Todavía no hay entrenos guardados. Sube uno desde el Atajo y vuelve a entrar aquí.")
    st.stop()

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

st.subheader("🗓️ Consistencia de entrenos")
conteo = df_summary.groupby(df_summary["Fecha"].dt.date).size().reset_index(name="Entrenos")
conteo.columns = ["Fecha", "Entrenos"]
fig_heatmap = px.bar(conteo, x="Fecha", y="Entrenos", title="Entrenos por día")
st.plotly_chart(fig_heatmap, use_container_width=True)

with st.expander("Ver tabla completa de entrenos"):
    st.dataframe(df_summary.sort_values("Fecha", ascending=False), use_container_width=True)
