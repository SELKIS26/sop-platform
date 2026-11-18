import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import base64
import json
import urllib.request
import io
import warnings

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    import streamlit_authenticator as stauth
except ImportError:
    stauth = None

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

warnings.filterwarnings("ignore")

st.set_page_config(page_title="S&OP Corporate Platform", layout="wide", initial_sidebar_state="auto")

# --- MODO KIOSK Y CSS CORPORATIVO RESPONSIVE ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Diseño base para PC (Métricas) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e6ed;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #1E3E5B;
    }

    /* Reglas exclusivas para Móviles */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        div[data-testid="metric-container"] {
            padding: 10px 10px !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
        }
        button[data-baseweb="tab"] {
            font-size: 0.9rem !important;
            padding: 5px 10px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# ESQUEMA OFICIAL ESTRICTO DE LAS 8 TABLAS
# ==========================================
COLS_HIST = ['Date', 'País', 'customer cod', 'customer desc', 'sku cod', 'sku desc', 'volume', 'revenue', 'margin', 'currency']
COLS_AJUSTES = ['Date', 'País', 'customer cod', 'sku cod', 'override_value']
COLS_STOCK = ['sku cod', 'sku desc', 'stock_disponible', 'Cobertura_Meses', 'LT_Meses', 'Categoria', 'Coste_Unitario']
COLS_BOM = ['sku cod', 'rm cod', 'rm desc', 'Cantidad']
COLS_RUTAS = ['sku cod', 'Maquina', 'Kilos_por_Hora']
COLS_CAL = ['Date', 'Maquina', 'Horas_Disponibles']
COLS_COMPRAS = ['Date', 'rm cod', 'Cantidad_Kg']
COLS_PROD = ['Date', 'sku cod', 'Cantidad_Kg']

LOG_FILE = "audit_log_accesos.csv"


def registrar_y_leer_auditoria_permanente(nuevo_evento=None):
    """Lee y guarda el historial directamente en GitHub (vía st.secrets) con fallback local."""
    try:
        token = st.secrets.get("GITHUB_TOKEN", None)
        repo = st.secrets.get("GITHUB_REPO", None)
    except Exception:
        token, repo = None, None

    cols_log = ["Fecha_Hora (CET)", "Username", "Nombre", "Rol"]

    if token and repo:
        url = f"https://api.github.com/repos/{repo}/contents/{LOG_FILE}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SOP-Platform-Audit"
        }

        df_actual = pd.DataFrame(columns=cols_log)
        sha_actual = None

        # 1. Leer archivo existente en GitHub
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                sha_actual = data.get("sha")
                contenido_csv = base64.b64decode(data["content"]).decode("utf-8-sig")
                df_actual = pd.read_csv(io.StringIO(contenido_csv))
        except Exception:
            pass

        # 2. Si hay nuevo login, añadir fila y hacer commit en GitHub
        if nuevo_evento is not None:
            df_actual = pd.concat([df_actual, pd.DataFrame([nuevo_evento])], ignore_index=True)
            csv_bytes = df_actual.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            payload = {
                "message": f"Audit log: {nuevo_evento['Username']} ({nuevo_evento['Fecha_Hora (CET)']})",
                "content": base64.b64encode(csv_bytes).decode("utf-8")
            }
            if sha_actual:
                payload["sha"] = sha_actual
            try:
                req_put = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={**headers, "Content-Type": "application/json"},
                    method="PUT"
                )
                urllib.request.urlopen(req_put, timeout=10)
            except Exception:
                pass
        return df_actual

    # Fallback local si no están configurados los Secrets
    if os.path.exists(LOG_FILE):
        try:
            df_actual = pd.read_csv(LOG_FILE)
        except Exception:
            df_actual = pd.DataFrame(columns=cols_log)
    else:
        df_actual = pd.DataFrame(columns=cols_log)

    if nuevo_evento is not None:
        df_actual = pd.concat([df_actual, pd.DataFrame([nuevo_evento])], ignore_index=True)
        try:
            df_actual.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
        except Exception:
            pass
    return df_actual


@st.cache_data
def obtener_excels_demo_8_tablas():
    """Genera los 8 DataFrames de Demo con las columnas exactas oficiales."""
    np.random.seed(42)
    fechas_hist = pd.date_range(start="2024-05-01", periods=28, freq="MS")
    mes_m1 = fechas_hist[-1] + pd.DateOffset(months=1)  # 2026-09-01
    mes_m2 = mes_m1 + pd.DateOffset(months=1)          # 2026-10-01
    fechas_fut = pd.date_range(start=mes_m1, periods=12, freq="MS")

    skus_demo = [
        ("A10800V3", "ADICARE EVOLUTION H", 35000, 2.85, 4.80, 1.45, "Linea_3_Pellet", 3536, "MTS"),
        ("M02031BB", "CEBADA EXTRUSIONADA Z1", 12000, 2.28, 3.10, 0.70, "Linea_1_Extrusion", 4200, "MTS"),
        ("N54700BB", "NUCLEO PORCINO CRECIMIENTO", 18000, 4.10, 6.20, 1.85, "Linea_2_Mezcla", 4134, "MTS"),
        ("PN190G10", "PIENSO GRANULADO BROILER", 65000, 0.55, 0.95, 0.28, "Linea_3_Pellet", 5000, "MTS"),
        ("PR01299X", "PREMEZCLA VITAMINICA AVEC", 8000, 12.50, 18.50, 5.20, "Linea_4_Premix", 2200, "MTS"),
    ]

    # 1. Histórico Ventas
    filas_ventas = []
    for f in fechas_hist:
        est = 1.18 if f.month in [3, 4, 10, 11] else (0.85 if f.month in [7, 8] else 1.0)
        for sku_cod, sku_desc, base_vol, cost_u, precio_u, margen_u, _, _, _ in skus_demo:
            ruido = 0.65 if sku_cod == "PR01299X" else 0.12
            vol = max(200, int(np.random.normal(base_vol * est, base_vol * ruido)))
            filas_ventas.append({
                "Date": f,
                "País": "España",
                "customer cod": "000007SCAAS",
                "customer desc": "Agropecuaria Catalana Stat.Coop.Ltda",
                "sku cod": sku_cod,
                "sku desc": sku_desc,
                "volume": vol,
                "revenue": round(vol * precio_u, 2),
                "margin": round(vol * margen_u, 2),
                "currency": "EUR"
            })
    df_1_hist = pd.DataFrame(filas_ventas)[COLS_HIST]

    # 2. Ajustes Consenso
    filas_ajustes = []
    for f in fechas_fut[:6]:
        for sku_cod, _, base_vol, _, _, _, _, _, _ in skus_demo:
            override = int(base_vol * np.random.uniform(0.95, 1.10))
            filas_ajustes.append({
                "Date": f,
                "País": "España",
                "customer cod": "000007SCAAS",
                "sku cod": sku_cod,
                "override_value": override
            })
    df_2_ajustes = pd.DataFrame(filas_ajustes)[COLS_AJUSTES]

    # 3. Stock Actual (incluye PTs y MPs con las columnas oficiales exactas)
    filas_stock = [
        {"sku cod": sku, "sku desc": desc, "stock_disponible": int(vol * 0.35), "Cobertura_Meses": 1, "LT_Meses": 1, "Categoria": cat, "Coste_Unitario": cost}
        for sku, desc, vol, cost, _, _, _, _, cat in skus_demo
    ] + [
        {"sku cod": "M12250SS", "sku desc": "FORMIATO DE CALCIO", "stock_disponible": 14000, "Cobertura_Meses": 2, "LT_Meses": 1, "Categoria": "MTS", "Coste_Unitario": 0.85},
        {"sku cod": "M09522E3", "sku desc": "PIGLET BOOZT (25 L) Z2", "stock_disponible": 4500, "Cobertura_Meses": 1, "LT_Meses": 1, "Categoria": "MTS", "Coste_Unitario": 3.40},
    ]
    df_3_stock = pd.DataFrame(filas_stock)[COLS_STOCK]

    # 4. BOM
    filas_bom = []
    for sku, _, _, _, _, _, _, _, _ in skus_demo:
        filas_bom.append({"sku cod": sku, "rm cod": "M12250SS", "rm desc": "FORMIATO DE CALCIO", "Cantidad": 0.6961})
        filas_bom.append({"sku cod": sku, "rm cod": "M09522E3", "rm desc": "PIGLET BOOZT (25 L) Z2", "Cantidad": 0.0363})
    df_4_bom = pd.DataFrame(filas_bom)[COLS_BOM]

    # 5. Rutas / Routing
    df_5_rutas = pd.DataFrame([
        {"sku cod": sku, "Maquina": maquina, "Kilos_por_Hora": kph}
        for sku, _, _, _, _, _, maquina, kph, _ in skus_demo
    ])[COLS_RUTAS]

    # 6. Calendario
    maquinas_unicas = ['Linea_1_Extrusion', 'Linea_2_Mezcla', 'Linea_3_Pellet', 'Linea_4_Premix']
    filas_cal = []
    for f in pd.date_range(start="2024-05-01", periods=48, freq="MS"):
        for maq in maquinas_unicas:
            filas_cal.append({
                "Date": f,
                "Maquina": maq,
                "Horas_Disponibles": 740
            })
    df_6_cal = pd.DataFrame(filas_cal)[COLS_CAL]

    # 7. ERP Compras POs
    df_7_compras = pd.DataFrame([
        {"Date": mes_m1, "rm cod": "M12250SS", "Cantidad_Kg": 11067},
        {"Date": mes_m2, "rm cod": "M12250SS", "Cantidad_Kg": 9821},
    ])[COLS_COMPRAS]

    # 8. ERP Producción
    df_8_prod = pd.DataFrame([
        {"Date": mes_m1, "sku cod": "A10800V3", "Cantidad_Kg": 15000},
        {"Date": mes_m1, "sku cod": "PN190G10", "Cantidad_Kg": 35000},
        {"Date": mes_m2, "sku cod": "PN190G10", "Cantidad_Kg": 40000},
    ])[COLS_PROD]

    return {
        "hist": df_1_hist,
        "ajustes": df_2_ajustes,
        "stock": df_3_stock,
        "bom": df_4_bom,
        "rutas": df_5_rutas,
        "cal": df_6_cal,
        "compras_erp": df_7_compras,
        "produccion_erp": df_8_prod,
    }


@st.cache_data
def generar_plantillas_oficiales_excel():
    """Genera un único libro Excel con las 8 plantillas oficiales y ejemplos de cabecera."""
    buf_tpl = io.BytesIO()
    demos_tpl = obtener_excels_demo_8_tablas()
    mapa_hojas = [
        ("1_Historico_Ventas", demos_tpl["hist"].head(5)),
        ("2_Ajustes_Consenso", demos_tpl["ajustes"].head(2)),
        ("3_Stock_Actual", demos_tpl["stock"].head(5)),
        ("4_BOM", demos_tpl["bom"].head(5)),
        ("5_Rutas_Routing", demos_tpl["rutas"].head(5)),
        ("6_Calendario", demos_tpl["cal"].head(5)),
        ("7_ERP_Compras_POs", demos_tpl["compras_erp"].head(2)),
        ("8_ERP_Produccion", demos_tpl["produccion_erp"].head(2)),
    ]
    with pd.ExcelWriter(buf_tpl, engine="openpyxl") as writer:
        for nombre_hoja, df_ejemplo in mapa_hojas:
            df_ejemplo.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return buf_tpl.getvalue()


# ==========================================
# 0. CONTROL DE ACCESO Y ROLES (LOGIN)
# ==========================================
credenciales = {
    "usernames": {
        "amancebo": {
            "email": "amancebo@abagri.com",
            "name": "Ángel Mancebo",
            "password": "Sop2026"
        },
        "borja": {
            "email": "bdelrio@abagri.com",
            "name": "Borja Del Rio",
            "password": "BorjaDR"
        }
    }
}

if stauth is not None:
    stauth.Hasher.hash_passwords(credenciales)
    authenticator = stauth.Authenticate(
        credentials=credenciales,
        cookie_name="sop_abagri_token",
        key="abcdef12345",
        cookie_expiry_days=30
    )
    authenticator.login("main")
else:
    authenticator = None
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None

    if not st.session_state["authentication_status"]:
        with st.form("login_local_form"):
            st.subheader("🔐 Acceso S&OP (Modo Local)")
            user_in = st.text_input("Usuario").strip()
            pass_in = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar Sesión"):
                usuarios_dict = credenciales.get("usernames", {})
                if user_in in usuarios_dict and pass_in == usuarios_dict[user_in].get("password"):
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = user_in
                    st.session_state["name"] = usuarios_dict[user_in].get("name", user_in)
                    st.rerun()
                else:
                    st.session_state["authentication_status"] = False

if st.session_state.get("authentication_status") is False:
    st.error("❌ Usuario o contraseña incorrectos")
    st.stop()
elif st.session_state.get("authentication_status") is None:
    st.warning("🔒 Por favor, introduce tus credenciales para acceder a la plataforma S&OP")
    st.stop()

usuario_actual = st.session_state["username"]

PERMISOS = {
    "amancebo": ["tab0", "tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7", "tab8", "tab9", "tab10"],
    "borja": ["tab0", "tab2"]
}
modulos_permitidos = PERMISOS.get(usuario_actual, ["tab0"])

# --- REGISTRO AUTOMÁTICO DE AUDITORÍA EN GITHUB AL INICIAR SESIÓN ---
if not st.session_state.get("acceso_registrado", False):
    ahora_es = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")
    rol_usuario = "Manager de Producción" if usuario_actual == "borja" else "Administrador Global"
    nuevo_evento = {
        "Fecha_Hora (CET)": ahora_es,
        "Username": usuario_actual,
        "Nombre": st.session_state.get("name", usuario_actual),
        "Rol": rol_usuario
    }
    st.session_state["df_audit_logs"] = registrar_y_leer_auditoria_permanente(nuevo_evento)
    st.session_state["acceso_registrado"] = True

with st.sidebar:
    st.markdown(f"👤 **Bienvenido/a, {st.session_state['name']}**")
    if usuario_actual == "borja":
        st.caption("🔹 Rol: Manager de Producción")
    else:
        st.caption("🔹 Rol: Administrador Global")

    if authenticator is not None:
        authenticator.logout("Cerrar Sesión", "main")
    else:
        if st.button("Cerrar Sesión"):
            st.session_state["authentication_status"] = None
            st.session_state["acceso_registrado"] = False
            st.rerun()

    # --- PANEL DE AUDITORÍA EXCLUSIVO PARA ADMINISTRADOR (AMANCEBO) ---
    if usuario_actual == "amancebo":
        with st.expander("🛡️ Registro de Accesos (Admin)"):
            if st.button("🔄 Actualizar Historial GitHub", use_container_width=True):
                st.session_state["df_audit_logs"] = registrar_y_leer_auditoria_permanente(None)
            df_logs = st.session_state.get("df_audit_logs", registrar_y_leer_auditoria_permanente(None))
            if df_logs is None or df_logs.empty:
                st.caption("Sin registros todavía.")
            else:
                st.caption(f"Total accesos registrados: **{len(df_logs)}**")
                st.dataframe(df_logs.iloc[::-1], use_container_width=True, hide_index=True)
                csv_logs = df_logs.iloc[::-1].to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 Descargar Historial (.csv)",
                    data=csv_logs,
                    file_name=f"Audit_Log_SOP_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    st.divider()

    with st.expander("📲 Compartir App (QR)"):
        enlace_app = "https://sop-mancew.streamlit.app/"
        if qrcode is not None:
            st.caption("Escanea para entrar desde móvil:")
            img_qr = qrcode.make(enlace_app)
            buf = io.BytesIO()
            img_qr.save(buf, format="PNG")
            st.image(buf.getvalue(), use_container_width=True)
        else:
            st.caption(f"🔗 Enlace directo: {enlace_app}")

