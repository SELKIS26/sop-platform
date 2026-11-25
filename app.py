# ==============================================================================
# S&OP / IBP CORPORATE PLATFORM - PARTE 1 DE 2 (CORE ENGINE, NPI & 2D MATRIX)
# ==============================================================================
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
    
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e6ed;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #1E3E5B;
    }

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
# ESQUEMA OFICIAL ESTRICTO DE LAS 8 TABLAS + NPI CLOUD
# ==========================================
COLS_HIST = ['Date', 'País', 'customer cod', 'customer desc', 'sku cod', 'sku desc', 'volume', 'revenue', 'margin', 'currency', 'Categoria_Producto', 'KAM']
COLS_BUDGET = ['Escenario', 'Categoria_Producto', 'customer cod', 'Date', 'Volume_Kg', 'Revenue_GBP', 'Margin_GBP']
COLS_AJUSTES = ['Date', 'País', 'customer cod', 'sku cod', 'override_value']
COLS_STOCK = ['sku cod', 'sku desc', 'stock_disponible', 'Cobertura_Meses', 'LT_Meses', 'Categoria', 'Coste_Unitario']
COLS_BOM = ['sku cod', 'rm cod', 'rm desc', 'Cantidad']
COLS_RUTAS = ['sku cod', 'Maquina', 'Kilos_por_Hora']
COLS_CAL = ['Date', 'Maquina', 'Horas_Disponibles']
COLS_COMPRAS = ['Date', 'rm cod', 'Cantidad_Kg']
COLS_PROD = ['Date', 'sku cod', 'Cantidad_Kg']

LOG_FILE = "audit_log_accesos.csv"
CLOUD_AJUSTES_FILE = "2_Ajustes_Consenso_Cloud.csv"
FVA_LOG_FILE = "audit_log_fva_consenso.csv"
SOP_CAL_FILE = "sop_calendar_status_cloud.csv"
ACTION_LOG_FILE = "sop_action_log_cloud.csv"
NPI_CLOUD_FILE = "npi_new_business_cloud.csv"

COLS_FVA_LOG = [
    "Fecha_Cambio (CET)", "Usuario", "Tipo_Ajuste", "Date", "País",
    "customer cod", "sku cod", "Forecast_Estadistico", "Consenso_Override",
    "Delta_Kg", "Delta_Pct_FVA"
]
COLS_SOP_CAL = ["Fase", "Etapa S&OP", "Dias_Mes", "Dia_Inicio", "Dia_Fin", "Owner", "Entregable_Clave", "Estado", "Notas_Comite"]
COLS_ACTION_LOG = ["ID", "Fecha_Alta", "Area_S&OP", "Accion_Acordada", "Responsable", "Fecha_Limite", "Impacto_GBP", "Estado"]
COLS_NPI = [
    "sku cod", "sku desc", "País", "customer cod", "customer desc",
    "SKU_Espejo", "Volumen_Mensual_Kg", "Mes_Inicio", "Precio_Unit_EUR",
    "Margen_Unit_EUR", "Maquina", "Kilos_por_Hora", "Politica_Stock"
]

# ==========================================
# MOTOR DE INTERNACIONALIZACIÓN COMPLETO (4 IDIOMAS)
# ==========================================
LANGUAGES = ["Español", "English", "Polski", "Dansk"]

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'Español'


def tr(es, en, pl=None, da=None):
    """Traduce dinámicamente cualquier texto de la interfaz al idioma activo."""
    lang = st.session_state.get('lang', 'Español')
    if lang == 'English':
        return en
    elif lang == 'Polski':
        return pl if pl is not None else en
    elif lang == 'Dansk':
        return da if da is not None else en
    return es


TEXTS = {
    "Español": {
        "title": "S&OP Execution & Planning Platform",
        "sidebar_lang": "🌐 Idioma / Language",
        "tab0": "📖 0. Guía", "tab1": "📊 1. Demanda", "tab2": "🏭 2. Producción",
        "tab3": "🧩 3. Compras", "tab4": "⚙️ 4. Capacidad", "tab5": "💷 5. Finanzas",
        "tab6": "🚀 6. Ejecución ERP", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Excepciones",
        "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Ingresos (Revenue)", "kpi_mar": "Margen Bruto", "kpi_wc": "Working Capital Promedio",
        "kpi_fab": "Volumen a Fabricar", "kpi_doh": "Cobertura Media"
    },
    "English": {
        "title": "S&OP Execution & Planning Platform",
        "sidebar_lang": "🌐 Language",
        "tab0": "📖 0. Guide", "tab1": "📊 1. Demand", "tab2": "🏭 2. Production",
        "tab3": "🧩 3. Purchasing", "tab4": "⚙️ 4. Capacity", "tab5": "💷 5. Finance",
        "tab6": "🚀 6. ERP Execution", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions",
        "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Total Revenue", "kpi_mar": "Gross Margin", "kpi_wc": "Avg Working Capital",
        "kpi_fab": "Volume to Produce", "kpi_doh": "Avg Days on Hand"
    },
    "Polski": {
        "title": "Platforma S&OP i Planowania",
        "sidebar_lang": "🌐 Język / Language",
        "tab0": "📖 0. Przewodnik", "tab1": "📊 1. Popyt", "tab2": "🏭 2. Produkcja",
        "tab3": "🧩 3. Zakupy", "tab4": "⚙️ 4. Zdolności", "tab5": "💷 5. Finanse",
        "tab6": "🚀 6. Realizacja ERP", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Wyjątki",
        "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Przychody", "kpi_mar": "Marża Brutto", "kpi_wc": "Śr. Kapitał Obrotowy",
        "kpi_fab": "Wolumen do Produkcji", "kpi_doh": "Średnie Pokrycie"
    },
    "Dansk": {
        "title": "S&OP Eksekveringsplatform",
        "sidebar_lang": "🌐 Sprog / Language",
        "tab0": "📖 0. Guide", "tab1": "📊 1. Efterspørgsel", "tab2": "🏭 2. Produktion",
        "tab3": "🧩 3. Indkøb", "tab4": "⚙️ 4. Kapacitet", "tab5": "💷 5. Økonomi",
        "tab6": "🚀 6. ERP Udførelse", "tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Undtagelser",
        "tab9": "🔀 9. What-If", "tab10": "📊 10. Dashboard",
        "kpi_rev": "Omsætning", "kpi_mar": "Bruttomargin", "kpi_wc": "Gns. Arbejdskapital",
        "kpi_fab": "Produktionsvolumen", "kpi_doh": "Gns. Dækning"
    }
}


# ==========================================
# MOTOR DE PERSISTENCIA EN GITHUB (API + LOCAL CON CACHÉ EN SESIÓN)
# ==========================================
def _github_creds():
    try:
        token = st.secrets.get("GITHUB_TOKEN", None)
        repo = st.secrets.get("GITHUB_REPO", None)
        return token, repo
    except Exception:
        return None, None


def github_leer_csv(filename, cols_default, forzar_recarga=False):
    cache_key = f"_cloud_cache_{filename}"
    if not forzar_recarga and cache_key in st.session_state:
        return st.session_state[cache_key].copy()

    token, repo = _github_creds()
    if token and repo:
        url = f"https://api.github.com/repos/{repo}/contents/{filename}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SOP-Platform-Cloud"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                contenido_csv = base64.b64decode(data["content"]).decode("utf-8-sig")
                df_out = pd.read_csv(io.StringIO(contenido_csv))
                st.session_state[cache_key] = df_out.copy()
                return df_out
        except Exception:
            pass

    if os.path.exists(filename):
        try:
            df_local = pd.read_csv(filename)
            st.session_state[cache_key] = df_local.copy()
            return df_local
        except Exception:
            pass

    df_empty = pd.DataFrame(columns=cols_default)
    st.session_state[cache_key] = df_empty.copy()
    return df_empty