# ==========================================
# 0. DICCIONARIO DE IDIOMAS 
# ==========================================
LANGUAGES = ["Español", "English", "Polski", "Dansk"]
TEXTS = {
    "Español": {
        "title": "S&OP Execution & Planning Platform",
        "sidebar_lang": "🌐 Idioma / Language",
        "tab0": "📖 0. Guía", "tab1": "📊 1. Demanda", "tab2": "🏭 2. Producción", 
        "tab3": "🧩 3. Compras", "tab4": "⚙️ 4. Capacidad", "tab5": "💷 5. Finanzas", "tab6": "🚀 6. Ejecución ERP", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Excepciones", "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Ingresos (Revenue)", "kpi_mar": "Margen Bruto", "kpi_wc": "Working Capital Promedio",
        "kpi_fab": "Volumen a Fabricar", "kpi_doh": "Cobertura Media",
        "guide_title": "📖 Plataforma S&OP Corporativa",
        "guide_desc": "El simulador cuenta con un motor MRP integrado y validación estricta de columnas:",
        "g_dem_t": "1. Demanda", "g_dem_d": "Holt-Winters sobre histórico. Prioriza Ajustes Consenso.",
        "g_pro_t": "2. Producción (MPS)", "g_pro_d": "Absorbe órdenes del ERP. `Nuevas Órdenes = Demanda + Stock Obj - Stock Inic - Órdenes ERP`.",
        "g_com_t": "3. Compras (MRP)", "g_com_d": "Explosiona las Nuevas Órdenes de Producción. Absorbe Pedidos de Compra del ERP. Incluye Trazabilidad (Pegging).",
        "g_cap_t": "4. Capacidad", "g_cap_d": "Convierte Kilos a Horas y cruza con Calendario de plantas.",
        "g_fin_t": "5. Finanzas", "g_fin_d": "Revenue y Working Capital consolidado en GBP.",
        "g_erp_t": "6. Ejecución", "g_erp_d": "Action Plan para el Mes 1 con las órdenes que debes lanzar de inmediato."
    },
    "English": {
        "title": "S&OP Execution & Planning Platform",
        "sidebar_lang": "🌐 Language",
        "tab0": "📖 0. Guide", "tab1": "📊 1. Demand", "tab2": "🏭 2. Production", 
        "tab3": "🧩 3. Purchasing", "tab4": "⚙️ 4. Capacity", "tab5": "💷 5. Finance", "tab6": "🚀 6. ERP Execution", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Total Revenue", "kpi_mar": "Gross Margin", "kpi_wc": "Avg Working Capital",
        "kpi_fab": "Volume to Produce", "kpi_doh": "Avg Days on Hand",
        "guide_title": "📖 Corporate S&OP Platform",
        "guide_desc": "The simulator runs a full integrated MRP engine with strict column validation:",
        "g_dem_t": "1. Demand", "g_dem_d": "Holt-Winters on history. Consensus Adjustments take priority.",
        "g_pro_t": "2. Production (MPS)", "g_pro_d": "Absorbs ERP orders. `New Orders = Demand + Target Stock - Init Stock - ERP Orders`.",
        "g_com_t": "3. Purchasing (MRP)", "g_com_d": "Explodes New Production Orders. Absorbs ERP Purchase Orders. Includes Pegging.",
        "g_cap_t": "4. Capacity", "g_cap_d": "Converts Kilos to Hours and crosses against Plant Calendars.",
        "g_fin_t": "5. Finance", "g_fin_d": "Revenue and Working Capital consolidated in GBP.",
        "g_erp_t": "6. Execution", "g_erp_d": "Action Plan for Month 1 with orders to be released immediately."
    },
    "Polski": {
        "title": "Platforma S&OP i Planowania",
        "sidebar_lang": "🌐 Język / Language",
        "tab0": "📖 0. Przewodnik", "tab1": "📊 1. Popyt", "tab2": "🏭 2. Produkcja", 
        "tab3": "🧩 3. Zakupy", "tab4": "⚙️ 4. Zdolności", "tab5": "💷 5. Finanse", "tab6": "🚀 6. Realizacja ERP", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Przychody", "kpi_mar": "Marża Brutto", "kpi_wc": "Śr. Kapitał Obrotowy",
        "kpi_fab": "Wolumen do Produkcji", "kpi_doh": "Średnie Pokrycie",
        "guide_title": "📖 Przewodnik",
        "guide_desc": "Symulator posiada pełny silnik MRP:",
        "g_dem_t": "1. Popyt", "g_dem_d": "Algorytm Holt-Winters na danych historycznych. Korekty ręczne mają priorytet.",
        "g_pro_t": "2. Produkcja (MPS)", "g_pro_d": "Absorbuje zlecenia ERP. `Nowe Zlecenia = Popyt + Zapas Doc. - Zapas Pocz. - Zlecenia ERP`.",
        "g_com_t": "3. Zakupy (MRP)", "g_com_d": "Rozbija nowe zlecenia produkcji. Absorbuje zlecenia zakupu z ERP. Zawiera Pegging.",
        "g_cap_t": "4. Zdolności", "g_cap_d": "Przelicza kilogramy na roboczogodziny maszyn.",
        "g_fin_t": "5. Finanse", "g_fin_d": "Przychody i Kapitał Obrotowy w GBP.",
        "g_erp_t": "6. Realizacja", "g_erp_d": "Plan Działania na Miesiąc 1 dla nowych zleceń do uruchomienia."
    },
    "Dansk": {
        "title": "S&OP Eksekveringsplatform",
        "sidebar_lang": "🌐 Sprog / Language",
        "tab0": "📖 0. Guide", "tab1": "📊 1. Efterspørgsel", "tab2": "🏭 2. Produktion", 
        "tab3": "🧩 3. Indkøb", "tab4": "⚙️ 4. Kapacitet", "tab5": "💷 5. Økonomi", "tab6": "🚀 6. ERP Udførelse", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Omsætning", "kpi_mar": "Bruttomargin", "kpi_wc": "Gns. Arbejdskapital",
        "kpi_fab": "Produktionsvolumen", "kpi_doh": "Gns. Dækning",
        "guide_title": "📖 Værktøjsguide",
        "guide_desc": "Simulatoren kører en fuld integreret MRP:",
        "g_dem_t": "1. Efterspørgsel", "g_dem_d": "Holt-Winters. Manuelle justeringer prioriteres.",
        "g_pro_t": "2. Produktion (MPS)", "g_pro_d": "Absorberer ERP-ordrer. `Nye Ordrer = Behov + Mållager - Startlager - ERP-ordrer`.",
        "g_com_t": "3. Indkøb (MRP)", "g_com_d": "Eksploderer nye produktionsordrer. Absorberer ERP indkøbsordrer. Inkluderer Pegging.",
        "g_cap_t": "4. Kapacitet", "g_cap_d": "Konverterer kilo til timer og krydser mod kalendere.",
        "g_fin_t": "5. Økonomi", "g_fin_d": "Omsætning og Arbejdskapital i GBP.",
        "g_erp_t": "6. Udførelse", "g_erp_d": "Handlingsplan for Måned 1 med de ordrer, der skal udstedes."
    }
}

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'Español'

with st.sidebar:
    st.divider()
    st.session_state['lang'] = st.selectbox(
        TEXTS[st.session_state['lang']]["sidebar_lang"],
        LANGUAGES,
        index=LANGUAGES.index(st.session_state['lang'])
    )

t = TEXTS[st.session_state['lang']]
st.title(t["title"])

# ==========================================
# 1. CONFIGURACIÓN Y CARGA DE ARCHIVOS
# ==========================================
with st.sidebar:
    st.markdown("### 🧪 Modo Demostración (1-Clic)")
    if "modo_demo_8" not in st.session_state:
        st.session_state["modo_demo_8"] = False

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚀 Cargar 8 Tablas", use_container_width=True, type="primary"):
            st.session_state["modo_demo_8"] = True
            st.rerun()
    with col_btn2:
        if st.button("🗑️ Limpiar Demo", use_container_width=True):
            st.session_state["modo_demo_8"] = False
            st.rerun()

    if st.session_state["modo_demo_8"]:
        st.success("✅ 8 Tablas Demo activas. Si arrastras un Excel abajo, sustituirá a esa tabla Demo.")

    st.download_button(
        label="📥 Descargar 8 Plantillas Oficiales (.xlsx)",
        data=generar_plantillas_oficiales_excel(),
        file_name="Plantillas_Oficiales_SOP_8_Tablas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.header("📂 1. S&OP Master Data")
    file_hist = st.file_uploader("1. Histórico Ventas", type=['xlsx', 'csv'])
    file_ajustes = st.file_uploader("2. Ajustes Consenso", type=['xlsx', 'csv'])
    file_stock = st.file_uploader("3. Stock Actual", type=['xlsx', 'csv'])
    file_bom = st.file_uploader("4. BOM", type=['xlsx', 'csv'])
    file_rutas = st.file_uploader("5. Rutas / Routing", type=['xlsx', 'csv'])
    file_cal = st.file_uploader("6. Calendario", type=['xlsx', 'csv'])
    
    st.divider()
    st.header("🚀 2. ERP Pipeline (Execution)")
    file_compras_erp = st.file_uploader("7. ERP Compras / POs", type=['xlsx', 'csv'])
    file_produccion_erp = st.file_uploader("8. ERP Producción / Prd. Orders", type=['xlsx', 'csv'])

    if st.session_state.get("modo_demo_8", False):
        demos = obtener_excels_demo_8_tablas()
        if file_hist is None:            file_hist            = demos["hist"]
        if file_ajustes is None:         file_ajustes         = demos["ajustes"]
        if file_stock is None:           file_stock           = demos["stock"]
        if file_bom is None:             file_bom             = demos["bom"]
        if file_rutas is None:           file_rutas           = demos["rutas"]
        if file_cal is None:             file_cal             = demos["cal"]
        if file_compras_erp is None:     file_compras_erp     = demos["compras_erp"]
        if file_produccion_erp is None:  file_produccion_erp  = demos["produccion_erp"]

    st.divider()
    st.header("📅 3. Parameters")
    horizonte = st.slider("Horizon (Months):", 1, 24, 12)
    cobertura_fg = st.slider("Cov. PT (Months):", 0, 6, 1)
    cobertura_rm = st.slider("Cov. MP (Months):", 0, 6, 2)
    
    if "tab5" in modulos_permitidos:
        st.divider()
        st.header("💱 4. Finance (FX to GBP)")
        fx_eur_gbp = st.number_input("EUR -> GBP:", value=0.85, step=0.01)
        fx_dkk_gbp = st.number_input("DKK -> GBP:", value=0.11, step=0.01)
        fx_pln_gbp = st.number_input("PLN -> GBP:", value=0.20, step=0.01)
    else:
        fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp = 0.85, 0.11, 0.20
    
    st.divider()
    usar_limpieza_outliers = st.checkbox("🧹 Clean Outliers", value=True)


def validar_y_cargar_tabla(uploaded_file, columnas_obligatorias, nombre_tabla, permitir_vacio=False):
    """Carga el archivo y valida estrictamente que contenga las columnas oficiales exactas."""
    if uploaded_file is None:
        return None
        
    if isinstance(uploaded_file, pd.DataFrame):
        d = uploaded_file.copy()
    else:
        try:
            uploaded_file.seek(0)
            if getattr(uploaded_file, 'name', '').endswith('.csv'):
                d = pd.read_csv(uploaded_file)
            else:
                d = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo para **{nombre_tabla}**: {e}")
            return None

    if d is None:
        st.error(f"❌ No se pudo procesar el archivo de **{nombre_tabla}**.")
        return None

    d.columns = d.columns.astype(str).str.strip()

    columnas_faltantes = [col for col in columnas_obligatorias if col not in d.columns]
    if columnas_faltantes:
        st.error(
            f"🚨 **Nombre de columna incorrecto en [{nombre_tabla}]**\n\n"
            f"Faltan las siguientes columnas obligatorias exactas: `{columnas_faltantes}`\n\n"
            f"Columnas esperadas: `{columnas_obligatorias}`\n\n"
            f"Columnas detectadas en tu archivo: `{d.columns.tolist()}`"
        )
        return None

    if d.empty and not permitir_vacio:
        st.warning(f"⚠️ El archivo **{nombre_tabla}** tiene las columnas correctas pero no contiene filas de datos.")
        return None

    return d


# --- CARGA Y VALIDACIÓN ESTRICTA DE LAS 8 TABLAS ---
if 'df_ajustes' not in st.session_state or not isinstance(st.session_state['df_ajustes'], pd.DataFrame):
    st.session_state['df_ajustes'] = pd.DataFrame(columns=COLS_AJUSTES)
if 'last_ajuste_file' not in st.session_state:
    st.session_state['last_ajuste_file'] = None

df = validar_y_cargar_tabla(file_hist, COLS_HIST, "1. Histórico Ventas")

id_ajuste_actual = "DEMO_AJUSTES" if isinstance(file_ajustes, pd.DataFrame) else getattr(file_ajustes, "name", None)
if file_ajustes is not None and id_ajuste_actual != st.session_state['last_ajuste_file']:
    df_aj_cargado = validar_y_cargar_tabla(file_ajustes, COLS_AJUSTES, "2. Ajustes Consenso", permitir_vacio=True)
    if isinstance(df_aj_cargado, pd.DataFrame):
        st.session_state['df_ajustes'] = df_aj_cargado
    else:
        st.session_state['df_ajustes'] = pd.DataFrame(columns=COLS_AJUSTES)
    st.session_state['last_ajuste_file'] = id_ajuste_actual
elif file_ajustes is None and st.session_state['last_ajuste_file'] is not None:
    st.session_state['df_ajustes'] = pd.DataFrame(columns=COLS_AJUSTES)
    st.session_state['last_ajuste_file'] = None

df_ajustes = st.session_state['df_ajustes']
df_stock = validar_y_cargar_tabla(file_stock, COLS_STOCK, "3. Stock Actual")
df_bom = validar_y_cargar_tabla(file_bom, COLS_BOM, "4. BOM")
df_rutas = validar_y_cargar_tabla(file_rutas, COLS_RUTAS, "5. Rutas / Routing")
df_cal = validar_y_cargar_tabla(file_cal, COLS_CAL, "6. Calendario")
df_compras_erp = validar_y_cargar_tabla(file_compras_erp, COLS_COMPRAS, "7. ERP Compras / POs", permitir_vacio=True)
df_produccion_erp = validar_y_cargar_tabla(file_produccion_erp, COLS_PROD, "8. ERP Producción / Prd. Orders", permitir_vacio=True)

if df is None or df.empty:
    st.info("👈 Pulsa **'🚀 Cargar 8 Tablas'** en la barra lateral para iniciar la Demo o sube el archivo **1. Histórico Ventas** con las columnas oficiales.")
    st.stop()

# --- TOPE HISTÓRICO Y CONVERSIÓN DE TIPOS ---
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df = df.dropna(subset=['Date'])
fecha_maxima = df['Date'].max()
fecha_corte = fecha_maxima - pd.DateOffset(months=24)
df = df[df['Date'] >= fecha_corte].copy()

df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)
df['margin'] = pd.to_numeric(df['margin'], errors='coerce').fillna(0)

# Conversión financiera a GBP fila a fila
dict_fx = {'EUR': fx_eur_gbp, 'DKK': fx_dkk_gbp, 'PLN': fx_pln_gbp, 'GBP': 1.0}
df['Moneda'] = df['currency'].astype(str).str.strip().str.upper()
df['FX'] = df['Moneda'].map(dict_fx).fillna(1.0)
df['Rev_GBP'] = df['revenue'] * df['FX']
df['Mar_GBP'] = df['margin'] * df['FX']

df_fin_base = df.groupby('sku cod').agg({'volume': 'sum', 'Rev_GBP': 'sum', 'Mar_GBP': 'sum'}).reset_index()
df_fin_base['unit_price'] = np.where(df_fin_base['volume'] > 0, df_fin_base['Rev_GBP'] / df_fin_base['volume'], 0.0)
df_fin_base['unit_margin'] = np.where(df_fin_base['volume'] > 0, df_fin_base['Mar_GBP'] / df_fin_base['volume'], 0.0)

dict_price = dict(zip(df_fin_base['sku cod'], df_fin_base['unit_price']))
dict_margin = dict(zip(df_fin_base['sku cod'], df_fin_base['unit_margin']))
dict_currency = dict(zip(df_fin_base['sku cod'], ['GBP'] * len(df_fin_base)))

# ==========================================
# 2. MOTOR ABC/XYZ Y FILTROS EN CASCADA
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def calcular_abc_xyz_global(df_in):
    if df_in is None or df_in.empty:
        return pd.DataFrame()
    
    df_vol = df_in.groupby('sku cod')['volume'].sum().reset_index().sort_values('volume', ascending=False)
    if df_vol['volume'].sum() == 0:
        return pd.DataFrame()
        
    df_vol['cum_pct'] = df_vol['volume'].cumsum() / df_vol['volume'].sum()
    df_vol['ABC'] = np.where(df_vol['cum_pct'] <= 0.8, 'A', np.where(df_vol['cum_pct'] <= 0.95, 'B', 'C'))
    
    df_mes = df_in.groupby(['sku cod', pd.Grouper(key='Date', freq='MS')])['volume'].sum().reset_index()
    df_cv = df_mes.groupby('sku cod')['volume'].agg(['mean', 'std']).reset_index()
    df_cv['CV'] = (df_cv['std'] / df_cv['mean'].replace(0, 1)).replace([np.inf, -np.inf], 0).fillna(0)
    df_cv['XYZ'] = np.where(df_cv['CV'] <= 0.5, 'X', np.where(df_cv['CV'] <= 1.0, 'Y', 'Z'))
    
    df_res = pd.merge(df_vol[['sku cod', 'volume', 'ABC']], df_cv[['sku cod', 'CV', 'XYZ']], on='sku cod')
    df_res['Clase'] = df_res['ABC'] + df_res['XYZ']

    mapa_desc = df_in.dropna(subset=['sku desc']).groupby('sku cod')['sku desc'].first().to_dict()
    df_res['sku desc'] = df_res['sku cod'].map(mapa_desc).fillna(df_res['sku cod'].astype(str))

    df_mg_agg = df_in.groupby('sku cod').agg({'volume': 'sum', 'Mar_GBP': 'sum'}).reset_index()
    df_mg_agg['Margen Unitario'] = np.where(df_mg_agg['volume'] > 0, df_mg_agg['Mar_GBP'] / df_mg_agg['volume'], 0.0)
    mapa_mg = dict(zip(df_mg_agg['sku cod'], df_mg_agg['Margen Unitario']))
    df_res['Margen Unitario'] = df_res['sku cod'].map(mapa_mg).replace([np.inf, -np.inf], 0).fillna(0.0)

    return df_res


df_abcxyz_global = calcular_abc_xyz_global(df)

col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    lista_paises = ["TODOS"] + sorted(df['País'].dropna().astype(str).unique().tolist())
    pais_sel = st.selectbox("1. Country / País:", lista_paises)
df_filtro1 = df if pais_sel == "TODOS" else df[df['País'].astype(str) == pais_sel]

with col_f2:
    lista_clientes = ["TODOS"] + sorted(df_filtro1['customer cod'].dropna().astype(str).unique().tolist())
    cliente_sel = st.selectbox("2. Customer / Cliente:", lista_clientes)
df_filtro2 = df_filtro1 if cliente_sel == "TODOS" else df_filtro1[df_filtro1['customer cod'].astype(str) == cliente_sel]

with col_f3:
    lista_clases = ["TODAS"] + sorted(df_abcxyz_global['Clase'].dropna().unique().tolist()) if not df_abcxyz_global.empty else ["TODAS"]
    clase_sel = st.selectbox("3. Clase ABC/XYZ:", lista_clases)

if clase_sel != "TODAS" and not df_abcxyz_global.empty:
    skus_en_clase = df_abcxyz_global[df_abcxyz_global['Clase'] == clase_sel]['sku cod'].unique()
    df_filtro3 = df_filtro2[df_filtro2['sku cod'].isin(skus_en_clase)]
else:
    df_filtro3 = df_filtro2

with col_f4:
    lista_skus = ["TODOS"] + sorted(df_filtro3['sku cod'].dropna().astype(str).unique().tolist())
    sku_sel = st.selectbox("4. Filter SKU (PT):", lista_skus)
df_final = df_filtro3 if sku_sel == "TODOS" else df_filtro3[df_filtro3['sku cod'].astype(str) == sku_sel]

col_objetivo = 'volume'
dict_sku_desc = dict(zip(df['sku cod'], df['sku desc']))

# 1. Diccionario de descripciones de Materia Prima (BOM)
if df_bom is not None and not df_bom.empty:
    dict_rm_desc = dict(zip(df_bom['rm cod'], df_bom['rm desc']))
else:
    dict_rm_desc = {}