def github_guardar_csv(df_to_save, filename, commit_msg):
    cache_key = f"_cloud_cache_{filename}"
    st.session_state[cache_key] = df_to_save.copy()
    try:
        df_to_save.to_csv(filename, index=False, encoding="utf-8-sig")
    except Exception:
        pass

    token, repo = _github_creds()
    if not (token and repo):
        return False

    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SOP-Platform-Cloud"
    }
    sha_actual = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha_actual = data.get("sha")
    except Exception:
        pass

    csv_bytes = df_to_save.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    payload = {
        "message": commit_msg,
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
        urllib.request.urlopen(req_put, timeout=8)
        return True
    except Exception:
        return False


def registrar_y_leer_auditoria_permanente(nuevo_evento=None, forzar=False):
    cols_log = ["Fecha_Hora (CET)", "Username", "Nombre", "Rol"]
    df_actual = github_leer_csv(LOG_FILE, cols_log, forzar_recarga=forzar)
    if nuevo_evento is not None:
        df_actual = pd.concat([df_actual, pd.DataFrame([nuevo_evento])], ignore_index=True)
        github_guardar_csv(
            df_actual,
            LOG_FILE,
            f"Audit log: {nuevo_evento['Username']} ({nuevo_evento['Fecha_Hora (CET)']})"
        )
    return df_actual


def registrar_evento_fva_consenso(lista_eventos_fva):
    if not lista_eventos_fva:
        return
    df_fva = github_leer_csv(FVA_LOG_FILE, COLS_FVA_LOG)
    df_fva = pd.concat([df_fva, pd.DataFrame(lista_eventos_fva)], ignore_index=True)
    usuario_log = lista_eventos_fva[0].get("Usuario", "user")
    github_guardar_csv(df_fva, FVA_LOG_FILE, f"FVA Consensus Log update by {usuario_log}")
    st.session_state["df_fva_logs"] = df_fva


def _pdf_safe(texto):
    return str(texto).encode("latin-1", "replace").decode("latin-1")


# ==========================================
# GENERADORES DE DATOS DEMO (LIGERO Y BIG DATA EQUILIBRADO POR PLANTA)
# ==========================================
@st.cache_data(show_spinner=False)
def obtener_excels_demo_8_tablas():
    """Genera los 8 DataFrames de Demo con las columnas exactas oficiales."""
    np.random.seed(42)
    fechas_hist = pd.date_range(start="2024-05-01", periods=28, freq="MS")
    mes_m1 = fechas_hist[-1] + pd.DateOffset(months=1)
    mes_m2 = mes_m1 + pd.DateOffset(months=1)
    fechas_fut = pd.date_range(start=mes_m1, periods=12, freq="MS")

    skus_demo = [
        ("A10800V3", "ADICARE EVOLUTION H", 35000, 2.85, 4.80, 1.45, "Linea_3_Pellet", 3536, "MTS"),
        ("M02031BB", "CEBADA EXTRUSIONADA Z1", 12000, 2.28, 3.10, 0.70, "Linea_1_Extrusion", 4200, "MTS"),
        ("N54700BB", "NUCLEO PORCINO CRECIMIENTO", 18000, 4.10, 6.20, 1.85, "Linea_2_Mezcla", 4134, "MTS"),
        ("PN190G10", "PIENSO GRANULADO BROILER", 65000, 0.55, 0.95, 0.28, "Linea_3_Pellet", 5000, "MTS"),
        ("PR01299X", "PREMEZCLA VITAMINICA AVEC", 8000, 12.50, 18.50, 5.20, "Linea_4_Premix", 2200, "MTS"),
    ]

    maquinas_locales = ['Linea_1_Extrusion', 'Linea_2_Mezcla', 'Linea_3_Pellet', 'Linea_4_Premix']

    filas_ventas = []
    for f in fechas_hist:
        est = 1.18 if f.month in [3, 4, 10, 11] else (0.85 if f.month in [7, 8] else 1.0)
        for sku_cod, sku_desc, base_vol, cost_u, precio_u, margen_u, _, _, _ in skus_demo:
            ruido = 0.65 if sku_cod == "PR01299X" else 0.12
            vol = max(200, int(np.random.normal(base_vol * est, base_vol * ruido)))
            
            c_cod = "000008JUAN" if sku_cod in ["PN190G10", "PR01299X"] else "000007SCAAS"
            c_desc = "Juan Key Account Ltd" if c_cod == "000008JUAN" else "Agropecuaria Catalana Stat.Coop.Ltda"
            kam_default = "kam_juan" if c_cod == "000008JUAN" else "amancebo"
            
            cat_default = "Lactoreemplazantes" if "ADICARE" in sku_desc else ("Pre-iniciadores" if "CEBADA" in sku_desc else "Núcleos")
            
            filas_ventas.append({
                "Date": f,
                "País": "España",
                "customer cod": c_cod,
                "customer desc": c_desc,
                "sku cod": sku_cod,
                "sku desc": sku_desc,
                "volume": vol,
                "revenue": round(vol * precio_u, 2),
                "margin": round(vol * margen_u, 2),
                "currency": "EUR",
                "Categoria_Producto": cat_default,
                "KAM": kam_default
            })
    df_1_hist = pd.DataFrame(filas_ventas)[COLS_HIST]

    filas_ajustes = []
    for f in fechas_fut[:6]:
        for sku_cod, _, base_vol, _, _, _, _, _, _ in skus_demo:
            override = int(base_vol * np.random.uniform(0.95, 1.10))
            c_cod = "000008JUAN" if sku_cod in ["PN190G10", "PR01299X"] else "000007SCAAS"
            filas_ajustes.append({
                "Date": f,
                "País": "España",
                "customer cod": c_cod,
                "sku cod": sku_cod,
                "override_value": override
            })
    df_2_ajustes = pd.DataFrame(filas_ajustes)[COLS_AJUSTES]

    filas_stock = [
        {"sku cod": sku, "sku desc": desc, "stock_disponible": int(vol * 0.55), "Cobertura_Meses": 1, "LT_Meses": 1, "Categoria": cat, "Coste_Unitario": cost}
        for sku, desc, vol, cost, _, _, _, _, cat in skus_demo
    ] + [
        {"sku cod": "M12250SS", "sku desc": "FORMIATO DE CALCIO", "stock_disponible": 14000, "Cobertura_Meses": 2, "LT_Meses": 1, "Categoria": "MTS", "Coste_Unitario": 0.85},
        {"sku cod": "M09522E3", "sku desc": "PIGLET BOOZT (25 L) Z2", "stock_disponible": 4500, "Cobertura_Meses": 1, "LT_Meses": 1, "Categoria": "MTS", "Coste_Unitario": 3.40},
    ]
    df_3_stock = pd.DataFrame(filas_stock)[COLS_STOCK]

    filas_bom = []
    for sku, _, _, _, _, _, _, _, _ in skus_demo:
        filas_bom.append({"sku cod": sku, "rm cod": "M12250SS", "rm desc": "FORMIATO DE CALCIO", "Cantidad": 0.6961})
        filas_bom.append({"sku cod": sku, "rm cod": "M09522E3", "rm desc": "PIGLET BOOZT (25 L) Z2", "Cantidad": 0.0363})
    df_4_bom = pd.DataFrame(filas_bom)[COLS_BOM]

    df_5_rutas = pd.DataFrame([
        {"sku cod": sku, "Maquina": maquina, "Kilos_por_Hora": kph}
        for sku, _, _, _, _, _, maquina, kph, _ in skus_demo
    ])[COLS_RUTAS]

    filas_cal = []
    for f in pd.date_range(start="2024-05-01", periods=48, freq="MS"):
        for maq in maquinas_locales:
            filas_cal.append({
                "Date": f,
                "Maquina": maq,
                "Horas_Disponibles": 740
            })
    df_6_cal = pd.DataFrame(filas_cal)[COLS_CAL]

    df_7_compras = pd.DataFrame([
        {"Date": mes_m1, "rm cod": "M12250SS", "Cantidad_Kg": 11067},
        {"Date": mes_m2, "rm cod": "M12250SS", "Cantidad_Kg": 9821},
    ])[COLS_COMPRAS]

    df_8_prod = pd.DataFrame([
        {"Date": mes_m1, "sku cod": "A10800V3", "Cantidad_Kg": 15000},
        {"Date": mes_m1, "sku cod": "PN190G10", "Cantidad_Kg": 35000},
        {"Date": mes_m2, "sku cod": "PN190G10", "Cantidad_Kg": 40000},
    ])[COLS_PROD]

    filas_budget = []
    for esc in ["Budget Original (0+12)", "Forecast 3+9"]:
        mult = 1.05 if "Original" in esc else 1.02
        for cat in ["Lactoreemplazantes", "Pre-iniciadores", "Núcleos"]:
            for c_cod in ["000007SCAAS", "000008JUAN"]:
                for f in fechas_fut:
                    filas_budget.append({"Escenario": esc, "Categoria_Producto": cat, "customer cod": c_cod, "Date": f, "Volume_Kg": 25000 * mult, "Revenue_GBP": 85000 * mult, "Margin_GBP": 18000 * mult})
    df_9_budget = pd.DataFrame(filas_budget)[COLS_BUDGET]

    return {
        "hist": df_1_hist,
        "ajustes": df_2_ajustes,
        "stock": df_3_stock,
        "bom": df_4_bom,
        "rutas": df_5_rutas,
        "cal": df_6_cal,
        "compras_erp": df_7_compras,
        "produccion_erp": df_8_prod,
        "budget": df_9_budget
    }


@st.cache_data(show_spinner=False)
def obtener_excels_big_data_8_tablas(n_rows_hist=150000, n_skus=500, n_rms=120, n_clientes=80):
    """Genera un dataset masivo equilibrado por planta/país (cada país tiene sus propias líneas y SKUs asignados)."""
    np.random.seed(42)
    paises = ["España", "UK", "Polonia", "Dinamarca"]
    monedas_map = {"España": "EUR", "UK": "GBP", "Polonia": "PLN", "Dinamarca": "DKK"}
    maquinas_por_pais = {
        "España": ["ES_Linea_1_Extrusion", "ES_Linea_2_Pellet", "ES_Linea_3_Mezcla"],
        "UK": ["UK_Linea_1_Pellet", "UK_Linea_2_Premix", "UK_Linea_3_Liquidos"],
        "Polonia": ["PL_Linea_1_Extrusion", "PL_Linea_2_Mezcla", "PL_Linea_3_BigBag"],
        "Dinamarca": ["DK_Linea_1_Pellet", "DK_Linea_2_Premix"]
    }
    todas_las_maquinas = [m for lista_m in maquinas_por_pais.values() for m in lista_m]

    fechas_hist = pd.date_range(start="2024-05-01", periods=28, freq="MS")
    mes_m1 = fechas_hist[-1] + pd.DateOffset(months=1)
    mes_m2 = mes_m1 + pd.DateOffset(months=1)
    fechas_fut = pd.date_range(start=mes_m1, periods=12, freq="MS")

    sku_cods = [f"SKU-{i:04d}" for i in range(1, n_skus + 1)]
    sku_descs = [f"PRODUCTO NUTRICION INDUSTRIAL {i:04d}" for i in range(1, n_skus + 1)]
    rm_cods = [f"RM-{j:03d}" for j in range(1, n_rms + 1)]
    rm_descs = [f"MATERIA PRIMA BASE {j:03d}" for j in range(1, n_rms + 1)]
    cli_cods = [f"CLI-{k:04d}" for k in range(1, n_clientes + 1)]
    cli_descs = [f"Corporacion Agroalimentaria {k:04d}" for k in range(1, n_clientes + 1)]

    pais_por_sku = np.array([paises[i % len(paises)] for i in range(n_skus)])

    idx_sku = np.random.randint(0, n_skus, size=n_rows_hist)
    paises_venta = pais_por_sku[idx_sku]
    idx_pais_num = np.array([i % len(paises) for i in idx_sku])
    idx_cli = idx_pais_num + np.random.randint(0, n_clientes // len(paises), size=n_rows_hist) * len(paises)
    idx_fecha = np.random.randint(0, len(fechas_hist), size=n_rows_hist)

    meses_arr = fechas_hist[idx_fecha].month.values
    factor_est = np.where(np.isin(meses_arr, [3, 6, 10]), 1.25, np.where(np.isin(meses_arr, [1, 7, 11]), 0.80, 1.0))
    vols = (np.random.randint(200, 1200, size=n_rows_hist) * factor_est).astype(int)

    precios_base = np.random.uniform(0.8, 12.0, size=n_skus)
    margenes_base = precios_base * np.random.uniform(0.18, 0.38, size=n_skus)
    cats_array = np.array(["Lactoreemplazantes", "Pre-iniciadores", "Núcleos"])
    cat_por_sku = np.array([cats_array[i % len(cats_array)] for i in range(n_skus)])

    df_1_hist = pd.DataFrame({
        "Date": fechas_hist[idx_fecha],
        "País": paises_venta,
        "customer cod": np.array(cli_cods)[idx_cli],
        "customer desc": np.array(cli_descs)[idx_cli],
        "sku cod": np.array(sku_cods)[idx_sku],
        "sku desc": np.array(sku_descs)[idx_sku],
        "volume": vols,
        "revenue": np.round(vols * precios_base[idx_sku], 2),
        "margin": np.round(vols * margenes_base[idx_sku], 2),
        "currency": np.array([monedas_map[p] for p in paises_venta]),
        "Categoria_Producto": cat_por_sku[idx_sku],
        "KAM": np.random.choice(["amancebo", "kam_juan", "borja"], size=n_clientes, p=[0.4, 0.4, 0.2])[idx_cli]
    })[COLS_HIST]

    idx_aj_sku = np.random.randint(0, 50, size=300)
    paises_aj = pais_por_sku[idx_aj_sku]
    cli_aj = [cli_cods[(i % len(paises)) + np.random.randint(0, 5) * len(paises)] for i in idx_aj_sku]
    df_2_ajustes = pd.DataFrame({
        "Date": np.random.choice(fechas_fut[:6], size=300),
        "País": paises_aj,
        "customer cod": cli_aj,
        "sku cod": np.array(sku_cods)[idx_aj_sku],
        "override_value": np.random.randint(2000, 15000, size=300)
    }).drop_duplicates(subset=["Date", "País", "customer cod", "sku cod"])[COLS_AJUSTES]

    df_3_stock = pd.DataFrame({
        "sku cod": sku_cods + rm_cods,
        "sku desc": sku_descs + rm_descs,
        "stock_disponible": np.random.randint(500, 12000, size=n_skus + n_rms),
        "Cobertura_Meses": np.random.choice([1, 2], size=n_skus + n_rms, p=[0.7, 0.3]),
        "LT_Meses": np.random.choice([0, 1, 2], size=n_skus + n_rms, p=[0.3, 0.5, 0.2]),
        "Categoria": np.random.choice(["MTS", "MTO"], size=n_skus + n_rms, p=[0.85, 0.15]),
        "Coste_Unitario": np.round(np.concatenate([precios_base - margenes_base, np.random.uniform(0.4, 5.0, size=n_rms)]), 2)
    })[COLS_STOCK]

    bom_sku_idx = np.repeat(np.arange(n_skus), 5)
    bom_rm_idx = np.arange(len(bom_sku_idx)) % n_rms
    np.random.shuffle(bom_rm_idx)
    df_4_bom = pd.DataFrame({
        "sku cod": np.array(sku_cods)[bom_sku_idx],
        "rm cod": np.array(rm_cods)[bom_rm_idx],
        "rm desc": np.array(rm_descs)[bom_rm_idx],
        "Cantidad": np.round(np.random.uniform(0.05, 0.35, size=len(bom_sku_idx)), 4)
    }).drop_duplicates(subset=["sku cod", "rm cod"])[COLS_BOM]

    maquinas_asignadas = [
        np.random.choice(maquinas_por_pais[pais_por_sku[i]]) for i in range(n_skus)
    ]
    df_5_rutas = pd.DataFrame({
        "sku cod": sku_cods,
        "Maquina": maquinas_asignadas,
        "Kilos_por_Hora": np.random.randint(8500, 18000, size=n_skus)
    })[COLS_RUTAS]

    filas_cal = [
        {"Date": f, "Maquina": m, "Horas_Disponibles": 740}
        for f in pd.date_range("2024-05-01", periods=48, freq="MS")
        for m in todas_las_maquinas
    ]
    df_6_cal = pd.DataFrame(filas_cal)[COLS_CAL]

    df_7_compras = pd.DataFrame({
        "Date": np.random.choice([mes_m1, mes_m2], size=150),
        "rm cod": np.random.choice(rm_cods, size=150),
        "Cantidad_Kg": np.random.randint(2000, 15000, size=150)
    })[COLS_COMPRAS]

    df_8_prod = pd.DataFrame({
        "Date": np.random.choice([mes_m1, mes_m2], size=200),
        "sku cod": np.random.choice(sku_cods, size=200),
        "Cantidad_Kg": np.random.randint(2000, 12000, size=200)
    })[COLS_PROD]

    filas_budget_bd = []
    for esc in ["Budget Original (0+12)", "Forecast 3+9", "Forecast 6+6", "Forecast 9+3"]:
        mult = 1.05 if "Original" in esc else (1.02 if "3+9" in esc else 0.98)
        for cat in ["Lactoreemplazantes", "Pre-iniciadores", "Núcleos"]:
            for c_cli in cli_cods[:3]: # Simular unos pocos clientes
                for f in fechas_fut:
                    filas_budget_bd.append({"Escenario": esc, "Categoria_Producto": cat, "customer cod": c_cli, "Date": f, "Volume_Kg": 25000 * mult, "Revenue_GBP": 85000 * mult, "Margin_GBP": 18000 * mult})
    df_9_budget = pd.DataFrame(filas_budget_bd)
    # Rellenar con columnas que falten si las hubiera
    for c in COLS_BUDGET:
        if c not in df_9_budget.columns:
            df_9_budget[c] = None
    df_9_budget = df_9_budget[COLS_BUDGET]

    return {
        "hist": df_1_hist, "ajustes": df_2_ajustes, "stock": df_3_stock, "bom": df_4_bom,
        "rutas": df_5_rutas, "cal": df_6_cal, "compras_erp": df_7_compras, "produccion_erp": df_8_prod,
        "budget": df_9_budget
    }


@st.cache_data(show_spinner=False)
def generar_plantillas_oficiales_excel():
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
        ("9_Presupuestos", demos_tpl["budget"].head(5)),
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
            "password": "Sop2026",
            "rol": "Admin"
        },
        "borja": {
            "email": "bdelrio@abagri.com",
            "name": "Borja Del Rio",
            "password": "BorjaDR",
            "rol": "Admin"
        },
        "kam_juan": {
            "email": "juan@abagri.com",
            "name": "Juan KAM",
            "password": "Kam123",
            "rol": "KAM"
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
            st.subheader(tr("🔐 Acceso S&OP (Modo Local)", "🔐 S&OP Access (Local Mode)", "🔐 Dostęp S&OP", "🔐 S&OP Adgang"))
            user_in = st.text_input(tr("Usuario", "Username", "Użytkownik", "Brugernavn")).strip()
            pass_in = st.text_input(tr("Contraseña", "Password", "Hasło", "Adgangskode"), type="password")
            if st.form_submit_button(tr("Iniciar Sesión", "Sign In", "Zaloguj się", "Log ind")):
                usuarios_dict = credenciales.get("usernames", {})
                if user_in in usuarios_dict and pass_in == usuarios_dict[user_in].get("password"):
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = user_in
                    st.session_state["name"] = usuarios_dict[user_in].get("name", user_in)
                    st.session_state["rol"] = usuarios_dict[user_in].get("rol", "KAM")
                    st.rerun()
                else:
                    st.session_state["authentication_status"] = False

if st.session_state.get("authentication_status") is False:
    st.error(tr("❌ Usuario o contraseña incorrectos", "❌ Incorrect username or password", "❌ Nieprawidłowy użytkownik lub hasło", "❌ Forkert brugernavn eller adgangskode"))
    st.stop()
elif st.session_state.get("authentication_status") is None:
    st.warning(tr("🔒 Por favor, introduce tus credenciales para acceder a la plataforma S&OP", "🔒 Please enter your credentials to access the S&OP platform", "🔒 Wprowadź dane logowania, aby uzyskać dostęp", "🔒 Indtast dine legitimationsoplysninger for at få adgang"))
    st.stop()

usuario_actual = st.session_state["username"]
rol_actual = st.session_state.get("rol", "KAM")

PERMISOS = {
    "amancebo": ["tab0", "tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7", "tab8", "tab9", "tab10"],
    "borja": ["tab0", "tab2"],
    "kam_juan": ["tab0", "tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7", "tab8", "tab9", "tab10"]
}
modulos_permitidos = PERMISOS.get(usuario_actual, ["tab0"])

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
    st.session_state['lang'] = st.selectbox(
        TEXTS[st.session_state['lang']]["sidebar_lang"],
        LANGUAGES,
        index=LANGUAGES.index(st.session_state['lang'])
    )
    st.divider()

    st.markdown(f"👤 **{tr('Bienvenido/a', 'Welcome', 'Witaj', 'Velkommen')}, {st.session_state['name']}**")
    if usuario_actual == "borja":
        st.caption(tr("🔹 Rol: Manager de Producción", "🔹 Role: Production Manager", "🔹 Rola: Kierownik Produkcji", "🔹 Rolle: Produktionschef"))
    elif usuario_actual == "kam_juan" or st.session_state.get("rol") == "KAM":
        st.caption(tr("🔹 Rol: KAM", "🔹 Role: KAM", "🔹 Rola: KAM", "🔹 Rolle: KAM"))
    else:
        st.caption(tr("🔹 Rol: Administrador Global", "🔹 Role: Global Administrator", "🔹 Rola: Administrator Globalny", "🔹 Rolle: Global Administrator"))

    if authenticator is not None:
        authenticator.logout(tr("Cerrar Sesión", "Sign Out", "Wyloguj", "Log ud"), "main")
    else:
        if st.button(tr("Cerrar Sesión", "Sign Out", "Wyloguj", "Log ud")):
            st.session_state["authentication_status"] = None
            st.session_state["acceso_registrado"] = False
            st.rerun()

    if usuario_actual == "amancebo":
        with st.expander(tr("🛡️ Registro de Accesos (Admin)", "🛡️ Access Audit Log (Admin)", "🛡️ Dziennik Dostępu (Admin)", "🛡️ Adgangslog (Admin)")):
            if st.button(tr("🔄 Actualizar Historial GitHub", "🔄 Refresh GitHub Log", "🔄 Odśwież dziennik GitHub", "🔄 Opdater GitHub Log"), use_container_width=True):
                st.session_state["df_audit_logs"] = registrar_y_leer_auditoria_permanente(None, forzar=True)
            df_logs = st.session_state.get("df_audit_logs", registrar_y_leer_auditoria_permanente(None))
            if df_logs is None or df_logs.empty:
                st.caption(tr("Sin registros todavía.", "No records yet.", "Brak wpisów.", "Ingen optegnelser endnu."))
            else:
                st.caption(f"{tr('Total accesos registrados', 'Total logged accesses', 'Łączna liczba logowań', 'Samlede adgange')}: **{len(df_logs)}**")
                st.dataframe(df_logs.iloc[::-1], use_container_width=True, hide_index=True)
                csv_logs = df_logs.iloc[::-1].to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=tr("📥 Descargar Historial (.csv)", "📥 Download Access Log (.csv)", "📥 Pobierz dziennik (.csv)", "📥 Download Log (.csv)"),
                    data=csv_logs,
                    file_name=f"Audit_Log_SOP_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    st.divider()

    with st.expander(tr("📲 Compartir App (QR)", "📲 Share App (QR)", "📲 Udostępnij aplikację (QR)", "📲 Del App (QR)")):
        enlace_app = "https://sop-mancew.streamlit.app/"
        if qrcode is not None:
            st.caption(tr("Escanea para entrar desde móvil:", "Scan to open on mobile:", "Zeskanuj telefonem:", "Scan for at åbne på mobil:"))
            img_qr = qrcode.make(enlace_app)
            buf = io.BytesIO()
            img_qr.save(buf, format="PNG")
            st.image(buf.getvalue(), use_container_width=True)
        else:
            st.caption(f"🔗 Link: {enlace_app}")

t = TEXTS[st.session_state['lang']]
st.title(t["title"])

# ==========================================
# 1. CONFIGURACIÓN Y CARGA DE ARCHIVOS (CON BIG DATA STRESS-TEST)
# ==========================================
with st.sidebar:
    st.session_state["modo_demo_8"] = st.toggle(tr("Activar Datos Demo", "Enable Demo Data"), value=True)
    escala_demo = st.selectbox(tr("Escala de la Demo:", "Demo Scale:"), ["Ligera (5 SKUs)", "🔥 Big Data Stress-Test"])

    st.download_button(
        label=tr("📥 Descargar 9 Plantillas Oficiales (.xlsx)", "📥 Download 9 Official Templates (.xlsx)", "📥 Pobierz 9 Oficjalnych Szablonów (.xlsx)", "📥 Download 9 Officielle Skabeloner (.xlsx)"),
        data=generar_plantillas_oficiales_excel(),
        file_name="Plantillas_Oficiales_SOP_8_Tablas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.header(tr("📂 1. Datos Maestros S&OP", "📂 1. S&OP Master Data", "📂 1. Dane Podstawowe S&OP", "📂 1. S&OP Stamdata"))
    file_hist = st.file_uploader(tr("1. Histórico Ventas", "1. Sales History", "1. Historia Sprzedaży", "1. Salgshistorik"), type=['xlsx', 'csv'])
    file_ajustes = st.file_uploader(tr("2. Ajustes Consenso", "2. Consensus Overrides", "2. Korekty Konsensusu", "2. Konsensusjusteringer"), type=['xlsx', 'csv'])
    file_stock = st.file_uploader(tr("3. Stock Actual", "3. Current Inventory", "3. Aktualny Zapas", "3. Nuværende Lager"), type=['xlsx', 'csv'])
    file_bom = st.file_uploader(tr("4. BOM (Recetas)", "4. BOM (Formulations)", "4. BOM (Receptury)", "4. BOM (Stykliste)"), type=['xlsx', 'csv'])
    file_rutas = st.file_uploader(tr("5. Rutas / Routing", "5. Production Routing", "5. Marszruty Produkcyjne", "5. Produktionsruter"), type=['xlsx', 'csv'])
    file_cal = st.file_uploader(tr("6. Calendario", "6. Plant Calendar", "6. Kalendarz Zakładu", "6. Fabriks-kalender"), type=['xlsx', 'csv'])
    
    st.divider()
    st.header(tr("🚀 2. ERP Pipeline (Ejecución)", "🚀 2. ERP Pipeline (Execution)", "🚀 2. Zlecenia ERP (Realizacja)", "🚀 2. ERP Pipeline (Udførelse)"))
    file_compras_erp = st.file_uploader(tr("7. ERP Compras / POs", "7. ERP Purchase Orders (POs)", "7. Zamówienia Zakupu ERP (PO)", "7. ERP Indkøbsordrer (PO)"), type=['xlsx', 'csv'])
    file_produccion_erp = st.file_uploader(tr("8. ERP Producción / Prd. Orders", "8. ERP Production Orders", "8. Zlecenia Produkcyjne ERP", "8. ERP Produktionsordrer"), type=['xlsx', 'csv'])
    
    st.divider()
    st.header(tr("📈 3. Escenarios Budget", "📈 3. Budget Scenarios", "📈 3. Scenariusze Budżetowe", "📈 3. Budgetscenarier"))
    file_budget = st.file_uploader(tr("9. Presupuestos (Cat+Cliente)", "9. Budgets (Cat+Cust)", "9. Budżety (Kat+Klient)", "9. Budgetter (Kat+Kunde)"), type=['xlsx', 'csv'])

    

    st.divider()
    st.header(tr("📅 3. Parámetros y Motor IA", "📅 3. Parameters & AI Engine", "📅 3. Parametry i Silnik AI", "📅 3. Parametre & AI-motor"))
    modelo_fcst_sel = st.selectbox(
        tr("🏆 Algoritmo de Forecasting:", "🏆 Forecasting Algorithm:", "🏆 Algorytm Prognozowania:", "🏆 Prognosealgoritme:"),
        ["Auto-ML Best-Fit", "Holt-Winters Seasonal", "Damped Moving Average (WMA)", "Croston TSB (Intermittent)"]
    )
    horizonte = st.slider(tr("Horizonte (Meses):", "Horizon (Months):", "Horyzont (Miesiące):", "Horisont (Måneder):"), 1, 24, 12)
    cobertura_fg = st.slider(tr("Cob. PT (Meses):", "FG Coverage (Months):", "Pokrycie WG (Miesiące):", "FG Dækning (Måneder):"), 0, 6, 1)
    cobertura_rm = st.slider(tr("Cob. MP (Meses):", "RM Coverage (Months):", "Pokrycie SM (Miesiące):", "RM Dækning (Måneder):"), 0, 6, 2)
    
    if "tab5" in modulos_permitidos:
        st.divider()
        st.header(tr("💱 4. Finanzas (FX a GBP)", "💱 4. Finance (FX to GBP)", "💱 4. Finanse (Kursy na GBP)", "💱 4. Økonomi (Valuta til GBP)"))
        fx_eur_gbp = st.number_input("EUR -> GBP:", value=0.85, step=0.01)
        fx_dkk_gbp = st.number_input("DKK -> GBP:", value=0.11, step=0.01)
        fx_pln_gbp = st.number_input("PLN -> GBP:", value=0.20, step=0.01)
    else:
        fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp = 0.85, 0.11, 0.20
    
    st.divider()
    usar_limpieza_outliers = st.checkbox(tr("🧹 Limpiar Outliers (IQR)", "🧹 Clean Outliers (IQR)", "🧹 Usuń Wartości Odstające", "🧹 Rens Outliers"), value=True)


@st.cache_data(show_spinner=False)
def _leer_archivo_subido_bytes(contenido_bytes, nombre_archivo):
    if nombre_archivo.endswith('.csv'):
        return pd.read_csv(io.BytesIO(contenido_bytes))
    return pd.read_excel(io.BytesIO(contenido_bytes))


def validar_y_cargar_tabla(uploaded_file, columnas_obligatorias, nombre_tabla, permitir_vacio=False):
    if uploaded_file is None:
        return None
        
    if isinstance(uploaded_file, pd.DataFrame):
        d = uploaded_file.copy()
    else:
        try:
            uploaded_file.seek(0)
            raw_bytes = uploaded_file.read()
            fname = getattr(uploaded_file, 'name', 'file.xlsx')
            d = _leer_archivo_subido_bytes(raw_bytes, fname).copy()
        except Exception as e:
            st.error(f"❌ {tr('Error al leer el archivo para', 'Error reading file for')} **{nombre_tabla}**: {e}")
            return None

    if d is None:
        st.error(f"❌ {tr('No se pudo procesar el archivo de', 'Could not process file for')} **{nombre_tabla}**.")
        return None

    d.columns = d.columns.astype(str).str.strip()

    columnas_faltantes = [col for col in columnas_obligatorias if col not in d.columns]
    if columnas_faltantes:
        st.error(
            f"🚨 **{tr('Nombre de columna incorrecto en', 'Incorrect column name in')} [{nombre_tabla}]**\n\n"
            f"{tr('Faltan las siguientes columnas obligatorias exactas', 'Missing exact mandatory columns')}: `{columnas_faltantes}`\n\n"
            f"{tr('Columnas esperadas', 'Expected columns')}: `{columnas_obligatorias}`\n\n"
            f"{tr('Columnas detectadas en tu archivo', 'Detected columns in your file')}: `{d.columns.tolist()}`"
        )
        return None

    if d.empty and not permitir_vacio:
        st.warning(f"⚠️ {tr('El archivo', 'File')} **{nombre_tabla}** {tr('tiene las columnas correctas pero está vacío.', 'has valid columns but contains no rows.')}")
        return None

    return d


# --- CARGA Y VALIDACIÓN ESTRICTA DE LAS 8 TABLAS + NPI CLOUD + SINCRONIZACIÓN GITHUB ---
if 'df_ajustes' not in st.session_state or not isinstance(st.session_state['df_ajustes'], pd.DataFrame):
    df_cloud_init = github_leer_csv(CLOUD_AJUSTES_FILE, COLS_AJUSTES)
    if not df_cloud_init.empty and set(COLS_AJUSTES).issubset(df_cloud_init.columns):
        st.session_state['df_ajustes'] = df_cloud_init[COLS_AJUSTES].copy()
    else:
        st.session_state['df_ajustes'] = pd.DataFrame(columns=COLS_AJUSTES)

if 'df_npi' not in st.session_state or not isinstance(st.session_state['df_npi'], pd.DataFrame):
    df_npi_init = github_leer_csv(NPI_CLOUD_FILE, COLS_NPI)
    if not df_npi_init.empty and set(COLS_NPI).issubset(df_npi_init.columns):
        st.session_state['df_npi'] = df_npi_init[COLS_NPI].copy()
    else:
        st.session_state['df_npi'] = pd.DataFrame(columns=COLS_NPI)

if 'last_ajuste_file' not in st.session_state:
    st.session_state['last_ajuste_file'] = None


# --- PERSISTENCIA AUTOMÁTICA DE DATOS REALES EN LA NUBE ---
def guardar_archivo_subido_cloud(file_obj, filename_cloud):
    if file_obj is not None:
        try:
            # Leemos el archivo recién subido
            df = _leer_archivo_subido_bytes(file_obj.getvalue() if hasattr(file_obj, 'getvalue') else file_obj.read(), getattr(file_obj, 'name', 'file.xlsx'))
            # Lo guardamos en GitHub para que esté disponible la próxima vez
            github_guardar_csv(df, filename_cloud, f"Actualización de {filename_cloud} por {usuario_actual}")
            # Reseteamos el puntero del archivo
            file_obj.seek(0)
            return True
        except Exception:
            pass
    return False

# Nombres en la nube para cada maestro
CLOUD_FILES = {
    "hist": "1_Historico_Ventas_Cloud.csv",
    "stock": "3_Stock_Actual_Cloud.csv",
    "bom": "4_BOM_Cloud.csv",
    "rutas": "5_Rutas_Cloud.csv",
    "cal": "6_Calendario_Cloud.csv",
    "compras": "7_POs_Compras_Cloud.csv",
    "prod": "8_Ordenes_Produccion_Cloud.csv",
    "budget": "9_Presupuestos_Cloud.csv"
}

# Guardamos en la nube si hay archivos subidos nuevos
if file_hist: guardar_archivo_subido_cloud(file_hist, CLOUD_FILES["hist"])
if file_stock: guardar_archivo_subido_cloud(file_stock, CLOUD_FILES["stock"])
if file_bom: guardar_archivo_subido_cloud(file_bom, CLOUD_FILES["bom"])
if file_rutas: guardar_archivo_subido_cloud(file_rutas, CLOUD_FILES["rutas"])
if file_cal: guardar_archivo_subido_cloud(file_cal, CLOUD_FILES["cal"])
if file_compras_erp: guardar_archivo_subido_cloud(file_compras_erp, CLOUD_FILES["compras"])
if file_produccion_erp: guardar_archivo_subido_cloud(file_produccion_erp, CLOUD_FILES["prod"])
if file_budget: guardar_archivo_subido_cloud(file_budget, CLOUD_FILES["budget"])

# --- LÓGICA DE CARGA: UPLOADER > CLOUD > DEMO ---
# Si no hay archivo en el uploader, intentamos leer de la nube. Si la nube está vacía, usamos el Demo (si está activo).
def cargar_maestro(file_obj, col_req, nombre_tabla, cloud_filename, vacio_ok=False, df_demo_fallback=None):
    if file_obj is not None:
        return validar_y_cargar_tabla(file_obj, col_req, nombre_tabla, permitir_vacio=vacio_ok)
    else:
        df_cloud = github_leer_csv(cloud_filename, col_req, forzar_recarga=False)
        if not df_cloud.empty:
            return df_cloud
        elif st.session_state.get("modo_demo_8", False) and df_demo_fallback is not None:
            return df_demo_fallback
        else:
            return pd.DataFrame(columns=col_req) if vacio_ok else None

# Obtenemos los demos por si acaso
if st.session_state.get("modo_demo_8", False):
    demos = obtener_excels_big_data_8_tablas() if "Big Data" in escala_demo else obtener_excels_demo_8_tablas()
else:
    demos = {k: None for k in ["hist", "ajustes", "stock", "bom", "rutas", "cal", "compras_erp", "produccion_erp", "budget"]}


df_raw = cargar_maestro(file_hist, COLS_HIST, "1. Histórico Ventas", CLOUD_FILES["hist"], vacio_ok=False, df_demo_fallback=demos["hist"])





id_ajuste_actual = f"DEMO_AJUSTES_{escala_demo}" if isinstance(file_ajustes, pd.DataFrame) else getattr(file_ajustes, "name", None)
if file_ajustes is not None and id_ajuste_actual != st.session_state['last_ajuste_file']:
    df_aj_cargado = validar_y_cargar_tabla(file_ajustes, COLS_AJUSTES, "2. Ajustes Consenso", permitir_vacio=True)
    if isinstance(df_aj_cargado, pd.DataFrame) and not df_aj_cargado.empty:
        st.session_state['df_ajustes'] = df_aj_cargado
    elif str(id_ajuste_actual).startswith("DEMO_AJUSTES") and isinstance(df_aj_cargado, pd.DataFrame):
        st.session_state['df_ajustes'] = df_aj_cargado
    st.session_state['last_ajuste_file'] = id_ajuste_actual
elif file_ajustes is None and str(st.session_state['last_ajuste_file']).startswith("DEMO_AJUSTES"):
    df_cloud_fallback = github_leer_csv(CLOUD_AJUSTES_FILE, COLS_AJUSTES)
    st.session_state['df_ajustes'] = df_cloud_fallback[COLS_AJUSTES].copy() if not df_cloud_fallback.empty else pd.DataFrame(columns=COLS_AJUSTES)
    st.session_state['last_ajuste_file'] = None

df_ajustes = st.session_state['df_ajustes']
df_stock = cargar_maestro(file_stock, COLS_STOCK, "3. Stock Actual", CLOUD_FILES["stock"], vacio_ok=False, df_demo_fallback=demos["stock"])
df_bom = cargar_maestro(file_bom, COLS_BOM, "4. BOM", CLOUD_FILES["bom"], vacio_ok=False, df_demo_fallback=demos["bom"])
df_rutas = cargar_maestro(file_rutas, COLS_RUTAS, "5. Rutas / Routing", CLOUD_FILES["rutas"], vacio_ok=False, df_demo_fallback=demos["rutas"])
df_cal = cargar_maestro(file_cal, COLS_CAL, "6. Calendario", CLOUD_FILES["cal"], vacio_ok=False, df_demo_fallback=demos["cal"])
df_compras_erp = cargar_maestro(file_compras_erp, COLS_COMPRAS, "7. ERP Compras / POs", CLOUD_FILES["compras"], vacio_ok=True, df_demo_fallback=demos["compras_erp"])
df_produccion_erp = cargar_maestro(file_produccion_erp, COLS_PROD, "8. ERP Producción", CLOUD_FILES["prod"], vacio_ok=True, df_demo_fallback=demos["produccion_erp"])
df_budget = cargar_maestro(file_budget, COLS_BUDGET, "9. Presupuestos", CLOUD_FILES["budget"], vacio_ok=True, df_demo_fallback=demos.get("budget", None))

if df_raw is None or df_raw.empty:
    st.info(tr(
        "👈 Pulsa **'🚀 Cargar 8 Tablas'** en la barra lateral para iniciar la Demo (Ligera o Big Data 150.000 filas) o sube **1. Histórico Ventas**.",
        "👈 Click **'🚀 Load 8 Tables'** in the sidebar to start the Demo (Light or Big Data 150,000 rows) or upload **1. Sales History**."
    ))
    st.stop()


# --- INYECCIÓN AUTOMÁTICA DE NUEVOS LANZAMIENTOS (NPI / NEW BUSINESS) EN MAESTROS ---
df_npi_active = st.session_state.get('df_npi', pd.DataFrame(columns=COLS_NPI))
if df_npi_active is not None and not df_npi_active.empty:
    f_max_raw = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce').max()
    if pd.isna(f_max_raw):
        f_max_raw = pd.Timestamp.today().replace(day=1)
    fechas_semilla_npi = pd.date_range(end=f_max_raw.replace(day=1), periods=6, freq="MS")

    filas_hist_npi = []
    filas_stk_npi = []
    filas_rut_npi = []
    for _, r_npi in df_npi_active.iterrows():
        s_npi = str(r_npi['sku cod']).strip()
        d_npi = str(r_npi['sku desc']).strip()
        p_npi = str(r_npi['País']).strip()
        c_npi = str(r_npi['customer cod']).strip()
        cd_npi = str(r_npi['customer desc']).strip()
        vol_npi = max(1.0, float(pd.to_numeric(r_npi['Volumen_Mensual_Kg'], errors='coerce') or 1000.0))
        pr_npi = max(0.1, float(pd.to_numeric(r_npi['Precio_Unit_EUR'], errors='coerce') or 3.5))
        mg_npi = float(pd.to_numeric(r_npi['Margen_Unit_EUR'], errors='coerce') or 1.1)
        maq_npi = str(r_npi['Maquina']).strip()
        kph_npi = max(100.0, float(pd.to_numeric(r_npi['Kilos_por_Hora'], errors='coerce') or 4000.0))
        pol_npi = str(r_npi.get('Politica_Stock', 'MTS')).strip().upper()

        for f_s in fechas_semilla_npi:
            filas_hist_npi.append({
                "Date": f_s, "País": p_npi, "customer cod": c_npi, "customer desc": cd_npi,
                "sku cod": s_npi, "sku desc": d_npi, "volume": vol_npi,
                "revenue": round(vol_npi * pr_npi, 2), "margin": round(vol_npi * mg_npi, 2), "currency": "EUR",
                "Categoria_Producto": "NPI / New Business", "KAM": usuario_actual
            })
        filas_stk_npi.append({
            "sku cod": s_npi, "sku desc": d_npi, "stock_disponible": 0.0,
            "Cobertura_Meses": 1 if pol_npi == "MTS" else 0, "LT_Meses": 1,
            "Categoria": pol_npi, "Coste_Unitario": max(0.1, round(pr_npi - mg_npi, 2))
        })
        filas_rut_npi.append({
            "sku cod": s_npi, "Maquina": maq_npi, "Kilos_por_Hora": kph_npi
        })

    if filas_hist_npi:
        df_raw = pd.concat([df_raw, pd.DataFrame(filas_hist_npi)[COLS_HIST]], ignore_index=True)
    if df_stock is not None and filas_stk_npi:
        df_stock = pd.concat([df_stock, pd.DataFrame(filas_stk_npi)[COLS_STOCK]], ignore_index=True).drop_duplicates(subset=['sku cod'], keep='last')
    if df_rutas is not None and filas_rut_npi:
        df_rutas = pd.concat([df_rutas, pd.DataFrame(filas_rut_npi)[COLS_RUTAS]], ignore_index=True).drop_duplicates(subset=['sku cod'], keep='last')


# --- ROW LEVEL SECURITY (RLS) POR KAM (POST-INYECCIÓN) ---
if df_raw is not None and not df_raw.empty and "KAM" in df_raw.columns:
    if st.session_state.get("rol") == "KAM" or usuario_actual == "kam_juan":
        df_raw = df_raw[df_raw['KAM'].astype(str).str.lower().str.strip() == usuario_actual.lower()]
        if df_raw.empty:
            st.warning(f"⚠️ {st.session_state.get('name', usuario_actual)}, no tienes clientes asignados en el histórico de ventas.")
            st.stop()


# ==========================================
# PREPROCESADO VECTORIZADO CON CACHÉ (BIG DATA OPTIMIZATION)
# ==========================================
@st.cache_data(show_spinner=False)
def preprocesar_historico_ventas(df_in, f_eur, f_dkk, f_pln):
    d = df_in.copy()
    d['Date'] = pd.to_datetime(d['Date'], dayfirst=True, errors='coerce')
    d = d.dropna(subset=['Date'])
    fecha_max = d['Date'].max()
    fecha_corte = fecha_max - pd.DateOffset(months=24)
    d = d[d['Date'] >= fecha_corte].copy()

    d['sku cod'] = d['sku cod'].astype(str).str.strip()
    d['volume'] = pd.to_numeric(d['volume'], errors='coerce').fillna(0.0)
    d['revenue'] = pd.to_numeric(d['revenue'], errors='coerce').fillna(0.0)
    d['margin'] = pd.to_numeric(d['margin'], errors='coerce').fillna(0.0)

    dict_fx = {'EUR': f_eur, 'DKK': f_dkk, 'PLN': f_pln, 'GBP': 1.0}
    d['Moneda'] = d['currency'].astype(str).str.strip().str.upper()
    d['FX'] = d['Moneda'].map(dict_fx).fillna(1.0)
    d['Rev_GBP'] = d['revenue'] * d['FX']
    d['Mar_GBP'] = d['margin'] * d['FX']

    df_fin_b = d.groupby('sku cod', as_index=False).agg({'volume': 'sum', 'Rev_GBP': 'sum', 'Mar_GBP': 'sum'})
    df_fin_b['unit_price'] = np.where(df_fin_b['volume'] > 0, df_fin_b['Rev_GBP'] / df_fin_b['volume'], 0.0)
    df_fin_b['unit_margin'] = np.where(df_fin_b['volume'] > 0, df_fin_b['Mar_GBP'] / df_fin_b['volume'], 0.0)

    d_price = dict(zip(df_fin_b['sku cod'], df_fin_b['unit_price']))
    d_margin = dict(zip(df_fin_b['sku cod'], df_fin_b['unit_margin']))
    d_curr = dict(zip(df_fin_b['sku cod'], ['GBP'] * len(df_fin_b)))
    d_desc = d.dropna(subset=['sku desc']).groupby('sku cod')['sku desc'].first().to_dict()
    d_cli_desc = d.dropna(subset=['customer desc']).groupby('customer cod')['customer desc'].first().to_dict()

    return d, d_price, d_margin, d_curr, d_desc, d_cli_desc


df, dict_price, dict_margin, dict_currency, dict_sku_desc, dict_cli_desc = preprocesar_historico_ventas(df_raw, fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp)

@st.cache_data(show_spinner=False)
def get_global_volumes(df_in):
    if df_in is None or df_in.empty:
        return {}, {}
    d_tmp = df_in.copy()
    d_tmp['País'] = d_tmp['País'].astype(str).str.strip()
    d_tmp['customer cod'] = d_tmp['customer cod'].astype(str).str.strip()
    d_tmp['sku cod'] = d_tmp['sku cod'].astype(str).str.strip()
    v_sku = d_tmp.groupby('sku cod')['volume'].sum().to_dict()
    v_tupla = d_tmp.groupby(['País', 'customer cod', 'sku cod'])['volume'].sum().to_dict()
    return v_sku, v_tupla

vol_global_sku_cached, vol_global_tupla_cached = get_global_volumes(df)



# ==========================================
# TORNEO MULTI-MODELO VECTORIZADO (AUTO-ML BEST-FIT + HERENCIA NPI)
# ==========================================
@st.cache_data(show_spinner=False)
def precalcular_matriz_forecast_vectorizada(df_in, steps=24, usar_outliers=True, npi_records=None):
    if df_in is None or df_in.empty:
        return {}, {}

    df_m = df_in.groupby([pd.Grouper(key='Date', freq='MS'), 'sku cod'])['volume'].sum().unstack(fill_value=0.0)
    idx_full = pd.date_range(start=df_m.index.min(), end=df_m.index.max(), freq="MS")
    df_m = df_m.reindex(idx_full, fill_value=0.0)
    df_m.columns = [str(c).strip() for c in df_m.columns]

    vals = df_m.values.astype(float)
    T, N = vals.shape
    skus = df_m.columns.tolist()

    if usar_outliers and T >= 6:
        q25 = np.percentile(vals, 25, axis=0, keepdims=True)
        q75 = np.percentile(vals, 75, axis=0, keepdims=True)
        iqr = q75 - q25
        vals_clean = np.clip(vals, np.maximum(0.0, q25 - 1.5 * iqr), q75 + 1.5 * iqr)
    else:
        vals_clean = vals.copy()

    meses_num = df_m.index.month.values
    media_global_sku = np.maximum(vals_clean.mean(axis=0, keepdims=True), 1e-6)
    indices_est = np.ones((12, N), dtype=float)
    if T >= 12:
        for m in range(1, 13):
            mask_m = (meses_num == m)
            if mask_m.any():
                indices_est[m - 1, :] = np.clip(vals_clean[mask_m, :].mean(axis=0) / media_global_sku[0, :], 0.4, 2.2)

    w_rec = min(6, T)
    pesos = np.arange(1, w_rec + 1, dtype=float).reshape(-1, 1)
    nivel_wma = (vals_clean[-w_rec:, :] * pesos).sum(axis=0) / pesos.sum()

    if T >= 6:
        mitad = min(6, T // 2)
        media_rec = vals_clean[-mitad:, :].mean(axis=0)
        media_ant = vals_clean[-2 * mitad:-mitad, :].mean(axis=0)
        slope = (media_rec - media_ant) / float(mitad)
    else:
        slope = np.zeros(N, dtype=float)

    mask_pos = (vals_clean > 0).astype(float)
    prob_dem = mask_pos[-w_rec:, :].mean(axis=0)
    sum_pos = (vals_clean * mask_pos).sum(axis=0)
    cnt_pos = np.maximum(mask_pos.sum(axis=0), 1.0)
    tam_pos = sum_pos / cnt_pos
    nivel_croston = prob_dem * tam_pos

    h_val = min(6, max(1, T - 1))
    actual_val = vals[-h_val:, :]
    meses_val = df_m.index[-h_val:].month.values - 1

    pred_hw_val = np.maximum(0.0, nivel_wma.reshape(1, -1) * indices_est[meses_val, :])
    pred_wma_val = np.repeat(np.maximum(0.0, nivel_wma.reshape(1, -1)), h_val, axis=0)
    pred_cro_val = np.repeat(np.maximum(0.0, nivel_croston.reshape(1, -1)), h_val, axis=0)

    denom_val = np.maximum(actual_val.sum(axis=0), 1.0)
    wape_hw = np.abs(actual_val - pred_hw_val).sum(axis=0) / denom_val * 100.0
    wape_wma = np.abs(actual_val - pred_wma_val).sum(axis=0) / denom_val * 100.0
    wape_cro = np.abs(actual_val - pred_cro_val).sum(axis=0) / denom_val * 100.0

    idx_fut = pd.date_range(start=df_m.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
    meses_fut = idx_fut.month.values - 1

    fcst_hw = np.zeros((steps, N), dtype=float)
    fcst_wma = np.zeros((steps, N), dtype=float)
    fcst_cro = np.zeros((steps, N), dtype=float)

    for s in range(steps):
        amort = (0.88 ** (s + 1))
        base_t = np.maximum(0.0, nivel_wma + slope * (s + 1) * amort)
        fcst_hw[s, :] = np.maximum(0.0, base_t * indices_est[meses_fut[s], :])
        fcst_wma[s, :] = np.maximum(0.0, nivel_wma + slope * 0.5 * amort)
        fcst_cro[s, :] = np.maximum(0.0, nivel_croston)

    matriz_wapes = np.vstack([wape_hw, wape_wma, wape_cro])
    ganador_idx = np.argmin(matriz_wapes, axis=0)
    nombres_mod = ["Holt-Winters Seasonal", "Damped Moving Average (WMA)", "Croston TSB (Intermittent)"]

    fcst_best = np.choose(ganador_idx.reshape(1, -1), [fcst_hw, fcst_wma, fcst_cro])

    # Aplicar curva de lanzamiento y estacionalidad espejo a los SKUs NPI (New Business)
    if npi_records:
        sku_to_col = {s: i for i, s in enumerate(skus)}
        for r_npi in npi_records:
            s_npi = str(r_npi.get('sku cod', '')).strip()
            s_esp = str(r_npi.get('SKU_Espejo', '')).strip()
            vol_obj = float(r_npi.get('Volumen_Mensual_Kg', 0.0))
            m_ini = max(1, int(r_npi.get('Mes_Inicio', 1)))
            if s_npi in sku_to_col:
                c_idx = sku_to_col[s_npi]
                est_vec = indices_est[:, sku_to_col[s_esp]] if s_esp in sku_to_col else np.ones(12)
                for s in range(steps):
                    if (s + 1) < m_ini:
                        val_m = 0.0
                    else:
                        val_m = vol_obj * est_vec[meses_fut[s]]
                    fcst_best[s, c_idx] = val_m
                    fcst_hw[s, c_idx] = val_m
                    fcst_wma[s, c_idx] = val_m
                    fcst_cro[s, c_idx] = val_m

    dict_series = {
        "Auto-ML Best-Fit": pd.DataFrame(fcst_best, index=idx_fut, columns=skus),
        "Holt-Winters Seasonal": pd.DataFrame(fcst_hw, index=idx_fut, columns=skus),
        "Damped Moving Average (WMA)": pd.DataFrame(fcst_wma, index=idx_fut, columns=skus),
        "Croston TSB (Intermittent)": pd.DataFrame(fcst_cro, index=idx_fut, columns=skus),
    }

    meta_torneo = {}
    for j, s_cod in enumerate(skus):
        g_i = int(ganador_idx[j])
        meta_torneo[s_cod] = {
            "Ganador": nombres_mod[g_i],
            "WAPE_HW": round(float(wape_hw[j]), 1),
            "WAPE_WMA": round(float(wape_wma[j]), 1),
            "WAPE_Croston": round(float(wape_cro[j]), 1),
            "WAPE_Min": round(float(matriz_wapes[g_i, j]), 1),
            "Std_Mensual": float(vals_clean[:, j].std()),
            "Media_Mensual": float(vals_clean[:, j].mean())
        }

    return dict_series, meta_torneo


# --- HUELLA DIGITAL DEL DATASET ACTIVO (INCLUYE SUMA DE VOLUMEN Y NPI PARA INVALIDAR CACHÉ) ---
_firma_skus = f"{len(df)}_{int(df['volume'].sum())}_{df['Date'].max().strftime('%Y%m%d') if not df.empty else 'none'}_{df['sku cod'].iloc[0]}" if (df is not None and not df.empty) else "empty"
_firma_bom = f"{len(df_bom)}_{df_bom['rm cod'].iloc[0]}_{df_bom['rm cod'].iloc[-1]}" if (df_bom is not None and not df_bom.empty) else "nobom"
_firma_stk = f"{len(df_stock)}_{int(pd.to_numeric(df_stock['stock_disponible'], errors='coerce').fillna(0).sum())}" if (df_stock is not None and not df_stock.empty) else "nostk"
_firma_aj = f"{len(st.session_state.get('df_ajustes', []))}_{float(st.session_state.get('df_ajustes', pd.DataFrame()).get('override_value', pd.Series(dtype=float)).sum()):.1f}"
_firma_npi = f"{len(st.session_state.get('df_npi', []))}"
DATASET_SIGNATURE = f"{_firma_skus}|{_firma_bom}|{_firma_stk}|{_firma_aj}|{_firma_npi}"

# --- SISTEMA DE CACHÉ DE FORECAST (RAM L1 + NUBE L2) ---
FCST_MATRIX_FILE = "fcst_matrix_cache.csv"
FCST_META_FILE = "fcst_meta_cache.json"
SIG_FILE = "dataset_signature.txt"
# El Forecast SOLO depende del histórico de ventas y de los nuevos NPIs, no de los ajustes.
FIRMA_FORECAST = f"{_firma_skus}|{_firma_npi}"

def cargar_forecast_desde_nube_si_valido(firma_actual):
    # L1 Cache (Memoria RAM instantánea en la sesión)
    if "mem_fcst_firma" in st.session_state and st.session_state["mem_fcst_firma"] == firma_actual:
        return st.session_state["mem_fcst_matrices"], st.session_state["mem_fcst_meta"]
        
    # L2 Cache (GitHub Cloud / Local)
    try:
        df_sig = github_leer_csv(SIG_FILE, ["signature"])
        if not df_sig.empty and df_sig.iloc[0]["signature"] == firma_actual:
            df_fcst = github_leer_csv(FCST_MATRIX_FILE, ["Date"])
            if not df_fcst.empty and "Modelo" in df_fcst.columns:
                dict_matrices = {}
                for modelo, grp in df_fcst.groupby("Modelo"):
                    df_mod = grp.drop(columns=["Modelo"]).set_index("Date")
                    df_mod.index = pd.to_datetime(df_mod.index)
                    dict_matrices[modelo] = df_mod
                
                try:
                    token, repo = _github_creds()
                    if token and repo:
                        url = f"https://api.github.com/repos/{repo}/contents/{FCST_META_FILE}"
                        req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SOP-Platform-Cloud"})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            contenido = base64.b64decode(data["content"]).decode("utf-8")
                            dict_meta = json.loads(contenido)
                            
                            # Guardar en RAM L1
                            st.session_state["mem_fcst_firma"] = firma_actual
                            st.session_state["mem_fcst_matrices"] = dict_matrices
                            st.session_state["mem_fcst_meta"] = dict_meta
                            
                            return dict_matrices, dict_meta
                except Exception:
                    pass
    except Exception:
        pass
    return None, None

def guardar_forecast_en_nube(dict_matrices, dict_meta, firma_actual):
    # Guardar en RAM L1 de inmediato
    st.session_state["mem_fcst_firma"] = firma_actual
    st.session_state["mem_fcst_matrices"] = dict_matrices
    st.session_state["mem_fcst_meta"] = dict_meta

    try:
        lista_df = []
        for modelo, df_m in dict_matrices.items():
            df_tmp = df_m.copy().reset_index()
            df_tmp["Modelo"] = modelo
            lista_df.append(df_tmp)
        df_final_fcst = pd.concat(lista_df, ignore_index=True)
        github_guardar_csv(df_final_fcst, FCST_MATRIX_FILE, "Update Forecast Matrix Cache")
        
        token, repo = _github_creds()
        if token and repo:
            url = f"https://api.github.com/repos/{repo}/contents/{FCST_META_FILE}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SOP-Platform-Cloud"}
            sha_actual = None
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sha_actual = data.get("sha")
            except Exception:
                pass
            payload = {"message": "Update Forecast Metadata Cache", "content": base64.b64encode(json.dumps(dict_meta).encode("utf-8")).decode("utf-8")}
            if sha_actual: payload["sha"] = sha_actual
            req_put = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="PUT")
            urllib.request.urlopen(req_put, timeout=5)
            
        github_guardar_csv(pd.DataFrame([{"signature": firma_actual}]), SIG_FILE, "Update Dataset Signature")
    except Exception:
        pass

npi_records_tuple = tuple(df_npi_active.to_dict('records')) if (df_npi_active is not None and not df_npi_active.empty) else None

dict_fcst_matrices, dict_meta_torneo = cargar_forecast_desde_nube_si_valido(FIRMA_FORECAST)

if dict_fcst_matrices is None or dict_meta_torneo is None:
    with st.spinner("Generando modelos estadísticos Auto-ML (Primera vez o datos nuevos)..."):
        dict_fcst_matrices, dict_meta_torneo = precalcular_matriz_forecast_vectorizada(df, steps=24, usar_outliers=usar_limpieza_outliers, npi_records=npi_records_tuple)
        guardar_forecast_en_nube(dict_fcst_matrices, dict_meta_torneo, FIRMA_FORECAST)



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
    df_cv['std'] = df_cv['std'].fillna(0.0)
    df_cv['CV'] = (df_cv['std'] / df_cv['mean'].replace(0, 1)).replace([np.inf, -np.inf], 0).fillna(0)
    df_cv['XYZ'] = np.where(df_cv['CV'] <= 0.5, 'X', np.where(df_cv['CV'] <= 1.0, 'Y', 'Z'))
    
    df_res = pd.merge(df_vol[['sku cod', 'volume', 'ABC']], df_cv[['sku cod', 'mean', 'std', 'CV', 'XYZ']], on='sku cod')
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
    pais_sel = st.selectbox(tr("1. País:", "1. Country:", "1. Kraj:", "1. Land:"), lista_paises)
df_f1 = df if pais_sel == "TODOS" else df[df['País'].astype(str) == pais_sel]

with col_f2:
    if 'Categoria_Producto' in df_f1.columns:
        lista_cats = ["TODAS"] + sorted(df_f1['Categoria_Producto'].dropna().astype(str).unique().tolist())
    else:
        lista_cats = ["TODAS"]
    cat_sel = st.selectbox(tr("2. Categoría:", "2. Category:"), lista_cats)
df_f2 = df_f1 if cat_sel == "TODAS" else df_f1[df_f1['Categoria_Producto'].astype(str) == cat_sel]

with col_f3:
    lista_clis = ["TODOS"] + sorted(df_f2['customer cod'].dropna().astype(str).unique().tolist())
    cliente_sel = st.selectbox(
        tr("3. Cliente:", "3. Customer:"), 
        lista_clis,
        format_func=lambda x: "TODOS" if x == "TODOS" else dict_cli_desc.get(x, x)
    )
df_f3 = df_f2 if cliente_sel == "TODOS" else df_f2[df_f2['customer cod'].astype(str) == cliente_sel]

with col_f4:
    lista_skus = ["TODOS"] + sorted(df_f3['sku cod'].dropna().astype(str).unique().tolist())
    sku_sel = st.selectbox(
        tr("4. SKU (PT):", "4. SKU (FG):"), 
        lista_skus,
        format_func=lambda x: "TODOS" if x == "TODOS" else dict_sku_desc.get(x, x)
    )
df_final = df_f3 if sku_sel == "TODOS" else df_f3[df_f3['sku cod'].astype(str) == sku_sel]

col_objetivo = 'volume'

if df_bom is not None and not df_bom.empty:
    dict_rm_desc = dict(zip(df_bom['rm cod'].astype(str).str.strip(), df_bom['rm desc']))
else:
    dict_rm_desc = {}

dict_prd_erp = {}
if df_produccion_erp is not None and not df_produccion_erp.empty:
    df_p_tmp = df_produccion_erp.copy()
    df_p_tmp['sku cod'] = df_p_tmp['sku cod'].astype(str).str.strip()
    df_p_tmp['Date'] = pd.to_datetime(df_p_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
    df_p_tmp['Cantidad_Kg'] = pd.to_numeric(df_p_tmp['Cantidad_Kg'], errors='coerce').fillna(0)
    dict_prd_erp = df_p_tmp.dropna(subset=['Date']).groupby(['sku cod', 'Date'])['Cantidad_Kg'].sum().to_dict()

dict_cmp_erp = {}
if df_compras_erp is not None and not df_compras_erp.empty:
    df_c_tmp = df_compras_erp.copy()
    df_c_tmp['rm cod'] = df_c_tmp['rm cod'].astype(str).str.strip()
    df_c_tmp['Date'] = pd.to_datetime(df_c_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
    df_c_tmp['Cantidad_Kg'] = pd.to_numeric(df_c_tmp['Cantidad_Kg'], errors='coerce').fillna(0)
    dict_cmp_erp = df_c_tmp.dropna(subset=['Date']).groupby(['rm cod', 'Date'])['Cantidad_Kg'].sum().to_dict()


# ==========================================
# 3. FUNCIONES CORE Y MOTOR MATRICIAL 2D (CON FIRMA DE CACHÉ DATASET_SIGNATURE)
# ==========================================
@st.cache_data(show_spinner=False)
def _indexar_stock_rapido(df_s):
    if df_s is None or df_s.empty:
        return {}
    d = df_s.copy()
    d['sku_clean'] = d['sku cod'].astype(str).str.strip()
    d['stk'] = pd.to_numeric(d['stock_disponible'], errors='coerce').fillna(0.0)
    d['cob'] = pd.to_numeric(d['Cobertura_Meses'], errors='coerce').fillna(1).astype(int)
    d['lt'] = pd.to_numeric(d['LT_Meses'], errors='coerce').fillna(0).astype(int)
    d['cat'] = d['Categoria'].astype(str).str.strip().str.upper()
    res = {}
    for s_c, grp in d.groupby('sku_clean'):
        cob_v = 0 if (grp['cat'].iloc[0] == 'MTO') else int(grp['cob'].iloc[0])
        res[s_c] = (float(grp['stk'].sum()), cob_v, int(grp['lt'].iloc[0]))
    return res


mapa_stock_fast = _indexar_stock_rapido(df_stock)


def obtener_parametros_stock(codigo, cob_defecto=2):
    s_clean = str(codigo).strip()
    if s_clean in mapa_stock_fast:
        return mapa_stock_fast[s_clean]
    return 0.0, int(cob_defecto), 0




@st.cache_data(show_spinner=False, max_entries=5000)
def limpiar_anomalias(serie):
    if len(serie) < 6:
        return serie
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return serie.clip(lower=max(0, q1 - 1.5 * iqr), upper=q3 + 1.5 * iqr)


@st.cache_data(show_spinner=False, max_entries=5000)
def calcular_forecast_serie_unica(serie, steps, metodo="Auto-ML Best-Fit"):
    if len(serie) == 0:
        return pd.Series([0.0] * steps, index=pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=steps, freq="MS"))
    idx_fut = pd.date_range(start=serie.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
    if len(serie) < 6:
        return pd.Series([max(0.0, float(serie.mean()))] * steps, index=idx_fut)

    if metodo == "Damped Moving Average (WMA)":
        w = min(6, len(serie))
        pesos = np.arange(1, w + 1, dtype=float)
        base_wma = float((serie.tail(w).values * pesos).sum() / pesos.sum())
        slope = float((serie.tail(3).mean() - serie.iloc[-6:-3].mean()) / 3.0) if len(serie) >= 6 else 0.0
        vals = [max(0.0, base_wma + slope * 0.5 * (0.88 ** (i + 1))) for i in range(steps)]
        return pd.Series(vals, index=idx_fut)

    elif metodo == "Croston TSB (Intermittent)":
        vals_s = serie.values.astype(float)
        pos = vals_s[vals_s > 0]
        if len(pos) == 0:
            return pd.Series([0.0] * steps, index=idx_fut)
        prob_p = float((vals_s[-min(6, len(vals_s)):] > 0).mean())
        tam_m = float(pos.mean())
        return pd.Series([max(0.0, prob_p * tam_m)] * steps, index=idx_fut)

    try:
        return ExponentialSmoothing(serie, trend="add", seasonal="add" if len(serie) >= 24 else None, seasonal_periods=12).fit().forecast(steps).apply(lambda x: max(0.0, x))
    except Exception:
        return pd.Series([max(0.0, float(serie.tail(6).mean()))] * steps, index=idx_fut)


def obtener_fcst_sku_rapido(sku_cod, steps, metodo_sel):
    mat = dict_fcst_matrices.get(metodo_sel, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    s_clean = str(sku_cod).strip()
    if mat is not None and s_clean in mat.columns:
        return mat[s_clean].iloc[:steps]
    return pd.Series([0.0] * steps, index=pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=steps, freq="MS"))


def aplicar_variacion_categoria_cliente(categoria, cliente, pct):
    try:
        sub = df[(df['Categoria_Producto'] == categoria) & (df['customer cod'] == cliente)].copy()
        if sub.empty:
            return False, tr("No hay histórico para esa Categoría y Cliente.", "No sales history for that Category and Customer.")
        
        factor = 1.0 + (float(pct) / 100.0)
        df_aj = st.session_state.get('df_ajustes', pd.DataFrame(columns=COLS_AJUSTES)).copy()
        
        skus_afectados = sub['sku cod'].unique()
        # Solo eliminar overrides que choquen exactamente con el cliente y los SKUs afectados de esta categoría
        df_aj = df_aj[~((df_aj['customer cod'] == cliente) & (df_aj['sku cod'].isin(skus_afectados)))]
        
        nuevas = []
        eventos_fva = []
        ahora_cet = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")
        
        vol_global = df.groupby('sku cod')['volume'].sum().to_dict()
        vol_cliente = sub.groupby('sku cod')['volume'].sum().to_dict()
        
        mat = dict_fcst_matrices.get(modelo_fcst_sel, dict_fcst_matrices.get("Auto-ML Best-Fit"))

        for sku_c in skus_afectados:
            # Obtener el país mayoritario para este SKU y cliente (para no fallar con múltiples países)
            pais_sku = sub[sub['sku cod'] == sku_c]['País'].mode()[0]
            s_c_str = str(sku_c).strip()
            
            if mat is not None and not mat.empty and s_c_str in mat.columns:
                fcst = mat[s_c_str].iloc[:int(horizonte)]
                share = vol_cliente.get(sku_c, 0.0) / max(1.0, vol_global.get(sku_c, 1.0))
                
                for f_dt, val in fcst.items():
                    est_val_global = float(val)
                    est_val_cliente = round(est_val_global * share, 2)
                    ovr_val_cliente = round(est_val_cliente * factor, 2)
                    
                    if ovr_val_cliente > 0 or est_val_cliente > 0:
                        nuevas.append({
                            'Date': f_dt, 'País': pais_sku, 'customer cod': cliente,
                            'sku cod': sku_c, 'override_value': ovr_val_cliente
                        })
                        eventos_fva.append({
                            "Fecha_Cambio (CET)": ahora_cet, "Usuario": usuario_actual,
                            "Tipo_Ajuste": f"Macro Factor Cat: {categoria} ({pct:+.1f}%)",
                            "Date": pd.to_datetime(f_dt).strftime("%Y-%m-%d"),
                            "País": pais_sku, "customer cod": cliente, "sku cod": sku_c,
                            "Forecast_Estadistico": est_val_cliente, "Consenso_Override": ovr_val_cliente,
                            "Delta_Kg": round(ovr_val_cliente - est_val_cliente, 2), "Delta_Pct_FVA": round(float(pct), 1)
                        })
        if nuevas:
            df_aj = pd.concat([df_aj, pd.DataFrame(nuevas)], ignore_index=True)
        st.session_state['df_ajustes'] = df_aj
        github_guardar_csv(df_aj, CLOUD_AJUSTES_FILE, f"Macro Factor {categoria} ({pct:+.1f}%) by {usuario_actual}")
        registrar_evento_fva_consenso(eventos_fva)
        return True, "OK"
    except Exception as e:
        return False, str(e)


def congelar_snapshot_ciclo_sop(df_target):
    if df_target is None or df_target.empty:
        return 0
    ahora_cet = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")
    aj_all = st.session_state.get('df_ajustes', pd.DataFrame(columns=COLS_AJUSTES)).copy()
    if not aj_all.empty:
        aj_all['Date_M'] = pd.to_datetime(aj_all['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()

    pares = df_target[['País', 'customer cod', 'sku cod']].drop_duplicates().head(300)
    eventos_snap = []
    h_snap = min(horizonte, 6)

    for _, row_p in pares.iterrows():
        p_val, c_val, s_val = row_p['País'], row_p['customer cod'], row_p['sku cod']
        fcst_est = obtener_fcst_sku_rapido(s_val, h_snap, modelo_fcst_sel)
        mapa_ovr = {}
        if not aj_all.empty:
            sub_aj = aj_all[(aj_all['País'] == p_val) & (aj_all['customer cod'] == c_val) & (aj_all['sku cod'] == s_val)]
            if not sub_aj.empty:
                mapa_ovr = sub_aj.dropna(subset=['Date_M']).groupby('Date_M')['override_value'].sum().to_dict()

        for f_dt, val_e in fcst_est.items():
            f_m = pd.to_datetime(f_dt).replace(day=1)
            est_v = round(float(val_e), 2)
            ovr_v = round(float(mapa_ovr.get(f_m, est_v)), 2)
            delta_kg = round(ovr_v - est_v, 2)
            delta_pct = round((delta_kg / est_v * 100), 1) if est_v > 0 else 0.0
            eventos_snap.append({
                "Fecha_Cambio (CET)": ahora_cet, "Usuario": usuario_actual,
                "Tipo_Ajuste": "Snapshot Ciclo S&OP",
                "Date": f_m.strftime("%Y-%m-%d"), "País": p_val,
                "customer cod": c_val, "sku cod": s_val,
                "Forecast_Estadistico": est_v, "Consenso_Override": ovr_v,
                "Delta_Kg": delta_kg, "Delta_Pct_FVA": delta_pct
            })

    if eventos_snap:
        registrar_evento_fva_consenso(eventos_snap)
    return len(eventos_snap)


@st.cache_data(show_spinner=False)
def calcular_kpis_forecast(df_in, usar_outliers):
    if df_in is None or df_in.empty:
        return 0.0, 0.0, 0.0
    df_eval = df_in.groupby('Date')['volume'].sum().resample("MS").sum().reset_index()
    if len(df_eval) < 6:
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


def aplicar_moq_y_lote_multiplo(serie_necesidad, moq_kg, lote_mult_kg):
    vals = pd.to_numeric(serie_necesidad, errors='coerce').fillna(0.0).values
    res = np.zeros_like(vals, dtype=float)
    moq_val = max(0.0, float(moq_kg))
    mult_val = max(1.0, float(lote_mult_kg))
    for idx, v in enumerate(vals):
        if v <= 0:
            res[idx] = 0.0
        else:
            base_v = max(v, moq_val)
            if mult_val > 1.0:
                res[idx] = np.ceil(base_v / mult_val) * mult_val
            else:
                res[idx] = base_v
    return pd.Series(res, index=serie_necesidad.index)


def construir_diagrama_sankey_red(df_mps_all, df_b, df_r, df_v):
    if df_mps_all is None or df_mps_all.empty or df_b is None or df_b.empty:
        return None

    df_mps_tot = df_mps_all.groupby('sku cod', as_index=False)[['Entradas_Netas', 'Recepciones_ERP']].sum()
    df_mps_tot['Fab_Total_Kg'] = df_mps_tot['Entradas_Netas'] + df_mps_tot['Recepciones_ERP']
    df_mps_tot = df_mps_tot[df_mps_tot['Fab_Total_Kg'] > 0].copy()
    if df_mps_tot.empty:
        return None

    top_skus_net = df_mps_tot.nlargest(8, 'Fab_Total_Kg')['sku cod'].astype(str).str.strip().tolist()
    df_mps_top = df_mps_tot[df_mps_tot['sku cod'].astype(str).str.strip().isin(top_skus_net)].copy()

    mapa_maq = {}
    if df_r is not None and not df_r.empty and 'Maquina' in df_r.columns:
        mapa_maq = dict(zip(df_r['sku cod'].astype(str).str.strip(), df_r['Maquina'].astype(str).str.strip()))

    enlaces = []
    for _, row_p in df_mps_top.iterrows():
        sku_c = str(row_p['sku cod']).strip()
        fab_kg = float(row_p['Fab_Total_Kg'])
        maq_c = f"⚙️ {mapa_maq.get(sku_c, 'Linea_General')}"
        nodo_sku = f"📦 {sku_c}"

        sub_b = df_b[df_b['sku cod'].astype(str).str.strip() == sku_c]
        if not sub_b.empty:
            for _, rb in sub_b.iterrows():
                rm_c = str(rb['rm cod']).strip()
                cant = float(pd.to_numeric(rb['Cantidad'], errors='coerce')) if pd.notna(rb['Cantidad']) else 0.0
                if cant > 0:
                    nodo_rm = f"🧩 {rm_c}"
                    enlaces.append((nodo_rm, maq_c, fab_kg * cant))
        enlaces.append((maq_c, nodo_sku, fab_kg))

        if df_v is not None and not df_v.empty:
            sub_v = df_v[df_v['sku cod'].astype(str).str.strip() == sku_c]
            if not sub_v.empty:
                tot_v_sku = sub_v['volume'].sum()
                if tot_v_sku > 0:
                    for pais_k, vol_p in sub_v.groupby('País')['volume'].sum().items():
                        prop = float(vol_p) / float(tot_v_sku)
                        if prop > 0:
                            enlaces.append((nodo_sku, f"🌍 {pais_k}", fab_kg * prop))

    if not enlaces:
        return None

    df_links = pd.DataFrame(enlaces, columns=['Origen', 'Destino', 'Valor']).groupby(['Origen', 'Destino'])['Valor'].sum().reset_index()
    nodos_unicos = pd.unique(df_links[['Origen', 'Destino']].values.ravel('K')).tolist()
    mapa_idx = {n: i for i, n in enumerate(nodos_unicos)}

    colores_nodos = [
        "#88FFBB" if n.startswith("🧩") else ("#1E3E5B" if n.startswith("⚙️") else ("#3A6B9C" if n.startswith("📦") else "#E6A100"))
        for n in nodos_unicos
    ]

    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(pad=18, thickness=20, line=dict(color="#e0e6ed", width=1), label=nodos_unicos, color=colores_nodos),
        link=dict(
            source=[mapa_idx[o] for o in df_links['Origen']],
            target=[mapa_idx[d] for d in df_links['Destino']],
            value=df_links['Valor'].round(0).tolist(),
            color="rgba(160, 178, 198, 0.38)"
        )
    )])
    fig_sankey.update_layout(
        title=tr(
            "🕸️ Flujo E2E de la Red de Suministro (Top 8 SKUs): Materias Primas → Líneas de Planta → SKUs PT → Mercados (Kg)",
            "🕸️ End-to-End Supply Network Flow (Top 8 SKUs): Raw Materials → Plant Lines → FG SKUs → Markets (Kg)"
        ),
        font=dict(size=12, family="Arial, sans-serif"), height=460, margin=dict(l=15, r=15, t=45, b=15)
    )
    return fig_sankey


def calcular_necesidades_netas(serie_salidas, stock_inicial, cobertura_meses, serie_erp=None):
    idx = serie_salidas.index
    n = len(idx)
    salidas = np.nan_to_num(serie_salidas.values.astype(float), nan=0.0)
    rec_erp = np.nan_to_num(serie_erp.values.astype(float), nan=0.0) if serie_erp is not None else np.zeros(n, dtype=float)

    stk_ini = np.zeros(n, dtype=float)
    stk_obj = np.zeros(n, dtype=float)
    entradas = np.zeros(n, dtype=float)
    stk_fin = np.zeros(n, dtype=float)

    stock_corriente = float(stock_inicial)
    media_reciente = float(salidas[-3:].mean()) if n > 0 else 0.0
    cob = int(cobertura_meses)

    for i in range(n):
        fut_slice = salidas[i + 1 : i + 1 + cob]
        faltantes = max(0, cob - len(fut_slice))
        salida_futura = float(fut_slice.sum()) + faltantes * media_reciente

        stk_ini[i] = stock_corriente
        stk_obj[i] = salida_futura

        nec_real = salidas[i] + salida_futura - stock_corriente - rec_erp[i]
        ent_sug = max(0.0, nec_real)

        entradas[i] = ent_sug
        stock_corriente = stock_corriente + ent_sug + rec_erp[i] - salidas[i]
        stk_fin[i] = stock_corriente

    plan = pd.DataFrame({
        'Salidas_Brutas': salidas, 'Recepciones_ERP': rec_erp,
        'Stock_Inicial': stk_ini, 'Stock_Objetivo': stk_obj,
        'Entradas_Netas': entradas, 'Stock_Final': stk_fin
    }, index=idx)

    demanda_futura_media = plan['Salidas_Brutas'].rolling(window=3, min_periods=1).mean().shift(-1)
    if n > 0:
        demanda_futura_media.iloc[-1] = media_reciente
    plan['DOH'] = np.where(demanda_futura_media > 0, (plan['Stock_Final'] / demanda_futura_media) * 30.0, 0.0)
    plan['DOH'] = plan['DOH'].fillna(0).round(0)
    return plan


# ==========================================
# MOTOR MPS Y MRP 100 % MATRICIAL 2D (CON HASH EXPLÍCITO DE FIRMA `sig`)
# ==========================================
@st.cache_data(show_spinner=False)
def _calcular_mps_df_2d_cached(horiz, cob_fg, metodo_fcst, sig):
    mat_fcst = dict_fcst_matrices.get(metodo_fcst, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if mat_fcst is None or mat_fcst.empty:
        return pd.DataFrame()

    mat_h = mat_fcst.iloc[:horiz].copy()
    idx_fechas = mat_h.index
    skus = [str(s).strip() for s in mat_h.columns.tolist()]
    mat_h.columns = skus
    H, N = mat_h.shape

    salidas_2d = np.nan_to_num(mat_h.values.astype(float), nan=0.0)

    aj_df = st.session_state.get('df_ajustes', pd.DataFrame())
    if aj_df is not None and not aj_df.empty:
        aj_tmp = aj_df.copy()
        aj_tmp['Date_M'] = pd.to_datetime(aj_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
        aj_tmp = aj_tmp.dropna(subset=['Date_M'])
        
        # Fast pivot to aggregate deltas instead of loops
        if not aj_tmp.empty:
            df_global_grp = df.groupby(['País', 'customer cod', 'sku cod'], as_index=False)['volume'].sum()
            df_sku_grp = df.groupby('sku cod')['volume'].sum().to_dict()
            
            aj_merged = pd.merge(aj_tmp, df_global_grp, on=['País', 'customer cod', 'sku cod'], how='inner')
            if not aj_merged.empty:
                for _, r_aj in aj_merged.iterrows():
                    s_c = str(r_aj['sku cod']).strip()
                    d_m = r_aj['Date_M']
                    ovr_v = float(r_aj['override_value'])
                    v_comb = float(r_aj['volume'])
                    
                    if s_c in skus and d_m in idx_fechas:
                        v_glob_sku = max(df_sku_grp.get(s_c, 1e-6), 1e-6)
                        share = v_comb / v_glob_sku
                        
                        idx_t = idx_fechas.get_loc(d_m)
                        idx_s = skus.index(s_c)
                        
                        stat_val_global = float(mat_h.iat[idx_t, idx_s])
                        stat_val_comb = stat_val_global * share
                        
                        delta = ovr_v - stat_val_comb
                        salidas_2d[idx_t, idx_s] = max(0.0, salidas_2d[idx_t, idx_s] + delta)

    rec_erp_2d = np.zeros((H, N), dtype=float)
    if dict_prd_erp:
        sku_to_j = {s: j for j, s in enumerate(skus)}
        fecha_to_i = {f: i for i, f in enumerate(idx_fechas)}
        for (s_k, f_k), v_erp in dict_prd_erp.items():
            s_clean = str(s_k).strip()
            if s_clean in sku_to_j and f_k in fecha_to_i:
                rec_erp_2d[fecha_to_i[f_k], sku_to_j[s_clean]] = float(v_erp)

    stk_ini_vec = np.zeros(N, dtype=float)
    cob_vec = np.full(N, int(cob_fg), dtype=int)
    for j, s_k in enumerate(skus):
        st_v, cb_v, _ = obtener_parametros_stock(s_k, cob_fg)
        stk_ini_vec[j] = st_v
        cob_vec[j] = cb_v

    stk_ini_2d = np.zeros((H, N), dtype=float)
    stk_obj_2d = np.zeros((H, N), dtype=float)
    entradas_2d = np.zeros((H, N), dtype=float)
    stk_fin_2d = np.zeros((H, N), dtype=float)

    stock_corr = stk_ini_vec.copy()
    media_rec_vec = salidas_2d[-min(3, H):, :].mean(axis=0)
    cobs_unicas = np.unique(cob_vec)

    for i in range(H):
        salida_futura = np.zeros(N, dtype=float)
        for c_val in cobs_unicas:
            if c_val <= 0:
                continue
            mask_c = (cob_vec == c_val)
            fut_slice = salidas_2d[i + 1 : i + 1 + c_val, mask_c]
            falt = max(0, int(c_val) - fut_slice.shape[0])
            salida_futura[mask_c] = fut_slice.sum(axis=0) + falt * media_rec_vec[mask_c]

        stk_ini_2d[i, :] = stock_corr
        stk_obj_2d[i, :] = salida_futura
        nec_real = salidas_2d[i, :] + salida_futura - stock_corr - rec_erp_2d[i, :]
        ent_sug = np.maximum(0.0, nec_real)
        entradas_2d[i, :] = ent_sug
        stock_corr = stock_corr + ent_sug + rec_erp_2d[i, :] - salidas_2d[i, :]
        stk_fin_2d[i, :] = stock_corr

    dem_futura_2d = np.vstack([salidas_2d[1:, :], media_rec_vec.reshape(1, -1)])
    doh_2d = np.where(dem_futura_2d > 0, np.round((stk_fin_2d / dem_futura_2d) * 30.0, 0), 0.0)

    fechas_rep = np.repeat(idx_fechas.values, N)
    skus_tile = np.tile(skus, H)
    descs_tile = np.tile([dict_sku_desc.get(s, str(s)) for s in skus], H)

    return pd.DataFrame({
        'Date': fechas_rep,
        'sku cod': skus_tile,
        'sku desc': descs_tile,
        'Salidas_Brutas': salidas_2d.ravel(),
        'Recepciones_ERP': rec_erp_2d.ravel(),
        'Stock_Inicial': stk_ini_2d.ravel(),
        'Stock_Objetivo': stk_obj_2d.ravel(),
        'Entradas_Netas': entradas_2d.ravel(),
        'Stock_Final': stk_fin_2d.ravel(),
        'DOH': doh_2d.ravel()
    })


def generar_mps_df_2d(horiz=None, cob_fg=None, metodo_fcst=None, sig=None):
    h = horiz if horiz is not None else int(horizonte)
    c_fg = cob_fg if cob_fg is not None else int(cobertura_fg)
    mod = metodo_fcst if metodo_fcst is not None else str(modelo_fcst_sel)
    s_key = sig if sig is not None else str(DATASET_SIGNATURE)
    return _calcular_mps_df_2d_cached(h, c_fg, mod, s_key).copy()


@st.cache_data(show_spinner=False)
def _calcular_mrp_global_cached(horiz, cob_fg, cob_rm, metodo_fcst, sig):
    df_mps_all = _calcular_mps_df_2d_cached(horiz, cob_fg, metodo_fcst, sig).copy()
    if df_bom is None or df_bom.empty or df_mps_all.empty:
        return pd.DataFrame()

    df_mps_all['Prod_Total'] = df_mps_all['Entradas_Netas'] + df_mps_all['Recepciones_ERP']
    df_mps_all['sku_clean'] = df_mps_all['sku cod'].astype(str).str.strip()

    df_b_clean = df_bom.copy()
    df_b_clean['sku_clean'] = df_b_clean['sku cod'].astype(str).str.strip()
    df_b_clean['rm_clean'] = df_b_clean['rm cod'].astype(str).str.strip()
    df_b_clean['cant_num'] = pd.to_numeric(df_b_clean['Cantidad'], errors='coerce').fillna(0.0)
    df_b_clean = df_b_clean[df_b_clean['cant_num'] > 0]

    df_explosion = pd.merge(
        df_mps_all[['Date', 'sku_clean', 'Prod_Total']],
        df_b_clean[['sku_clean', 'rm_clean', 'cant_num']],
        on='sku_clean', how='inner'
    )
    if df_explosion.empty:
        return pd.DataFrame()

    df_explosion['Necesidad_Bruta'] = df_explosion['Prod_Total'] * df_explosion['cant_num']
    piv_rm = df_explosion.pivot_table(index='Date', columns='rm_clean', values='Necesidad_Bruta', aggfunc='sum').fillna(0.0)

    idx_fechas = piv_rm.index
    rms = [str(r).strip() for r in piv_rm.columns.tolist()]
    piv_rm.columns = rms
    H, M = piv_rm.shape
    salidas_rm_2d = piv_rm.values.astype(float)

    rec_erp_rm_2d = np.zeros((H, M), dtype=float)
    if dict_cmp_erp:
        rm_to_j = {r: j for j, r in enumerate(rms)}
        fecha_to_i = {f: i for i, f in enumerate(idx_fechas)}
        for (r_k, f_k), v_erp in dict_cmp_erp.items():
            r_clean = str(r_k).strip()
            if r_clean in rm_to_j and f_k in fecha_to_i:
                rec_erp_rm_2d[fecha_to_i[f_k], rm_to_j[r_clean]] = float(v_erp)

    stk_ini_vec = np.zeros(M, dtype=float)
    cob_vec = np.full(M, int(cob_rm), dtype=int)
    lt_vec = np.zeros(M, dtype=int)
    for j, r_k in enumerate(rms):
        st_v, cb_v, lt_v = obtener_parametros_stock(r_k, cob_rm)
        stk_ini_vec[j] = st_v
        cob_vec[j] = cb_v
        lt_vec[j] = lt_v

    stk_ini_2d = np.zeros((H, M), dtype=float)
    stk_obj_2d = np.zeros((H, M), dtype=float)
    entradas_2d = np.zeros((H, M), dtype=float)
    stk_fin_2d = np.zeros((H, M), dtype=float)

    stock_corr = stk_ini_vec.copy()
    media_rec_vec = salidas_rm_2d[-min(3, H):, :].mean(axis=0)
    cobs_unicas = np.unique(cob_vec)

    for i in range(H):
        salida_futura = np.zeros(M, dtype=float)
        for c_val in cobs_unicas:
            if c_val <= 0:
                continue
            mask_c = (cob_vec == c_val)
            fut_slice = salidas_rm_2d[i + 1 : i + 1 + c_val, mask_c]
            falt = max(0, int(c_val) - fut_slice.shape[0])
            salida_futura[mask_c] = fut_slice.sum(axis=0) + falt * media_rec_vec[mask_c]

        stk_ini_2d[i, :] = stock_corr
        stk_obj_2d[i, :] = salida_futura
        nec_real = salidas_rm_2d[i, :] + salida_futura - stock_corr - rec_erp_rm_2d[i, :]
        ent_sug = np.maximum(0.0, nec_real)
        entradas_2d[i, :] = ent_sug
        stock_corr = stock_corr + ent_sug + rec_erp_rm_2d[i, :] - salidas_rm_2d[i, :]
        stk_fin_2d[i, :] = stock_corr

    lanz_2d = entradas_2d.copy()
    for j in range(M):
        lt_j = int(lt_vec[j])
        if lt_j > 0 and lt_j < H:
            lanz_2d[:-lt_j, j] = entradas_2d[lt_j:, j]

    dem_futura_2d = np.vstack([salidas_rm_2d[1:, :], media_rec_vec.reshape(1, -1)])
    doh_2d = np.where(dem_futura_2d > 0, np.round((stk_fin_2d / dem_futura_2d) * 30.0, 0), 0.0)

    return pd.DataFrame({
        'Date': np.repeat(idx_fechas.values, M),
        'rm cod': np.tile(rms, H),
        'rm desc': np.tile([dict_rm_desc.get(r, str(r)) for r in rms], H),
        'LT_Meses': np.tile(lt_vec, H),
        'Salidas_Brutas': salidas_rm_2d.ravel(),
        'Stock_Inicial': stk_ini_2d.ravel(),
        'Recepciones_ERP': rec_erp_rm_2d.ravel(),
        'Stock_Objetivo': stk_obj_2d.ravel(),
        'Entradas_Netas': entradas_2d.ravel(),
        'Lanzamiento_Pedidos': lanz_2d.ravel(),
        'Stock_Final': stk_fin_2d.ravel(),
        'DOH': doh_2d.ravel()
    })


def generar_mrp_global(horiz=None, cob_fg=None, cob_rm=None, metodo_fcst=None, sig=None):
    h = horiz if horiz is not None else int(horizonte)
    c_fg = cob_fg if cob_fg is not None else int(cobertura_fg)
    c_rm = cob_rm if cob_rm is not None else int(cobertura_rm)
    mod = metodo_fcst if metodo_fcst is not None else str(modelo_fcst_sel)
    s_key = sig if sig is not None else str(DATASET_SIGNATURE)
    return _calcular_mrp_global_cached(h, c_fg, c_rm, mod, s_key).copy()


# ==========================================
# FUNCIONES AUXILIARES PARA TABS 9 Y 10 + WATERFALL BRIDGE (ESCALADO POR SHARE DE FILTRO)
# ==========================================
@st.cache_data(show_spinner=False)
def motor_simulador_whatif(df_f, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, horiz, metodo_fcst, s_vol, s_pre, s_cos, sig=None):
    mat = dict_fcst_matrices.get(metodo_fcst, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if mat is None or mat.empty or df_f is None or df_f.empty:
        return pd.DataFrame(), pd.DataFrame()

    vol_global_sku = df.groupby('sku cod')['volume'].sum().to_dict()
    vol_filtro_sku = df_f.groupby('sku cod')['volume'].sum().to_dict()

    skus_filtrados = [str(s).strip() for s in df_f['sku cod'].unique()]
    cols_validas = [s for s in skus_filtrados if s in mat.columns]
    if not cols_validas:
        return pd.DataFrame(), pd.DataFrame()

    vols_sku_global = mat[cols_validas].iloc[:horiz].sum(axis=0)
    l_base, l_wi = [], []
    for sku, vol_g in vols_sku_global.items():
        g_tot = float(vol_global_sku.get(sku, 0.0))
        f_tot = float(vol_filtro_sku.get(sku, 0.0))
        share_sku = (f_tot / g_tot) if g_tot > 0 else 0.0

        vol = float(vol_g) * share_sku
        p, m = dict_p.get(sku, 0.0), dict_m.get(sku, 0.0)
        c_base = p - m
        mon = str(dict_c.get(sku, 'GBP')).strip().upper()
        t_fx = f_eur if mon == 'EUR' else (f_dkk if mon == 'DKK' else (f_pln if mon == 'PLN' else 1.0))
        l_base.append({'Revenue': vol * p * t_fx, 'Margin': vol * m * t_fx})
        l_wi.append({
            'Revenue': vol * (1 + s_vol / 100.0) * p * (1 + s_pre / 100.0) * t_fx,
            'Margin': vol * (1 + s_vol / 100.0) * (p * (1 + s_pre / 100.0) - c_base * (1 + s_cos / 100.0)) * t_fx
        })
    return pd.DataFrame(l_base), pd.DataFrame(l_wi)


@st.cache_data(show_spinner=False)
def motor_kpis_n12m_y_puente(df_f, aj_df, abc_df, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, max_date_global, metodo_fcst, horiz=12, sig=None):
    mat = dict_fcst_matrices.get(metodo_fcst, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if mat is None or mat.empty or df_f is None or df_f.empty:
        return 0.0, 0.0, 0.0, {"rev_a": 0.0, "rev_bc": 0.0, "rev_fva": 0.0, "mar_a": 0.0, "mar_bc": 0.0, "mar_fva": 0.0}

    min_date_12m = max_date_global - pd.DateOffset(months=11)
    vols_l12 = df_f[(df_f['Date'] >= min_date_12m) & (df_f['Date'] <= max_date_global)].groupby('sku cod')['volume'].sum().to_dict()
    mapa_abc = dict(zip(abc_df['sku cod'], abc_df['ABC'])) if (abc_df is not None and not abc_df.empty and 'ABC' in abc_df.columns) else {}

    vol_global_sku = df.groupby('sku cod')['volume'].sum().to_dict()
    vol_filtro_sku = df_f.groupby('sku cod')['volume'].sum().to_dict()

    mapa_aj = {}
    if aj_df is not None and not aj_df.empty:
        aj_clean = aj_df.copy()
        aj_clean['sku cod'] = aj_clean['sku cod'].astype(str).str.strip()
        paises_f = set(df_f['País'].dropna().unique())
        clientes_f = set(df_f['customer cod'].dropna().unique())
        aj_clean = aj_clean[aj_clean['País'].isin(paises_f) & aj_clean['customer cod'].isin(clientes_f)]
        if not aj_clean.empty:
            aj_clean['Date_M'] = pd.to_datetime(aj_clean['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
            mapa_aj = aj_clean.dropna(subset=['Date_M']).groupby(['sku cod', 'Date_M'])['override_value'].sum().to_dict()

    mat_h = mat.iloc[:horiz]
    idx_fut = mat_h.index

    v_total_con, r_total_con, m_total_con = 0.0, 0.0, 0.0
    delta_rev_a, delta_rev_bc, delta_rev_fva = 0.0, 0.0, 0.0
    delta_mar_a, delta_mar_bc, delta_mar_fva = 0.0, 0.0, 0.0

    df_global_grp = df.groupby(['País', 'customer cod', 'sku cod'])['volume'].sum().to_dict()
    df_filtro_grp = df_f.groupby(['País', 'customer cod', 'sku cod'])['volume'].sum().to_dict()
    
    dict_aj = {}
    if aj_df is not None and not aj_df.empty:
        aj_df['Date_M'] = pd.to_datetime(aj_df['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
        for _, r_aj in aj_df.dropna(subset=['Date_M']).iterrows():
            dict_aj[(str(r_aj['País']).strip(), str(r_aj['customer cod']).strip(), str(r_aj['sku cod']).strip(), r_aj['Date_M'])] = float(r_aj['override_value'])

    # Optimizamos agregación del KPI saltando los loops anidados pesados
    for sku in df_f['sku cod'].unique():
        s_clean = str(sku).strip()
        if s_clean not in mat_h.columns:
            continue
            
        vol_l12_sku = float(vols_l12.get(s_clean, 0.0))
        
        g_tot = float(vol_global_sku.get(s_clean, 0.0))
        f_tot = float(vol_filtro_sku.get(s_clean, 0.0))
        share_sku = (f_tot / g_tot) if g_tot > 0 else 0.0
        
        serie_est = mat_h[s_clean].values.astype(float) * share_sku
        serie_con = serie_est.copy()
        
        # Filtrar solo el cruce exacto en la UI para este SKU
        df_cruce_sku = df_f[df_f['sku cod'] == sku].drop_duplicates(subset=['País', 'customer cod'])
        
        for m_i, d_m in enumerate(idx_fut):
            ajuste_acum = 0.0
            hay_ajuste = False
            
            for _, r_cru in df_cruce_sku.iterrows():
                p_c = str(r_cru['País']).strip()
                c_c = str(r_cru['customer cod']).strip()
                
                aj_val = dict_aj.get((p_c, c_c, s_clean, d_m), None)
                if aj_val is not None:
                    hay_ajuste = True
                    ajuste_acum += aj_val
                else:
                    v_tupla = vol_global_tupla_cached.get((p_c, c_c, s_clean), 0.0)
                    share_tupla = v_tupla / max(g_tot, 1e-6)
                    ajuste_acum += (mat_h[s_clean].iloc[m_i] * share_tupla)
            
            if hay_ajuste:
                serie_con[m_i] = ajuste_acum

        vol_est_sku = float(serie_est.sum())
        vol_con_sku = float(serie_con.sum())

        p, mg = dict_p.get(s_clean, 0.0), dict_m.get(s_clean, 0.0)
        mon = str(dict_c.get(s_clean, 'GBP')).strip().upper()
        t_fx = f_eur if mon == 'EUR' else (f_dkk if mon == 'DKK' else (f_pln if mon == 'PLN' else 1.0))

        v_total_con += vol_con_sku
        r_total_con += vol_con_sku * p * t_fx
        m_total_con += vol_con_sku * mg * t_fx

        d_est_vol = vol_est_sku - vol_l12_sku
        d_fva_vol = vol_con_sku - vol_est_sku
        if mapa_abc.get(s_clean, 'B') == 'A':
            delta_rev_a += d_est_vol * p * t_fx
            delta_mar_a += d_est_vol * mg * t_fx
        else:
            delta_rev_bc += d_est_vol * p * t_fx
            delta_mar_bc += d_est_vol * mg * t_fx

        delta_rev_fva += d_fva_vol * p * t_fx
        delta_mar_fva += d_fva_vol * mg * t_fx

    puente_dict = {
        "rev_a": delta_rev_a, "rev_bc": delta_rev_bc, "rev_fva": delta_rev_fva,
        "mar_a": delta_mar_a, "mar_bc": delta_mar_bc, "mar_fva": delta_mar_fva
    }
    return v_total_con, r_total_con, m_total_con, puente_dict


def generar_pdf_executive_sop_deck(
    pais_f, cli_f, sku_f, total_skus, total_clientes,
    fa_val, bias_val, wape_val,
    vol_l12, rev_l12, mar_l12,
    vol_n12, rev_n12, mar_n12,
    vol_bud=None, rev_bud=None, mar_bud=None
):
    if FPDF is None:
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_fill_color(30, 62, 91)
    pdf.rect(0, 0, 210, 32, 'F')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(8)
    pdf.cell(0, 8, txt=_pdf_safe("EXECUTIVE S&OP DECK - MONTHLY CYCLE"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    ahora_str = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M CET")
    pdf.cell(0, 6, txt=_pdf_safe(f"AB Agri Global Supply Chain | Generated: {ahora_str} | Scope: Country={pais_f} | Customer={cli_f} | SKU={sku_f}"), ln=True, align='C')
    pdf.ln(12)

    pdf.set_text_color(30, 62, 91)
    pdf.set_font("Arial", 'B', 13)
    pdf.cell(0, 9, txt=_pdf_safe("1. Consolidated P&L: L12M vs. Annual Budget vs. N12M Consensus (GBP)"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, txt=_pdf_safe(f"   - Active Portfolio Scope: {total_skus} SKUs (FG) | {total_clientes} Active Customers | Model: {modelo_fcst_sel}"), ln=True)

    v_b = vol_bud if vol_bud is not None else vol_l12 * 1.05
    r_b = rev_bud if rev_bud is not None else rev_l12 * 1.05
    m_b = mar_bud if mar_bud is not None else mar_l12 * 1.05

    gap_vol_b = vol_n12 - v_b
    gap_rev_b = rev_n12 - r_b
    gap_mar_b = mar_n12 - m_b

    pdf.ln(2)
    pdf.set_fill_color(224, 230, 237)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(46, 8, _pdf_safe("S&OP Metric"), 1, 0, 'L', True)
    pdf.cell(36, 8, _pdf_safe("Last 12M (Hist)"), 1, 0, 'R', True)
    pdf.cell(36, 8, _pdf_safe("Annual Budget"), 1, 0, 'R', True)
    pdf.cell(36, 8, _pdf_safe("Next 12M (Plan)"), 1, 0, 'R', True)
    pdf.cell(36, 8, _pdf_safe("Gap vs Budget"), 1, 1, 'R', True)

    pdf.set_font("Arial", '', 9)
    pdf.cell(46, 8, _pdf_safe("Total Volume (Kg)"), 1, 0, 'L')
    pdf.cell(36, 8, _pdf_safe(f"{vol_l12:,.0f} Kg"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"{v_b:,.0f} Kg"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"{vol_n12:,.0f} Kg"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"{gap_vol_b:+,.0f} Kg"), 1, 1, 'R')

    pdf.cell(46, 8, _pdf_safe("Consolidated Revenue"), 1, 0, 'L')
    pdf.cell(36, 8, _pdf_safe(f"GBP {rev_l12:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {r_b:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {rev_n12:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {gap_rev_b:+,.0f}"), 1, 1, 'R')

    pdf.cell(46, 8, _pdf_safe("Gross Margin (GBP)"), 1, 0, 'L')
    pdf.cell(36, 8, _pdf_safe(f"GBP {mar_l12:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {m_b:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {mar_n12:,.0f}"), 1, 0, 'R')
    pdf.cell(36, 8, _pdf_safe(f"GBP {gap_mar_b:+,.0f}"), 1, 1, 'R')
    pdf.ln(5)

    pdf.set_text_color(30, 62, 91)
    pdf.set_font("Arial", 'B', 13)
    pdf.cell(0, 9, txt=_pdf_safe("2. Demand Model Statistical Reliability (L12M)"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, txt=_pdf_safe(f"   - Forecast Accuracy (FA): {fa_val:.1f}%  |  WAPE: {wape_val:.1f}%  |  Global Bias: {bias_val:+.1f}%"), ln=True)

    df_fva_hist = github_leer_csv(FVA_LOG_FILE, COLS_FVA_LOG)
    if not df_fva_hist.empty and 'Delta_Kg' in df_fva_hist.columns:
        tot_cambios = len(df_fva_hist)
        delta_neto_fva = pd.to_numeric(df_fva_hist['Delta_Kg'], errors='coerce').fillna(0).sum()
        pdf.cell(0, 6, txt=_pdf_safe(f"   - Consensus Governance (FVA Cloud): {tot_cambios} logged entries | Net Impact: {delta_neto_fva:+,.0f} Kg"), ln=True)
    pdf.ln(4)

    pdf.set_text_color(30, 62, 91)
    pdf.set_font("Arial", 'B', 13)
    pdf.cell(0, 9, txt=_pdf_safe("3. Month 1 Operational Exception Radar & RCCP Line Saturation"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)

    df_mps_d = generar_mps_df_2d()
    if not df_mps_d.empty:
        df_mps_d['Date'] = pd.to_datetime(df_mps_d['Date'])
        m1_dt = sorted(df_mps_d['Date'].unique())[0]
        df_alert_pt = df_mps_d[(df_mps_d['Date'] == m1_dt) & ((df_mps_d['DOH'] < 15) | (df_mps_d['DOH'] > 60))].sort_values('DOH').head(5)
        for _, r_pt in df_alert_pt.iterrows():
            est_al = "STOCKOUT (<15d)" if r_pt['DOH'] < 15 else "EXCESS (>60d)"
            pdf.cell(0, 5, txt=_pdf_safe(f"   * FG [{r_pt['sku cod']}] {str(r_pt['sku desc'])[:28]} -> {est_al} | DOH: {r_pt['DOH']:.0f}d | End Stock: {r_pt['Stock_Final']:,.0f} Kg"), ln=True)

    df_act_pdf = github_leer_csv(ACTION_LOG_FILE, COLS_ACTION_LOG)
    if not df_act_pdf.empty:
        pdf.ln(4)
        pdf.set_text_color(30, 62, 91)
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 9, txt=_pdf_safe("4. Executive S&OP Committee Action Log & Decisions"), ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", '', 9)
        for _, r_a in df_act_pdf.head(6).iterrows():
            pdf.cell(0, 5, txt=_pdf_safe(f"   - [{r_a.get('Estado', '')}] {r_a.get('Area_S&OP', '')}: {str(r_a.get('Accion_Acordada', ''))[:55]} (Owner: {r_a.get('Responsable', '')} | GBP {pd.to_numeric(r_a.get('Impacto_GBP', 0), errors='coerce'):,.0f})"), ln=True)

    return bytes(pdf.output())


## ==========================================
# PREPARACIÓN DATOS BASE (SERIE VISUALIZADA EN PESTAÑA 1 Y 2) - VECTORIZADO Y CACHEADO
# ==========================================
@st.cache_data(show_spinner=False)
def obtener_curvas_demanda_vectorizadas(df_f, aj_df, metodo_fcst, horiz, sig):
    df_g = df_f.groupby('Date')['volume'].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)
    s_real = df_g['volume'] if not df_g.empty else pd.Series(dtype=float)
    
    mat = dict_fcst_matrices.get(metodo_fcst, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if mat is None or mat.empty or df_f.empty:
        idx_f = pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=int(horiz), freq="MS")
        return s_real, pd.DataFrame({"Estadistico": np.zeros(int(horiz)), "Consenso": np.zeros(int(horiz))}, index=idx_f)
        
    skus_validos = [str(s).strip() for s in df_f['sku cod'].unique() if str(s).strip() in mat.columns]
    idx_f = mat.index[:int(horiz)]
    
    if not skus_validos:
        return s_real, pd.DataFrame({"Estadistico": np.zeros(int(horiz)), "Consenso": np.zeros(int(horiz))}, index=idx_f)
        
    mat_h = mat.iloc[:int(horiz)]
    
    vol_global_sku = vol_global_sku_cached
    vol_filtro_sku = df_f.groupby('sku cod')['volume'].sum().to_dict()
    
    fcst_base_arr = np.zeros(int(horiz))
    fcst_con_arr = np.zeros(int(horiz))
    
    for s_clean in skus_validos:
        g_tot = float(vol_global_sku.get(s_clean, 0.0))
        f_tot = float(vol_filtro_sku.get(s_clean, 0.0))
        share_sku = (f_tot / g_tot) if g_tot > 0 else 0.0
        
        arr_base = mat_h[s_clean].values.astype(float) * share_sku
        fcst_base_arr += arr_base
        fcst_con_arr += arr_base
        
    if aj_df is not None and not aj_df.empty:
        aj_tmp = aj_df.copy()
        aj_tmp['Date_M'] = pd.to_datetime(aj_tmp['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
        aj_tmp['País_s'] = aj_tmp['País'].astype(str).str.strip()
        aj_tmp['cli_s'] = aj_tmp['customer cod'].astype(str).str.strip()
        aj_tmp['sku_s'] = aj_tmp['sku cod'].astype(str).str.strip()
        aj_tmp = aj_tmp.dropna(subset=['Date_M'])
        
        pares_filt = df_f[['País', 'customer cod', 'sku cod']].drop_duplicates().copy()
        pares_filt['País_s'] = pares_filt['País'].astype(str).str.strip()
        pares_filt['cli_s'] = pares_filt['customer cod'].astype(str).str.strip()
        pares_filt['sku_s'] = pares_filt['sku cod'].astype(str).str.strip()
        
        aj_match = pd.merge(
            aj_tmp[['País_s', 'cli_s', 'sku_s', 'Date_M', 'override_value']],
            pares_filt[['País_s', 'cli_s', 'sku_s']],
            on=['País_s', 'cli_s', 'sku_s'],
            how='inner'
        )
        
        if not aj_match.empty:
            fecha_to_idx = {d: i for i, d in enumerate(idx_f)}
            for _, r_aj in aj_match.iterrows():
                s_str = r_aj['sku_s']
                d_m = r_aj['Date_M']
                
                if s_str in skus_validos and d_m in fecha_to_idx:
                    idx_t = fecha_to_idx[d_m]
                    ovr_val = float(r_aj['override_value'])
                    
                    v_glob_sku = max(vol_global_sku.get(s_str, 1e-6), 1e-6)
                    v_tupla = vol_global_tupla_cached.get((r_aj['País_s'], r_aj['cli_s'], s_str), 0.0)
                    share_tupla = v_tupla / v_glob_sku if v_glob_sku > 0 else 0.0
                    
                    stat_val = float(mat_h.at[d_m, s_str]) * share_tupla
                    
                    delta = ovr_val - stat_val
                    fcst_con_arr[idx_t] += delta
                    
    df_comp = pd.DataFrame({"Estadistico": fcst_base_arr, "Consenso": fcst_con_arr}, index=idx_f)
    df_comp.index.name = 'Date'
    return s_real, df_comp

serie_real, df_comparativo = obtener_curvas_demanda_vectorizadas(
    df_final, 
    st.session_state.get('df_ajustes', pd.DataFrame()), 
    modelo_fcst_sel, 
    horizonte, 
    DATASET_SIGNATURE
)

LAYOUT_STYLE = dict(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Arial, sans-serif"),
    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e6ed')
)

# ==========================================
# PESTAÑAS (TABS) DEFINIDAS UNA SOLA VEZ
# ==========================================
opciones_tabs = [
    t["tab0"], t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"], 
    t["tab6"], t["tab7"], t["tab8"], t["tab9"], t["tab10"]
]
st.markdown("<br>", unsafe_allow_html=True)
modulo_activo = st.radio("Módulos S&OP", opciones_tabs, horizontal=True, label_visibility="collapsed")
st.markdown("---")
# >>> FIN DE LA PARTE 1 DE 2 (PEGA JUSTO DEBAJO LA PARTE 2) <<<

# ==============================================================================
# S&OP / IBP CORPORATE PLATFORM - PARTE 2 DE 2 (MÓDULOS 0 AL 10 + NPI + TURNOS + MTO/MTS FIX)
# ==============================================================================

# ==========================================
# MODULO 0: GUÍA DE USO + CALENDARIO S&OP + ACTION LOG DEL COMITÉ
# ==========================================
if modulo_activo == t["tab0"]:
    st.header(tr(
        "📖 Manual Corporativo y Arquitectura de la Plataforma S&OP / IBP",
        "📖 Corporate S&OP / IBP Platform Manual & Architecture",
        "📖 Podręcznik Korporacyjny i Architektura Platformy S&OP / IBP",
        "📖 Koncernmanual og S&OP / IBP-platformarkitektur"
    ))
    st.markdown(tr(
        "Esta plataforma integra de extremo a extremo el ciclo mensual de **Integrated Business Planning (IBP)**, **Sales & Operations Planning (S&OP)** y **Sales & Operations Execution (S&OE)** con cálculo matricial 2D vectorizado para soportar cientos de miles de registros sin bloqueos.",
        "This platform provides end-to-end integration of the monthly **Integrated Business Planning (IBP)**, **S&OP**, and **S&OE** cycle powered by vectorized 2D matrix algebra for large enterprise datasets."
    ))

    st.divider()
    st.subheader(tr(
        "🧭 Guía Detallada de los 10 Módulos Operativos y Ejecutivos",
        "🧭 Detailed Guide to the 10 Operational & Executive Modules"
    ))

    st.markdown(tr(
        """
1. **📊 1. Demanda (Torneo Auto-ML Best-Fit, Gestor NPI / New Business, Consenso Cloud y Post-Mortem FVA):** Compite automáticamente entre **3 algoritmos** (*Holt-Winters Estacional*, *Media Móvil Ponderada Amortiguada WMA* y *Croston TSB Intermitente*) seleccionando el de menor WAPE por SKU. Incluye alta de **Nuevos Lanzamientos / Licitaciones (NPI)** con SKU espejo, guardado en GitHub Cloud, Snapshots mensuales y evaluación Post-Mortem contra ventas reales.
2. **🏭 2. Producción (Plan Maestro de Producción - MPS 2D):** Calcula las necesidades netas de fabricación (`Demanda + Stock Obj - Stock Inicial - ERP Firme`) con semáforo de cobertura **DOH**.
3. **🧩 3. Compras (MRP, Pegging, Red Sankey E2E y Simulador de Reformulación BOM):** Explosión de materiales con *Lead Time*, trazabilidad inversa de margen en riesgo (**Pegging**), diagrama de flujo **Sankey E2E** y **Simulador de Cambio de Fórmula (Phase-in / Sustitución de MP)**.
4. **⚙️ 4. Capacidad (RCCP por Planta/País, Simulador de Turnos Extra y Nivelación Finita / Pre-Build):** Filtra automáticamente las líneas de la planta seleccionada, simula la apertura de **turnos adicionales / horas extra** y permite **auto-nivelar la capacidad adelantando producción (*Pre-Build*)** hacia meses previos con holgura.
5. **💷 5. Finanzas (P&L Consolidado y Working Capital en GBP):** Valoración multimoneda (`EUR`, `DKK`, `PLN` $\\rightarrow$ `GBP`) de ingresos, márgenes y capital circulante (PT + MP).
6. **🚀 6. Ejecución ERP & S&OE (Restricciones Logísticas MOQ / Lotes Múltiplos y Master Pack):** Redondea las órdenes del Mes 1 a lotes reales de mezcladora y camión completo, exportando el **Master Pack S&OP (.xlsx)**.
7. **🔠 7. ABC/XYZ (Segmentación, Racionalización MTO/MTS y Stock de Seguridad Científico):** Matriz de burbujas Riesgo vs. Rentabilidad, auditoría `MTS` $\\rightarrow$ `MTO`, detección de exceso sobre **Stock de Seguridad Científico ($Z \\cdot \\sigma \\cdot \\sqrt{LT}$)** y filtrado estricto de alertas.
8. **🚨 8. Excepciones (Radar Management by Exception):** Vigilancia dual en Mes 1 (`DOH < 15d` y `DOH > 60d`) para PT y MP.
9. **🔀 9. What-If (Simulador de Escenarios Financieros):** Sensibilidad a shocks de Volumen, Precio y Coste MP con informe PDF.
10. **📊 10. Dashboard (Triple Comparativa Budget, Puente Waterfall, Radar Churn y PDF Deck):** Control contra Presupuesto Anual, gráfico **Waterfall Bridge**, **Radar de Riesgo de Fuga de Clientes (Churn)** y exportación del **Executive S&OP Deck (.pdf)**.
        """,
        """
1. **📊 1. Demand (Auto-ML Best-Fit Tournament, NPI / New Business Manager, Cloud Consensus & Post-Mortem FVA):** Automatically competes across **3 algorithms**, includes **New Product Introduction (NPI) & New Business** injection with mirror SKU seasonality, GitHub Cloud sync, monthly Snapshots, and Post-Mortem FVA evaluation.
2. **🏭 2. Production (Master Production Schedule - 2D MPS):** Computes net FG production requirements with **DOH** traffic-light alerts.
3. **🧩 3. Purchasing (MRP, Pegging, E2E Sankey Network & BOM Reformulation Simulator):** Multi-level BOM explosion, interactive **Pegging**, **E2E Sankey flow**, and **BOM Formulation Change Simulator**.
4. **⚙️ 4. Capacity (Plant/Country RCCP, Extra Shifts Simulator & Automated Finite Leveling / Pre-Build):** Dynamically filters plant lines, simulates **extra shifts / overtime**, and runs **automated Pre-Build leveling**.
5. **💷 5. Finance (Consolidated P&L & Working Capital in GBP):** Multi-currency valuation (`EUR`, `DKK`, `PLN` $\\rightarrow$ `GBP`).
6. **🚀 6. ERP Execution & S&OE (MOQ / Lot Multiples & Master Pack Export):** Rounds Month 1 orders to mixer batch and truckload multiples, exporting the 5-tab **S&OP Master Pack (.xlsx)**.
7. **🔠 7. ABC/XYZ (Segmentation, MTO/MTS Optimizer & Scientific Safety Stock):** Bubble matrix, `MTS` $\\rightarrow$ `MTO` cash release, **Cycle Service Level Safety Stock ($Z \\cdot \\sigma \\cdot \\sqrt{LT}$)**, and strict exception filtering.
8. **🚨 8. Exceptions:** Dual Month 1 radar (`DOH < 15d` and `DOH > 60d`).
9. **🔀 9. What-If:** Volume, Price, and COGS stress-testing with PDF report.
10. **📊 10. Dashboard (Triple Budget Control, Waterfall Bridge, Customer Churn Radar & PDF Deck):** Tracks Budget Gap, **GBP Waterfall Bridge**, **Customer Churn & Concentration Risk**, and exports the **Executive S&OP Deck (.pdf)**.
        """
    ))

    # --- CALENDARIO INTERACTIVO DE GOBERNANZA DEL CICLO S&OP ---
    st.divider()
    st.subheader(tr(
        "🗓️ Calendario de Gobernanza del Ciclo Mensual S&OP (Workflow & Sign-Off)",
        "🗓️ Monthly S&OP Cycle Governance Calendar (Workflow & Sign-Off)"
    ))

    mes_actual_base = pd.Timestamp.today().replace(day=1)
    fases_defecto = [
        {
            "Fase": "01. Data & Portfolio",
            "Etapa S&OP": tr("1. Limpieza de Datos y Revisión de Cartera", "1. Data Gathering & Portfolio Review"),
            "Dias_Mes": "Días 1 - 5", "Dia_Inicio": 1, "Dia_Fin": 5,
            "Owner": "S&OP Manager / IT",
            "Entregable_Clave": tr("Carga de 8 Tablas ERP, NPI y Torneo Auto-ML", "8 ERP Tables Upload, NPI & Auto-ML Tournament"),
            "Estado": "✅ Completado", "Notas_Comite": "Datos validados sin errores de esquema."
        },
        {
            "Fase": "02. Demand Review",
            "Etapa S&OP": tr("2. Revisión de Demanda y Consenso Comercial", "2. Demand Review & Commercial Consensus"),
            "Dias_Mes": "Días 6 - 10", "Dia_Inicio": 6, "Dia_Fin": 10,
            "Owner": "Commercial Manager",
            "Entregable_Clave": tr("Overrides en Pestaña 1 y Snapshot FVA congelado", "Tab 1 Overrides & Frozen FVA Snapshot"),
            "Estado": "🔄 En Curso", "Notas_Comite": "Revisión de cuentas clave y licitaciones NPI."
        },
        {
            "Fase": "03. Supply & RCCP",
            "Etapa S&OP": tr("3. Revisión de Suministro, MRP y Capacidad Planta", "3. Supply, MRP & Plant Capacity Review (RCCP)"),
            "Dias_Mes": "Días 11 - 16", "Dia_Inicio": 11, "Dia_Fin": 16,
            "Owner": "Operations & Procurement",
            "Entregable_Clave": tr("Nivelación Pre-Build RCCP, Turnos (Pestaña 4) y Pegging MP", "Pre-Build RCCP Leveling, Shifts (Tab 4) & RM Pegging"),
            "Estado": "⏳ Pendiente", "Notas_Comite": "Validar turnos por planta y POs críticas."
        },
        {
            "Fase": "04. Pre-S&OP Finance",
            "Etapa S&OP": tr("4. Pre-S&OP: Reconciliación Financiera y Escenarios", "4. Pre-S&OP: Financial Reconciliation & What-If"),
            "Dias_Mes": "Días 17 - 21", "Dia_Inicio": 17, "Dia_Fin": 21,
            "Owner": "Finance & S&OP Manager",
            "Entregable_Clave": tr("Puente Waterfall GBP, Budget Gap y Working Capital", "GBP Waterfall Bridge, Budget Gap & Working Capital"),
            "Estado": "⏳ Pendiente", "Notas_Comite": "Evaluar liberación de caja MTS -> MTO."
        },
        {
            "Fase": "05. Executive S&OP",
            "Etapa S&OP": tr("5. Reunión Ejecutiva S&OP y Aprobación Plan Único", "5. Executive S&OP Meeting & Single Plan Sign-Off"),
            "Dias_Mes": "Días 22 - 25", "Dia_Inicio": 22, "Dia_Fin": 25,
            "Owner": "SLT / General Management",
            "Entregable_Clave": tr("Firma del Executive S&OP Deck PDF y Master Pack ERP", "Executive S&OP Deck PDF Sign-Off & ERP Master Pack"),
            "Estado": "⏳ Pendiente", "Notas_Comite": "Aprobación final y lanzamiento de órdenes M1."
        }
    ]

    df_cal_sop = github_leer_csv(SOP_CAL_FILE, COLS_SOP_CAL)
    if df_cal_sop.empty or len(df_cal_sop) != 5 or not set(["Dia_Inicio", "Dia_Fin"]).issubset(df_cal_sop.columns):
        df_cal_sop = pd.DataFrame(fases_defecto)

    df_gantt = df_cal_sop.copy()
    df_gantt["Inicio_Fecha"] = [mes_actual_base + pd.Timedelta(days=int(d) - 1) for d in pd.to_numeric(df_gantt["Dia_Inicio"], errors="coerce").fillna(1)]
    df_gantt["Fin_Fecha"] = [mes_actual_base + pd.Timedelta(days=int(d)) for d in pd.to_numeric(df_gantt["Dia_Fin"], errors="coerce").fillna(5)]

    mapa_colores_estado = {
        "✅ Completado": "#2E8B57",
        "🔄 En Curso": "#1E3E5B",
        "⏳ Pendiente": "#A0B2C6",
        "🚨 Bloqueado": "#D9534F"
    }

    fig_gantt = px.timeline(
        df_gantt,
        x_start="Inicio_Fecha",
        x_end="Fin_Fecha",
        y="Fase",
        color="Estado",
        text="Owner",
        hover_name="Etapa S&OP",
        hover_data={"Entregable_Clave": True, "Dias_Mes": True, "Notas_Comite": True, "Inicio_Fecha": False, "Fin_Fecha": False},
        color_discrete_map=mapa_colores_estado,
        title=tr(f"Cronograma Oficial del Ciclo S&OP — {mes_actual_base.strftime('%Y-%m')}", f"Official S&OP Cycle Timeline — {mes_actual_base.strftime('%Y-%m')}")
    )
    hoy_ms = pd.Timestamp.today().timestamp() * 1000
    fig_gantt.add_vline(x=hoy_ms, line_width=2, line_dash="dash", line_color="#D9534F", annotation_text=tr("Hoy", "Today"))
    fig_gantt.update_yaxes(autorange="reversed", title="")
    fig_gantt.update_xaxes(title=tr("Calendario del Mes en Curso", "Current Month Timeline"))
    fig_gantt.update_layout(**LAYOUT_STYLE, height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gantt, use_container_width=True)

    df_cal_edit = st.data_editor(
        df_cal_sop[["Fase", "Etapa S&OP", "Dias_Mes", "Owner", "Entregable_Clave", "Estado", "Notas_Comite"]],
        column_config={
            "Fase": st.column_config.TextColumn(disabled=True),
            "Etapa S&OP": st.column_config.TextColumn(disabled=True),
            "Dias_Mes": st.column_config.TextColumn(label=tr("Ventana", "Window"), disabled=True),
            "Owner": st.column_config.TextColumn(label="Owner"),
            "Entregable_Clave": st.column_config.TextColumn(label=tr("Entregable Clave", "Key Deliverable"), disabled=True),
            "Estado": st.column_config.SelectboxColumn(
                label=tr("Estado", "Status"),
                options=["⏳ Pendiente", "🔄 En Curso", "✅ Completado", "🚨 Bloqueado"],
                required=True
            ),
            "Notas_Comite": st.column_config.TextColumn(label=tr("Acuerdos / Notas del Ciclo", "Cycle Decisions / Notes"))
        },
        use_container_width=True,
        hide_index=True
    )

    if st.button(tr("💾 Guardar Estado del Ciclo S&OP (GitHub Cloud)", "💾 Save S&OP Cycle Status (GitHub Cloud)"), type="primary"):
        df_cal_sop[["Owner", "Estado", "Notas_Comite"]] = df_cal_edit[["Owner", "Estado", "Notas_Comite"]]
        github_guardar_csv(df_cal_sop, SOP_CAL_FILE, f"S&OP Calendar status updated by {usuario_actual}")
        st.success(tr("✅ Estado del calendario S&OP actualizado y guardado en GitHub.", "✅ S&OP Calendar status updated and saved to GitHub."))
        st.rerun()

    # ==========================================
    # TRACKER DE DECISIONES Y ACCIONES DEL COMITÉ S&OP (ACTION LOG)
    # ==========================================
    st.divider()
    st.subheader(tr(
        "📋 Registro Ejecutivo de Decisiones y Acciones del Comité S&OP (Action Log & Risk Register)",
        "📋 Executive S&OP Committee Action Log & Risk Register"
    ))
    st.caption(tr(
        "Registra los acuerdos tácticos y estratégicos de cada reunión S&OP con responsable, fecha límite e impacto estimado en GBP (£). Se sincroniza en GitHub y se incluye automáticamente en el Executive S&OP Deck PDF.",
        "Log tactical and strategic decisions from each S&OP meeting with owner, due date, and estimated GBP (£) impact. Syncs to GitHub and prints automatically in the Executive S&OP Deck PDF."
    ))

    acciones_defecto = [
        {
            "ID": "ACT-01", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"),
            "Area_S&OP": "03. Supply & RCCP",
            "Accion_Acordada": "Adelantar 12.000 Kg de ADICARE EVOLUTION H (Pre-Build) en Línea 3 Pellet para evitar cuello de botella.",
            "Responsable": "Borja Del Rio", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=15)).strftime("%Y-%m-%d"),
            "Impacto_GBP": 18500, "Estado": "🔄 En Curso"
        },
        {
            "ID": "ACT-02", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"),
            "Area_S&OP": "04. Working Capital",
            "Accion_Acordada": "Pasar referencias erráticas Clase CZ/BZ de política MTS a MTO según auditoría de Pestaña 7.",
            "Responsable": "Ángel Mancebo", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=22)).strftime("%Y-%m-%d"),
            "Impacto_GBP": 34200, "Estado": "⏳ Pendiente"
        },
        {
            "ID": "ACT-03", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"),
            "Area_S&OP": "02. Demand & Margin",
            "Accion_Acordada": "Validar sustitución parcial del 10% en FORMIATO DE CALCIO por alternativa homologada en BOM.",
            "Responsable": "Technical & Procurement", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=25)).strftime("%Y-%m-%d"),
            "Impacto_GBP": 14800, "Estado": "✅ Completado"
        }
    ]

    df_act_log = github_leer_csv(ACTION_LOG_FILE, COLS_ACTION_LOG)
    if df_act_log.empty or not set(COLS_ACTION_LOG).issubset(df_act_log.columns):
        df_act_log = pd.DataFrame(acciones_defecto)

    df_act_edit = st.data_editor(
        df_act_log[COLS_ACTION_LOG],
        num_rows="dynamic",
        column_config={
            "ID": st.column_config.TextColumn(label="ID", width="small"),
            "Fecha_Alta": st.column_config.TextColumn(label=tr("Alta", "Created"), width="small"),
            "Area_S&OP": st.column_config.SelectboxColumn(
                label=tr("Área S&OP", "S&OP Area"),
                options=["01. Data & Portfolio", "02. Demand & Margin", "03. Supply & RCCP", "04. Working Capital", "05. Executive Sign-Off"],
                required=True
            ),
            "Accion_Acordada": st.column_config.TextColumn(label=tr("Decisión / Acción Acordada", "Agreed Action / Decision"), width="large"),
            "Responsable": st.column_config.TextColumn(label="Owner"),
            "Fecha_Limite": st.column_config.TextColumn(label=tr("Fecha Límite", "Due Date")),
            "Impacto_GBP": st.column_config.NumberColumn(label=tr("Impacto (£)", "Impact (£)"), format="£ %d"),
            "Estado": st.column_config.SelectboxColumn(
                label=tr("Estado", "Status"),
                options=["⏳ Pendiente", "🔄 En Curso", "✅ Completado", "🚨 Bloqueado"],
                required=True
            )
        },
        use_container_width=True,
        hide_index=True
    )

    ac_k1, ac_k2, ac_k3 = st.columns([1, 1, 2])
    ac_k1.metric(tr("Acciones Activas", "Active Actions"), f"{len(df_act_edit)}")
    impacto_tot_act = pd.to_numeric(df_act_edit["Impacto_GBP"], errors="coerce").fillna(0).sum()
    ac_k2.metric(tr("Valor en Juego en Comité (£)", "Total Value at Stake (£)"), f"£ {impacto_tot_act:,.0f}")
    with ac_k3:
        if st.button(tr("💾 Guardar Action Log del Comité en GitHub", "💾 Save Committee Action Log to GitHub"), use_container_width=True):
            github_guardar_csv(df_act_edit, ACTION_LOG_FILE, f"Action Log updated by {usuario_actual}")
            st.success(tr("✅ Action Log guardado en GitHub e incluido en el PDF Ejecutivo.", "✅ Action Log saved to GitHub and included in the Executive PDF."))
            st.rerun()

# ==========================================
# MODULO 1: DEMANDA + GESTOR NPI (NEW BUSINESS) + TORNEO AUTO-ML + POST-MORTEM FVA
# ==========================================
if modulo_activo == t["tab1"]:
    if "tab1" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Demanda.", "🔒 You do not have permission to access the Demand module."))
    else:
        st.subheader(f"{tr('Pronóstico de Demanda', 'Demand Forecast')}: {sku_sel}  |  🤖 {modelo_fcst_sel}")
        if sku_sel != "TODOS" and sku_sel in dict_meta_torneo:
            info_m = dict_meta_torneo[sku_sel]
            st.caption(
                f"🏆 **Auto-ML Winner [{sku_sel}]:** `{info_m['Ganador']}` "
                f"(WAPE Backtest: Holt-Winters `{info_m['WAPE_HW']}%` | Damped WMA `{info_m['WAPE_WMA']}%` | Croston TSB `{info_m['WAPE_Croston']}%`)"
            )

        df_chart = pd.DataFrame({
            tr('Histórico Real', 'Actual History'): serie_real,
            f"{tr('Estadístico', 'Statistical')} ({modelo_fcst_sel})": df_comparativo['Estadistico'],
            tr('Forecast Consenso', 'Consensus Forecast'): df_comparativo['Consenso']
        })
        st.line_chart(df_chart, color=["#A0B2C6", "#888888", "#1E3E5B"], height=350, use_container_width=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"#### {tr('Tabla Editable / Editar Consenso', 'Editable Table / Edit Consensus')}")
            df_display = df_comparativo.copy()
            df_display.index = df_display.index.strftime('%Y-%m')
            
            if pais_sel != "TODOS" and cliente_sel != "TODOS" and sku_sel != "TODOS":
                df_editado = st.data_editor(
                    df_display,
                    column_config={
                        "Estadistico": st.column_config.NumberColumn(label=tr("Estadístico", "Statistical"), disabled=True, format="%.2f"),
                        "Consenso": st.column_config.NumberColumn(label=tr("Consenso", "Consensus"), step=1, format="%.2f")
                    },
                    use_container_width=True
                )
            else:
                st.dataframe(df_display.style.format("{:,.2f}"), use_container_width=True)
                
            st.markdown("---")
            
            btn_c1, btn_c2, btn_c3 = st.columns(3)
            with btn_c1:
                if pais_sel != "TODOS" and cliente_sel != "TODOS" and sku_sel != "TODOS":
                    if st.button(tr("💾 Guardar Consenso (RAM + GitHub)", "💾 Save Consensus (RAM + GitHub)"), use_container_width=True, type="primary"):
                        if st.session_state['df_ajustes'] is not None:
                            df_aj = st.session_state['df_ajustes'].copy()
                            df_prev_sku = df_aj[(df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel)].copy()
                            mapa_prev = {}
                            if not df_prev_sku.empty:
                                df_prev_sku['Date_Str'] = pd.to_datetime(df_prev_sku['Date'], errors='coerce').dt.strftime('%Y-%m')
                                mapa_prev = dict(zip(df_prev_sku['Date_Str'], pd.to_numeric(df_prev_sku['override_value'], errors='coerce').fillna(0)))

                            df_aj = df_aj[~((df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel))]
                            df_mod = df_editado[np.abs(df_editado['Consenso'] - df_editado['Estadistico']) > 0.01].copy()
                            ahora_cet = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")
                            nuevas_filas = []
                            eventos_fva = []
                            for f, r in df_mod.iterrows():
                                est_v = round(float(r['Estadistico']), 2)
                                ovr_v = round(float(r['Consenso']), 2)
                                delta_kg = round(ovr_v - est_v, 2)
                                delta_pct = round((delta_kg / est_v * 100), 1) if est_v > 0 else 0.0
                                nuevas_filas.append({
                                    'Date': pd.to_datetime(f),
                                    'País': pais_sel,
                                    'customer cod': cliente_sel,
                                    'sku cod': sku_sel,
                                    'override_value': ovr_v
                                })
                                val_anterior = mapa_prev.get(str(f), est_v)
                                if abs(ovr_v - float(val_anterior)) > 0.01:
                                    eventos_fva.append({
                                        "Fecha_Cambio (CET)": ahora_cet,
                                        "Usuario": usuario_actual,
                                        "Tipo_Ajuste": "Override Manual",
                                        "Date": pd.to_datetime(f).strftime("%Y-%m-%d"),
                                        "País": pais_sel,
                                        "customer cod": cliente_sel,
                                        "sku cod": sku_sel,
                                        "Forecast_Estadistico": est_v,
                                        "Consenso_Override": ovr_v,
                                        "Delta_Kg": delta_kg,
                                        "Delta_Pct_FVA": delta_pct
                                    })
                            if nuevas_filas:
                                df_aj = pd.concat([df_aj, pd.DataFrame(nuevas_filas)], ignore_index=True)
                            st.session_state['df_ajustes'] = df_aj
                            ok_cloud = github_guardar_csv(df_aj, CLOUD_AJUSTES_FILE, f"Consensus override by {usuario_actual} on {sku_sel}")
                            registrar_evento_fva_consenso(eventos_fva)
                            if ok_cloud:
                                st.success(tr("✅ Guardado en RAM y sincronizado en GitHub Cloud", "✅ Saved in RAM and synced to GitHub Cloud"))
                            else:
                                st.success(tr("✅ Guardado en RAM y almacenamiento local", "✅ Saved in RAM and local storage"))
                            st.rerun()
                else:
                    st.info(tr("⚠️ Selecciona País, Cliente y SKU para editar celdas.", "⚠️ Select Country, Customer, and SKU to edit cells."))
                    
            with btn_c2:
                if st.button(tr("📸 Congelar Snapshot Ciclo S&OP", "📸 Freeze S&OP Cycle Snapshot"), use_container_width=True):
                    with st.spinner(tr("Congelando foto fija del ciclo S&OP en GitHub...", "Freezing S&OP cycle snapshot in GitHub...")):
                        n_reg = congelar_snapshot_ciclo_sop(df_final)
                        st.success(f"📸 Snapshot OK ({n_reg} rows).")
                        st.rerun()

            with btn_c3:
                if not st.session_state['df_ajustes'].empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        st.session_state['df_ajustes'].to_excel(writer, index=False, sheet_name='Sheet1')
                    st.download_button(
                        label=tr("📥 Descargar Ajustes (.xlsx)", "📥 Download Overrides (.xlsx)"),
                        data=output.getvalue(),
                        file_name="2_Ajustes_Consenso.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
        with col2:
            st.markdown(f"#### {tr('Pronóstico Top-Down (Cat + Cliente)', 'Top-Down Forecast (Cat + Customer)')}")
            cat_macro = st.selectbox(tr("Categoría de Producto:", "Product Category:"), sorted(df['Categoria_Producto'].dropna().unique()) if 'Categoria_Producto' in df.columns else [], key="macro_cat")
            cli_macro = st.selectbox(
                tr("Cliente:", "Customer:"), 
                sorted(df[df['Categoria_Producto'] == cat_macro]['customer cod'].dropna().unique()) if cat_macro else [], 
                format_func=lambda x: dict_cli_desc.get(x, x), 
                key="macro_cli"
            )
            pct_macro = st.number_input(tr("Variación % (ej. 15, -20):", "Variation % (e.g. 15, -20):"), value=15.0, step=5.0, format="%.1f")
            
            if st.button(tr("🚀 Aplicar Consenso a la Categoría", "🚀 Apply Consensus to Category"), use_container_width=True):
                if cat_macro and cli_macro:
                    with st.spinner(tr("Desagregando variaciones a nivel SKU...", "Disaggregating variations to SKU level...")):
                        exito, msg = aplicar_variacion_categoria_cliente(cat_macro, cli_macro, pct_macro)
                        if exito:
                            st.success(tr("¡Sincronizado en la nube!", "Synced to cloud!"))
                            st.rerun()
                        else:
                            st.error(msg)

            st.markdown("---")
            if st.button(tr("🧹 Limpiar Overrides Activos (Cloud)", "🧹 Clear Active Overrides (Cloud)"), use_container_width=True):
                df_vacio_aj = pd.DataFrame(columns=COLS_AJUSTES)
                st.session_state['df_ajustes'] = df_vacio_aj
                github_guardar_csv(df_vacio_aj, CLOUD_AJUSTES_FILE, f"Reset active overrides by {usuario_actual}")
                st.success(tr("✅ Overrides activos reseteados.", "✅ Active overrides cleared."))
                st.rerun()

        st.divider()
        # --- NOVEDAD 1 (VISIBLE): GESTOR DE NUEVOS LANZAMIENTOS (NPI & NEW BUSINESS) ---
        with st.expander(tr("🆕 Gestor de Nuevos Lanzamientos y Licitaciones Comerciales (NPI & New Business - 0 Kg Histórico)", "🆕 New Product Introduction (NPI) & New Business Manager (0 Kg History)"), expanded=True):
            st.caption(tr(
                "Da de alta SKUs nuevos o licitaciones comerciales ganadas sin histórico previo. Hereda la curva estacional de un 'SKU Espejo' e inyecta el nuevo SKU en MPS, MRP, Capacidad de Planta y P&L (GBP).",
                "Register new SKUs or won commercial tenders with zero prior history. Inherits seasonal shape from a 'Mirror SKU' and injects into MPS, MRP, Plant Capacity, and P&L (GBP)."
            ))
            npi_c1, npi_c2, npi_c3, npi_c4 = st.columns(4)
            with npi_c1:
                npi_cod = st.text_input(tr("Código Nuevo SKU:", "New SKU Code:"), value="NPI-2027-01")
                npi_desc = st.text_input(tr("Descripción Nuevo SKU:", "New SKU Description:"), value="NUEVA FORMULA AVANZADA PRO")
                npi_pais = st.selectbox(tr("Planta / País Destino:", "Target Plant / Country:"), sorted(df['País'].dropna().unique().tolist()), key="npi_pais_sel")
            with npi_c2:
                clis_pais_npi = sorted(df[df['País'] == npi_pais]['customer cod'].dropna().unique().tolist()) if npi_pais else ["CLI-NEW"]
                opcion_nuevo = "➕ NUEVO CLIENTE (Licitación)..."
                lista_clis_npi = [opcion_nuevo] + clis_pais_npi
                
                npi_cli_sel = st.selectbox(tr("Cliente Asignado:", "Assigned Customer:"), lista_clis_npi, key="npi_cli_sel")
                if npi_cli_sel == opcion_nuevo:
                    npi_cli = st.text_input(tr("Código del Nuevo Cliente:", "New Customer Code:"), value="CLI-NEW-001", key="npi_cli_manual")
                else:
                    npi_cli = npi_cli_sel
                    
                npi_espejo = st.selectbox(tr("SKU Espejo (Estacionalidad):", "Mirror SKU (Seasonality):"), sorted(df['sku cod'].dropna().unique().tolist()), key="npi_esp_sel")
                npi_pol = st.selectbox(tr("Política de Stock:", "Stock Policy:"), ["MTS", "MTO"], key="npi_pol_sel")
            with npi_c3:
                npi_vol = st.number_input(tr("Volumen Mensual Objetivo (Kg):", "Target Monthly Volume (Kg):"), min_value=100, max_value=500000, value=18000, step=1000)
                npi_mes_ini = st.slider(tr("Mes de Lanzamiento (1..H):", "Launch Month (1..H):"), min_value=1, max_value=int(horizonte), value=2)
            with npi_c4:
                npi_precio = st.number_input(tr("Precio Venta Unitario (EUR/Kg):", "Unit Sales Price (EUR/Kg):"), min_value=0.1, max_value=200.0, value=4.50, step=0.25)
                npi_margen = st.number_input(tr("Margen Bruto Unitario (EUR/Kg):", "Unit Gross Margin (EUR/Kg):"), min_value=0.05, max_value=150.0, value=1.40, step=0.10)
                maqs_disp_npi = sorted(df_rutas['Maquina'].dropna().unique().tolist()) if (df_rutas is not None and not df_rutas.empty) else ["ES_Linea_1_Extrusion"]
                npi_maq = st.selectbox(tr("Línea de Fabricación:", "Production Line:"), maqs_disp_npi, key="npi_maq_sel")

            nb_b1, nb_b2 = st.columns([1, 1])
            with nb_b1:
                if st.button(tr("➕ Inyectar Nuevo Lanzamiento NPI en el Plan S&OP (Cloud)", "➕ Inject New NPI Launch into S&OP Plan (Cloud)"), type="primary", use_container_width=True):
                    df_npi_curr = st.session_state.get('df_npi', pd.DataFrame(columns=COLS_NPI)).copy()
                    df_npi_curr = df_npi_curr[df_npi_curr['sku cod'].astype(str).str.strip() != str(npi_cod).strip()]
                    nueva_fila_npi = {
                        "sku cod": str(npi_cod).strip(), "sku desc": str(npi_desc).strip(),
                        "País": npi_pais, "customer cod": npi_cli, "customer desc": f"Cuenta {npi_cli}",
                        "SKU_Espejo": npi_espejo, "Volumen_Mensual_Kg": float(npi_vol),
                        "Mes_Inicio": int(npi_mes_ini), "Precio_Unit_EUR": float(npi_precio),
                        "Margen_Unit_EUR": float(npi_margen), "Maquina": npi_maq,
                        "Kilos_por_Hora": 5500, "Politica_Stock": npi_pol
                    }
                    df_npi_curr = pd.concat([df_npi_curr, pd.DataFrame([nueva_fila_npi])], ignore_index=True)
                    st.session_state['df_npi'] = df_npi_curr
                    github_guardar_csv(df_npi_curr, NPI_CLOUD_FILE, f"NPI Launch {npi_cod} added by {usuario_actual}")
                    st.success(tr(f"✅ Lanzamiento NPI [{npi_cod}] integrado en toda la cadena S&OP.", f"✅ NPI Launch [{npi_cod}] integrated across the S&OP chain."))
                    st.rerun()
            with nb_b2:
                if st.button(tr("🗑️ Limpiar Todos los Lanzamientos NPI", "🗑️ Clear All NPI Launches"), use_container_width=True):
                    df_npi_empty = pd.DataFrame(columns=COLS_NPI)
                    st.session_state['df_npi'] = df_npi_empty
                    github_guardar_csv(df_npi_empty, NPI_CLOUD_FILE, f"Clear NPI launches by {usuario_actual}")
                    st.rerun()

            if not st.session_state.get('df_npi', pd.DataFrame()).empty:
                st.dataframe(st.session_state['df_npi'], use_container_width=True, hide_index=True)

        with st.expander(tr("🏆 Tabla del Torneo Multi-Modelo Auto-ML (Selección del Mejor Algoritmo por SKU)", "🏆 Multi-Model Auto-ML Tournament Table (Best-Fit Algorithm per SKU)"), expanded=False):
            st.caption(tr(
                "Muestra el error histórico de validación (WAPE %) de los 3 motores estadísticos en cada SKU y el algoritmo ganador asignado por el modo Auto-ML Best-Fit.",
                "Displays the backtest validation error (WAPE %) across all 3 statistical engines per SKU and the winning algorithm assigned by Auto-ML Best-Fit."
            ))
            filas_torneo = []
            for s_c, m_info in dict_meta_torneo.items():
                filas_torneo.append({
                    "sku cod": s_c,
                    "Descripción SKU": dict_sku_desc.get(s_c, s_c),
                    "Algoritmo Ganador (Best-Fit)": m_info["Ganador"],
                    "WAPE Holt-Winters (%)": m_info["WAPE_HW"],
                    "WAPE Damped WMA (%)": m_info["WAPE_WMA"],
                    "WAPE Croston TSB (%)": m_info["WAPE_Croston"],
                    "Mejor WAPE (%)": m_info["WAPE_Min"]
                })
            if filas_torneo:
                df_torneo_show = pd.DataFrame(filas_torneo).sort_values("Mejor WAPE (%)").reset_index(drop=True)
                st.dataframe(
                    df_torneo_show.style.format({
                        "WAPE Holt-Winters (%)": "{:.1f}%",
                        "WAPE Damped WMA (%)": "{:.1f}%",
                        "WAPE Croston TSB (%)": "{:.1f}%",
                        "Mejor WAPE (%)": "{:.1f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

        with st.expander(tr(
            "📋 Historial de Cambios de Consenso, Snapshots & Evaluador Post-Mortem FVA",
            "📋 Consensus Change History, Snapshots & Post-Mortem FVA Evaluator"
        ), expanded=False):
            col_fva1, col_fva2 = st.columns([1, 4])
            with col_fva1:
                if st.button(tr("🔄 Refrescar Log FVA", "🔄 Refresh FVA Log"), use_container_width=True):
                    st.session_state["df_fva_logs"] = github_leer_csv(FVA_LOG_FILE, COLS_FVA_LOG, forzar_recarga=True)
            df_fva_view = st.session_state.get("df_fva_logs", github_leer_csv(FVA_LOG_FILE, COLS_FVA_LOG))
            if df_fva_view is None or df_fva_view.empty:
                st.info(tr("Aún no se han registrado modificaciones manuales ni Snapshots de consenso en la nube.", "No manual overrides or consensus snapshots logged in the cloud yet."))
            else:
                fva_c1, fva_c2, fva_c3 = st.columns(3)
                fva_c1.metric(tr("Registros / Snapshots en Log", "Logged Entries / Snapshots"), f"{len(df_fva_view)}")
                fva_c2.metric(tr("SKUs Intervenidos", "Modified SKUs"), f"{df_fva_view['sku cod'].nunique()}")
                delta_sum_fva = pd.to_numeric(df_fva_view['Delta_Kg'], errors='coerce').fillna(0).sum()
                fva_c3.metric(tr("Volumen Neto Añadido (FVA)", "Net Volume Added (FVA)"), f"{delta_sum_fva:+,.0f} Kg")

                st.dataframe(
                    df_fva_view.iloc[::-1].style.format({
                        "Forecast_Estadistico": "{:,.0f} Kg",
                        "Consenso_Override": "{:,.0f} Kg",
                        "Delta_Kg": "{:+,.0f} Kg",
                        "Delta_Pct_FVA": "{:+.1f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                csv_fva = df_fva_view.iloc[::-1].to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=tr("📥 Descargar Auditoría FVA (.csv)", "📥 Download FVA Audit Log (.csv)"),
                    data=csv_fva,
                    file_name=f"Audit_FVA_Consenso_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

                st.markdown("---")
                st.markdown(f"#### {tr('🎯 Evaluación Post-Mortem de FVA (Foto Congelada vs. Venta Real Cerrada)', '🎯 Post-Mortem FVA Evaluation (Frozen Snapshot vs. Closed Actual Sales)')}")

                df_snap = df_fva_view.copy()
                df_snap['Date_Mes'] = pd.to_datetime(df_snap['Date'], errors='coerce').dt.to_period('M').dt.to_timestamp()
                df_snap = df_snap.dropna(subset=['Date_Mes']).drop_duplicates(subset=['Date_Mes', 'País', 'customer cod', 'sku cod'], keep='last')

                df_real_mes = df.copy()
                df_real_mes['Date_Mes'] = pd.to_datetime(df_real_mes['Date'], errors='coerce').dt.to_period('M').dt.to_timestamp()
                df_real_agg = df_real_mes.groupby(['Date_Mes', 'País', 'customer cod', 'sku cod'])['volume'].sum().reset_index()
                df_real_agg = df_real_agg.rename(columns={'volume': 'Venta_Real_Kg'})

                df_postmortem = pd.merge(
                    df_snap,
                    df_real_agg,
                    on=['Date_Mes', 'País', 'customer cod', 'sku cod'],
                    how='inner'
                )

                if df_postmortem.empty:
                    st.info(tr(
                        "ℹ️ Todavía no hay cruce entre las fechas futuras guardadas en el Log FVA y los meses cerrados de tu archivo '1. Histórico Ventas'.",
                        "ℹ️ No overlap yet between future dates stored in the FVA Log and closed months in '1. Sales History'."
                    ))
                else:
                    est_fijo = pd.to_numeric(df_postmortem['Forecast_Estadistico'], errors='coerce').fillna(0)
                    con_fijo = pd.to_numeric(df_postmortem['Consenso_Override'], errors='coerce').fillna(0)
                    real_kg = pd.to_numeric(df_postmortem['Venta_Real_Kg'], errors='coerce').fillna(0)

                    df_postmortem['Error_Abs_Estadistico'] = (real_kg - est_fijo).abs()
                    df_postmortem['Error_Abs_Consenso'] = (real_kg - con_fijo).abs()
                    df_postmortem['FVA_Neto_Kg'] = df_postmortem['Error_Abs_Estadistico'] - df_postmortem['Error_Abs_Consenso']
                    df_postmortem['Veredicto_S&OP'] = np.where(
                        df_postmortem['FVA_Neto_Kg'] > 0,
                        tr('🟢 Aportó Valor (Mejoró al Modelo)', '🟢 Added Value (Beat Model)'),
                        np.where(df_postmortem['FVA_Neto_Kg'] < 0, tr('🔴 Destruyó Valor (Peor que el Modelo)', '🔴 Destroyed Value (Worse than Model)'), '⚪ Neutral')
                    )

                    pm1, pm2, pm3 = st.columns(3)
                    err_est_tot = df_postmortem['Error_Abs_Estadistico'].sum()
                    err_con_tot = df_postmortem['Error_Abs_Consenso'].sum()
                    real_tot_pm = real_kg.sum()
                    wape_est_pm = (err_est_tot / real_tot_pm * 100) if real_tot_pm > 0 else 0.0
                    wape_con_pm = (err_con_tot / real_tot_pm * 100) if real_tot_pm > 0 else 0.0
                    fva_global_pct = wape_est_pm - wape_con_pm

                    pm1.metric(tr("Error WAPE Modelo Base", "Baseline Model WAPE"), f"{wape_est_pm:.1f}%")
                    pm2.metric(tr("Error WAPE Consenso", "Consensus WAPE"), f"{wape_con_pm:.1f}%", f"{-fva_global_pct:+.1f}% vs Base", delta_color="inverse")
                    pm3.metric(tr("FVA Neto Acumulado (Kg)", "Cumulative Net FVA (Kg)"), f"{df_postmortem['FVA_Neto_Kg'].sum():+,.0f} Kg")

                    df_pm_show = df_postmortem[[
                        'Date', 'País', 'customer cod', 'sku cod', 'Usuario',
                        'Forecast_Estadistico', 'Consenso_Override', 'Venta_Real_Kg',
                        'Error_Abs_Estadistico', 'Error_Abs_Consenso', 'FVA_Neto_Kg', 'Veredicto_S&OP'
                    ]].copy()

                    st.dataframe(
                        df_pm_show.style.format({
                            'Forecast_Estadistico': '{:,.0f} Kg',
                            'Consenso_Override': '{:,.0f} Kg',
                            'Venta_Real_Kg': '{:,.0f} Kg',
                            'Error_Abs_Estadistico': '{:,.0f} Kg',
                            'Error_Abs_Consenso': '{:,.0f} Kg',
                            'FVA_Neto_Kg': '{:+,.0f} Kg'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

# ==========================================
# MODULO 2: PRODUCCIÓN (MPS)
# ==========================================
if modulo_activo == t["tab2"]:
    if "tab2" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Producción.", "🔒 You do not have permission to access the Production module."))
    else:
        if df_stock is None or sku_sel == "TODOS":
            st.info(tr("👈 Sube el archivo '3. Stock Actual' y selecciona un SKU específico en el filtro 4.", "👈 Upload '3. Current Inventory' file and select a specific SKU in filter 4."))
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
            c3.metric(t["kpi_doh"], f"{df_plan_fg['DOH'].mean():.0f} {tr('Días', 'Days')}")
            st.markdown("<br>", unsafe_allow_html=True)
            
            fig_prod = go.Figure()
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Salidas_Brutas'], name=tr('Demanda', 'Demand'), marker_color='#E5E9ED'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Recepciones_ERP'], name='ERP Pipeline', marker_color='#A0B2C6'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Entradas_Netas'], name=tr('Nuevas Órdenes', 'New Orders'), marker_color='#1E3E5B'))
            fig_prod.add_trace(go.Scatter(x=df_plan_fg.index, y=df_plan_fg['Stock_Final'], mode='lines+markers', name=f"Stock FG ({tr('Obj', 'Target')}: {cob_real_fg}m)", line=dict(color='#88FFBB', width=3)))
            
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
# MODULO 3: COMPRAS (MRP 2D) + PEGGING + SANKEY E2E + SIMULADOR REFORMULACIÓN BOM
# ==========================================
if modulo_activo == t["tab3"]:
    if "tab3" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Compras (MRP).", "🔒 You do not have permission to access the Purchasing (MRP) module."))
    else:
        st.subheader(tr("Planificación de Compras (MRP Matricial 2D)", "MRP / Purchasing Plan (2D Matrix Engine)"))
        if df_bom is None or df_stock is None:
            st.info(tr("👈 Sube los archivos '3. Stock Actual' y '4. BOM' en la barra lateral.", "👈 Upload '3. Current Inventory' & '4. BOM' files in the sidebar."))
        else:
            lista_rms = ["TODAS"] + sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist())
            rm_sel = st.selectbox(
                tr("🔍 Filtrar Materia Prima:", "🔍 Filter Raw Material:"), 
                lista_rms,
                format_func=lambda x: "TODAS" if x == "TODAS" else f"[{x}] {str(dict_rm_desc.get(x, ''))}"
            )
            
            if st.button(tr("🚀 Ejecutar Explosión BOM (MRP)", "🚀 Execute BOM Explosion (MRP)")):
                with st.spinner(tr("Procesando explosión BOM matricial 2D...", "Processing 2D matrix BOM explosion...")):
                    df_viz = generar_mrp_global()
                    
                    if df_viz is None or df_viz.empty or 'rm cod' not in df_viz.columns:
                        st.warning(tr("⚠️ No se han generado necesidades de compra.", "⚠️ No purchasing requirements generated."))
                    else:
                        if rm_sel != "TODAS":
                            df_viz = df_viz[df_viz['rm cod'] == rm_sel]
                            
                        if df_viz.empty:
                            st.warning(tr("Sin demanda para el material seleccionado.", "No demand for the selected material."))
                        else:
                            df_viz['MP_Visual'] = "[" + df_viz['rm cod'].astype(str) + "] " + df_viz['rm desc'].fillna('')
                            
                            top_mps = df_viz.groupby('MP_Visual')['Entradas_Netas'].sum().nlargest(9).index
                            df_plot_rm = df_viz[df_viz['MP_Visual'].isin(top_mps)] if rm_sel == "TODAS" else df_viz
                            titulo_graf = tr("Llegadas a Fábrica - Top 9 Materias Primas Críticas", "Factory Arrivals - Top 9 Critical Raw Materials") if rm_sel == "TODAS" else f"MRP - {rm_sel}"
                            
                            lbl_new = tr('Nuevas (Teóricas)', 'New Orders (Planned)')
                            lbl_erp = tr('ERP (Firme)', 'ERP (Firm PO)')

                            fig_rm = px.bar(
                                pd.melt(
                                    df_plot_rm,
                                    id_vars=['Date', 'MP_Visual'],
                                    value_vars=['Recepciones_ERP', 'Entradas_Netas'],
                                    var_name='Tipo',
                                    value_name='Volumen'
                                ).replace({'Entradas_Netas': lbl_new, 'Recepciones_ERP': lbl_erp}),
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
                                df_show.head(500).reset_index(drop=True).style.format(
                                    "{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final']
                                ).format(
                                    "{:.0f}", subset=['DOH']
                                ).map(estilo_doh, subset=['DOH']),
                                use_container_width=True
                            )

            st.divider()
            st.markdown(f"### {tr('🔗 Trazabilidad Inversa (Pegging: Materia Prima → Producto Terminado → Margen en Riesgo)', '🔗 Interactive Pegging (Raw Material → Finished Good → Margin at Risk)')}")
            lista_rm_pegging = sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist())
            rm_peg_sel = st.selectbox(
                tr("🧬 Seleccionar Materia Prima para Pegging:", "🧬 Select Raw Material for Pegging:"), 
                lista_rm_pegging, 
                key="sel_pegging_rm",
                format_func=lambda x: f"[{x}] {str(dict_rm_desc.get(x, ''))}"
            )

            if rm_peg_sel:
                df_mps_peg_all = generar_mps_df_2d()
                sub_bom_peg = df_bom[df_bom['rm cod'].astype(str).str.strip() == str(rm_peg_sel).strip()].copy()

                if not df_mps_peg_all.empty and not sub_bom_peg.empty:
                    df_fab_sku = df_mps_peg_all.groupby('sku cod', as_index=False)[['Entradas_Netas', 'Recepciones_ERP']].sum()
                    df_fab_sku['Plan Fabricación PT (Kg)'] = df_fab_sku['Entradas_Netas'] + df_fab_sku['Recepciones_ERP']
                    df_fab_sku['sku_clean'] = df_fab_sku['sku cod'].astype(str).str.strip()

                    sub_bom_peg['sku_clean'] = sub_bom_peg['sku cod'].astype(str).str.strip()
                    sub_bom_peg['Dosificación BOM'] = pd.to_numeric(sub_bom_peg['Cantidad'], errors='coerce').fillna(0.0)

                    df_pegging = pd.merge(sub_bom_peg[['sku_clean', 'Dosificación BOM']], df_fab_sku[['sku_clean', 'Plan Fabricación PT (Kg)']], on='sku_clean', how='inner')
                    df_pegging = df_pegging[(df_pegging['Dosificación BOM'] > 0) & (df_pegging['Plan Fabricación PT (Kg)'] > 0)].copy()

                    if df_pegging.empty:
                        st.info(tr("No hay órdenes de fabricación proyectadas que consuman esta materia prima en el horizonte actual.", "No planned production orders consume this raw material in the current horizon."))
                    else:
                        df_pegging['sku cod (PT)'] = df_pegging['sku_clean']
                        df_pegging['Descripción PT'] = df_pegging['sku cod (PT)'].map(dict_sku_desc).fillna(df_pegging['sku cod (PT)'])
                        df_pegging['Consumo MP Requerido (Kg)'] = df_pegging['Plan Fabricación PT (Kg)'] * df_pegging['Dosificación BOM']
                        df_pegging['Revenue Expuesto (£)'] = df_pegging['Plan Fabricación PT (Kg)'] * df_pegging['sku cod (PT)'].map(dict_price).fillna(0.0)
                        df_pegging['Margen Bruto en Riesgo (£)'] = df_pegging['Plan Fabricación PT (Kg)'] * df_pegging['sku cod (PT)'].map(dict_margin).fillna(0.0)

                        df_pegging = df_pegging.sort_values(by="Margen Bruto en Riesgo (£)", ascending=False).reset_index(drop=True)
                        kp1, kp2, kp3 = st.columns(3)
                        kp1.metric(tr("PTs Dependientes", "Dependent FGs"), f"{len(df_pegging)} SKUs")
                        kp2.metric(tr("Consumo Total MP (Horizonte)", "Total RM Consumption"), f"{df_pegging['Consumo MP Requerido (Kg)'].sum():,.0f} Kg")
                        kp3.metric(tr("Margen Bruto Protegido (£)", "Protected Gross Margin (£)"), f"£ {df_pegging['Margen Bruto en Riesgo (£)'].sum():,.0f}")

                        cols_peg_show = ["sku cod (PT)", "Descripción PT", "Dosificación BOM", "Plan Fabricación PT (Kg)", "Consumo MP Requerido (Kg)", "Revenue Expuesto (£)", "Margen Bruto en Riesgo (£)"]
                        st.dataframe(
                            df_pegging[cols_peg_show].head(100).style.format({
                                "Dosificación BOM": "{:.4f}",
                                "Plan Fabricación PT (Kg)": "{:,.0f} Kg",
                                "Consumo MP Requerido (Kg)": "{:,.0f} Kg",
                                "Revenue Expuesto (£)": "£ {:,.0f}",
                                "Margen Bruto en Riesgo (£)": "£ {:,.0f}"
                            }),
                            use_container_width=True,
                            hide_index=True
                        )

                        # --- SIMULADOR DE REFORMULACIÓN Y SUSTITUCIÓN DE MP (BOM CHANGE CONTROL) ---
                        st.markdown("---")
                        st.markdown(f"#### {tr('🧪 Gobernanza de Reformulación y Sustitución de Materia Prima (BOM Change Control)', '🧪 BOM Formulation Change Control & Raw Material Substitution Simulator')}")
                        coste_rm_actual = 0.85
                        if df_stock is not None and not df_stock.empty:
                            c_match = df_stock.loc[df_stock['sku cod'].astype(str).str.strip() == str(rm_peg_sel).strip(), 'Coste_Unitario'].values
                            if len(c_match) > 0 and pd.notna(c_match[0]):
                                coste_rm_actual = float(c_match[0])

                        b_sim1, b_sim2, b_sim3 = st.columns(3)
                        with b_sim1:
                            pct_sust_bom = st.slider(
                                tr("% Sustitución / Reducción de Dosificación en Receta:", "% Substitution / Dosage Reduction in BOM:"),
                                min_value=0, max_value=100, value=15, step=5
                            )
                        with b_sim2:
                            coste_rm_alt = st.number_input(
                                tr("Coste Unitario MP Alternativa (EUR/Kg):", "Alternative RM Unit Cost (EUR/Kg):"),
                                min_value=0.0, max_value=500.0, value=round(coste_rm_actual * 0.80, 2), step=0.05
                            )
                        with b_sim3:
                            mes_phase_in = st.slider(
                                tr("Mes de Entrada en Vigor (Phase-In Month 1..H):", "Effective Phase-In Month (1..H):"),
                                min_value=1, max_value=int(horizonte), value=2
                            )

                        fraccion_horizonte = max(0.0, float(horizonte - mes_phase_in + 1) / float(horizonte))
                        consumo_actual_tot = float(df_pegging['Consumo MP Requerido (Kg)'].sum())
                        kilos_sustituidos = consumo_actual_tot * (pct_sust_bom / 100.0) * fraccion_horizonte
                        ahorro_eur_por_kg = coste_rm_actual - coste_rm_alt
                        impacto_margen_gbp_bom = kilos_sustituidos * ahorro_eur_por_kg * fx_eur_gbp

                        bs1, bs2, bs3 = st.columns(3)
                        bs1.metric(tr("Coste Actual MP (EUR/Kg)", "Current RM Cost (EUR/Kg)"), f"€ {coste_rm_actual:,.2f}/Kg")
                        bs2.metric(tr("Volumen MP Sustituido (Phase-Out)", "Substituted RM Volume (Phase-Out)"), f"-{kilos_sustituidos:,.0f} Kg")
                        bs3.metric(tr("Impacto Neto en Margen Bruto (£)", "Net Gross Margin Impact (£)"), f"£ {impacto_margen_gbp_bom:+,.0f}")

            st.divider()
            st.markdown(f"### {tr('🕸️ Visualización de la Red de Suministro E2E (Diagrama Sankey)', '🕸️ End-to-End Supply Network Visualization (Sankey Diagram)')}")
            fig_sk = construir_diagrama_sankey_red(generar_mps_df_2d(), df_bom, df_rutas, df)
            if fig_sk is not None:
                st.plotly_chart(fig_sk, use_container_width=True)

# ==========================================
# MODULO 4: CAPACIDAD (RCCP POR PLANTA + NOVEDAD 2 SIMULADOR DE TURNOS + PRE-BUILD)
# ==========================================
if modulo_activo == t["tab4"]:
    if "tab4" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Capacidad.", "🔒 You do not have permission to access the Capacity module."))
    else:
        st.subheader(tr("Planificación de Capacidad por Planta (RCCP), Simulador de Turnos & Pre-Build", "Plant Capacity Planning (RCCP), Shift Simulator & Pre-Build"))
        if df_rutas is None or df_cal is None:
            st.info(tr("👈 Sube '5. Rutas / Routing' y '6. Calendario' en la barra lateral.", "👈 Upload '5. Production Routing' & '6. Plant Calendar' in the sidebar."))
        else:
            skus_scope_cap = set(df_final['sku cod'].astype(str).str.strip().unique()) if not df_final.empty else set()
            df_rutas_clean = df_rutas.copy()
            df_rutas_clean['sku cod'] = df_rutas_clean['sku cod'].astype(str).str.strip()
            df_rutas_clean['Maquina'] = df_rutas_clean['Maquina'].astype(str).str.strip()

            df_rutas_scope = df_rutas_clean[df_rutas_clean['sku cod'].isin(skus_scope_cap)].copy()

            maquinas_disponibles = sorted(df_rutas_scope['Maquina'].dropna().unique().tolist())
            lista_maquinas = ["TODOS"] + maquinas_disponibles

            st.caption(
                f"🌍 **{tr('Ámbito de Planta Activo', 'Active Plant Scope')}:** "
                f"{tr('País', 'Country')}: `{pais_sel}` | {tr('Cliente', 'Customer')}: `{cliente_sel}` | "
                f"{tr('Líneas detectadas', 'Detected Lines')}: `{len(maquinas_disponibles)}`"
            )

            col_c_top1, col_c_top2, col_c_top3 = st.columns(3)
            with col_c_top1:
                maq_sel = st.selectbox(tr("⚙️ Filtrar Línea / Máquina de la Planta:", "⚙️ Filter Plant Line / Work Center:"), lista_maquinas)
            with col_c_top2:
                umbral_prebuild = st.slider(tr("🎯 Techo Máximo de Utilización para Pre-Build (%):", "🎯 Max Utilization Cap for Pre-Build Leveling (%):"), 70, 120, 95, step=5)
            with col_c_top3:
                opciones_turnos = {
                    tr("Turno Base (Calendario 100%)", "Base Shift (Calendar 100%)"): 1.00,
                    tr("+1 Turno Fin de Semana (+15% Horas)", "+1 Weekend Shift (+15% Hours)"): 1.15,
                    tr("+2 Turnos Intensivos (+25% Horas)", "+2 Intensive Shifts (+25% Hours)"): 1.25,
                    tr("Operación Continua 24/7 (+35% Horas)", "24/7 Continuous Operation (+35% Hours)"): 1.35
                }
                turno_label_sel = st.selectbox(tr("⏱️ Simulador de Turnos / Horas Extra:", "⏱️ Extra Shifts / Overtime Simulator:"), list(opciones_turnos.keys()), key="sel_turno_cap")
                factor_turno = opciones_turnos[turno_label_sel]
            
            df_mps_concat = generar_mps_df_2d()
            if not df_mps_concat.empty and not df_rutas_scope.empty:
                vol_global_sku = df.groupby('sku cod')['volume'].sum().to_dict()
                vol_filtro_sku = df_final.groupby('sku cod')['volume'].sum().to_dict()

                df_mps_concat['sku cod'] = df_mps_concat['sku cod'].astype(str).str.strip()
                df_mps_scope = df_mps_concat[df_mps_concat['sku cod'].isin(skus_scope_cap)].copy()

                df_mps_scope['Share_Cap'] = [
                    float(vol_filtro_sku.get(s, 0.0)) / max(1.0, float(vol_global_sku.get(s, 1.0)))
                    for s in df_mps_scope['sku cod']
                ]
                df_mps_scope['Carga_Total_Kg'] = (df_mps_scope['Entradas_Netas'] + df_mps_scope['Recepciones_ERP']) * df_mps_scope['Share_Cap']
                df_mps_pos = df_mps_scope[df_mps_scope['Carga_Total_Kg'] > 0].copy()

                df_req = pd.merge(df_mps_pos, df_rutas_scope, on='sku cod', how='inner')

                if df_req.empty:
                    st.warning(tr("⚠️ Ningún SKU del filtro actual requiere horas de fabricación en las líneas de esta planta.", "⚠️ No SKU in the current filter requires production hours on this plant's lines."))
                else:
                    df_req['Kilos_por_Hora'] = pd.to_numeric(df_req['Kilos_por_Hora'], errors='coerce').fillna(1).replace(0, 1)
                    df_req['Horas_Necesarias'] = df_req['Carga_Total_Kg'] / df_req['Kilos_por_Hora']

                    df_cal_clean = df_cal.copy()
                    df_cal_clean['Maquina'] = df_cal_clean['Maquina'].astype(str).str.strip()
                    df_cal_clean['Date'] = pd.to_datetime(df_cal_clean['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
                    df_cal_clean['Horas_Base'] = pd.to_numeric(df_cal_clean['Horas_Disponibles'], errors='coerce').fillna(740).replace(0, 1)
                    df_cal_clean['Horas_Disponibles'] = df_cal_clean['Horas_Base'] * factor_turno
                    df_req['Date'] = pd.to_datetime(df_req['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()

                    df_capacidad = pd.merge(
                        df_req.groupby(['Date', 'Maquina']).agg(
                            Horas_Necesarias=('Horas_Necesarias', 'sum'),
                            Kilos_Totales=('Carga_Total_Kg', 'sum'),
                            Tasa_Media_KPH=('Kilos_por_Hora', 'mean')
                        ).reset_index(),
                        df_cal_clean,
                        on=['Date', 'Maquina'],
                        how='left'
                    ).fillna({'Horas_Base': 740, 'Horas_Disponibles': 740 * factor_turno})
                    
                    df_capacidad['Utilizacion'] = (df_capacidad['Horas_Necesarias'] / df_capacidad['Horas_Disponibles']) * 100.0

                    # NOVEDAD 2: Panel de KPIs del Simulador de Turnos Extra
                    horas_extra_tot = float((df_capacidad['Horas_Disponibles'] - df_capacidad['Horas_Base']).sum())
                    coste_turnos_gbp = horas_extra_tot * 145.0
                    t_k1, t_k2, t_k3 = st.columns(3)
                    t_k1.metric(tr("⏱️ Régimen Activo", "⏱️ Active Shift Regime"), turno_label_sel.split("(")[0].strip())
                    t_k2.metric(tr("➕ Horas Extra Añadidas", "➕ Added Overtime Hours"), f"+{horas_extra_tot:,.0f} h")
                    t_k3.metric(tr("💷 Coste Operativo Turnos (£)", "💷 Shift Overtime Cost (£)"), f"£ {coste_turnos_gbp:,.0f}")

                    if maq_sel == "TODOS":
                        df_pivot = df_capacidad.pivot(index='Maquina', columns='Date', values='Utilizacion').fillna(0)
                        df_pivot.columns = pd.to_datetime(df_pivot.columns).strftime('%Y-%m')
                        
                        st.markdown(f"#### {tr('1. Matriz de Utilización por Planta (Sin Nivelar %)', '1. Unconstrained Plant Utilization Matrix (%)')}")
                        try:
                            st.dataframe(df_pivot.style.background_gradient(cmap='RdYlGn_r', vmin=0, vmax=120).format("{:.1f}%"), use_container_width=True)
                        except Exception:
                            st.dataframe(df_pivot.style.format("{:.1f}%"), use_container_width=True)
                    else:
                        df_req_maq = df_req[df_req['Maquina'] == maq_sel]
                        if not df_req_maq.empty:
                            top_skus_maq = df_req_maq.groupby('sku desc')['Horas_Necesarias'].sum().nlargest(12).index
                            df_req_maq_plot = df_req_maq.copy()
                            df_req_maq_plot['SKU_Agrupado'] = np.where(df_req_maq_plot['sku desc'].isin(top_skus_maq), df_req_maq_plot['sku desc'], 'Otros SKUs')
                            fig_cap = px.bar(
                                df_req_maq_plot.groupby(['Date', 'SKU_Agrupado'])['Horas_Necesarias'].sum().reset_index(),
                                x='Date', y='Horas_Necesarias', color='SKU_Agrupado',
                                title=f"{tr('Carga vs Capacidad', 'Load vs Capacity')}: {maq_sel}"
                            )
                            df_cal_maq = df_cal_clean[df_cal_clean['Maquina'] == maq_sel]
                            merged_line = pd.merge(
                                df_req_maq.groupby('Date')['Horas_Necesarias'].sum().reset_index(),
                                df_cal_maq, on='Date', how='left'
                            ).fillna({'Horas_Disponibles': 740 * factor_turno})
                            
                            fig_cap.add_trace(go.Scatter(
                                x=merged_line['Date'], y=merged_line['Horas_Disponibles'],
                                mode='lines', name='Max Hours', line=dict(color='red', width=3, dash='dash')
                            ))
                            fig_cap.update_layout(**LAYOUT_STYLE, yaxis_title=tr("Horas", "Hours"), barmode='stack')
                            st.plotly_chart(fig_cap, use_container_width=True)

                    st.divider()
                    st.markdown(f"### {tr('⚖️ Motor de Nivelación Automática de Capacidad Finita (Pre-Build & Line Balancing)', '⚖️ Automated Finite Capacity Leveling Engine (Pre-Build & Line Balancing)')}")
                    filas_niveladas = []
                    movimientos_prebuild = []
                    for maq_k, grp_m in df_capacidad.sort_values('Date').groupby('Maquina'):
                        fechas_m = grp_m['Date'].tolist()
                        h_nec = grp_m['Horas_Necesarias'].values.astype(float).copy()
                        h_disp = grp_m['Horas_Disponibles'].values.astype(float).copy()
                        kph_m = grp_m['Tasa_Media_KPH'].values.astype(float).copy()
                        h_cap = h_disp * (float(umbral_prebuild) / 100.0)

                        for idx_t in range(len(h_nec) - 1, 0, -1):
                            if h_nec[idx_t] > h_cap[idx_t]:
                                exceso_h = h_nec[idx_t] - h_cap[idx_t]
                                holgura_prev = max(0.0, h_cap[idx_t - 1] - h_nec[idx_t - 1])
                                desplazado_h = min(exceso_h, holgura_prev)
                                if desplazado_h > 0.1:
                                    h_nec[idx_t] -= desplazado_h
                                    h_nec[idx_t - 1] += desplazado_h
                                    kilos_mov = desplazado_h * kph_m[idx_t]
                                    movimientos_prebuild.append({
                                        "Línea / Máquina": maq_k,
                                        "Mes Pico (Origen)": pd.to_datetime(fechas_m[idx_t]).strftime('%Y-%m'),
                                        "Mes Pre-Build (Adelanto)": pd.to_datetime(fechas_m[idx_t - 1]).strftime('%Y-%m'),
                                        "Horas Adelantadas": round(desplazado_h, 1),
                                        "Volumen Pre-Build (Kg)": round(kilos_mov, 0),
                                        "Sobrecoste WC Temporal (£)": round(kilos_mov * 1.85 * 0.015, 0)
                                    })

                        for idx_t, f_dt in enumerate(fechas_m):
                            filas_niveladas.append({
                                "Date": f_dt,
                                "Maquina": maq_k,
                                "Utilizacion_Nivelada": (h_nec[idx_t] / h_disp[idx_t]) * 100.0 if h_disp[idx_t] > 0 else 0.0
                            })

                    df_cap_niv = pd.DataFrame(filas_niveladas)
                    if maq_sel != "TODOS":
                        df_cap_niv = df_cap_niv[df_cap_niv['Maquina'] == maq_sel]
                    df_piv_niv = df_cap_niv.pivot(index='Maquina', columns='Date', values='Utilizacion_Nivelada').fillna(0)
                    df_piv_niv.columns = pd.to_datetime(df_piv_niv.columns).strftime('%Y-%m')

                    st.markdown(f"#### {tr('2. Matriz de Utilización Nivelada tras Pre-Build (%)', '2. Leveled Utilization Matrix after Pre-Build (%)')}")
                    try:
                        st.dataframe(df_piv_niv.style.background_gradient(cmap='RdYlGn_r', vmin=0, vmax=120).format("{:.1f}%"), use_container_width=True)
                    except Exception:
                        st.dataframe(df_piv_niv.style.format("{:.1f}%"), use_container_width=True)

                    if movimientos_prebuild:
                        df_mov_pb = pd.DataFrame(movimientos_prebuild)
                        if maq_sel != "TODOS":
                            df_mov_pb = df_mov_pb[df_mov_pb["Línea / Máquina"] == maq_sel]
                        pb1, pb2, pb3 = st.columns(3)
                        pb1.metric(tr("Adelantos Pre-Build Sugeridos", "Suggested Pre-Build Shifts"), f"{len(df_mov_pb)}")
                        pb2.metric(tr("Volumen Total Adelantado (Kg)", "Total Shifted Volume (Kg)"), f"{df_mov_pb['Volumen Pre-Build (Kg)'].sum():,.0f} Kg")
                        pb3.metric(tr("Coste Financiero Pre-Build (£)", "Pre-Build Holding Cost (£)"), f"£ {df_mov_pb['Sobrecoste WC Temporal (£)'].sum():,.0f}")
                        st.dataframe(
                            df_mov_pb.style.format({
                                "Horas Adelantadas": "{:.1f} h",
                                "Volumen Pre-Build (Kg)": "{:,.0f} Kg",
                                "Sobrecoste WC Temporal (£)": "£ {:,.0f}"
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        max_util_post = float(df_cap_niv['Utilizacion_Nivelada'].max()) if not df_cap_niv.empty else 0.0
                        if max_util_post > float(umbral_prebuild):
                            st.error(tr(
                                f"🚨 Saturación Estructural Detectada (Pico máx: {max_util_post:.1f}% > {umbral_prebuild}%): Prueba a incrementar turnos en el desplegable superior '⏱️ Simulador de Turnos / Horas Extra'.",
                                f"🚨 Structural Bottleneck Detected (Peak: {max_util_post:.1f}% > {umbral_prebuild}%): Try adding shifts in the '⏱️ Extra Shifts / Overtime Simulator' dropdown above."
                            ))
                        else:
                            st.success(tr(
                                f"✅ Capacidad en rango óptimo: Ninguna línea supera el techo del {umbral_prebuild}%.",
                                f"✅ Capacity within optimal range: No line exceeds the {umbral_prebuild}% cap."
                            ))
            else:
                st.warning(tr("⚠️ No hay datos de producción o rutas para los filtros seleccionados.", "⚠️ No production or routing data for the selected filters."))

# ==========================================
# MODULO 5: FINANZAS (100% REACTIVO Y ALINEADO POR PAÍS / CLIENTE / SKU)
# ==========================================
if modulo_activo == t["tab5"]:
    if "tab5" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Finanzas.", "🔒 You do not have permission to access the Finance module."))
    else:
        st.subheader(tr("Valoración Financiera y Working Capital (GBP)", "Financial Valuation & Working Capital (GBP)"))
        if not dict_price:
            st.warning("⚠️ No 'revenue' or 'margin' columns in history.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                opciones_pl = ["Seguir Filtros Superiores", "Consolidado Global", "Por País", "Por Cliente", "Por SKU"]
                nivel_pl = st.selectbox(tr("📊 Nivel de Análisis:", "📊 Level of Analysis:"), opciones_pl, index=0, key="fin_nivel")
                filtro_pl = None
                if nivel_pl == "Por País":
                    filtro_pl = st.selectbox(tr("País:", "Country:"), sorted(df['País'].dropna().unique()), key="fin_pais")
                elif nivel_pl == "Por Cliente":
                    filtro_pl = st.selectbox(tr("Cliente:", "Customer:"), sorted(df['customer cod'].dropna().unique()), key="fin_cli")
                elif nivel_pl == "Por SKU":
                    filtro_pl = st.selectbox("SKU:", sorted(df['sku cod'].dropna().unique()), key="fin_sku")
            with col2:
                vista_wc = st.selectbox(tr("📦 Vista Working Capital:", "📦 Working Capital View:"), ["Total (PT + MP)", "Producto Terminado (PT)", "Materia Prima (MP)"], key="fin_wc")

            if nivel_pl == "Seguir Filtros Superiores":
                df_fin_target = df_final.copy()
                titulo_estrategico = f"{pais_sel} | {cliente_sel} | {sku_sel}"
            elif nivel_pl == "Por País":
                df_fin_target = df[df['País'] == filtro_pl].copy()
                titulo_estrategico = f"{tr('País', 'Country')}: {filtro_pl}"
            elif nivel_pl == "Por Cliente":
                df_fin_target = df[df['customer cod'] == filtro_pl].copy()
                titulo_estrategico = f"{tr('Cliente', 'Customer')}: {filtro_pl}"
            elif nivel_pl == "Por SKU":
                df_fin_target = df[df['sku cod'].astype(str).str.strip() == str(filtro_pl).strip()].copy()
                titulo_estrategico = f"SKU: {filtro_pl}"
            else:
                df_fin_target = df.copy()
                titulo_estrategico = tr("Consolidado Global", "Global Consolidated")

            skus_validos = set(df_fin_target['sku cod'].astype(str).str.strip().unique())

            df_hist_pl = df_fin_target.groupby(pd.Grouper(key='Date', freq='MS'))[['Rev_GBP', 'Mar_GBP', 'volume']].sum().reset_index()
            df_hist_pl = df_hist_pl.rename(columns={'Rev_GBP': 'Revenue_GBP', 'Mar_GBP': 'Margin_GBP', 'volume': 'Vol_Kg'})
            df_hist_pl['Tipo_Periodo'] = tr('Histórico Real', 'Actual History')

            serie_vol_target = df_hist_pl.set_index('Date')['Vol_Kg'] if not df_hist_pl.empty else pd.Series(dtype=float)
            serie_vol_limpia = limpiar_anomalias(serie_vol_target) if usar_limpieza_outliers else serie_vol_target
            fcst_vol_target = calcular_forecast_serie_unica(serie_vol_limpia, int(horizonte), modelo_fcst_sel)

            aj_sub = st.session_state.get('df_ajustes', pd.DataFrame()).copy()
            if not aj_sub.empty:
                dict_aj_fin = {}
                aj_sub['Date_M'] = pd.to_datetime(aj_sub['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()
                for _, r_aj in aj_sub.dropna(subset=['Date_M']).iterrows():
                    dict_aj_fin[(str(r_aj['País']).strip(), str(r_aj['customer cod']).strip(), str(r_aj['sku cod']).strip(), r_aj['Date_M'])] = float(r_aj['override_value'])
                
                df_global_grp_fin = df.groupby(['País', 'customer cod', 'sku cod'])['volume'].sum().to_dict()
                df_filtro_grp_fin = df_fin_target.groupby(['País', 'customer cod', 'sku cod'])['volume'].sum().to_dict()
                
                fcst_con_fin_arr = np.zeros(int(horizonte))
                mat_fin = dict_fcst_matrices.get(modelo_fcst_sel, dict_fcst_matrices.get("Auto-ML Best-Fit"))
                
                if mat_fin is not None and not mat_fin.empty:
                    # Enfoque vectorizado para finanzas
                    vol_global_sku_tot_fin = df.groupby('sku cod')['volume'].sum().to_dict()
                    for s_c_str in skus_validos:
                        if s_c_str in mat_fin.columns:
                            df_cruce_fin = df_fin_target[df_fin_target['sku cod'].astype(str).str.strip() == s_c_str].drop_duplicates(subset=['País', 'customer cod'])
                            v_glob_sku = max(vol_global_sku_tot_fin.get(s_c_str, 1e-6), 1e-6)
                            
                            for i, d_m in enumerate(fcst_vol_target.index):
                                for _, r_cru in df_cruce_fin.iterrows():
                                    p_c = str(r_cru['País']).strip()
                                    c_c = str(r_cru['customer cod']).strip()
                                    
                                    aj_val = dict_aj_fin.get((p_c, c_c, s_c_str, d_m), None)
                                    if aj_val is not None:
                                        fcst_con_fin_arr[i] += aj_val
                                    else:
                                        v_tupla_fin = vol_global_tupla_cached.get((p_c, c_c, s_c_str), 0.0)
                                        share_t = v_tupla_fin / v_glob_sku if v_glob_sku > 0 else 0.0
                                        fcst_con_fin_arr[i] += (mat_fin[s_c_str].iloc[i] * share_t)
                                        
                    fcst_vol_target = pd.Series(fcst_con_fin_arr, index=fcst_vol_target.index)

            df_ult6 = df_hist_pl.tail(6)
            vol_u6 = float(df_ult6['Vol_Kg'].sum()) if not df_ult6.empty else 0.0
            precio_u_ambito = float(df_ult6['Revenue_GBP'].sum() / vol_u6) if vol_u6 > 0 else 4.0
            margen_u_ambito = float(df_ult6['Margin_GBP'].sum() / vol_u6) if vol_u6 > 0 else 1.2

            df_fcst_pl = pd.DataFrame({
                'Date': fcst_vol_target.index,
                'Revenue_GBP': fcst_vol_target.values * precio_u_ambito,
                'Margin_GBP': fcst_vol_target.values * margen_u_ambito,
                'Vol_Kg': fcst_vol_target.values,
                'Tipo_Periodo': tr('Proyección S&OP', 'S&OP Projection')
            })

            df_plot_pl = pd.concat([df_hist_pl, df_fcst_pl], ignore_index=True)

            df_mps_fin = generar_mps_df_2d()
            proporcion_ambito = float(df_fin_target['volume'].sum() / max(1.0, df['volume'].sum()))
            if not df_mps_fin.empty:
                df_mps_fin['sku_clean'] = df_mps_fin['sku cod'].astype(str).str.strip()
                df_mps_sub = df_mps_fin[df_mps_fin['sku_clean'].isin(skus_validos)].copy()
                vol_g_sku = df.groupby('sku cod')['volume'].sum().to_dict()
                vol_f_sku = df_fin_target.groupby('sku cod')['volume'].sum().to_dict()
                df_mps_sub['Share'] = [float(vol_f_sku.get(s, 0.0)) / max(1.0, float(vol_g_sku.get(s, 1.0))) for s in df_mps_sub['sku_clean']]
                df_mps_sub['P_U'] = df_mps_sub['sku_clean'].map(dict_price).fillna(precio_u_ambito)
                df_mps_sub['M_U'] = df_mps_sub['sku_clean'].map(dict_margin).fillna(margen_u_ambito)
                df_mps_sub['WorkingCapital_GBP'] = df_mps_sub['Stock_Final'] * df_mps_sub['Share'] * np.maximum(0.0, df_mps_sub['P_U'] - df_mps_sub['M_U'])
                df_wc_pt_filtrado = df_mps_sub[['Date', 'sku_clean', 'WorkingCapital_GBP']].rename(columns={'sku_clean': 'Elemento'}).copy()
                df_wc_pt_filtrado['Categoria'] = 'Producto Terminado'
            else:
                df_wc_pt_filtrado = pd.DataFrame()

            df_mrp = generar_mrp_global()
            if not df_mrp.empty and df_stock is not None:
                mapa_coste_rm = df_stock.drop_duplicates('sku cod').set_index('sku cod')['Coste_Unitario'].to_dict()
                rms_validos = set(df_bom[df_bom['sku cod'].astype(str).str.strip().isin(skus_validos)]['rm cod'].astype(str).str.strip().unique()) if (df_bom is not None and not df_bom.empty) else set()
                df_mrp['rm_clean'] = df_mrp['rm cod'].astype(str).str.strip()
                df_mrp_sub = df_mrp[df_mrp['rm_clean'].isin(rms_validos)].copy()
                df_mrp_sub['Coste_U'] = pd.to_numeric(df_mrp_sub['rm_clean'].map(mapa_coste_rm), errors='coerce').fillna(1.2)
                df_mrp_sub['WorkingCapital_GBP'] = df_mrp_sub['Stock_Final'] * df_mrp_sub['Coste_U'] * fx_eur_gbp * proporcion_ambito
                df_wc_mp_filtrado = df_mrp_sub[['Date', 'rm_clean', 'WorkingCapital_GBP']].rename(columns={'rm_clean': 'Elemento'}).copy()
                df_wc_mp_filtrado['Categoria'] = 'Materia Prima'
            else:
                df_wc_mp_filtrado = pd.DataFrame()

            df_wc_total = pd.concat([df_wc_pt_filtrado, df_wc_mp_filtrado], ignore_index=True) if (not df_wc_pt_filtrado.empty or not df_wc_mp_filtrado.empty) else pd.DataFrame()

            if df_stock is None or df_stock.empty or df_wc_total.empty:
                df_plot_pl['WC_PT_GBP'] = 0.0
                df_plot_pl['WC_MP_GBP'] = 0.0
                df_plot_pl['WC_Total_GBP'] = 0.0
            else:
                df_wc_pivot = df_wc_total.pivot_table(index='Date', columns='Categoria', values='WorkingCapital_GBP', aggfunc='sum').reset_index().fillna(0.0)
                if 'Producto Terminado' not in df_wc_pivot.columns: df_wc_pivot['Producto Terminado'] = 0.0
                if 'Materia Prima' not in df_wc_pivot.columns: df_wc_pivot['Materia Prima'] = 0.0
                df_plot_pl = pd.merge(
                    df_plot_pl,
                    df_wc_pivot.rename(columns={'Producto Terminado': 'WC_PT_GBP', 'Materia Prima': 'WC_MP_GBP'})[['Date', 'WC_PT_GBP', 'WC_MP_GBP']],
                    on='Date', how='left'
                ).fillna(0.0)
                df_plot_pl['WC_Total_GBP'] = df_plot_pl['WC_PT_GBP'] + df_plot_pl['WC_MP_GBP']

            if not df_plot_pl.empty:
                tot_rev_fcst = df_fcst_pl['Revenue_GBP'].sum()
                tot_mar_fcst = df_fcst_pl['Margin_GBP'].sum()
                mar_pct = (tot_mar_fcst / tot_rev_fcst * 100) if tot_rev_fcst > 0 else 0.0
                avg_wc = df_plot_pl[df_plot_pl['WC_Total_GBP'] > 0]['WC_Total_GBP'].mean() if (df_plot_pl['WC_Total_GBP'] > 0).any() else 0.0

                c1, c2, c3 = st.columns(3)
                c1.metric(f"{t['kpi_rev']} (Proyectado {horizonte}m)", f"£ {tot_rev_fcst:,.0f}")
                c2.metric(f"{t['kpi_mar']} (Proyectado {horizonte}m)", f"£ {tot_mar_fcst:,.0f} ({mar_pct:.1f}%)")
                c3.metric(t["kpi_wc"], f"£ {avg_wc:,.0f}")

                fig_pl = go.Figure()
                fig_pl.add_trace(go.Bar(x=df_hist_pl['Date'], y=df_hist_pl['Revenue_GBP'], name=tr('Revenue Histórico', 'Historical Revenue'), marker_color='#A0B2C6'))
                fig_pl.add_trace(go.Bar(x=df_fcst_pl['Date'], y=df_fcst_pl['Revenue_GBP'], name=tr('Revenue Proyectado', 'Projected Revenue'), marker_color='#1E3E5B'))
                fig_pl.add_trace(go.Scatter(x=df_plot_pl['Date'], y=df_plot_pl['Margin_GBP'], name=t["kpi_mar"], mode='lines+markers', line=dict(color='#88FFBB', width=4)))
                fig_pl.update_layout(**LAYOUT_STYLE, title=f"Revenue & Margin: {titulo_estrategico} (GBP)", yaxis_title="GBP (£)", hovermode="x unified")
                st.plotly_chart(fig_pl, use_container_width=True)

                if vista_wc == "Total (PT + MP)" and not df_wc_total.empty:
                    fig_wc = px.area(df_wc_total.groupby(['Date', 'Categoria'], as_index=False)['WorkingCapital_GBP'].sum(), x='Date', y='WorkingCapital_GBP', color='Categoria', title=f"Working Capital: {titulo_estrategico}", color_discrete_sequence=['#88FFBB', '#1E3E5B'])
                    st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)
                elif vista_wc == "Producto Terminado (PT)" and not df_wc_pt_filtrado.empty:
                    top_pt_wc = df_wc_pt_filtrado.groupby('Elemento')['WorkingCapital_GBP'].sum().nlargest(10).index
                    fig_wc = px.area(df_wc_pt_filtrado[df_wc_pt_filtrado['Elemento'].isin(top_pt_wc)], x='Date', y='WorkingCapital_GBP', color='Elemento', title=f"WC Top 10 (PT): {titulo_estrategico}")
                    st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)
                elif vista_wc == "Materia Prima (MP)" and not df_wc_mp_filtrado.empty:
                    top_mp_wc = df_wc_mp_filtrado.groupby('Elemento')['WorkingCapital_GBP'].sum().nlargest(10).index
                    fig_wc = px.area(df_wc_mp_filtrado[df_wc_mp_filtrado['Elemento'].isin(top_mp_wc)], x='Date', y='WorkingCapital_GBP', color='Elemento', title=f"WC Top 10 (MP): {titulo_estrategico}")
                    st.plotly_chart(fig_wc.update_layout(**LAYOUT_STYLE, yaxis_title="GBP (£)"), use_container_width=True)

                df_tbl_pl = df_plot_pl[['Date', 'Tipo_Periodo', 'Revenue_GBP', 'Margin_GBP', 'WC_PT_GBP', 'WC_MP_GBP', 'WC_Total_GBP']].copy()
                df_tbl_pl['Date'] = pd.to_datetime(df_tbl_pl['Date']).dt.strftime('%Y-%m')
                st.dataframe(
                    df_tbl_pl.rename(columns={"Revenue_GBP": "Revenue (£)", "Margin_GBP": "Margin (£)", "WC_PT_GBP": "WC PT (£)", "WC_MP_GBP": "WC MP (£)", "WC_Total_GBP": "Total WC (£)"})
                    .style.format({c: "£ {:,.0f}" for c in ["Revenue (£)", "Margin (£)", "WC PT (£)", "WC MP (£)", "Total WC (£)"]}),
                    use_container_width=True,
                    hide_index=True
                )

# ==========================================
# MODULO 6: EJECUCIÓN ERP + S&OE (MOQ & LOTES MÚLTIPLOS) + MASTER PACK EXCEL
# ==========================================
if modulo_activo == t["tab6"]:
    if "tab6" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Ejecución ERP.", "🔒 You do not have permission to access the ERP Execution module."))
    else:
        st.subheader(tr("🚀 Plan de Ejecución Inmediata & S&OE (Lanzamientos al ERP con MOQ / Lotes)", "🚀 Immediate ERP Execution & S&OE Plan (Order Releases with MOQ / Lot Multiples)"))
        df_mps_all = generar_mps_df_2d()
        mrp_exec = generar_mrp_global()

        if df_mps_all.empty:
            st.warning(tr("⚠️ Carga primero el histórico de ventas para calcular el plan de ejecución.", "⚠️ Upload sales history first to calculate the execution plan."))
        else:
            df_mps_all['Date'] = pd.to_datetime(df_mps_all['Date'])
            fechas_disp = sorted(df_mps_all['Date'].unique())
            hoy_mes = pd.Timestamp.today().replace(day=1)
            mes_objetivo = hoy_mes if hoy_mes in fechas_disp else fechas_disp[0]
            base_date = pd.to_datetime(mes_objetivo)

            st.info(f"📅 **{tr('Mes Objetivo de Ejecución (Nuevos Lanzamientos)', 'Target Execution Month (New Releases)')}:** {base_date.strftime('%Y-%m')}")

            with st.expander(tr("⚡ Reglas de Loteado Operativo S&OE (Pedido Mínimo MOQ y Lote Múltiplo Industrial/Logístico)", "⚡ S&OE Operational Lot Sizing Rules (MOQ & Industrial/Logistical Lot Multiples)"), expanded=True):
                soe_c1, soe_c2, soe_c3, soe_c4 = st.columns(4)
                with soe_c1:
                    moq_pt_kg = st.number_input(tr("🏭 MOQ Fabricación PT (Kg):", "🏭 FG Production MOQ (Kg):"), min_value=0, max_value=100000, value=2000, step=500)
                with soe_c2:
                    mult_pt_kg = st.number_input(tr("🔄 Lote Múltiplo PT (Mezcladora Kg):", "🔄 FG Batch Multiple (Mixer Kg):"), min_value=1, max_value=50000, value=1000, step=500)
                with soe_c3:
                    moq_mp_kg = st.number_input(tr("🛒 MOQ Compra Proveedor MP (Kg):", "🛒 RM Supplier PO MOQ (Kg):"), min_value=0, max_value=100000, value=5000, step=1000)
                with soe_c4:
                    mult_mp_kg = st.number_input(tr("🚚 Lote Múltiplo MP (Palet/Camión Kg):", "🚚 RM Lot Multiple (Pallet/Truck Kg):"), min_value=1, max_value=50000, value=1000, step=500)

            st.markdown(f"### {tr('🏭 NUEVAS Órdenes de Fabricación a lanzar en el ERP', '🏭 NEW Production Orders to Release in ERP')}")
            df_fab_lanzar = df_mps_all[(df_mps_all['Date'] == mes_objetivo) & (df_mps_all['Entradas_Netas'] > 0)].copy()

            if df_fab_lanzar.empty:
                st.success(tr("✅ Todo cubierto. No necesitas lanzar nuevas órdenes de PT para el Mes 1.", "✅ All covered. No new FG production orders needed for Month 1."))
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
                df_fab_lanzar['Orden_Redondeada_SOE'] = aplicar_moq_y_lote_multiplo(df_fab_lanzar['Entradas_Netas'], moq_pt_kg, mult_pt_kg)
                df_fab_lanzar['Lotes_Mezcladora'] = np.ceil(df_fab_lanzar['Orden_Redondeada_SOE'] / max(1.0, float(mult_pt_kg))).astype(int)

                cols_fab = ['sku cod', 'sku desc', 'Fecha_Lanzamiento', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Orden_Redondeada_SOE', 'Lotes_Mezcladora', 'Stock_Final', 'DOH']
                df_fab_lanzar = df_fab_lanzar[cols_fab].sort_values(by=['Fecha_Lanzamiento', 'Orden_Redondeada_SOE'], ascending=[True, False]).reset_index(drop=True)
                
                st.dataframe(
                    df_fab_lanzar.head(200).style.format({
                        'Salidas_Brutas': '{:,.0f} Kg',
                        'Stock_Inicial': '{:,.0f} Kg',
                        'Recepciones_ERP': '{:,.0f} Kg',
                        'Entradas_Netas': '{:,.0f} Kg',
                        'Orden_Redondeada_SOE': '{:,.0f} Kg',
                        'Lotes_Mezcladora': '{:,.0f} batches',
                        'Stock_Final': '{:,.0f} Kg',
                        'DOH': '{:.0f}'
                    }).map(estilo_doh, subset=['DOH']),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown(f"### {tr('🛒 NUEVOS Pedidos de Compra a lanzar a Proveedores', '🛒 NEW Purchase Orders (POs) to Release to Suppliers')}")
            df_cmp_lanzar = pd.DataFrame()
            if mrp_exec is None or mrp_exec.empty:
                st.info(tr("👈 Carga el archivo de BOM y Stock para calcular los lanzamientos de compra.", "👈 Upload BOM and Stock files to calculate PO releases."))
            else:
                col_lanz = 'Lanzamiento_Pedidos' if 'Lanzamiento_Pedidos' in mrp_exec.columns else 'Entradas_Netas'
                df_cmp_lanzar = mrp_exec[(mrp_exec['Date'] == mes_objetivo) & (mrp_exec[col_lanz] > 0)].copy()

                if df_cmp_lanzar.empty:
                    st.success(tr("✅ Todo cubierto. No necesitas emitir nuevos pedidos de Materia Prima para el Mes 1.", "✅ All covered. No new Raw Material POs needed for Month 1."))
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
                    df_cmp_lanzar['PO_Redondeada_SOE'] = aplicar_moq_y_lote_multiplo(df_cmp_lanzar[col_lanz], moq_mp_kg, mult_mp_kg)
                    df_cmp_lanzar['Lotes_Logisticos'] = np.ceil(df_cmp_lanzar['PO_Redondeada_SOE'] / max(1.0, float(mult_mp_kg))).astype(int)

                    cols_cmp = [c for c in ['rm cod', 'rm desc', 'Fecha_Lanzamiento', 'LT_Meses', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Lanzamiento_Pedidos', 'PO_Redondeada_SOE', 'Lotes_Logisticos', 'Stock_Final', 'DOH'] if c in df_cmp_lanzar.columns]
                    df_cmp_lanzar = df_cmp_lanzar[cols_cmp].sort_values(by=['Fecha_Lanzamiento', 'PO_Redondeada_SOE'], ascending=[True, False]).reset_index(drop=True)
                    
                    fmt_dict = {c: '{:,.0f} Kg' for c in ['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Lanzamiento_Pedidos', 'PO_Redondeada_SOE', 'Stock_Final'] if c in df_cmp_lanzar.columns}
                    if 'Lotes_Logisticos' in df_cmp_lanzar.columns:
                        fmt_dict['Lotes_Logisticos'] = '{:,.0f} lots'
                    if 'DOH' in df_cmp_lanzar.columns:
                        fmt_dict['DOH'] = '{:.0f}'
                    
                    styler_cmp = df_cmp_lanzar.head(200).style.format(fmt_dict)
                    if 'DOH' in df_cmp_lanzar.columns:
                        styler_cmp = styler_cmp.map(estilo_doh, subset=['DOH'])
                        
                    st.dataframe(styler_cmp, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown(f"### {tr('📦 Exportar Master Pack S&OP Corporativo (Multi-Pestaña)', '📦 Export Corporate S&OP Master Pack (Multi-Tab Excel)')}")
            if st.button(tr("⚙️ Preparar Libro Excel Master Pack S&OP", "⚙️ Prepare S&OP Master Pack Excel Workbook")):
                with st.spinner(tr("Generando Master Pack Excel...", "Generating Master Pack Excel...")):
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
                        label=tr("📥 Descargar Master Pack S&OP Completo (.xlsx)", "📥 Download Full S&OP Master Pack (.xlsx)"),
                        data=buf_master.getvalue(),
                        file_name=f"Master_Pack_SOP_{base_date.strftime('%Y_%m')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )

# ==========================================
# MODULO 7: ABC / XYZ + OPTIMIZADOR MTO/MTS + NOVEDAD 3 FILTRO CORREGIDO
# ==========================================
if modulo_activo == t["tab7"]:
    if "tab7" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder a la segmentación ABC/XYZ.", "🔒 You do not have permission to access ABC/XYZ segmentation."))
    else:
        st.subheader(tr("🔠 Segmentación Estratégica ABC / XYZ", "🔠 Strategic ABC / XYZ Segmentation"))
        
        if df_abcxyz_global is not None and not df_abcxyz_global.empty:
            df_abcxyz_show = df_abcxyz_global.copy()
            if 'sku desc' not in df_abcxyz_show.columns:
                df_abcxyz_show['sku desc'] = df_abcxyz_show['sku cod'].map(dict_sku_desc).fillna(df_abcxyz_show['sku cod'].astype(str))
            
            if dict_margin:
                st.markdown(f"### {tr('🫧 Matriz de Riesgo vs Rentabilidad', '🫧 Risk vs. Profitability Matrix')}")
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
                        labels={
                            "CV": tr("Riesgo / Volatilidad (CV)", "Risk / Volatility (CV)"),
                            "Margen Unitario": tr("Margen Bruto Unitario (£)", "Unit Gross Margin (£)"),
                            "volume": tr("Volumen (Kg)", "Volume (Kg)")
                        },
                        size_max=45, color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig_bubble.add_vline(x=0.5, line_width=1, line_dash="dash", line_color="gray", annotation_text="X | Y")
                    fig_bubble.add_vline(x=1.0, line_width=1, line_dash="dash", line_color="gray", annotation_text="Y | Z")
                    margen_medio = float(df_plot['Margen Unitario'].median())
                    fig_bubble.add_hline(y=margen_medio, line_width=1, line_dash="dash", line_color="gray", annotation_text=tr("Margen Medio", "Median Margin"))
                    fig_bubble.update_layout(plot_bgcolor='white', height=500, margin=dict(l=20, r=20, t=30, b=20))
                    fig_bubble.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                    fig_bubble.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                    
                    st.plotly_chart(fig_bubble, use_container_width=True)
                    st.info(tr(
                        "👈 **Cuadrante Superior Izquierdo:** Estrellas (Alto Margen, Demanda Estable). 👉 **Cuadrante Inferior Derecho:** Tóxicos (Bajo Margen, Demanda Errática).",
                        "👈 **Top-Left Quadrant:** Stars (High Margin, Stable Demand). 👉 **Bottom-Right Quadrant:** Toxic SKUs (Low Margin, Erratic Demand)."
                    ))
                    st.divider()

            col_mat1, col_mat2 = st.columns([1, 2])
            with col_mat1:
                st.markdown(f"#### {tr('Distribución de SKUs', 'SKU Distribution')}")
                resumen_matriz = df_abcxyz_show.groupby(['ABC', 'XYZ'])['sku cod'].count().unstack().fillna(0).astype(int)
                resumen_matriz = resumen_matriz.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0)
                st.dataframe(resumen_matriz.style.background_gradient(cmap='Blues'), use_container_width=True)
                
            with col_mat2:
                st.markdown(f"#### {tr('Detalle de Clasificación', 'Classification Detail')}")
                filtro_clase = st.multiselect(tr("Filtrar por Clase (ej. AX, CZ):", "Filter by Class (e.g. AX, CZ):"), sorted(df_abcxyz_show['Clase'].unique()))
                df_show_abc = df_abcxyz_show if not filtro_clase else df_abcxyz_show[df_abcxyz_show['Clase'].isin(filtro_clase)]

                st.dataframe(
                    df_show_abc[['sku cod', 'sku desc', 'Clase', 'volume', 'CV', 'Margen Unitario']].head(250)
                    .rename(columns={'volume': tr('Volumen', 'Volume'), 'CV': tr('Volatilidad (CV)', 'Volatility (CV)')})
                    .style.format({tr('Volumen', 'Volume'): "{:,.0f}", tr('Volatilidad (CV)', 'Volatility (CV)'): "{:.2f}", "Margen Unitario": "{:.2f}"}),
                    use_container_width=True
                )

            st.divider()
            st.markdown(f"### {tr('💡 Optimizador Estratégico de Inventario (Racionalización MTS vs. MTO & Stock de Seguridad Científico)', '💡 Strategic Inventory Optimizer (MTS vs. MTO & Scientific Safety Stock by Service Level)')}")
            if df_stock is None or df_stock.empty:
                st.info(tr("👈 Sube el archivo '3. Stock Actual' para auditar la política MTO/MTS y el Stock de Seguridad Científico.", "👈 Upload '3. Current Inventory' to audit MTO/MTS policy and Scientific Safety Stock."))
            else:
                csl_c1, csl_c2, csl_c3 = st.columns(3)
                mapa_z = {85: 1.04, 90: 1.28, 92: 1.41, 95: 1.65, 97: 1.88, 98: 2.05, 99: 2.33}
                with csl_c1:
                    csl_a = st.select_slider(tr("🎯 Nivel Servicio Clase A (CSL %):", "🎯 Class A Service Level (CSL %):"), options=[90, 92, 95, 97, 98, 99], value=98)
                with csl_c2:
                    csl_b = st.select_slider(tr("🎯 Nivel Servicio Clase B (CSL %):", "🎯 Class B Service Level (CSL %):"), options=[85, 90, 92, 95, 97, 98], value=95)
                with csl_c3:
                    csl_c = st.select_slider(tr("🎯 Nivel Servicio Clase C (CSL %):", "🎯 Class C Service Level (CSL %):"), options=[85, 90, 92, 95], value=90)

                df_stk_clean = df_stock.copy()
                df_stk_clean['sku cod'] = df_stk_clean['sku cod'].astype(str).str.strip()
                df_abcxyz_show['sku cod'] = df_abcxyz_show['sku cod'].astype(str).str.strip()

                df_audit = pd.merge(
                    df_abcxyz_show[['sku cod', 'sku desc', 'ABC', 'XYZ', 'Clase', 'volume', 'mean', 'std', 'CV', 'Margen Unitario']],
                    df_stk_clean[['sku cod', 'stock_disponible', 'Cobertura_Meses', 'LT_Meses', 'Categoria', 'Coste_Unitario']].drop_duplicates(subset=['sku cod']),
                    on='sku cod',
                    how='inner'
                )

                if df_audit.empty:
                    st.info(tr("No hay cruce entre los SKUs del histórico de ventas y la tabla de Stock Actual.", "No matching SKUs between sales history and Current Inventory."))
                else:
                    df_audit['Categoria_Actual'] = df_audit['Categoria'].astype(str).str.strip().str.upper()
                    df_audit['Coste_Unitario'] = pd.to_numeric(df_audit['Coste_Unitario'], errors='coerce').fillna(0.0)
                    df_audit['stock_disponible'] = pd.to_numeric(df_audit['stock_disponible'], errors='coerce').fillna(0.0)
                    df_audit['LT_Meses'] = pd.to_numeric(df_audit['LT_Meses'], errors='coerce').fillna(1.0).clip(lower=0.25)

                    condiciones_pol = [
                        df_audit['Clase'].isin(['AX', 'AY', 'BX']),
                        df_audit['Clase'].isin(['CZ', 'BZ', 'CY', 'CX'])
                    ]
                    opciones_pol = ['MTS', 'MTO']
                    df_audit['Politica_Recomendada'] = np.select(condiciones_pol, opciones_pol, default='MTS (Min Cov)')

                    df_audit['Z_Factor'] = np.where(
                        df_audit['ABC'] == 'A', mapa_z[csl_a],
                        np.where(df_audit['ABC'] == 'B', mapa_z[csl_b], mapa_z[csl_c])
                    )
                    df_audit['SS_Cientifico_Kg'] = np.where(
                        df_audit['Politica_Recomendada'] == 'MTO',
                        0.0,
                        df_audit['Z_Factor'] * pd.to_numeric(df_audit['std'], errors='coerce').fillna(0.0) * np.sqrt(df_audit['LT_Meses'])
                    ).round(0)

                    df_audit['WC_Actual_GBP'] = df_audit['stock_disponible'] * df_audit['Coste_Unitario'] * fx_eur_gbp
                    df_audit['WC_Optimo_Cientifico_GBP'] = df_audit['SS_Cientifico_Kg'] * df_audit['Coste_Unitario'] * fx_eur_gbp
                    df_audit['WC_Liberable_GBP'] = np.maximum(0.0, df_audit['WC_Actual_GBP'] - df_audit['WC_Optimo_Cientifico_GBP'])

                    lbl_mts_mto = tr('🔴 Cambiar MTS → MTO (Liberar Caja)', '🔴 Switch MTS → MTO (Release Cash)')
                    lbl_mto_mts = tr('🟠 Pasar MTO → MTS (Proteger Servicio)', '🟠 Switch MTO → MTS (Protect Service)')
                    lbl_exceso_ss = tr('🟡 Exceso Stock (>SS Científico)', '🟡 Excess Stock (>Scientific SS)')
                    lbl_ok = tr('🟢 Alineado', '🟢 Aligned')

                    df_audit['Estado_Auditoria'] = np.where(
                        (df_audit['Politica_Recomendada'] == 'MTO') & (df_audit['Categoria_Actual'] == 'MTS'),
                        lbl_mts_mto,
                        np.where(
                            (df_audit['Politica_Recomendada'] == 'MTS') & (df_audit['Categoria_Actual'] == 'MTO'),
                            lbl_mto_mts,
                            np.where(
                                df_audit['WC_Liberable_GBP'] > 100.0,
                                lbl_exceso_ss,
                                lbl_ok
                            )
                        )
                    )

                    ca1, ca2, ca3, ca4 = st.columns(4)
                    ca1.metric(tr("SKUs Auditados", "Audited SKUs"), f"{len(df_audit)}")
                    ca2.metric(tr("WC Actual en Stock (£)", "Current Stock WC (£)"), f"£ {df_audit['WC_Actual_GBP'].sum():,.0f}")
                    ca3.metric(tr("WC Óptimo Científico (£)", "Optimal Scientific WC (£)"), f"£ {df_audit['WC_Optimo_Cientifico_GBP'].sum():,.0f}")
                    ca4.metric(tr("Potencial Total Liberación WC (£)", "Total Releasable WC (£)"), f"£ {df_audit['WC_Liberable_GBP'].sum():,.0f}")

                    solo_alertas = st.checkbox(
                        tr("🔍 Mostrar solo SKUs con exceso de stock o cambio MTS ↔ MTO", "🔍 Show only SKUs with excess stock or policy change"),
                        value=False,
                        key="chk_solo_alertas_abc_v2"
                    )
                    if solo_alertas:
                        df_mostrar_audit = df_audit[df_audit['Estado_Auditoria'] != lbl_ok].copy()
                        st.caption(tr(
                            f"🔎 Filtro activo: Mostrando **{len(df_mostrar_audit)}** de {len(df_audit)} SKUs (excluidos {len(df_audit) - len(df_mostrar_audit)} SKUs en estado '🟢 Alineado').",
                            f"🔎 Active filter: Showing **{len(df_mostrar_audit)}** of {len(df_audit)} SKUs (excluded {len(df_audit) - len(df_mostrar_audit)} '🟢 Aligned' SKUs)."
                        ))
                    else:
                        df_mostrar_audit = df_audit.copy()

                    df_mostrar_audit = df_mostrar_audit.sort_values(by='WC_Liberable_GBP', ascending=False).reset_index(drop=True)

                    if df_mostrar_audit.empty:
                        st.success(tr("✅ Todos los SKUs están 100% alineados en política MTO/MTS y sin exceso de stock sobre el SS Científico.", "✅ All SKUs are 100% aligned in MTO/MTS policy with no excess stock above Scientific SS."))
                    else:
                        st.dataframe(
                            df_mostrar_audit[[
                                'sku cod', 'sku desc', 'Clase', 'CV', 'Categoria_Actual',
                                'Politica_Recomendada', 'Estado_Auditoria', 'stock_disponible',
                                'SS_Cientifico_Kg', 'WC_Actual_GBP', 'WC_Optimo_Cientifico_GBP', 'WC_Liberable_GBP'
                            ]].head(250).rename(columns={
                                'Categoria_Actual': tr('Política Actual', 'Current Policy'),
                                'Politica_Recomendada': tr('Política Sugerida', 'Suggested Policy'),
                                'Estado_Auditoria': tr('Diagnóstico S&OP', 'S&OP Diagnosis'),
                                'stock_disponible': tr('Stock Actual (Kg)', 'Current Stock (Kg)'),
                                'SS_Cientifico_Kg': tr('SS Científico CSL (Kg)', 'Scientific SS (Kg)'),
                                'WC_Actual_GBP': 'WC Actual (£)',
                                'WC_Optimo_Cientifico_GBP': 'WC Óptimo (£)',
                                'WC_Liberable_GBP': tr('Ahorro WC Potencial (£)', 'Potential WC Savings (£)')
                            }).style.format({
                                'CV': '{:.2f}',
                                tr('Stock Actual (Kg)', 'Current Stock (Kg)'): '{:,.0f} Kg',
                                tr('SS Científico CSL (Kg)', 'Scientific SS (Kg)'): '{:,.0f} Kg',
                                'WC Actual (£)': '£ {:,.0f}',
                                'WC Óptimo (£)': '£ {:,.0f}',
                                tr('Ahorro WC Potencial (£)', 'Potential WC Savings (£)'): '£ {:,.0f}'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )

# ==========================================
# MODULO 8: EXCEPCIONES (MOTOR 2D)
# ==========================================
if modulo_activo == t["tab8"]:
    if "tab8" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Panel de Excepciones.", "🔒 You do not have permission to access the Exceptions Panel."))
    else:
        st.subheader(tr("🚨 Panel de Excepciones (Management by Exception)", "🚨 Exceptions Panel (Management by Exception)"))
        df_mps_all = generar_mps_df_2d()
        mrp_exc = generar_mrp_global()

        if df_mps_all.empty:
            st.warning(tr("⚠️ Carga primero el histórico de ventas.", "⚠️ Upload sales history first."))
        else:
            df_mps_all['Date'] = pd.to_datetime(df_mps_all['Date'])
            fechas_disp = sorted(df_mps_all['Date'].unique())
            hoy_mes = pd.Timestamp.today().replace(day=1)
            mes_m1 = hoy_mes if hoy_mes in fechas_disp else fechas_disp[0]

            col_pt, col_mp = st.columns(2)

            with col_pt:
                st.markdown(f"### {tr('📦 Producto Terminado (PT)', '📦 Finished Goods (FG)')}")
                df_pt_m1 = df_mps_all[
                    (df_mps_all['Date'] == mes_m1) &
                    ((df_mps_all['DOH'] < 15) | (df_mps_all['DOH'] > 60))
                ].copy()

                if df_pt_m1.empty:
                    st.success(tr("✅ Sin alertas para M1.", "✅ No alerts for M1."))
                else:
                    df_pt_m1['Tipo_Alerta'] = np.where(
                        df_pt_m1['DOH'] < 15,
                        tr('🔴 Riesgo Rotura (<15d)', '🔴 Stockout Risk (<15d)'),
                        tr('🟠 Sobrestock / Exceso ERP (>60d)', '🟠 Overstock / Excess ERP (>60d)')
                    )
                    df_pt_m1['Accion_Sugerida'] = np.where(
                        df_pt_m1['DOH'] < 15,
                        tr('⚡ Priorizar / Subir Cobertura', '⚡ Prioritize / Increase Coverage'),
                        np.where(df_pt_m1['Recepciones_ERP'] > df_pt_m1['Salidas_Brutas'], tr('✂️ Posponer Orden ERP', '✂️ Defer ERP Order'), tr('📉 Drenar Stock', '📉 Drain Inventory'))
                    )
                    cols_show_pt = ['sku cod', 'sku desc', 'Tipo_Alerta', 'DOH', 'Stock_Final', 'Recepciones_ERP', 'Accion_Sugerida']
                    df_pt_m1 = df_pt_m1[cols_show_pt].sort_values(by='DOH', ascending=True).reset_index(drop=True)

                    st.dataframe(
                        df_pt_m1.head(150).style.format({
                            'DOH': '{:.0f} d',
                            'Stock_Final': '{:,.0f} Kg',
                            'Recepciones_ERP': '{:,.0f} Kg'
                        }).map(estilo_doh, subset=['DOH']),
                        use_container_width=True,
                        hide_index=True
                    )

            with col_mp:
                st.markdown(f"### {tr('🧩 Materias Primas (MP)', '🧩 Raw Materials (RM)')}")
                if mrp_exc is None or mrp_exc.empty:
                    st.info(tr("👈 Carga el BOM y Stock para evaluar alertas de MP.", "👈 Upload BOM and Stock to evaluate RM alerts."))
                else:
                    mrp_exc['Date'] = pd.to_datetime(mrp_exc['Date'])
                    df_mp_m1 = mrp_exc[
                        (mrp_exc['Date'] == mes_m1) &
                        ((mrp_exc['DOH'] < 15) | (mrp_exc['DOH'] > 60))
                    ].copy()

                    if df_mp_m1.empty:
                        st.success(tr("✅ Sin alertas para M1.", "✅ No alerts for M1."))
                    else:
                        df_mp_m1['Tipo_Alerta'] = np.where(
                            df_mp_m1['DOH'] < 15,
                            tr('🔴 Riesgo Rotura (<15d)', '🔴 Stockout Risk (<15d)'),
                            tr('🟠 Exceso PO / Sobrestock (>60d)', '🟠 Excess PO / Overstock (>60d)')
                        )
                        df_mp_m1['Accion_Sugerida'] = np.where(
                            df_mp_m1['DOH'] < 15,
                            tr('⚡ Urgencia a Proveedor', '⚡ Expedite Supplier PO'),
                            np.where(df_mp_m1['Recepciones_ERP'] > df_mp_m1['Salidas_Brutas'], tr('✂️ Reprogramar PO ERP', '✂️ Reschedule ERP PO'), tr('📉 Reducir Lote', '📉 Reduce Lot Size'))
                        )
                        cols_show_mp = ['rm cod', 'rm desc', 'Tipo_Alerta', 'DOH', 'Stock_Final', 'Recepciones_ERP', 'Accion_Sugerida']
                        df_mp_m1 = df_mp_m1[cols_show_mp].sort_values(by='DOH', ascending=True).reset_index(drop=True)

                        st.dataframe(
                            df_mp_m1.head(150).style.format({
                                'DOH': '{:.0f} d',
                                'Stock_Final': '{:,.0f} Kg',
                                'Recepciones_ERP': '{:,.0f} Kg'
                            }).map(estilo_doh, subset=['DOH']),
                            use_container_width=True,
                            hide_index=True
                        )

# ==========================================
# MODULO 9: WHAT-IF (CONECTADO AL SHARE DE FILTROS Y DATASET_SIGNATURE)
# ==========================================
if modulo_activo == t["tab9"]:
    if "tab9" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Simulador What-If.", "🔒 You do not have permission to access the What-If Simulator."))
    else:
        st.subheader(tr("🔀 Simulador de Escenarios (What-If)", "🔀 What-If Scenario Simulator"))
        if not dict_price:
            st.warning("⚠️ No 'revenue' or 'margin' columns in history.")
        else:
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                shock_vol = st.slider(tr("📈 Variación Volumen (%)", "📈 Volume Shock (%)"), -50, 50, 0, step=5)
            with col_w2:
                shock_precio = st.slider(tr("🏷️ Variación Precios (%)", "🏷️ Sales Price Shock (%)"), -30, 30, 0, step=5)
            with col_w3:
                shock_coste = st.slider(tr("💸 Variación Costes MP (%)", "💸 RM / COGS Shock (%)"), -30, 50, 0, step=5)
            st.divider()
            
            if not df_final.empty:
                df_base, df_sim = motor_simulador_whatif(
                    df_final, dict_price, dict_margin, dict_currency,
                    fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp,
                    horizonte, modelo_fcst_sel, shock_vol, shock_precio, shock_coste,
                    sig=DATASET_SIGNATURE
                )
                
                tot_rev_base = df_base['Revenue'].sum() if not df_base.empty else 0
                tot_mar_base = df_base['Margin'].sum() if not df_base.empty else 0
                tot_rev_sim = df_sim['Revenue'].sum() if not df_sim.empty else 0
                tot_mar_sim = df_sim['Margin'].sum() if not df_sim.empty else 0
                
                col_r1, col_r2, col_r3 = st.columns(3)
                delta_rev = tot_rev_sim - tot_rev_base
                col_r1.metric(tr("Revenue (Simulado)", "Revenue (Simulated)"), f"£ {tot_rev_sim:,.0f}", f"{delta_rev:,.0f} £ vs Base")
                delta_mar = tot_mar_sim - tot_mar_base
                col_r2.metric(tr("Margen (Simulado)", "Gross Margin (Simulated)"), f"£ {tot_mar_sim:,.0f}", f"{delta_mar:,.0f} £ vs Base")
                mar_pct_base = (tot_mar_base / tot_rev_base * 100) if tot_rev_base > 0 else 0
                mar_pct_sim = (tot_mar_sim / tot_rev_sim * 100) if tot_rev_sim > 0 else 0
                delta_pct = mar_pct_sim - mar_pct_base
                col_r3.metric(tr("% Margen Bruto (Simulado)", "Gross Margin % (Simulated)"), f"{mar_pct_sim:.1f}%", f"{delta_pct:.1f}% vs Base")
                
                fig_wi = go.Figure(data=[
                    go.Bar(name='Baseline', x=['Revenue', 'Gross Margin'], y=[tot_rev_base, tot_mar_base], marker_color='#A0B2C6'),
                    go.Bar(name='What-If', x=['Revenue', 'Gross Margin'], y=[tot_rev_sim, tot_mar_sim], marker_color='#1E3E5B')
                ])
                fig_wi.update_layout(**LAYOUT_STYLE, barmode='group', title=tr("Impacto Financiero (GBP)", "Financial Impact (GBP)"), yaxis_title="GBP (£)")
                st.plotly_chart(fig_wi, use_container_width=True)
                
                if FPDF is not None:
                    st.divider()
                    st.markdown(f"### {tr('📥 Exportar Informe Directivo', '📥 Export Executive Report')}")
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
                    st.download_button(label=tr("📄 Descargar Resumen PDF", "📄 Download PDF Summary"), data=bytes(pdf.output()), file_name="SOP_WhatIf.pdf", mime="application/pdf", type="primary")

# ==========================================
# MODULO 10: DASHBOARD EJECUTIVO + TRIPLE BUDGET + WATERFALL + RADAR CHURN & CONCENTRACIÓN + PDF DECK
# ==========================================
if modulo_activo == t["tab10"]:
    if "tab10" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Dashboard de KPIs.", "🔒 You do not have permission to access the Executive Dashboard."))
    else:
        st.subheader(tr("📊 Dashboard Ejecutivo y KPIs Globales", "📊 Executive Dashboard & Global KPIs"))
        if df_final is not None and not df_final.empty and dict_price:
            with st.spinner(tr("Consolidando datos filtrados...", "Consolidating filtered data...")):
                total_skus = df_final['sku cod'].nunique()
                df_clientes = df_final.groupby('País')['customer cod'].nunique().reset_index()
                df_clientes.columns = [tr('País', 'Country'), tr('Clientes Activos', 'Active Customers')]
                total_clientes = df_clientes[tr('Clientes Activos', 'Active Customers')].sum()
                
                st.markdown(f"#### {tr('🌍 Estructura Comercial (Datos Filtrados)', '🌍 Commercial Structure (Filtered Scope)')}")
                col_e1, col_e2, col_e3 = st.columns(3)
                col_e1.metric(tr("SKUs Activos (PT)", "Active SKUs (FG)"), f"{total_skus}")
                col_e2.metric(tr("Total Clientes", "Total Customers"), f"{total_clientes}")
                with col_e3:
                    st.dataframe(df_clientes.style.format({tr('Clientes Activos', 'Active Customers'): "{:,.0f}"}), use_container_width=True, hide_index=True)
                
                max_date_global = df['Date'].max()
                min_date_12m = max_date_global - pd.DateOffset(months=11)
                
                df_12m = df_final[(df_final['Date'] >= min_date_12m) & (df_final['Date'] <= max_date_global)].copy()
                vol_12m_hist = df_12m['volume'].sum() if not df_12m.empty else 0.0
                rev_12m_hist = df_12m['Rev_GBP'].sum() if not df_12m.empty else 0.0
                mar_12m_hist = df_12m['Mar_GBP'].sum() if not df_12m.empty else 0.0
                
                vol_12m_fcst, rev_12m_fcst, mar_12m_fcst, puente_data = motor_kpis_n12m_y_puente(
                    df_final, st.session_state.get('df_ajustes', pd.DataFrame()), df_abcxyz_global,
                    dict_price, dict_margin, dict_currency,
                    fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp,
                    max_date_global, modelo_fcst_sel, horiz=12,
                    sig=DATASET_SIGNATURE
                )
                
                st.divider()
                st.markdown(f"#### {tr('🎯 Fiabilidad del Modelo de Demanda (Forecast Performance - L12M)', '🎯 Demand Model Reliability (Forecast Performance - L12M)')}")
                fa_val, bias_val, wape_val = calcular_kpis_forecast(df_final, usar_limpieza_outliers)
                
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("Forecast Accuracy (FA)", f"{fa_val:.1f}%", tr("Acierto global ponderado", "Weighted global accuracy"))
                col_k2.metric("Forecast Bias", f"{bias_val:+.1f}%", tr("+ = Infrademanda / - = Sobredemanda", "+ = Under-forecast / - = Over-forecast"))
                col_k3.metric("WAPE (Error Absoluto)", f"{wape_val:.1f}%", tr("Desviación porcentual neta", "Weighted Absolute Percentage Error"))
                
                st.divider()
                st.subheader(tr("🎯 Control Presupuestario S&OP vs. Escenarios (Budget, 3+9, 6+6, 9+3)", "🎯 S&OP Budget Control vs. Scenarios (Budget, 3+9, 6+6, 9+3)"))
                b_col1, b_col2 = st.columns([1, 3])
                with b_col1:
                    escenario_sel = st.selectbox(
                        "Tipo de Escenario (Target N12M):", 
                        ["Budget Original (0+12)", "Forecast 3+9", "Forecast 6+6", "Forecast 9+3"]
                    )
                    
                    if 'df_budget' in locals() and df_budget is not None and not df_budget.empty:
                        df_b_esc = df_budget[df_budget['Escenario'] == escenario_sel].copy()
                        if cat_sel != "TODAS": df_b_esc = df_b_esc[df_b_esc['Categoria_Producto'] == cat_sel]
                        if cliente_sel != "TODOS": df_b_esc = df_b_esc[df_b_esc['customer cod'] == cliente_sel]
                        
                        vol_budget_n12 = df_b_esc['Volume_Kg'].sum()
                        rev_budget_n12 = df_b_esc['Revenue_GBP'].sum()
                        mar_budget_n12 = df_b_esc['Margin_GBP'].sum()
                        budget_growth_pct = ((vol_budget_n12 - vol_12m_hist) / vol_12m_hist * 100) if vol_12m_hist > 0 else 0.0
                        st.success(f"✅ Leyendo de archivo externo: {escenario_sel}")
                    else:
                        st.info("Sin archivo de Budget. Simulando crecimiento %")
                        mapa_crecimientos = {"Budget Original (0+12)": 6.0, "Forecast 3+9": 4.5, "Forecast 6+6": 2.0, "Forecast 9+3": -1.5}
                        budget_growth_pct = st.number_input(tr(f"Crecimiento Asignado al {escenario_sel} (%):", f"Target Growth for {escenario_sel} (%):"), value=mapa_crecimientos[escenario_sel], step=0.5)
                        vol_budget_n12 = vol_12m_hist * (1.0 + budget_growth_pct / 100.0)
                        rev_budget_n12 = rev_12m_hist * (1.0 + budget_growth_pct / 100.0)
                        mar_budget_n12 = mar_12m_hist * (1.0 + budget_growth_pct / 100.0)

                    gap_vol_bud = vol_12m_fcst - vol_budget_n12
                    gap_rev_bud = rev_12m_fcst - rev_budget_n12
                    gap_mar_bud = mar_12m_fcst - mar_budget_n12

                with b_col2:
                    fig_triple = go.Figure(data=[
                        go.Bar(name=tr("1. Real L12M", "1. Actual L12M"), x=["Revenue (£)", "Gross Margin (£)"], y=[rev_12m_hist, mar_12m_hist], marker_color="#A0B2C6"),
                        go.Bar(name=escenario_sel, x=["Revenue (£)", "Gross Margin (£)"], y=[rev_budget_n12, mar_budget_n12], marker_color="#E6A100"),
                        go.Bar(name=tr("3. Plan Consenso N12M", "3. Consensus Plan N12M"), x=["Revenue (£)", "Gross Margin (£)"], y=[rev_12m_fcst, mar_12m_fcst], marker_color="#1E3E5B")
                    ])
                    fig_triple.update_layout(**LAYOUT_STYLE, barmode="group", height=300, margin=dict(l=10, r=10, t=25, b=10), yaxis_title="GBP (£)")
                    st.plotly_chart(fig_triple, use_container_width=True)

                col_h1, col_h2, col_h3 = st.columns(3)
                col_h1.metric(tr("Volumen Real L12M", "Actual Volume L12M"), f"{vol_12m_hist:,.0f} Kg")
                col_h2.metric("Revenue Real L12M", f"£ {rev_12m_hist:,.0f}")
                col_h3.metric(tr("Margen Real L12M", "Actual Margin L12M"), f"£ {mar_12m_hist:,.0f} ({(mar_12m_hist / rev_12m_hist * 100) if rev_12m_hist else 0:.1f}%)")
                
                col_b1, col_b2, col_b3 = st.columns(3)
                col_b1.metric(tr("Target Budget N12M (Vol)", "Budget Target N12M (Vol)"), f"{vol_budget_n12:,.0f} Kg", f"{budget_growth_pct:+.1f}% Target")
                col_b2.metric(tr("Target Budget N12M (Rev)", "Budget Target N12M (Rev)"), f"£ {rev_budget_n12:,.0f}", f"{budget_growth_pct:+.1f}% Target")
                col_b3.metric(tr("Target Budget N12M (Mar)", "Budget Target N12M (Mar)"), f"£ {mar_budget_n12:,.0f}", f"{budget_growth_pct:+.1f}% Target")

                col_f1_k, col_f2_k, col_f3_k = st.columns(3)
                col_f1_k.metric(tr("Consenso N12M vs. Budget (Vol)", "Consensus N12M vs. Budget (Vol)"), f"{vol_12m_fcst:,.0f} Kg", f"{gap_vol_bud:+,.0f} Kg vs Budget")
                col_f2_k.metric(tr("Consenso N12M vs. Budget (Rev)", "Consensus N12M vs. Budget (Rev)"), f"£ {rev_12m_fcst:,.0f}", f"{gap_rev_bud:+,.0f} £ vs Budget")
                col_f3_k.metric(tr("Consenso N12M vs. Budget (Mar)", "Consensus N12M vs. Budget (Mar)"), f"£ {mar_12m_fcst:,.0f}", f"{gap_mar_bud:+,.0f} £ vs Budget")

                st.divider()
                st.subheader(tr("🌉 Puente Financiero S&OP: Transición L12M → N12M (Waterfall Bridge en GBP)", "🌉 S&OP Financial Waterfall Bridge: L12M → N12M Transition (GBP)"))
                wf_col1, wf_col2 = st.columns(2)
                x_labels_wf = [
                    tr("1. Real L12M", "1. Actual L12M"),
                    tr("2. Efecto Vol. Clase A", "2. Class A Vol. Effect"),
                    tr("3. Efecto Mix Clase B/C", "3. Class B/C Mix Effect"),
                    tr("4. Ajustes Consenso (FVA)", "4. Consensus Overrides (FVA)"),
                    tr("5. Proyectado N12M", "5. Projected N12M")
                ]

                with wf_col1:
                    y_rev_wf = [rev_12m_hist, puente_data["rev_a"], puente_data["rev_bc"], puente_data["rev_fva"], rev_12m_fcst]
                    fig_wf_rev = go.Figure(go.Waterfall(
                        name="Revenue Bridge", orientation="v",
                        measure=["absolute", "relative", "relative", "relative", "total"],
                        x=x_labels_wf, y=y_rev_wf,
                        text=[f"£ {v:,.0f}" if i in [0, 4] else f"£ {v:+,.0f}" for i, v in enumerate(y_rev_wf)],
                        textposition="outside",
                        connector={"line": {"color": "#A0B2C6", "width": 1.5, "dash": "dot"}},
                        increasing={"marker": {"color": "#2E8B57"}},
                        decreasing={"marker": {"color": "#D9534F"}},
                        totals={"marker": {"color": "#1E3E5B"}}
                    ))
                    fig_wf_rev.update_layout(**LAYOUT_STYLE, title=tr("Puente de Ingresos / Revenue Bridge (£)", "Revenue Bridge L12M → N12M (£)"), yaxis_title="GBP (£)", height=420)
                    st.plotly_chart(fig_wf_rev, use_container_width=True)

                with wf_col2:
                    y_mar_wf = [mar_12m_hist, puente_data["mar_a"], puente_data["mar_bc"], puente_data["mar_fva"], mar_12m_fcst]
                    fig_wf_mar = go.Figure(go.Waterfall(
                        name="Margin Bridge", orientation="v",
                        measure=["absolute", "relative", "relative", "relative", "total"],
                        x=x_labels_wf, y=y_mar_wf,
                        text=[f"£ {v:,.0f}" if i in [0, 4] else f"£ {v:+,.0f}" for i, v in enumerate(y_mar_wf)],
                        textposition="outside",
                        connector={"line": {"color": "#A0B2C6", "width": 1.5, "dash": "dot"}},
                        increasing={"marker": {"color": "#2E8B57"}},
                        decreasing={"marker": {"color": "#D9534F"}},
                        totals={"marker": {"color": "#1E3E5B"}}
                    ))
                    fig_wf_mar.update_layout(**LAYOUT_STYLE, title=tr("Puente de Margen Bruto / Gross Margin Bridge (£)", "Gross Margin Bridge L12M → N12M (£)"), yaxis_title="GBP (£)", height=420)
                    st.plotly_chart(fig_wf_mar, use_container_width=True)

                st.divider()
                st.subheader(tr("🛡️ Radar de Riesgo Comercial: Alerta de Fuga de Clientes (Churn L6M) & Monopolio de SKUs", "🛡️ Commercial Risk Radar: Customer Churn Alert (L6M) & Single-Customer SKU Dependency"))
                corte_6m = max_date_global - pd.DateOffset(months=6)
                corte_12m = max_date_global - pd.DateOffset(months=12)

                df_rec_cli = df[df['Date'] >= corte_6m].groupby(['País', 'customer cod', 'customer desc']).agg(Vol_L6M=('volume', 'sum'), Mar_L6M=('Mar_GBP', 'sum')).reset_index()
                df_ant_cli = df[(df['Date'] < corte_6m) & (df['Date'] >= corte_12m)].groupby(['País', 'customer cod']).agg(Vol_Prev6M=('volume', 'sum')).reset_index()
                df_churn = pd.merge(df_rec_cli, df_ant_cli, on=['País', 'customer cod'], how='left').fillna({'Vol_Prev6M': 0.0})
                df_churn['Variacion_L6M_Pct'] = np.where(df_churn['Vol_Prev6M'] > 0, ((df_churn['Vol_L6M'] - df_churn['Vol_Prev6M']) / df_churn['Vol_Prev6M']) * 100.0, 0.0)
                df_churn['Estado_Cuenta'] = np.where(
                    df_churn['Variacion_L6M_Pct'] < -10.0,
                    tr('🔴 Riesgo Fuga (Caída >10%)', '🔴 High Churn Risk (Drop >10%)'),
                    np.where(df_churn['Variacion_L6M_Pct'] < 0.0, tr('🟠 Enfriamiento Comercial', '🟠 Cooling Account'), tr('🟢 Crecimiento / Estable', '🟢 Growing / Stable'))
                )

                df_sku_cli = df.groupby(['sku cod', 'customer desc'])['volume'].sum().reset_index()
                df_sku_tot = df.groupby('sku cod')['volume'].sum().reset_index(name='Vol_Total_SKU')
                df_conc = pd.merge(df_sku_cli, df_sku_tot, on='sku cod')
                df_conc['Share_Cliente_Pct'] = np.where(df_conc['Vol_Total_SKU'] > 0, (df_conc['volume'] / df_conc['Vol_Total_SKU']) * 100.0, 0.0)
                df_conc_top = df_conc.sort_values('Share_Cliente_Pct', ascending=False).drop_duplicates('sku cod')
                df_conc_top['Descripción SKU'] = df_conc_top['sku cod'].map(dict_sku_desc).fillna('')
                df_conc_top['Riesgo_Dependencia'] = np.where(
                    df_conc_top['Share_Cliente_Pct'] >= 70.0,
                    tr('🔴 Dependencia Crítica (>=70%)', '🔴 Critical Dependency (>=70%)'),
                    tr('🟢 Diversificado', '🟢 Diversified')
                )

                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    st.markdown(f"#### {tr('📉 Salud de Cuentas y Riesgo Churn (L6M)', '📉 Account Health & Churn Risk (L6M)')}")
                    st.dataframe(
                        df_churn[['País', 'customer desc', 'Vol_L6M', 'Mar_L6M', 'Variacion_L6M_Pct', 'Estado_Cuenta']]
                        .sort_values('Variacion_L6M_Pct').head(100)
                        .rename(columns={'customer desc': tr('Cliente', 'Customer'), 'Vol_L6M': 'Vol L6M (Kg)', 'Mar_L6M': 'Margin L6M (£)', 'Variacion_L6M_Pct': 'Delta L6M (%)'})
                        .style.format({'Vol L6M (Kg)': '{:,.0f} Kg', 'Margin L6M (£)': '£ {:,.0f}', 'Delta L6M (%)': '{:+.1f}%'}),
                        use_container_width=True,
                        hide_index=True
                    )
                with r_col2:
                    st.markdown(f"#### {tr('🎯 Concentración de Cartera por SKU (Pareto Cliente)', '🎯 Portfolio Concentration per SKU (Customer Share)')}")
                    st.dataframe(
                        df_conc_top[['sku cod', 'Descripción SKU', 'customer desc', 'Share_Cliente_Pct', 'Riesgo_Dependencia']].head(100)
                        .rename(columns={'customer desc': tr('Cliente Principal', 'Top Customer'), 'Share_Cliente_Pct': 'Share (%)'})
                        .style.format({'Share (%)': '{:.1f}%'}),
                        use_container_width=True,
                        hide_index=True
                    )

                st.divider()
                st.subheader(tr("📋 Rendimiento Comercial y Bias por Cliente y SKU (L12M - Top 250 por Revenue)", "📋 Commercial Performance & Bias by Customer and SKU (L12M - Top 250 by Revenue)"))
                df_granular = df.groupby(['País', 'customer cod', 'customer desc', 'sku cod']).agg(
                    Volumen_Kg=('volume', 'sum'),
                    Revenue_GBP=('Rev_GBP', 'sum'),
                    Margen_GBP=('Mar_GBP', 'sum')
                ).reset_index().rename(columns={'customer desc': 'Cliente Desc'})
                
                df_granular['Margen %'] = np.where(df_granular['Revenue_GBP'] > 0, (df_granular['Margen_GBP'] / df_granular['Revenue_GBP']) * 100, 0.0)
                df_reciente = df[df['Date'] >= corte_6m].groupby(['customer cod', 'sku cod'])['volume'].sum().reset_index(name='Vol_Reciente')
                df_antiguo = df[(df['Date'] < corte_6m) & (df['Date'] >= corte_12m)].groupby(['customer cod', 'sku cod'])['volume'].sum().reset_index(name='Vol_Antiguo')
                
                df_granular = pd.merge(df_granular, df_reciente, on=['customer cod', 'sku cod'], how='left').fillna({'Vol_Reciente': 0})
                df_granular = pd.merge(df_granular, df_antiguo, on=['customer cod', 'sku cod'], how='left').fillna({'Vol_Antiguo': 0})
                df_granular['Bias L6M (%)'] = np.where(df_granular['Vol_Antiguo'] > 0, ((df_granular['Vol_Reciente'] - df_granular['Vol_Antiguo']) / df_granular['Vol_Antiguo']) * 100, 0.0).round(1)
                df_granular['Descripción SKU'] = df_granular['sku cod'].map(dict_sku_desc).fillna('')
                df_granular = df_granular[['País', 'customer cod', 'Cliente Desc', 'sku cod', 'Descripción SKU', 'Volumen_Kg', 'Revenue_GBP', 'Margen_GBP', 'Margen %', 'Bias L6M (%)']]
                
                col_g1, col_g2, col_g3 = st.columns(3)
                with col_g1:
                    filtro_pais_g = st.selectbox(tr("País:", "Country:"), ["TODOS"] + sorted(df_granular['País'].dropna().unique().tolist()), key="g_pais")
                with col_g2:
                    filtro_cli_g = st.selectbox(tr("Cliente:", "Customer:"), ["TODOS"] + sorted(df_granular['Cliente Desc'].dropna().unique().tolist()), key="g_cli")
                with col_g3:
                    search_sku = st.text_input(tr("🔍 Buscar SKU / Descripción:", "🔍 Search SKU / Description:"), placeholder="...")
                    
                if filtro_pais_g != "TODOS":
                    df_granular = df_granular[df_granular['País'] == filtro_pais_g]
                if filtro_cli_g != "TODOS":
                    df_granular = df_granular[df_granular['Cliente Desc'] == filtro_cli_g]
                if search_sku:
                    query = search_sku.strip().lower()
                    mask = (
                        df_granular['sku cod'].astype(str).str.lower().str.contains(query) |
                        df_granular['Descripción SKU'].astype(str).str.lower().str.contains(query) |
                        df_granular['Cliente Desc'].astype(str).str.contains(query, case=False)
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
                    df_granular.sort_values(by='Revenue_GBP', ascending=False).head(250)
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

                if FPDF is not None:
                    st.divider()
                    st.markdown(f"### {tr('📑 Exportar Dossier Directivo: Executive S&OP Deck (PDF)', '📑 Export Executive S&OP Deck (PDF)')}")
                    bytes_deck = generar_pdf_executive_sop_deck(
                        pais_sel, cliente_sel, sku_sel, total_skus, total_clientes,
                        fa_val, bias_val, wape_val,
                        vol_12m_hist, rev_12m_hist, mar_12m_hist,
                        vol_12m_fcst, rev_12m_fcst, mar_12m_fcst,
                        vol_budget_n12, rev_budget_n12, mar_budget_n12
                    )
                    if bytes_deck:
                        st.download_button(
                            label=tr("📄 Descargar Executive S&OP Deck Completo (.pdf)", "📄 Download Full Executive S&OP Deck (.pdf)"),
                            data=bytes_deck,
                            file_name=f"Executive_SOP_Deck_{datetime.now().strftime('%Y_%m')}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