# 2. Diccionario de Pedidos de Producción ERP (8_ERP_Produccion_PrdOrders.xlsx)
dict_prd_erp = {}
if df_produccion_erp is not None and not df_produccion_erp.empty:
    df_p_tmp = df_produccion_erp.copy()
    df_p_tmp['Date'] = pd.to_datetime(df_p_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
    df_p_tmp['Cantidad_Kg'] = pd.to_numeric(df_p_tmp['Cantidad_Kg'], errors='coerce').fillna(0)
    dict_prd_erp = df_p_tmp.dropna(subset=['Date']).groupby(['sku cod', 'Date'])['Cantidad_Kg'].sum().to_dict()

# 3. Diccionario de Pedidos de Compra ERP (7_ERP_Compras_POs.xlsx)
dict_cmp_erp = {}
if df_compras_erp is not None and not df_compras_erp.empty:
    df_c_tmp = df_compras_erp.copy()
    df_c_tmp['Date'] = pd.to_datetime(df_c_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
    df_c_tmp['Cantidad_Kg'] = pd.to_numeric(df_c_tmp['Cantidad_Kg'], errors='coerce').fillna(0)
    dict_cmp_erp = df_c_tmp.dropna(subset=['Date']).groupby(['rm cod', 'Date'])['Cantidad_Kg'].sum().to_dict()


# ==========================================
# 3. FUNCIONES CORE Y OPTIMIZACIÓN DE CACHÉ
# ==========================================
def obtener_parametros_stock(codigo, cob_defecto=2):
    stk, cob, lt = 0.0, int(cob_defecto), 0
    if df_stock is not None and not df_stock.empty:
        fila = df_stock[df_stock['sku cod'].astype(str).str.strip() == str(codigo).strip()]
        if not fila.empty:
            stk = float(pd.to_numeric(fila['stock_disponible'], errors='coerce').fillna(0).sum())
            if pd.notna(fila['Cobertura_Meses'].iloc[0]):
                cob = int(fila['Cobertura_Meses'].iloc[0])
            if str(fila['Categoria'].iloc[0]).strip().upper() == 'MTO':
                cob = 0
            if pd.notna(fila['LT_Meses'].iloc[0]):
                lt = int(fila['LT_Meses'].iloc[0])
    return stk, cob, lt


@st.cache_data(show_spinner=False, max_entries=5000)
def limpiar_anomalias(serie):
    if len(serie) < 6:
        return serie
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return serie.clip(lower=max(0, q1 - 1.5 * iqr), upper=q3 + 1.5 * iqr)


@st.cache_data(show_spinner=False, max_entries=5000)
def calcular_forecast(serie, steps):
    if len(serie) == 0:
        return pd.Series([0.0] * steps, index=pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=steps, freq="MS"))
    if len(serie) < 6:
        return pd.Series([serie.mean()] * steps, index=pd.date_range(start=serie.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS"))
    try:
        return ExponentialSmoothing(serie, trend="add", seasonal="add" if len(serie) >= 24 else None, seasonal_periods=12).fit().forecast(steps).apply(lambda x: max(0, x))
    except Exception:
        return pd.Series([serie.tail(6).mean()] * steps, index=pd.date_range(start=serie.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS"))


def aplicar_variacion_cliente(pais, cliente, pct):
    try:
        sub = df[(df['País'] == pais) & (df['customer cod'] == cliente)].copy()
        if sub.empty:
            return False, "No hay histórico para ese País y Cliente."
        factor = 1.0 + (float(pct) / 100.0)
        df_aj = st.session_state['df_ajustes'].copy()
        df_aj = df_aj[~((df_aj['País'] == pais) & (df_aj['customer cod'] == cliente))]
        nuevas = []
        for sku_c in sub['sku cod'].unique():
            s_sku = sub[sub['sku cod'] == sku_c].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
            s_mod = limpiar_anomalias(s_sku) if usar_limpieza_outliers else s_sku
            fcst = calcular_forecast(s_mod, horizonte)
            for f_dt, val in fcst.items():
                nuevas.append({
                    'Date': f_dt,
                    'País': pais,
                    'customer cod': cliente,
                    'sku cod': sku_c,
                    'override_value': round(float(val) * factor, 2)
                })
        if nuevas:
            df_aj = pd.concat([df_aj, pd.DataFrame(nuevas)], ignore_index=True)
        st.session_state['df_ajustes'] = df_aj
        return True, "OK"
    except Exception as e:
        return False, str(e)


@st.cache_data(show_spinner=False)
def calcular_kpis_forecast(df_in, usar_outliers):
    if df_in is None or df_in.empty:
        return 0.0, 0.0, 0.0
    df_eval = df_in.groupby('Date')['volume'].sum().resample("MS").sum().reset_index()
    if len(df_eval) < 12:
        return 0.0, 0.0, 0.0
    
    serie = df_eval.set_index('Date')['volume']
    serie_limpia = limpiar_anomalias(serie) if usar_outliers else serie
    try:
        modelo = ExponentialSmoothing(serie_limpia, trend="add", seasonal="add" if len(serie_limpia) >= 24 else None, seasonal_periods=12).fit()
        fitted_values = modelo.fittedvalues
    except Exception:
        fitted_values = serie_limpia.shift(1).fillna(serie_limpia.mean())
        
    df_eval['Forecast'] = fitted_values.values
    df_eval['Error'] = df_eval['volume'] - df_eval['Forecast']
    df_eval['Abs_Error'] = df_eval['Error'].abs()
    
    sum_actual = df_eval['volume'].sum()
    sum_abs_error = df_eval['Abs_Error'].sum()
    sum_error = df_eval['Error'].sum()
    
    wape = (sum_abs_error / sum_actual) * 100 if sum_actual > 0 else 0.0
    forecast_accuracy = max(0.0, 100.0 - wape)
    bias = (sum_error / sum_actual) * 100 if sum_actual > 0 else 0.0
    
    return forecast_accuracy, bias, wape


def estilo_doh(val):
    if pd.isna(val):
        return ''
    if val < 15:
        return 'background-color: #ffcccc; color: #900; font-weight: bold;'
    elif val > 60:
        return 'background-color: #ffe6cc; color: #b35900; font-weight: bold;'
    else:
        return 'background-color: #e6ffe6; color: #006600;'


def calcular_necesidades_netas(serie_salidas, stock_inicial, cobertura_meses, serie_erp=None):
    plan = pd.DataFrame(index=serie_salidas.index)
    plan['Salidas_Brutas'] = serie_salidas.fillna(0)
    plan['Recepciones_ERP'] = serie_erp if serie_erp is not None else 0.0
    plan['Recepciones_ERP'] = plan['Recepciones_ERP'].fillna(0)
    
    plan['Stock_Inicial'], plan['Stock_Objetivo'], plan['Entradas_Netas'], plan['Stock_Final'] = 0.0, 0.0, 0.0, 0.0
    stock_corriente = float(stock_inicial)
    
    media_reciente = plan['Salidas_Brutas'].tail(3).mean() if len(plan) > 0 else 0.0
    
    for i in range(len(plan)):
        futuro_disponible = plan['Salidas_Brutas'].iloc[i + 1 : i + 1 + cobertura_meses]
        meses_faltantes = max(0, cobertura_meses - len(futuro_disponible))
        salida_futura = futuro_disponible.sum() + (meses_faltantes * media_reciente)
        
        plan.iloc[i, plan.columns.get_loc('Stock_Inicial')] = stock_corriente
        plan.iloc[i, plan.columns.get_loc('Stock_Objetivo')] = salida_futura
        
        rec_erp = plan['Recepciones_ERP'].iloc[i]
        necesidad_real = plan['Salidas_Brutas'].iloc[i] + salida_futura - stock_corriente - rec_erp
        entradas_sugeridas = max(0.0, necesidad_real)
        
        plan.iloc[i, plan.columns.get_loc('Entradas_Netas')] = entradas_sugeridas
        stock_corriente = stock_corriente + entradas_sugeridas + rec_erp - plan['Salidas_Brutas'].iloc[i]
        plan.iloc[i, plan.columns.get_loc('Stock_Final')] = stock_corriente
        
    demanda_futura_media = plan['Salidas_Brutas'].rolling(window=3, min_periods=1).mean().shift(-1)
    if len(plan) > 0:
        demanda_futura_media.iloc[-1] = media_reciente
    plan['DOH'] = np.where(demanda_futura_media > 0, (plan['Stock_Final'] / demanda_futura_media) * 30, 0)
    plan['DOH'] = plan['DOH'].fillna(0).round(0)
    return plan


@st.cache_data(show_spinner=False)
def generar_mps_global(df_v=None, df_stk=None, aj_df=None, horiz=None, cob_fg=None, prod_erp=None, _v_cache=99):
    if df_v is None: df_v = globals().get('df')
    if df_stk is None: df_stk = globals().get('df_stock')
    if aj_df is None: aj_df = st.session_state.get('df_ajustes', pd.DataFrame())
    if horiz is None: horiz = globals().get('horizonte', 12)
    if cob_fg is None: cob_fg = globals().get('cobertura_fg', 1)
    if prod_erp is None: prod_erp = globals().get('dict_prd_erp', {})

    mps_dict = {}
    if df_v is None or df_v.empty:
        return mps_dict

    fecha_max_global = pd.to_datetime(df_v['Date']).max().replace(day=1)
    idx_futuro_global = pd.date_range(start=fecha_max_global + pd.DateOffset(months=1), periods=horiz, freq="MS")

    for sku in df_v['sku cod'].unique():
        serie_sku = df_v[df_v['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
        media_positiva = float(serie_sku[serie_sku > 0].mean()) if (serie_sku > 0).any() else 0.0
        fcst_vals = calcular_forecast(serie_sku, horiz)
        vals = np.maximum(fcst_vals.values, media_positiva * 0.5) if media_positiva > 0 else fcst_vals.values
        df_fcst = pd.DataFrame({'Consenso': vals}, index=idx_futuro_global)

        if aj_df is not None and not aj_df.empty:
            aj_sku = aj_df[aj_df['sku cod'] == sku].copy()
            if not aj_sku.empty:
                aj_sku['Date'] = pd.to_datetime(aj_sku['Date'], dayfirst=True, errors='coerce')
                for f_dt, r in aj_sku.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
                    if f_dt.replace(day=1) in df_fcst.index:
                        df_fcst.at[f_dt.replace(day=1), 'Consenso'] = r['override_value']

        stk_inicial, cob_meses, _ = obtener_parametros_stock(sku, cob_fg)

        serie_erp = pd.Series(0.0, index=df_fcst.index)
        for idx in df_fcst.index:
            serie_erp[idx] = prod_erp.get((sku, idx), 0.0)

        df_plan = calcular_necesidades_netas(df_fcst['Consenso'], stk_inicial, cob_meses, serie_erp)
        df_plan['sku cod'] = sku
        df_plan['sku desc'] = dict_sku_desc.get(sku, str(sku))
        mps_dict[sku] = df_plan
    return mps_dict


@st.cache_data(show_spinner=False)
def generar_mrp_global(df_v=None, df_stk=None, df_b=None, aj_df=None, horiz=None, cob_fg=None, cob_rm=None, prod_erp=None, cmp_erp=None, _v_cache=99):
    if df_v is None: df_v = globals().get('df')
    if df_stk is None: df_stk = globals().get('df_stock')
    if df_b is None: df_b = globals().get('df_bom')
    if aj_df is None: aj_df = st.session_state.get('df_ajustes', pd.DataFrame())
    if horiz is None: horiz = globals().get('horizonte', 12)
    if cob_fg is None: cob_fg = globals().get('cobertura_fg', 1)
    if cob_rm is None: cob_rm = globals().get('cobertura_rm', 2)
    if prod_erp is None: prod_erp = globals().get('dict_prd_erp', {})
    if cmp_erp is None: cmp_erp = globals().get('dict_cmp_erp', {})

    mps_g = generar_mps_global(df_v, df_stk, aj_df, horiz, cob_fg, prod_erp, _v_cache=_v_cache)
    if df_b is None or df_b.empty or not mps_g:
        return pd.DataFrame()
    
    lista_req = []
    for sku in mps_g:
        sub_bom = df_b[df_b['sku cod'].astype(str).str.strip() == str(sku).strip()]
        for _, row in sub_bom.iterrows():
            rm_c = row['rm cod']
            if pd.notna(rm_c):
                cant = float(pd.to_numeric(row['Cantidad'], errors='coerce')) if pd.notna(row['Cantidad']) else 0.0
                if cant > 0:
                    lista_req.append(pd.DataFrame({
                        'Date': mps_g[sku].index,
                        'Necesidad_Bruta': (mps_g[sku]['Entradas_Netas'] + mps_g[sku]['Recepciones_ERP']) * cant,
                        'rm cod': str(rm_c).strip()
                    }))
                
    if not lista_req:
        return pd.DataFrame()
    df_req_all = pd.concat(lista_req)
    
    lista_compras_g = []
    for rm_cod, df_rm in df_req_all.groupby(['Date', 'rm cod'])['Necesidad_Bruta'].sum().reset_index().groupby('rm cod'):
        stk, cob, lt = obtener_parametros_stock(rm_cod, cob_rm)
            
        serie_erp = pd.Series(0.0, index=df_rm['Date'])
        for idx in df_rm['Date']:
            serie_erp[idx] = cmp_erp.get((rm_cod, idx), 0.0)
        
        plan = calcular_necesidades_netas(df_rm.set_index('Date')['Necesidad_Bruta'], stk, cob, serie_erp)
        plan['Lanzamiento_Pedidos'] = plan['Entradas_Netas'].shift(-lt).fillna(plan['Entradas_Netas'])
        plan['rm cod'] = rm_cod
        plan['rm desc'] = dict_rm_desc.get(rm_cod, str(rm_cod))
        plan['LT_Meses'] = lt
        lista_compras_g.append(plan.reset_index())
        
    return pd.concat(lista_compras_g) if lista_compras_g else pd.DataFrame()


# ==========================================
# FUNCIONES AUXILIARES PARA TABS 9 Y 10
# ==========================================
@st.cache_data(show_spinner=False)
def motor_simulador_whatif(df_f, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, horiz, outl, s_vol, s_pre, s_cos):
    l_base, l_wi = [], []
    for sku in df_f['sku cod'].unique():
        serie = df_f[df_f['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
        fcst = calcular_forecast(limpiar_anomalias(serie) if outl else serie, horiz)
        p, m = dict_p.get(sku, 0), dict_m.get(sku, 0)
        c_base = p - m
        mon = str(dict_c.get(sku, 'EUR')).strip().upper()
        t_fx = f_eur if mon == 'EUR' else (f_dkk if mon == 'DKK' else (f_pln if mon == 'PLN' else 1.0))
        vol = fcst.sum()
        l_base.append({'Revenue': vol * p * t_fx, 'Margin': vol * m * t_fx})
        l_wi.append({
            'Revenue': vol * (1 + s_vol / 100) * p * (1 + s_pre / 100) * t_fx,
            'Margin': vol * (1 + s_vol / 100) * (p * (1 + s_pre / 100) - c_base * (1 + s_cos / 100)) * t_fx
        })
    return pd.DataFrame(l_base), pd.DataFrame(l_wi)


@st.cache_data(show_spinner=False)
def motor_kpis_n12m(df_f, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, outl, max_date_global, horiz=12):
    inicio_fcst = max_date_global.replace(day=1) + pd.DateOffset(months=1)
    rango_futuro = pd.date_range(start=inicio_fcst, periods=horiz, freq="MS")
    
    v_total, r_total, m_total = 0.0, 0.0, 0.0
    
    for sku in df_f['sku cod'].unique():
        serie = df_f[df_f['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum()
        serie_completa = serie.reindex(pd.date_range(start=serie.index.min(), end=max_date_global.replace(day=1), freq="MS"), fill_value=0)
        fcst = calcular_forecast(limpiar_anomalias(serie_completa) if outl else serie_completa, horiz)
        fcst.index = rango_futuro
        
        vol_sku = fcst.sum()
        p, mg = dict_p.get(sku, 0), dict_m.get(sku, 0)
        mon = str(dict_c.get(sku, 'EUR')).strip().upper()
        t_fx = f_eur if mon == 'EUR' else (f_dkk if mon == 'DKK' else (f_pln if mon == 'PLN' else 1.0))
        
        v_total += vol_sku
        r_total += vol_sku * p * t_fx
        m_total += vol_sku * mg * t_fx
        
    return v_total, r_total, m_total


# ==========================================
# PREPARACIÓN DATOS BASE
# ==========================================
df_grouped = df_final.groupby('Date')[col_objetivo].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)
serie_real = df_grouped[col_objetivo] if not df_grouped.empty else pd.Series(dtype=float)
serie_modelo = limpiar_anomalias(serie_real) if usar_limpieza_outliers else serie_real
df_comparativo = pd.DataFrame({"Estadistico": calcular_forecast(serie_modelo, horizonte), "Consenso": calcular_forecast(serie_modelo, horizonte)})
df_comparativo.index.name = 'Date'

ajustes_activos = st.session_state['df_ajustes'].copy() if isinstance(st.session_state.get('df_ajustes'), pd.DataFrame) else pd.DataFrame()
if not ajustes_activos.empty and sku_sel != "TODOS":
    if pais_sel != "TODOS":
        ajustes_activos = ajustes_activos[ajustes_activos['País'] == pais_sel]
    if cliente_sel != "TODOS":
        ajustes_activos = ajustes_activos[ajustes_activos['customer cod'] == cliente_sel]
    ajustes_activos = ajustes_activos[ajustes_activos['sku cod'] == sku_sel]
    if not ajustes_activos.empty:
        ajustes_activos['Date'] = pd.to_datetime(ajustes_activos['Date'], dayfirst=True, errors='coerce')
        for fecha, row in ajustes_activos.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
            if fecha.replace(day=1) in df_comparativo.index:
                df_comparativo.at[fecha.replace(day=1), 'Consenso'] = row['override_value']

LAYOUT_STYLE = dict(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Arial, sans-serif"),
    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e6ed')
)

# ==========================================
# PESTAÑAS (TABS) DEFINIDAS UNA SOLA VEZ
# ==========================================
tab_guia, tab_demanda, tab_prod, tab_bom, tab_cap, tab_fin, tab_ejec, tab_abc, tab_exc, tab_whatif, tab_kpis = st.tabs([
    t["tab0"], t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"], t.get("tab6", "🚀 6. Ejecución ERP"), t.get("tab7", "🔠 7. ABC/XYZ"), t.get("tab8", "🚨 8. Excepciones"), t.get("tab9", "🔀 9. What-If"), t.get("tab10", "📊 10. Dashboard")
])

# ==========================================
# MODULO 0: GUÍA DE USO
# ==========================================
with tab_guia:
    st.header(t["guide_title"])
    st.write(t["guide_desc"])
    st.markdown(f"**{t['g_dem_t']}**: {t['g_dem_d']}")
    st.markdown(f"**{t['g_pro_t']}**: {t['g_pro_d']}")
    st.markdown(f"**{t['g_com_t']}**: {t['g_com_d']}")
    st.markdown(f"**{t['g_cap_t']}**: {t['g_cap_d']}")
    st.markdown(f"**{t['g_fin_t']}**: {t['g_fin_d']}")
    st.markdown(f"**{t['g_erp_t']}**: {t['g_erp_d']}")
    st.markdown("**🔠 7. ABC/XYZ**: Segmentación estratégica cruzando volumen (ABC), volatilidad (XYZ) y racionalización MTS/MTO con ahorro de Working Capital.")
    st.markdown("**🚨 8. Excepciones**: Radar automático para riesgo de roturas (DOH < 15) y excesos (DOH > 60).")
    st.markdown("**🔀 9. What-If**: Simulador financiero interactivo. Estresa volúmenes, precios y costes para evaluar impacto en margen.")

# ==========================================
# MODULO 1: DEMANDA
# ==========================================
with tab_demanda:
    if "tab1" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Demanda.")
    else:
        st.subheader(f"Forecast: {sku_sel}")
        fig_demanda = go.Figure()
        if not df_grouped.empty:
            fig_demanda.add_trace(go.Scatter(x=df_grouped.index, y=serie_real, mode='lines+markers', name='Histórico Real', line=dict(color='#A0B2C6', width=2)))
        fig_demanda.add_trace(go.Scatter(x=df_comparativo.index, y=df_comparativo['Estadistico'], mode='lines', name='Forecast Estadistico', line=dict(color='gray', width=2, dash='dot')))
        fig_demanda.add_trace(go.Scatter(x=df_comparativo.index, y=df_comparativo['Consenso'], mode='lines+markers', name='Forecast Consenso', line=dict(color='#1E3E5B', width=4)))
        
        fig_demanda.update_layout(**LAYOUT_STYLE, hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_demanda, use_container_width=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### Tabla Editable / Edit Forecast")
            df_display = df_comparativo.copy()
            df_display.index = df_display.index.strftime('%Y-%m')
            
            if pais_sel != "TODOS" and cliente_sel != "TODOS" and sku_sel != "TODOS":
                df_editado = st.data_editor(
                    df_display,
                    column_config={
                        "Estadistico": st.column_config.NumberColumn(disabled=True, format="%.2f"),
                        "Consenso": st.column_config.NumberColumn(step=1, format="%.2f")
                    },
                    use_container_width=True
                )
            else:
                st.dataframe(df_display.style.format("{:,.2f}"), use_container_width=True)
                
            st.markdown("---")
            
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if pais_sel != "TODOS" and cliente_sel != "TODOS" and sku_sel != "TODOS":
                    if st.button("💾 Guardar / Save (RAM)", use_container_width=True):
                        if st.session_state['df_ajustes'] is not None:
                            df_aj = st.session_state['df_ajustes'].copy()
                            df_aj = df_aj[~((df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel))]
                            df_mod = df_editado[df_editado['Consenso'] != df_editado['Estadistico']].copy()
                            nuevas_filas = [
                                {'Date': pd.to_datetime(f), 'País': pais_sel, 'customer cod': cliente_sel, 'sku cod': sku_sel, 'override_value': r['Consenso']}
                                for f, r in df_mod.iterrows()
                            ]
                            if nuevas_filas:
                                df_aj = pd.concat([df_aj, pd.DataFrame(nuevas_filas)], ignore_index=True)
                            st.session_state['df_ajustes'] = df_aj
                            st.success("✅ Guardado Temporal en RAM")
                            st.rerun()
                else:
                    st.info("⚠️ Selecciona País, Cliente y SKU para editar.")
                    
            with btn_c2:
                if not st.session_state['df_ajustes'].empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        st.session_state['df_ajustes'].to_excel(writer, index=False, sheet_name='Sheet1')
                    st.download_button(
                        label="📥 Descargar Ajustes (Excel Final)",
                        data=output.getvalue(),
                        file_name="2_Ajustes_Consenso.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
        with col2:
            st.markdown("#### Matrix Forecasting (Macro Factor)")
            pais_macro = st.selectbox("País / Country:", sorted(df['País'].dropna().unique()), key="macro_pais")
            cli_macro = st.selectbox("Cliente / Customer:", sorted(df[df['País'] == pais_macro]['customer cod'].dropna().unique()) if pais_macro else [], key="macro_cli")
            pct_macro = st.number_input("Variation % (e.g. 15, -20):", value=15.0, step=5.0, format="%.1f")
            if st.button("🚀 Apply Macro Factor"):
                if pais_macro and cli_macro:
                    with st.spinner("Processing..."):
                        exito, msg = aplicar_variacion_cliente(pais_macro, cli_macro, pct_macro)
                        if exito:
                            st.success("Done!")
                            st.rerun()
                        else:
                            st.error(msg)

# ==========================================
# MODULO 2: PRODUCCIÓN (MPS)
# ==========================================
with tab_prod:
    if "tab2" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Producción.")
    else:
        if df_stock is None or sku_sel == "TODOS":
            st.info("👈 Upload '3. Stock Actual' file and select a specific SKU in filter 4.")
        else:
            st.subheader(f"Master Production Schedule (MPS): [{sku_sel}] {dict_sku_desc.get(sku_sel, sku_sel)}")
            stock_sku_fg, cob_real_fg, _ = obtener_parametros_stock(sku_sel, cobertura_fg)
            
            serie_erp = pd.Series(0.0, index=df_comparativo.index)
            for idx in df_comparativo.index:
                serie_erp[idx] = dict_prd_erp.get((sku_sel, idx), 0.0)
                
            df_plan_fg = calcular_necesidades_netas(df_comparativo['Consenso'], stock_sku_fg, cob_real_fg, serie_erp)
            
            c1, c2, c3 = st.columns(3)
            c1.metric(t["kpi_fab"], f"{df_plan_fg['Entradas_Netas'].sum():,.0f} Kg")
            c2.metric("ERP Pipeline", f"{df_plan_fg['Recepciones_ERP'].sum():,.0f} Kg")
            c3.metric(t["kpi_doh"], f"{df_plan_fg['DOH'].mean():.0f} Días/Days")
            st.markdown("<br>", unsafe_allow_html=True)
            
            fig_prod = go.Figure()
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Salidas_Brutas'], name='Demanda / Demand', marker_color='#E5E9ED'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Recepciones_ERP'], name='ERP Pipeline', marker_color='#A0B2C6'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Entradas_Netas'], name='Nuevas Órdenes / New Prod', marker_color='#1E3E5B'))
            fig_prod.add_trace(go.Scatter(x=df_plan_fg.index, y=df_plan_fg['Stock_Final'], mode='lines+markers', name=f'Stock FG (Obj: {cob_real_fg}m)', line=dict(color='#88FFBB', width=3)))
            
            fig_prod.update_layout(**LAYOUT_STYLE, barmode='stack', hovermode="x unified")
            st.plotly_chart(fig_prod, use_container_width=True)
            
            df_show_fg = df_plan_fg.copy()
            df_show_fg.index = df_show_fg.index.strftime('%Y-%m')
            st.dataframe(
                df_show_fg.style.format("{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Stock_Objetivo', 'Entradas_Netas', 'Stock_Final'])
                .format("{:.0f}", subset=['DOH'])
                .map(estilo_doh, subset=['DOH']),
                use_container_width=True
            )

# ==========================================
# MODULO 3: COMPRAS (MRP) + PEGGING INTERACTIVO
# ==========================================
with tab_bom:
    if "tab3" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Compras (MRP).")
    else:
        st.subheader("MRP / Purchasing Plan")
        if df_bom is None or df_stock is None:
            st.info("👈 Upload '3. Stock Actual' & '4. BOM' files in the sidebar.")
        else:
            lista_rms = ["TODAS"] + sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist())
            rm_sel = st.selectbox("🔍 Filter Material:", lista_rms)
            
            if st.button("🚀 Execute BOM Explosion"):
                with st.spinner("Processing BOM..."):
                    df_viz = generar_mrp_global()
                    
                    if df_viz is None or df_viz.empty or 'rm cod' not in df_viz.columns:
                        st.warning("⚠️ No se han generado necesidades de compra (comprueba que el Stock y el BOM estén cargados correctamente).")
                    else:
                        if rm_sel != "TODAS":
                            df_viz = df_viz[df_viz['rm cod'] == rm_sel]
                            
                        if df_viz.empty:
                            st.warning("No demand for the selected material.")
                        else:
                            df_viz['MP_Visual'] = "[" + df_viz['rm cod'].astype(str) + "] " + df_viz['rm desc'].fillna('')
                            
                            top_mps = df_viz.groupby('MP_Visual')['Entradas_Netas'].sum().nlargest(9).index
                            df_plot_rm = df_viz[df_viz['MP_Visual'].isin(top_mps)] if rm_sel == "TODAS" else df_viz
                            titulo_graf = "Llegadas a Fábrica - Top 9 Materias Primas Críticas" if rm_sel == "TODAS" else f"Llegadas a Fábrica - {rm_sel}"
                            
                            fig_rm = px.bar(
                                pd.melt(
                                    df_plot_rm,
                                    id_vars=['Date', 'MP_Visual'],
                                    value_vars=['Recepciones_ERP', 'Entradas_Netas'],
                                    var_name='Tipo',
                                    value_name='Volumen'
                                ).replace({'Entradas_Netas': 'Nuevas (Teóricas)', 'Recepciones_ERP': 'ERP (Firme)'}),
                                x='Date', y='Volumen', color='Tipo', facet_col='MP_Visual', facet_col_wrap=3,
                                facet_row_spacing=0.08,
                                title=titulo_graf, barmode='stack',
                                color_discrete_sequence=['#1E3E5B', '#88FFBB']
                            )
                            fig_rm.update_layout(**LAYOUT_STYLE, height=650 if rm_sel == "TODAS" else 400)
                            st.plotly_chart(fig_rm, use_container_width=True)
                            
                            cols_mostrar = ['Date', 'rm cod', 'rm desc', 'LT_Meses', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final', 'DOH']
                            df_show = df_viz[cols_mostrar].copy()
                            df_show['Date'] = pd.to_datetime(df_show['Date']).dt.strftime('%Y-%m')

                            st.dataframe(
                                df_show.reset_index(drop=True).style.format(
                                    "{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final']
                                ).format(
                                    "{:.0f}", subset=['DOH']
                                ).map(estilo_doh, subset=['DOH']),
                                use_container_width=True
                            )

            st.divider()
            st.markdown("### 🔗 Trazabilidad Inversa (Pegging: Materia Prima → Producto Terminado → Margen en Riesgo)")
            st.caption("Selecciona cualquier Materia Prima para identificar qué SKUs dependen de ella, qué clientes los compran y cuánto Revenue/Margen Bruto en GBP está expuesto.")

            lista_rm_pegging = sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist())
            rm_peg_sel = st.selectbox("🧬 Seleccionar Materia Prima para Pegging:", lista_rm_pegging, key="sel_pegging_rm")

            if rm_peg_sel:
                mps_peg = generar_mps_global()
                sub_bom_peg = df_bom[df_bom['rm cod'].astype(str).str.strip() == str(rm_peg_sel).strip()].copy()

                filas_peg = []
                for _, r_b in sub_bom_peg.iterrows():
                    sku_p = str(r_b['sku cod']).strip()
                    dosaje = float(pd.to_numeric(r_b['Cantidad'], errors='coerce')) if pd.notna(r_b['Cantidad']) else 0.0
                    if sku_p in mps_peg and dosaje > 0:
                        df_p_sku = mps_peg[sku_p]
                        fab_total_pt = float((df_p_sku['Entradas_Netas'] + df_p_sku['Recepciones_ERP']).sum())
                        consumo_mp_kg = fab_total_pt * dosaje
                        rev_riesgo_gbp = fab_total_pt * dict_price.get(sku_p, 0.0)
                        mar_riesgo_gbp = fab_total_pt * dict_margin.get(sku_p, 0.0)

                        sub_cli = df[df['sku cod'].astype(str).str.strip() == sku_p]
                        top_clientes = ", ".join(sub_cli['customer desc'].dropna().astype(str).unique()[:3]) if not sub_cli.empty else "Sin histórico"

                        filas_peg.append({
                            "sku cod (PT)": sku_p,
                            "Descripción PT": dict_sku_desc.get(sku_p, sku_p),
                            "Dosificación BOM": dosaje,
                            "Plan Fabricación PT (Kg)": fab_total_pt,
                            "Consumo MP Requerido (Kg)": consumo_mp_kg,
                            "Revenue Expuesto (£)": rev_riesgo_gbp,
                            "Margen Bruto en Riesgo (£)": mar_riesgo_gbp,
                            "Clientes Afectados (Top 3)": top_clientes
                        })

                if not filas_peg:
                    st.info("No hay órdenes de fabricación proyectadas que consuman esta materia prima en el horizonte actual.")
                else:
                    df_pegging = pd.DataFrame(filas_peg).sort_values(by="Margen Bruto en Riesgo (£)", ascending=False).reset_index(drop=True)
                    kp1, kp2, kp3 = st.columns(3)
                    kp1.metric("PTs Dependientes", f"{len(df_pegging)} SKUs")
                    kp2.metric("Consumo Total MP (Horizonte)", f"{df_pegging['Consumo MP Requerido (Kg)'].sum():,.0f} Kg")
                    kp3.metric("Margen Bruto Protegido (£)", f"£ {df_pegging['Margen Bruto en Riesgo (£)'].sum():,.0f}")

                    st.dataframe(
                        df_pegging.style.format({
                            "Dosificación BOM": "{:.4f}",
                            "Plan Fabricación PT (Kg)": "{:,.0f} Kg",
                            "Consumo MP Requerido (Kg)": "{:,.0f} Kg",
                            "Revenue Expuesto (£)": "£ {:,.0f}",
                            "Margen Bruto en Riesgo (£)": "£ {:,.0f}"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

# ==========================================
# MODULO 4: CAPACIDAD (RCCP)
# ==========================================
with tab_cap:
    if "tab4" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Capacidad.")
    else:
        st.subheader("Capacity Planning (RCCP)")
        if df_rutas is None or df_cal is None:
            st.info("👈 Upload '5. Rutas / Routing' & '6. Calendario' in the sidebar.")
        else:
            lista_maquinas = ["TODOS"] + sorted(df_rutas['Maquina'].dropna().astype(str).unique().tolist())
            maq_sel = st.selectbox("⚙️ Filter Line / Línea:", lista_maquinas)
            
            if st.button("⚖️ Calculate Saturation"):
                with st.spinner("Processing..."):
                    mps_g = generar_mps_global()
                    if mps_g:
                        df_mps_concat = pd.concat(mps_g.values()).rename_axis('Date').reset_index()
                        df_mps_concat['Carga_Total_Kg'] = df_mps_concat['Entradas_Netas'] + df_mps_concat['Recepciones_ERP']
                        df_mps_pos = df_mps_concat[df_mps_concat['Carga_Total_Kg'] > 0].copy()

                        df_rutas_clean = df_rutas.copy()
                        df_rutas_clean['sku cod'] = df_rutas_clean['sku cod'].astype(str).str.strip()
                        df_mps_pos['sku cod'] = df_mps_pos['sku cod'].astype(str).str.strip()

                        df_req = pd.merge(df_mps_pos, df_rutas_clean, on='sku cod', how='inner')

                        if df_req.empty:
                            st.warning("⚠️ Ningún SKU con necesidad de producción cruza con la tabla '5. Rutas / Routing'.")
                        else:
                            df_req['Kilos_por_Hora'] = pd.to_numeric(df_req['Kilos_por_Hora'], errors='coerce').fillna(1).replace(0, 1)
                            df_req['Horas_Necesarias'] = df_req['Carga_Total_Kg'] / df_req['Kilos_por_Hora']

                            df_cal_clean = df_cal.copy()
                            df_cal_clean['Date'] = pd.to_datetime(df_cal_clean['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
                            df_cal_clean['Horas_Disponibles'] = pd.to_numeric(df_cal_clean['Horas_Disponibles'], errors='coerce').fillna(740).replace(0, 1)
                            df_req['Date'] = pd.to_datetime(df_req['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()

                            if maq_sel == "TODOS":
                                df_capacidad = pd.merge(
                                    df_req.groupby(['Date', 'Maquina'])['Horas_Necesarias'].sum().reset_index(),
                                    df_cal_clean,
                                    on=['Date', 'Maquina'],
                                    how='left'
                                ).fillna({'Horas_Disponibles': 740})
                                
                                df_capacidad['Utilizacion'] = (df_capacidad['Horas_Necesarias'] / df_capacidad['Horas_Disponibles']) * 100
                                df_pivot = df_capacidad.pivot(index='Maquina', columns='Date', values='Utilizacion').fillna(0)
                                df_pivot.columns = pd.to_datetime(df_pivot.columns).strftime('%Y-%m')
                                
                                st.markdown("#### % Utilización / Utilization")
                                try:
                                    st.dataframe(df_pivot.style.background_gradient(cmap='RdYlGn_r', vmin=0, vmax=120).format("{:.1f}%"), use_container_width=True)
                                except Exception:
                                    st.dataframe(df_pivot.style.format("{:.1f}%"), use_container_width=True)
                            else:
                                df_req_maq = df_req[df_req['Maquina'] == maq_sel]
                                if not df_req_maq.empty:
                                    fig_cap = px.bar(
                                        df_req_maq.groupby(['Date', 'sku desc'])['Horas_Necesarias'].sum().reset_index(),
                                        x='Date',
                                        y='Horas_Necesarias',
                                        color='sku desc',
                                        title=f"Carga vs Capacidad: {maq_sel}"
                                    )
                                    df_cal_maq = df_cal_clean[df_cal_clean['Maquina'] == maq_sel]
                                    merged_line = pd.merge(
                                        df_req_maq.groupby('Date')['Horas_Necesarias'].sum().reset_index(),
                                        df_cal_maq,
                                        on='Date',
                                        how='left'
                                    ).fillna({'Horas_Disponibles': 740})
                                    
                                    fig_cap.add_trace(go.Scatter(
                                        x=merged_line['Date'],
                                        y=merged_line['Horas_Disponibles'],
                                        mode='lines',
                                        name='Max Hours',
                                        line=dict(color='red', width=3, dash='dash')
                                    ))
                                    fig_cap.update_layout(**LAYOUT_STYLE, yaxis_title="Horas", barmode='stack', colorway=['#1E3E5B', '#88FFBB', '#A0B2C6'])
                                    st.plotly_chart(fig_cap, use_container_width=True)
                                else:
                                    st.warning(f"No hay demanda asignada para la línea: {maq_sel}")

# ==========================================
# MODULO 5: FINANZAS
# ==========================================
with tab_fin:
    if "tab5" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Finanzas.")
    else:
        st.subheader("Financial Valuation & Working Capital (GBP)")
        if not dict_price:
            st.warning("⚠️ No 'revenue' or 'margin' columns in history.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                nivel_pl = st.selectbox("📊 Level of Analysis:", ["Consolidado Global", "Por País", "Por Cliente", "Por SKU"])
                filtro_pl = None
                if nivel_pl == "Por País":
                    filtro_pl = st.selectbox("Country:", sorted(df['País'].dropna().unique()))
                elif nivel_pl == "Por Cliente":
                    filtro_pl = st.selectbox("Customer:", sorted(df['customer cod'].dropna().unique()))
                elif nivel_pl == "Por SKU":
                    filtro_pl = st.selectbox("SKU:", sorted(df['sku cod'].dropna().unique()))
            with col2:
                vista_wc = st.selectbox("📦 Working Capital View:", ["Total (PT + MP)", "Producto Terminado (PT)", "Materia Prima (MP)"])
                
            if st.button("📈 Calculate Finance"):
                with st.spinner("Processing P&L (Optimized)..."):
                    if nivel_pl == "Por País":
                        df_fin_target = df[df['País'] == filtro_pl]
                        group_cols = ['País', 'sku cod']
                    elif nivel_pl == "Por Cliente":
                        df_fin_target = df[df['customer cod'] == filtro_pl]
                        group_cols = ['customer cod', 'sku cod']
                    elif nivel_pl == "Por SKU":
                        df_fin_target = df[df['sku cod'] == filtro_pl]
                        group_cols = ['sku cod']
                    else:
                        df_fin_target = df
                        group_cols = ['sku cod']

                    lista_pl = []
                    for keys, df_grupo in df_fin_target.groupby(group_cols):
                        sku = keys[-1] if isinstance(keys, tuple) else keys
                        pais = keys[0] if nivel_pl == "Por País" else "Varios"
                        cli = keys[0] if nivel_pl == "Por Cliente" else "Varios"

                        df_hist = df_grupo.groupby('Date')[['Rev_GBP', 'Mar_GBP']].sum().resample("MS").sum().fillna(0).reset_index()
                        df_hist = df_hist.rename(columns={'Rev_GBP': 'Revenue_GBP', 'Mar_GBP': 'Margin_GBP'})
                        df_hist['País'], df_hist['Cliente'], df_hist['SKU'] = pais, cli, sku
                        lista_pl.append(df_hist)

                        serie_vol = df_grupo.groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
                        df_fcst = pd.DataFrame({'Consenso': calcular_forecast(limpiar_anomalias(serie_vol) if usar_limpieza_outliers else serie_vol, horizonte)})
                        
                        aj_filtro = st.session_state['df_ajustes']
                        if nivel_pl == "Por País":
                            aj_filtro = aj_filtro[(aj_filtro['País'] == filtro_pl) & (aj_filtro['sku cod'] == sku)]
                        elif nivel_pl == "Por Cliente":
                            aj_filtro = aj_filtro[(aj_filtro['customer cod'] == filtro_pl) & (aj_filtro['sku cod'] == sku)]
                        else:
                            aj_filtro = aj_filtro[aj_filtro['sku cod'] == sku]

                        if not aj_filtro.empty:
                            aj_filtro = aj_filtro.copy()
                            aj_filtro['Date'] = pd.to_datetime(aj_filtro['Date'], dayfirst=True, errors='coerce')
                            for f, r in aj_filtro.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
                                if f.replace(day=1) in df_fcst.index:
                                    df_fcst.at[f.replace(day=1), 'Consenso'] = r['override_value']
                        
                        precio, margen = dict_price.get(sku, 0), dict_margin.get(sku, 0)
                        df_res = pd.DataFrame({
                            'Date': df_fcst.index, 'País': pais, 'Cliente': cli, 'SKU': sku,
                            'Revenue_GBP': df_fcst['Consenso'].values * precio,
                            'Margin_GBP': df_fcst['Consenso'].values * margen
                        })
                        lista_pl.append(df_res)
                        
                    df_plot_pl = pd.concat(lista_pl) if lista_pl else pd.DataFrame()
                    skus_validos = df_fin_target['sku cod'].unique()
                    titulo_estrategico = filtro_pl if nivel_pl != "Consolidado Global" else "Consolidado Global"
                    
                    if not df_plot_pl.empty:
                        df_plot_pl = df_plot_pl.groupby('Date')[['Revenue_GBP', 'Margin_GBP']].sum().reset_index()
                    
                    mps_g = generar_mps_global()
                    lista_wc_pt = [
                        pd.DataFrame({
                            'Date': mps_g[sku].index,
                            'Elemento': sku,
                            'WorkingCapital_GBP': mps_g[sku]['Stock_Final'].values * max(0.0, dict_price.get(sku, 0) - dict_margin.get(sku, 0)),
                            'Categoria': 'Producto Terminado'
                        })
                        for sku in mps_g if sku in skus_validos
                    ]
                    df_wc_pt_filtrado = pd.concat(lista_wc_pt) if lista_wc_pt else pd.DataFrame()
                    
                    df_mrp = generar_mrp_global()
                    lista_wc_mp = []
                    if not df_mrp.empty and df_stock is not None:
                        for rm_cod, df_rm in df_mrp.groupby('rm cod'):
                            coste_rm_serie = df_stock.loc[df_stock['sku cod'] == rm_cod, 'Coste_Unitario'].values
                            val_coste = float(coste_rm_serie[0]) if len(coste_rm_serie) > 0 and pd.notna(coste_rm_serie[0]) else 0.0
                            lista_wc_mp.append(pd.DataFrame({
                                'Date': df_rm['Date'],
                                'Elemento': rm_cod,
                                'WorkingCapital_GBP': df_rm['Stock_Final'].values * val_coste * fx_eur_gbp,
                                'Categoria': 'Materia Prima'
                            }))
                    
                    df_wc_mp = pd.concat(lista_wc_mp) if lista_wc_mp else pd.DataFrame()
                    rms_validos = df_bom[df_bom['sku cod'].isin(skus_validos)]['rm cod'].unique() if (df_bom is not None and not df_bom.empty) else []
                    df_wc_mp_filtrado = df_wc_mp[df_wc_mp['Elemento'].isin(rms_validos)] if not df_wc_mp.empty else pd.DataFrame()
                    df_wc_total = pd.concat([df_wc_pt_filtrado, df_wc_mp_filtrado]) if not df_wc_pt_filtrado.empty or not df_wc_mp_filtrado.empty else pd.DataFrame()

                    if df_stock is None or df_stock.empty:
                        df_plot_pl['WC_PT_GBP'] = 0
                        df_plot_pl['WC_MP_GBP'] = 0
                        df_plot_pl['WC_Total_GBP'] = 0
                        df_wc_total = pd.DataFrame()
                    
                    if not df_wc_total.empty and not df_plot_pl.empty:
                        df_wc_pivot = df_wc_total.pivot_table(index='Date', columns='Categoria', values='WorkingCapital_GBP', aggfunc='sum').reset_index().fillna(0)
                        if 'Producto Terminado' not in df_wc_pivot.columns:
                            df_wc_pivot['Producto Terminado'] = 0
                        if 'Materia Prima' not in df_wc_pivot.columns:
                            df_wc_pivot['Materia Prima'] = 0
                        df_plot_pl = pd.merge(
                            df_plot_pl,
                            df_wc_pivot.rename(columns={'Producto Terminado': 'WC_PT_GBP', 'Materia Prima': 'WC_MP_GBP'})[['Date', 'WC_PT_GBP', 'WC_MP_GBP']],
                            on='Date', how='left'
                        ).fillna(0)
                        df_plot_pl['WC_Total_GBP'] = df_plot_pl['WC_PT_GBP'] + df_plot_pl['WC_MP_GBP']
                    elif not df_plot_pl.empty:
                        df_plot_pl['WC_PT_GBP'], df_plot_pl['WC_MP_GBP'], df_plot_pl['WC_Total_GBP'] = 0, 0, 0

                    if not df_plot_pl.empty:
                        tot_rev = df_plot_pl['Revenue_GBP'].sum()
                        tot_mar = df_plot_pl['Margin_GBP'].sum()
                        mar_pct = (tot_mar / tot_rev * 100) if tot_rev > 0 else 0
                        avg_wc = df_plot_pl['WC_Total_GBP'].mean()
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric(t["kpi_rev"], f"£ {tot_rev:,.0f}")
                        c2.metric(t["kpi_mar"], f"£ {tot_mar:,.0f} ({mar_pct:.1f}%)")
                        c3.metric(t["kpi_wc"], f"£ {avg_wc:,.0f}")
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        fig_pl = go.Figure()
                        fig_pl.add_trace(go.Bar(x=df_plot_pl['Date'], y=df_plot_pl['Revenue_GBP'], name='Revenue', marker_color='#1E3E5B'))
                        fig_pl.add_trace(go.Scatter(x=df_plot_pl['Date'], y=df_plot_pl['Margin_GBP'], name='Margen Bruto', mode='lines+markers', line=dict(color='#88FFBB', width=4)))
                        fig_pl.update_layout(**LAYOUT_STYLE, title=f"Revenue & Margin: {titulo_estrategico} (GBP)", yaxis_title="GBP (£)", hovermode="x unified")
                        st.plotly_chart(fig_pl, use_container_width=True)

                        if vista_wc == "Total (PT + MP)" and not df_wc_total.empty:
                            fig_wc = px.area(df_wc_total.groupby(['Date', 'Categoria'])['WorkingCapital_GBP'].sum().reset_index(), x='Date', y='WorkingCapital_GBP', color='Categoria', title=f"Working Capital: {titulo_estrategico}", color_discrete_sequence=['#88FFBB', '#1E3E5B'])
                            st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)
                        elif vista_wc == "Producto Terminado (PT)" and not df_wc_pt_filtrado.empty:
                            fig_wc = px.area(df_wc_pt_filtrado, x='Date', y='WorkingCapital_GBP', color='Elemento', title=f"WC (PT): {titulo_estrategico}", color_discrete_sequence=px.colors.sequential.Blues_r)
                            st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)
                        elif vista_wc == "Materia Prima (MP)" and not df_wc_mp_filtrado.empty:
                            fig_wc = px.area(df_wc_mp_filtrado, x='Date', y='WorkingCapital_GBP', color='Elemento', title=f"WC (MP): {titulo_estrategico}", color_discrete_sequence=px.colors.sequential.Mint_r)
                            st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)
                                
                        df_plot_pl.set_index('Date', inplace=True)
                        df_plot_pl.index = df_plot_pl.index.strftime('%Y-%m')
                        st.dataframe(
                            df_plot_pl.rename(columns={"Revenue_GBP": "Revenue (£)", "Margin_GBP": "Margin (£)", "WC_PT_GBP": "WC PT (£)", "WC_MP_GBP": "WC MP (£)", "WC_Total_GBP": "Total WC (£)"})
                            .style.format({c: "£ {:,.0f}" for c in ["Revenue (£)", "Margin (£)", "WC PT (£)", "WC MP (£)", "Total WC (£)"]}),
                            use_container_width=True
                        )

# ==========================================
# MODULO 6: EJECUCIÓN ERP + MASTER PACK EXCEL
# ==========================================
with tab_ejec:
    if "tab6" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Ejecución ERP.")
    else:
        st.subheader("🚀 Plan de Ejecución Inmediata (Lanzamientos al ERP)")
        mps_exec = generar_mps_global()
        mrp_exec = generar_mrp_global()

        if not mps_exec:
            st.warning("⚠️ Carga primero el histórico de ventas para calcular el plan de ejecución.")
        else:
            df_mps_all = pd.concat(mps_exec.values()).rename_axis('Date').reset_index()
            df_mps_all['Date'] = pd.to_datetime(df_mps_all['Date'])
            fechas_disp = sorted(df_mps_all['Date'].unique())
            hoy_mes = pd.Timestamp.today().replace(day=1)
            mes_objetivo = hoy_mes if hoy_mes in fechas_disp else fechas_disp[0]
            base_date = pd.to_datetime(mes_objetivo)

            st.info(f"📅 **Mes Objetivo de Ejecución (Nuevos Lanzamientos):** {base_date.strftime('%Y-%m')}")

            st.markdown("### 🏭 NUEVAS Órdenes de Fabricación a lanzar en el ERP")
            df_fab_lanzar = df_mps_all[(df_mps_all['Date'] == mes_objetivo) & (df_mps_all['Entradas_Netas'] > 0)].copy()

            if df_fab_lanzar.empty:
                st.success("✅ Todo cubierto. No necesitas lanzar nuevas órdenes de PT para el Mes 1.")
            else:
                dias_autonomia_pt = np.where(
                    df_fab_lanzar['Salidas_Brutas'] > 0,
                    ((df_fab_lanzar['Stock_Inicial'] + df_fab_lanzar['Recepciones_ERP']) / df_fab_lanzar['Salidas_Brutas']) * 30,
                    0
                )
                offset_dias_pt = np.clip(np.floor(dias_autonomia_pt) - 5, 0, 27).astype(int)
                df_fab_lanzar['Fecha_Lanzamiento'] = [
                    (base_date + pd.Timedelta(days=int(d))).strftime('%Y-%m-%d') for d in offset_dias_pt
                ]

                cols_fab = ['sku cod', 'sku desc', 'Fecha_Lanzamiento', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Stock_Final', 'DOH']
                df_fab_lanzar = df_fab_lanzar[cols_fab].sort_values(by=['Fecha_Lanzamiento', 'Entradas_Netas'], ascending=[True, False]).reset_index(drop=True)
                
                st.dataframe(
                    df_fab_lanzar.style.format({
                        'Salidas_Brutas': '{:,.0f} Kg',
                        'Stock_Inicial': '{:,.0f} Kg',
                        'Recepciones_ERP': '{:,.0f} Kg',
                        'Entradas_Netas': '{:,.0f} Kg',
                        'Stock_Final': '{:,.0f} Kg',
                        'DOH': '{:.0f}'
                    }).map(estilo_doh, subset=['DOH']),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("### 🛒 NUEVOS Pedidos de Compra a lanzar a Proveedores")
            df_cmp_lanzar = pd.DataFrame()
            if mrp_exec is None or mrp_exec.empty:
                st.info("👈 Carga el archivo de BOM y Stock para calcular los lanzamientos de compra.")
            else:
                col_lanz = 'Lanzamiento_Pedidos' if 'Lanzamiento_Pedidos' in mrp_exec.columns else 'Entradas_Netas'
                df_cmp_lanzar = mrp_exec[(mrp_exec['Date'] == mes_objetivo) & (mrp_exec[col_lanz] > 0)].copy()

                if df_cmp_lanzar.empty:
                    st.success("✅ Todo cubierto. No necesitas emitir nuevos pedidos de Materia Prima para el Mes 1.")
                else:
                    dias_autonomia_rm = np.where(
                        df_cmp_lanzar['Salidas_Brutas'] > 0,
                        ((df_cmp_lanzar['Stock_Inicial'] + df_cmp_lanzar['Recepciones_ERP']) / df_cmp_lanzar['Salidas_Brutas']) * 30,
                        0
                    )
                    offset_dias_rm = np.clip(np.floor(dias_autonomia_rm) - 7, 0, 27).astype(int)
                    df_cmp_lanzar['Fecha_Lanzamiento'] = [
                        (base_date + pd.Timedelta(days=int(d))).strftime('%Y-%m-%d') for d in offset_dias_rm
                    ]

                    cols_cmp = [c for c in ['rm cod', 'rm desc', 'Fecha_Lanzamiento', 'LT_Meses', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final', 'DOH'] if c in df_cmp_lanzar.columns]
                    df_cmp_lanzar = df_cmp_lanzar[cols_cmp].sort_values(by=['Fecha_Lanzamiento', col_lanz], ascending=[True, False]).reset_index(drop=True)
                    
                    fmt_dict = {c: '{:,.0f} Kg' for c in ['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final'] if c in df_cmp_lanzar.columns}
                    if 'DOH' in df_cmp_lanzar.columns:
                        fmt_dict['DOH'] = '{:.0f}'
                    
                    styler_cmp = df_cmp_lanzar.style.format(fmt_dict)
                    if 'DOH' in df_cmp_lanzar.columns:
                        styler_cmp = styler_cmp.map(estilo_doh, subset=['DOH'])
                        
                    st.dataframe(styler_cmp, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("### 📦 Exportar Master Pack S&OP Corporativo (Multi-Pestaña)")
            st.caption("Descarga en un único libro Excel el Plan Maestro de Producción (MPS), el Plan de Compras (MRP), las Órdenes a Lanzar en M1 y la Segmentación ABC/XYZ.")

            buf_master = io.BytesIO()
            with pd.ExcelWriter(buf_master, engine="openpyxl") as writer:
                df_mps_export = df_mps_all.copy()
                df_mps_export['Date'] = pd.to_datetime(df_mps_export['Date']).dt.strftime('%Y-%m')
                df_mps_export.to_excel(writer, index=False, sheet_name="1_MPS_Produccion")

                if mrp_exec is not None and not mrp_exec.empty:
                    df_mrp_export = mrp_exec.copy()
                    df_mrp_export['Date'] = pd.to_datetime(df_mrp_export['Date']).dt.strftime('%Y-%m')
                    df_mrp_export.to_excel(writer, index=False, sheet_name="2_MRP_Compras")

                if not df_fab_lanzar.empty:
                    df_fab_lanzar.to_excel(writer, index=False, sheet_name="3_Lanzar_ERP_PT_M1")

                if not df_cmp_lanzar.empty:
                    df_cmp_lanzar.to_excel(writer, index=False, sheet_name="4_Lanzar_PO_MP_M1")

                if df_abcxyz_global is not None and not df_abcxyz_global.empty:
                    df_abcxyz_global.to_excel(writer, index=False, sheet_name="5_Segmentacion_ABC_XYZ")

            st.download_button(
                label="📥 Descargar Master Pack S&OP Completo (.xlsx)",
                data=buf_master.getvalue(),
                file_name=f"Master_Pack_SOP_{base_date.strftime('%Y_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )

# ==========================================
# MODULO 7: ABC / XYZ + OPTIMIZADOR MTO/MTS
# ==========================================
with tab_abc:
    if "tab7" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder a la segmentación ABC/XYZ.")
    else:
        st.subheader("🔠 Segmentación Estratégica ABC / XYZ")
        
        if df_abcxyz_global is not None and not df_abcxyz_global.empty:
            df_abcxyz_show = df_abcxyz_global.copy()
            if 'sku desc' not in df_abcxyz_show.columns:
                df_abcxyz_show['sku desc'] = df_abcxyz_show['sku cod'].map(dict_sku_desc).fillna(df_abcxyz_show['sku cod'].astype(str))
            
            if dict_margin:
                st.markdown("### 🫧 Matriz de Riesgo vs Rentabilidad")
                st.markdown("Identifica visualmente las 'Estrellas' (rentables y estables) frente a los 'Tóxicos' (bajo margen y altamente erráticos).")
                
                df_abcxyz_show['Margen Unitario'] = df_abcxyz_show['sku cod'].map(dict_margin).replace([np.inf, -np.inf], 0).fillna(0.0)
                df_plot = df_abcxyz_show[df_abcxyz_show['volume'] > 0].copy()
                df_plot['CV'] = pd.to_numeric(df_plot['CV'], errors='coerce').replace([np.inf, -np.inf], 0).fillna(0.0)
                df_plot['Margen Unitario'] = pd.to_numeric(df_plot['Margen Unitario'], errors='coerce').replace([np.inf, -np.inf], 0).fillna(0.0)
                df_plot['volume'] = pd.to_numeric(df_plot['volume'], errors='coerce').fillna(1.0).clip(lower=1.0)
                df_plot['sku desc'] = df_plot['sku desc'].fillna(df_plot['sku cod'].astype(str)).astype(str)
                
                if not df_plot.empty:
                    fig_bubble = px.scatter(
                        df_plot, x='CV', y='Margen Unitario', size='volume', color='Clase', hover_name='sku desc',
                        hover_data={'sku cod': True, 'CV': ':.2f', 'Margen Unitario': ':.2f', 'volume': ':,.0f', 'Clase': False},
                        labels={"CV": "Riesgo / Volatilidad (CV)", "Margen Unitario": "Margen Bruto Unitario (£)", "volume": "Volumen (Kg)"},
                        size_max=45, color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig_bubble.add_vline(x=0.5, line_width=1, line_dash="dash", line_color="gray", annotation_text="X | Y")
                    fig_bubble.add_vline(x=1.0, line_width=1, line_dash="dash", line_color="gray", annotation_text="Y | Z")
                    margen_medio = float(df_plot['Margen Unitario'].median())
                    fig_bubble.add_hline(y=margen_medio, line_width=1, line_dash="dash", line_color="gray", annotation_text="Margen Medio")
                    fig_bubble.update_layout(plot_bgcolor='white', height=500, margin=dict(l=20, r=20, t=30, b=20))
                    fig_bubble.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                    fig_bubble.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                    
                    st.plotly_chart(fig_bubble, use_container_width=True)
                    st.info("👈 **Cuadrante Superior Izquierdo:** Estrellas (Alto Margen, Demanda Estable). 👉 **Cuadrante Inferior Derecho:** Tóxicos (Bajo Margen, Demanda Errática).")
                    st.divider()

            col_mat1, col_mat2 = st.columns([1, 2])
            with col_mat1:
                st.markdown("#### Distribución de SKUs")
                resumen_matriz = df_abcxyz_show.groupby(['ABC', 'XYZ'])['sku cod'].count().unstack().fillna(0).astype(int)
                resumen_matriz = resumen_matriz.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0)
                st.dataframe(resumen_matriz.style.background_gradient(cmap='Blues'), use_container_width=True)
                
            with col_mat2:
                st.markdown("#### Detalle de Clasificación")
                filtro_clase = st.multiselect("Filtrar por Clase (ej. AX, CZ):", sorted(df_abcxyz_show['Clase'].unique()))
                df_show_abc = df_abcxyz_show if not filtro_clase else df_abcxyz_show[df_abcxyz_show['Clase'].isin(filtro_clase)]

                st.dataframe(
                    df_show_abc[['sku cod', 'sku desc', 'Clase', 'volume', 'CV', 'Margen Unitario']]
                    .rename(columns={'volume': 'Volumen', 'CV': 'Volatilidad (CV)'})
                    .style.format({"Volumen": "{:,.0f}", "Volatilidad (CV)": "{:.2f}", "Margen Unitario": "{:.2f}"}),
                    use_container_width=True
                )

            st.divider()
            st.markdown("### 💡 Optimizador Estratégico de Inventario (Racionalización MTS vs. MTO)")
            st.caption("Cruza la volatilidad/volumen (ABC/XYZ) con tu archivo '3. Stock Actual' para detectar SKUs erráticos (CZ, BZ, CY) configurados como MTS y cuantificar cuánta caja (£) liberarías pasándolos a Make-to-Order (MTO).")

            if df_stock is None or df_stock.empty:
                st.info("👈 Sube el archivo '3. Stock Actual' para auditar la política MTO/MTS y cuantificar el ahorro de Working Capital.")
            else:
                df_audit = pd.merge(
                    df_abcxyz_show[['sku cod', 'sku desc', 'ABC', 'XYZ', 'Clase', 'volume', 'CV', 'Margen Unitario']],
                    df_stock[['sku cod', 'stock_disponible', 'Cobertura_Meses', 'Categoria', 'Coste_Unitario']].drop_duplicates(subset=['sku cod']),
                    on='sku cod',
                    how='inner'
                )

                if df_audit.empty:
                    st.info("No hay cruce entre los SKUs del histórico de ventas y la tabla de Stock Actual.")
                else:
                    df_audit['Categoria_Actual'] = df_audit['Categoria'].astype(str).str.strip().str.upper()
                    df_audit['Coste_Unitario'] = pd.to_numeric(df_audit['Coste_Unitario'], errors='coerce').fillna(0.0)
                    df_audit['stock_disponible'] = pd.to_numeric(df_audit['stock_disponible'], errors='coerce').fillna(0.0)
                    df_audit['Cobertura_Meses'] = pd.to_numeric(df_audit['Cobertura_Meses'], errors='coerce').fillna(0.0)

                    condiciones_pol = [
                        df_audit['Clase'].isin(['AX', 'AY', 'BX']),
                        df_audit['Clase'].isin(['CZ', 'BZ', 'CY', 'CX'])
                    ]
                    opciones_pol = ['MTS', 'MTO']
                    df_audit['Politica_Recomendada'] = np.select(condiciones_pol, opciones_pol, default='MTS (Cobertura Mínima)')

                    df_audit['Estado_Auditoria'] = np.where(
                        (df_audit['Politica_Recomendada'] == 'MTO') & (df_audit['Categoria_Actual'] == 'MTS'),
                        '🔴 Cambiar MTS → MTO (Liberar Caja)',
                        np.where(
                            (df_audit['Politica_Recomendada'] == 'MTS') & (df_audit['Categoria_Actual'] == 'MTO'),
                            '🟠 Pasar MTO → MTS (Proteger Servicio)',
                            '🟢 Alineado'
                        )
                    )

                    df_audit['WC_Actual_GBP'] = df_audit['stock_disponible'] * df_audit['Coste_Unitario'] * fx_eur_gbp
                    df_audit['WC_Liberable_GBP'] = np.where(
                        df_audit['Estado_Auditoria'] == '🔴 Cambiar MTS → MTO (Liberar Caja)',
                        df_audit['WC_Actual_GBP'],
                        0.0
                    )

                    df_desalineados = df_audit[df_audit['Estado_Auditoria'] != '🟢 Alineado'].sort_values(by='WC_Liberable_GBP', ascending=False).reset_index(drop=True)

                    ca1, ca2, ca3 = st.columns(3)
                    ca1.metric("SKUs Auditados en Stock", f"{len(df_audit)}")
                    ca2.metric("SKUs Desalineados (MTS/MTO)", f"{len(df_desalineados)}")
                    ca3.metric("Working Capital Liberable (£)", f"£ {df_audit['WC_Liberable_GBP'].sum():,.0f}")

                    solo_alertas = st.checkbox("🔍 Mostrar solo SKUs con recomendación de cambio (MTS ↔ MTO)", value=True)
                    df_mostrar_audit = df_desalineados if solo_alertas else df_audit.sort_values(by='WC_Liberable_GBP', ascending=False).reset_index(drop=True)

                    st.dataframe(
                        df_mostrar_audit[[
                            'sku cod', 'sku desc', 'Clase', 'CV', 'Categoria_Actual',
                            'Politica_Recomendada', 'Estado_Auditoria', 'stock_disponible',
                            'WC_Actual_GBP', 'WC_Liberable_GBP'
                        ]].rename(columns={
                            'Categoria_Actual': 'Política Actual',
                            'Politica_Recomendada': 'Política Sugerida',
                            'Estado_Auditoria': 'Diagnóstico S&OP',
                            'stock_disponible': 'Stock Actual (Kg)',
                            'WC_Actual_GBP': 'WC Actual (£)',
                            'WC_Liberable_GBP': 'Ahorro WC Potencial (£)'
                        }).style.format({
                            'CV': '{:.2f}',
                            'Stock Actual (Kg)': '{:,.0f} Kg',
                            'WC Actual (£)': '£ {:,.0f}',
                            'Ahorro WC Potencial (£)': '£ {:,.0f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

# ==========================================
# MODULO 8: EXCEPCIONES
# ==========================================
with tab_exc:
    if "tab8" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al Panel de Excepciones.")
    else:
        st.subheader("🚨 Panel de Excepciones (Management by Exception)")
        st.caption("Radar automático de **roturas inminentes** (DOH < 15 días) y **excesos de inventario / reprogramaciones ERP** (DOH > 60 días) para el próximo ciclo.")

        mps_exc = generar_mps_global()
        mrp_exc = generar_mrp_global()

        if not mps_exc:
            st.warning("⚠️ Carga primero el histórico de ventas.")
        else:
            df_mps_all = pd.concat(mps_exc.values()).rename_axis('Date').reset_index()
            df_mps_all['Date'] = pd.to_datetime(df_mps_all['Date'])
            fechas_disp = sorted(df_mps_all['Date'].unique())
            hoy_mes = pd.Timestamp.today().replace(day=1)
            mes_m1 = hoy_mes if hoy_mes in fechas_disp else fechas_disp[0]

            col_pt, col_mp = st.columns(2)

            with col_pt:
                st.markdown("### 📦 Producto Terminado")
                df_pt_m1 = df_mps_all[
                    (df_mps_all['Date'] == mes_m1) &
                    ((df_mps_all['DOH'] < 15) | (df_mps_all['DOH'] > 60))
                ].copy()

                if df_pt_m1.empty:
                    st.success("✅ Sin alertas para M1.")
                else:
                    df_pt_m1['Tipo_Alerta'] = np.where(
                        df_pt_m1['DOH'] < 15,
                        '🔴 Riesgo Rotura (<15d)',
                        '🟠 Sobrestock / Exceso ERP (>60d)'
                    )
                    df_pt_m1['Accion_Sugerida'] = np.where(
                        df_pt_m1['DOH'] < 15,
                        '⚡ Priorizar / Subir Cobertura',
                        np.where(df_pt_m1['Recepciones_ERP'] > df_pt_m1['Salidas_Brutas'], '✂️ Posponer Orden ERP', '📉 Drenar Stock')
                    )
                    cols_show_pt = ['sku cod', 'sku desc', 'Tipo_Alerta', 'DOH', 'Stock_Final', 'Recepciones_ERP', 'Accion_Sugerida']
                    df_pt_m1 = df_pt_m1[cols_show_pt].sort_values(by='DOH', ascending=True).reset_index(drop=True)

                    st.dataframe(
                        df_pt_m1.style.format({
                            'DOH': '{:.0f} d',
                            'Stock_Final': '{:,.0f} Kg',
                            'Recepciones_ERP': '{:,.0f} Kg'
                        }).map(estilo_doh, subset=['DOH']),
                        use_container_width=True,
                        hide_index=True
                    )

            with col_mp:
                st.markdown("### 🧩 Materias Primas")
                if mrp_exc is None or mrp_exc.empty:
                    st.info("👈 Carga el BOM y Stock para evaluar alertas de MP.")
                else:
                    mrp_exc['Date'] = pd.to_datetime(mrp_exc['Date'])
                    df_mp_m1 = mrp_exc[
                        (mrp_exc['Date'] == mes_m1) &
                        ((mrp_exc['DOH'] < 15) | (mrp_exc['DOH'] > 60))
                    ].copy()

                    if df_mp_m1.empty:
                        st.success("✅ Sin alertas para M1.")
                    else:
                        df_mp_m1['Tipo_Alerta'] = np.where(
                            df_mp_m1['DOH'] < 15,
                            '🔴 Riesgo Rotura (<15d)',
                            '🟠 Exceso PO / Sobrestock (>60d)'
                        )
                        df_mp_m1['Accion_Sugerida'] = np.where(
                            df_mp_m1['DOH'] < 15,
                            '⚡ Urgencia a Proveedor',
                            np.where(df_mp_m1['Recepciones_ERP'] > df_mp_m1['Salidas_Brutas'], '✂️ Reprogramar PO ERP', '📉 Reducir Lote')
                        )
                        cols_show_mp = ['rm cod', 'rm desc', 'Tipo_Alerta', 'DOH', 'Stock_Final', 'Recepciones_ERP', 'Accion_Sugerida']
                        df_mp_m1 = df_mp_m1[cols_show_mp].sort_values(by='DOH', ascending=True).reset_index(drop=True)

                        st.dataframe(
                            df_mp_m1.style.format({
                                'DOH': '{:.0f} d',
                                'Stock_Final': '{:,.0f} Kg',
                                'Recepciones_ERP': '{:,.0f} Kg'
                            }).map(estilo_doh, subset=['DOH']),
                            use_container_width=True,
                            hide_index=True
                        )

# ==========================================
# MODULO 9: WHAT-IF
# ==========================================
with tab_whatif:
    if "tab9" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al Simulador What-If.")
    else:
        st.subheader("🔀 Simulador de Escenarios (What-If)")
        st.markdown("Aplica shocks a los datos filtrados para evaluar el impacto en el P&L consolidado.")
        
        if not dict_price:
            st.warning("⚠️ Necesitas cargar datos históricos que incluyan 'revenue' y 'margin'.")
        else:
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                shock_vol = st.slider("📈 Variación Volumen (%)", -50, 50, 0, step=5)
            with col_w2:
                shock_precio = st.slider("🏷️ Variación Precios (%)", -30, 30, 0, step=5)
            with col_w3:
                shock_coste = st.slider("💸 Variación Costes MP (%)", -30, 50, 0, step=5)
            st.divider()
            
            if not df_final.empty:
                df_base, df_sim = motor_simulador_whatif(df_final, dict_price, dict_margin, dict_currency, fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp, horizonte, usar_limpieza_outliers, shock_vol, shock_precio, shock_coste)
                
                tot_rev_base = df_base['Revenue'].sum() if not df_base.empty else 0
                tot_mar_base = df_base['Margin'].sum() if not df_base.empty else 0
                tot_rev_sim = df_sim['Revenue'].sum() if not df_sim.empty else 0
                tot_mar_sim = df_sim['Margin'].sum() if not df_sim.empty else 0
                
                col_r1, col_r2, col_r3 = st.columns(3)
                delta_rev = tot_rev_sim - tot_rev_base
                col_r1.metric("Revenue (Simulado)", f"£ {tot_rev_sim:,.0f}", f"{delta_rev:,.0f} £ vs Base")
                delta_mar = tot_mar_sim - tot_mar_base
                col_r2.metric("Margen (Simulado)", f"£ {tot_mar_sim:,.0f}", f"{delta_mar:,.0f} £ vs Base")
                mar_pct_base = (tot_mar_base / tot_rev_base * 100) if tot_rev_base > 0 else 0
                mar_pct_sim = (tot_mar_sim / tot_rev_sim * 100) if tot_rev_sim > 0 else 0
                delta_pct = mar_pct_sim - mar_pct_base
                col_r3.metric("% Margen Bruto (Simulado)", f"{mar_pct_sim:.1f}%", f"{delta_pct:.1f}% vs Base")
                
                fig_wi = go.Figure(data=[
                    go.Bar(name='Baseline', x=['Revenue (Ingresos)', 'Margin (Bruto)'], y=[tot_rev_base, tot_mar_base], marker_color='#A0B2C6'),
                    go.Bar(name='What-If', x=['Revenue (Ingresos)', 'Margin (Bruto)'], y=[tot_rev_sim, tot_mar_sim], marker_color='#1E3E5B')
                ])
                fig_wi.update_layout(**LAYOUT_STYLE, barmode='group', title="Impacto Financiero (GBP)", yaxis_title="GBP (£)")
                st.plotly_chart(fig_wi, use_container_width=True)
                
                if FPDF is not None:
                    st.divider()
                    st.markdown("### 📥 Exportar Informe Directivo")
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.set_text_color(30, 62, 91)
                    pdf.cell(0, 10, txt="S&OP What-If Scenario Analysis", ln=True, align='C')
                    pdf.set_font("Arial", size=10)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(0, 10, txt="Confidential - AB Agri Supply Chain", ln=True, align='C')
                    pdf.ln(10)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(0, 10, txt="1. Scenario Parameters (Shocks Applied):", ln=True)
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 8, txt=f"    - Volume Variation: {shock_vol}%", ln=True)
                    pdf.cell(0, 8, txt=f"    - Sales Price Variation: {shock_precio}%", ln=True)
                    pdf.cell(0, 8, txt=f"    - COGS / Raw Material Variation: {shock_coste}%", ln=True)
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, txt="2. Financial Impact (Consolidated in GBP):", ln=True)
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 8, txt=f"    - Baseline Revenue: GBP {tot_rev_base:,.0f}", ln=True)
                    pdf.cell(0, 8, txt=f"    - Simulated Revenue: GBP {tot_rev_sim:,.0f} (Delta: {delta_rev:,.0f})", ln=True)
                    pdf.cell(0, 8, txt=f"    - Baseline Margin: GBP {tot_mar_base:,.0f} ({mar_pct_base:.1f}%)", ln=True)
                    pdf.cell(0, 8, txt=f"    - Simulated Margin: GBP {tot_mar_sim:,.0f} ({mar_pct_sim:.1f}%)", ln=True)
                    pdf.ln(2)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(0, 128, 0) if tot_mar_sim >= tot_mar_base else pdf.set_text_color(200, 0, 0)
                    pdf.cell(0, 10, txt=f"    >>> TOTAL MARGIN IMPACT: GBP {delta_mar:,.0f}", ln=True)
                    st.download_button(label="📄 Descargar Resumen PDF", data=bytes(pdf.output()), file_name="SOP_WhatIf.pdf", mime="application/pdf", type="primary")

# ==========================================
# MODULO 10: DASHBOARD EJECUTIVO
# ==========================================
with tab_kpis:
    if "tab10" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al Dashboard de KPIs.")
    else:
        st.subheader("📊 Executive Dashboard & Global KPIs")
        if df_final is not None and not df_final.empty and dict_price:
            with st.spinner("Consolidando datos filtrados..."):
                total_skus = df_final['sku cod'].nunique()
                df_clientes = df_final.groupby('País')['customer cod'].nunique().reset_index()
                df_clientes.columns = ['País', 'Clientes Activos']
                total_clientes = df_clientes['Clientes Activos'].sum()
                
                st.markdown("#### 🌍 Estructura Comercial (Datos Filtrados)")
                col_e1, col_e2, col_e3 = st.columns(3)
                col_e1.metric("SKUs Activos (PT)", f"{total_skus}")
                col_e2.metric("Total Clientes", f"{total_clientes}")
                with col_e3:
                    st.dataframe(df_clientes.style.format({"Clientes Activos": "{:,.0f}"}), use_container_width=True, hide_index=True)
                
                max_date_global = df['Date'].max()
                min_date_12m = max_date_global - pd.DateOffset(months=11)
                
                df_12m = df_final[(df_final['Date'] >= min_date_12m) & (df_final['Date'] <= max_date_global)].copy()
                vol_12m_hist = df_12m['volume'].sum() if not df_12m.empty else 0
                rev_12m_hist = df_12m['Rev_GBP'].sum() if not df_12m.empty else 0
                mar_12m_hist = df_12m['Mar_GBP'].sum() if not df_12m.empty else 0
                
                vol_12m_fcst, rev_12m_fcst, mar_12m_fcst = motor_kpis_n12m(
                    df_final, dict_price, dict_margin, dict_currency,
                    fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp,
                    usar_limpieza_outliers, max_date_global, horiz=12
                )
                
                st.divider()
                st.markdown("#### 🎯 Fiabilidad del Modelo de Demanda (Forecast Performance - L12M)")
                fa_val, bias_val, wape_val = calcular_kpis_forecast(df_final, usar_limpieza_outliers)
                
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("Forecast Accuracy (FA)", f"{fa_val:.1f}%", "Acierto global ponderado")
                col_k2.metric("Forecast Bias", f"{bias_val:+.1f}%", "+ = Infrademanda / - = Sobredemanda")
                col_k3.metric("WAPE (Error Absoluto)", f"{wape_val:.1f}%", "Desviación porcentual neta")
                
                st.divider()
                st.markdown("#### 📈 Crecimiento S&OP: Last 12M vs Next 12M (GBP)")
                col_h1, col_h2, col_h3 = st.columns(3)
                col_h1.metric("Volumen L12M", f"{vol_12m_hist:,.0f} Kg")
                col_h2.metric("Revenue L12M", f"£ {rev_12m_hist:,.0f}")
                col_h3.metric("Margen L12M", f"£ {mar_12m_hist:,.0f} ({(mar_12m_hist / rev_12m_hist * 100) if rev_12m_hist else 0:.1f}%)")
                
                col_f1_k, col_f2_k, col_f3_k = st.columns(3)
                delta_vol = vol_12m_fcst - vol_12m_hist
                col_f1_k.metric("Volumen Proyectado N12M", f"{vol_12m_fcst:,.0f} Kg", f"{delta_vol:,.0f} Kg vs L12M")
                delta_rev2 = rev_12m_fcst - rev_12m_hist
                col_f2_k.metric("Revenue Proyectado N12M", f"£ {rev_12m_fcst:,.0f}", f"{delta_rev2:,.0f} £ vs L12M")
                delta_mar2 = mar_12m_fcst - mar_12m_hist
                col_f3_k.metric("Margen Proyectado N12M", f"£ {mar_12m_fcst:,.0f}", f"{delta_mar2:,.0f} £ vs L12M")

                st.divider()
                st.subheader("📋 Rendimiento Comercial y Bias por Cliente y SKU (L12M)")
                st.markdown("Desglose detallado de Volumen, Revenue, Margen y Sesgo Histórico (Bias) con alertas visuales.")

                df_granular = df.groupby(['País', 'customer cod', 'customer desc', 'sku cod']).agg(
                    Volumen_Kg=('volume', 'sum'),
                    Revenue_GBP=('Rev_GBP', 'sum'),
                    Margen_GBP=('Mar_GBP', 'sum')
                ).reset_index().rename(columns={'customer desc': 'Cliente Desc'})
                
                df_granular['Margen %'] = np.where(
                    df_granular['Revenue_GBP'] > 0,
                    (df_granular['Margen_GBP'] / df_granular['Revenue_GBP']) * 100,
                    0.0
                )
                
                df_reciente = df[df['Date'] >= (df['Date'].max() - pd.DateOffset(months=6))].groupby(['customer cod', 'sku cod'])['volume'].sum().reset_index(name='Vol_Reciente')
                df_antiguo = df[(df['Date'] < (df['Date'].max() - pd.DateOffset(months=6))) & (df['Date'] >= (df['Date'].max() - pd.DateOffset(months=12)))].groupby(['customer cod', 'sku cod'])['volume'].sum().reset_index(name='Vol_Antiguo')
                
                df_granular = pd.merge(df_granular, df_reciente, on=['customer cod', 'sku cod'], how='left').fillna({'Vol_Reciente': 0})
                df_granular = pd.merge(df_granular, df_antiguo, on=['customer cod', 'sku cod'], how='left').fillna({'Vol_Antiguo': 0})
                
                df_granular['Bias L6M (%)'] = np.where(
                    df_granular['Vol_Antiguo'] > 0,
                    ((df_granular['Vol_Reciente'] - df_granular['Vol_Antiguo']) / df_granular['Vol_Antiguo']) * 100,
                    0.0
                ).round(1)
                
                df_granular['Descripción SKU'] = df_granular['sku cod'].map(dict_sku_desc).fillna('')
                df_granular = df_granular[['País', 'customer cod', 'Cliente Desc', 'sku cod', 'Descripción SKU', 'Volumen_Kg', 'Revenue_GBP', 'Margen_GBP', 'Margen %', 'Bias L6M (%)']]
                
                col_g1, col_g2, col_g3 = st.columns(3)
                with col_g1:
                    filtro_pais_g = st.selectbox("País:", ["TODOS"] + sorted(df_granular['País'].dropna().unique().tolist()), key="g_pais")
                with col_g2:
                    filtro_cli_g = st.selectbox("Cliente:", ["TODOS"] + sorted(df_granular['Cliente Desc'].dropna().unique().tolist()), key="g_cli")
                with col_g3:
                    search_sku = st.text_input("🔍 Buscar SKU / Descripción:", placeholder="Escribe código o texto...")
                    
                if filtro_pais_g != "TODOS":
                    df_granular = df_granular[df_granular['País'] == filtro_pais_g]
                if filtro_cli_g != "TODOS":
                    df_granular = df_granular[df_granular['Cliente Desc'] == filtro_cli_g]
                if search_sku:
                    query = search_sku.strip().lower()
                    mask = (
                        df_granular['sku cod'].astype(str).str.lower().str.contains(query) |
                        df_granular['Descripción SKU'].astype(str).str.lower().str.contains(query) |
                        df_granular['Cliente Desc'].astype(str).str.lower().str.contains(query)
                    )
                    df_granular = df_granular[mask]
                    
                def color_bias(val):
                    if pd.isna(val):
                        return ''
                    if -5 <= val <= 5:
                        return 'background-color: #e6ffe6; color: #006600; font-weight: bold;'
                    elif -15 <= val < -5 or 5 < val <= 15:
                        return 'background-color: #ffe6cc; color: #b35900; font-weight: bold;'
                    else:
                        return 'background-color: #ffcccc; color: #900; font-weight: bold;'

                st.dataframe(
                    df_granular.sort_values(by='Revenue_GBP', ascending=False)
                    .style.format({
                        "Volumen_Kg": "{:,.0f} Kg",
                        "Revenue_GBP": "£ {:,.0f}",
                        "Margen_GBP": "£ {:,.0f}",
                        "Margen %": "{:.1f}%",
                        "Bias L6M (%)": "{:+.1f}%"
                    })
                    .map(color_bias, subset=['Bias L6M (%)']),
                    use_container_width=True,
                    hide_index=True
                )
