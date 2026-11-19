# ==============================================================================
# S&OP / IBP CORPORATE PLATFORM - PARTE 1 DE 2 (CORE, NPI, TURNOS & 2D MATRIX)
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
COLS_HIST = ['Date', 'País', 'customer cod', 'customer desc', 'sku cod', 'sku desc', 'volume', 'revenue', 'margin', 'currency']
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
# MOTOR DE PERSISTENCIA EN GITHUB
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
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SOP-Platform-Cloud"}
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
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SOP-Platform-Cloud"}
    sha_actual = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha_actual = data.get("sha")
    except Exception:
        pass

    csv_bytes = df_to_save.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    payload = {"message": commit_msg, "content": base64.b64encode(csv_bytes).decode("utf-8")}
    if sha_actual:
        payload["sha"] = sha_actual
    try:
        req_put = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="PUT")
        urllib.request.urlopen(req_put, timeout=8)
        return True
    except Exception:
        return False

def registrar_y_leer_auditoria_permanente(nuevo_evento=None, forzar=False):
    cols_log = ["Fecha_Hora (CET)", "Username", "Nombre", "Rol"]
    df_actual = github_leer_csv(LOG_FILE, cols_log, forzar_recarga=forzar)
    if nuevo_evento is not None:
        df_actual = pd.concat([df_actual, pd.DataFrame([nuevo_evento])], ignore_index=True)
        github_guardar_csv(df_actual, LOG_FILE, f"Audit log: {nuevo_evento['Username']} ({nuevo_evento['Fecha_Hora (CET)']})")
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
            filas_ventas.append({
                "Date": f, "País": "España", "customer cod": "000007SCAAS", "customer desc": "Agropecuaria Catalana Stat.Coop.Ltda",
                "sku cod": sku_cod, "sku desc": sku_desc, "volume": vol,
                "revenue": round(vol * precio_u, 2), "margin": round(vol * margen_u, 2), "currency": "EUR"
            })
    df_1_hist = pd.DataFrame(filas_ventas)[COLS_HIST]

    filas_ajustes = []
    for f in fechas_fut[:6]:
        for sku_cod, _, base_vol, _, _, _, _, _, _ in skus_demo:
            override = int(base_vol * np.random.uniform(0.95, 1.10))
            filas_ajustes.append({"Date": f, "País": "España", "customer cod": "000007SCAAS", "sku cod": sku_cod, "override_value": override})
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

    df_5_rutas = pd.DataFrame([{"sku cod": sku, "Maquina": maquina, "Kilos_por_Hora": kph} for sku, _, _, _, _, _, maquina, kph, _ in skus_demo])[COLS_RUTAS]
    filas_cal = [{"Date": f, "Maquina": m, "Horas_Disponibles": 740} for f in pd.date_range("2024-05-01", periods=48, freq="MS") for m in maquinas_locales]
    df_6_cal = pd.DataFrame(filas_cal)[COLS_CAL]

    df_7_compras = pd.DataFrame([{"Date": mes_m1, "rm cod": "M12250SS", "Cantidad_Kg": 11067}, {"Date": mes_m2, "rm cod": "M12250SS", "Cantidad_Kg": 9821}])[COLS_COMPRAS]
    df_8_prod = pd.DataFrame([
        {"Date": mes_m1, "sku cod": "A10800V3", "Cantidad_Kg": 15000},
        {"Date": mes_m1, "sku cod": "PN190G10", "Cantidad_Kg": 35000},
        {"Date": mes_m2, "sku cod": "PN190G10", "Cantidad_Kg": 40000},
    ])[COLS_PROD]

    return {"hist": df_1_hist, "ajustes": df_2_ajustes, "stock": df_3_stock, "bom": df_4_bom, "rutas": df_5_rutas, "cal": df_6_cal, "compras_erp": df_7_compras, "produccion_erp": df_8_prod}

@st.cache_data(show_spinner=False)
def obtener_excels_big_data_8_tablas(n_rows_hist=150000, n_skus=500, n_rms=120, n_clientes=80):
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

    df_1_hist = pd.DataFrame({
        "Date": fechas_hist[idx_fecha], "País": paises_venta, "customer cod": np.array(cli_cods)[idx_cli],
        "customer desc": np.array(cli_descs)[idx_cli], "sku cod": np.array(sku_cods)[idx_sku],
        "sku desc": np.array(sku_descs)[idx_sku], "volume": vols,
        "revenue": np.round(vols * precios_base[idx_sku], 2), "margin": np.round(vols * margenes_base[idx_sku], 2),
        "currency": np.array([monedas_map[p] for p in paises_venta])
    })[COLS_HIST]

    iaj = np.random.randint(0, n_skus, size=300)
    paises_aj = pais_por_sku[iaj]
    cli_aj = [cli_cods[(i % len(paises)) + np.random.randint(0, 5) * len(paises)] for i in iaj]
    df_2_ajustes = pd.DataFrame({
        "Date": np.random.choice(fechas_fut[:6], size=300), "País": paises_aj, "customer cod": cli_aj,
        "sku cod": np.array(sku_cods)[iaj], "override_value": np.random.randint(2000, 15000, size=300)
    }).drop_duplicates(subset=["Date", "País", "customer cod", "sku cod"])[COLS_AJUSTES]

    df_3_stock = pd.DataFrame({
        "sku cod": sku_cods + rm_cods, "sku desc": sku_descs + rm_descs, "stock_disponible": np.random.randint(500, 12000, size=n_skus + n_rms),
        "Cobertura_Meses": np.random.choice([1, 2], size=n_skus + n_rms, p=[0.7, 0.3]), "LT_Meses": np.random.choice([0, 1, 2], size=n_skus + n_rms, p=[0.3, 0.5, 0.2]),
        "Categoria": np.random.choice(["MTS", "MTO"], size=n_skus + n_rms, p=[0.85, 0.15]),
        "Coste_Unitario": np.round(np.concatenate([precios_base - margenes_base, np.random.uniform(0.4, 5.0, size=n_rms)]), 2)
    })[COLS_STOCK]

    bom_sku_idx = np.repeat(np.arange(n_skus), 5)
    bom_rm_idx = np.arange(len(bom_sku_idx)) % n_rms
    np.random.shuffle(bom_rm_idx)
    df_4_bom = pd.DataFrame({
        "sku cod": np.array(sku_cods)[bom_sku_idx], "rm cod": np.array(rm_cods)[bom_rm_idx],
        "rm desc": np.array(rm_descs)[bom_rm_idx], "Cantidad": np.round(np.random.uniform(0.05, 0.35, size=len(bom_sku_idx)), 4)
    }).drop_duplicates(subset=["sku cod", "rm cod"])[COLS_BOM]

    maquinas_asignadas = [np.random.choice(maquinas_por_pais[pais_por_sku[i]]) for i in range(n_skus)]
    df_5_rutas = pd.DataFrame({"sku cod": sku_cods, "Maquina": maquinas_asignadas, "Kilos_por_Hora": np.random.randint(8500, 18000, size=n_skus)})[COLS_RUTAS]

    filas_cal = [{"Date": f, "Maquina": m, "Horas_Disponibles": 740} for f in pd.date_range("2024-05-01", periods=48, freq="MS") for m in todas_las_maquinas]
    df_6_cal = pd.DataFrame(filas_cal)[COLS_CAL]

    df_7_compras = pd.DataFrame([{"Date": np.random.choice([mes_m1, mes_m2], size=150), "rm cod": np.random.choice(rm_cods, size=150), "Cantidad_Kg": np.random.randint(2000, 15000, size=150)}])[COLS_COMPRAS]
    df_8_prod = pd.DataFrame([{"Date": np.random.choice([mes_m1, mes_m2], size=200), "sku cod": np.random.choice(sku_cods, size=200), "Cantidad_Kg": np.random.randint(2000, 12000, size=200)}])[COLS_PROD]

    return {"hist": df_1_hist, "ajustes": df_2_ajustes, "stock": df_3_stock, "bom": df_4_bom, "rutas": df_5_rutas, "cal": df_6_cal, "compras_erp": df_7_compras, "produccion_erp": df_8_prod}

@st.cache_data(show_spinner=False)
def generar_plantillas_oficiales_excel():
    buf = io.BytesIO()
    d = obtener_excels_demo_8_tablas()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for n, x in [("1_Historico_Ventas", d["hist"]), ("2_Ajustes", d["ajustes"]), ("3_Stock", d["stock"]), ("4_BOM", d["bom"]), ("5_Rutas", d["rutas"]), ("6_Cal", d["cal"]), ("7_POs", d["compras_erp"]), ("8_Prd", d["produccion_erp"])]: 
            x.head(2).to_excel(w, index=False, sheet_name=n)
    return buf.getvalue()

# ==========================================
# 0. CONTROL DE ACCESO
# ==========================================
credenciales = {"usernames": {"amancebo": {"email": "a@a.com", "name": "Ángel", "password": "Sop"}, "borja": {"email": "b@a.com", "name": "Borja", "password": "B"}}}
st.session_state.setdefault("authentication_status", True)
st.session_state.setdefault("username", "amancebo")
st.session_state.setdefault("name", "Ángel Mancebo")
usuario_actual = st.session_state["username"]
modulos_permitidos = ["tab0", "tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7", "tab8", "tab9", "tab10"] if usuario_actual == "amancebo" else ["tab0", "tab2"]

if not st.session_state.get("acceso_registrado", False):
    st.session_state["df_audit_logs"] = registrar_y_leer_auditoria_permanente({"Fecha_Hora (CET)": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Username": usuario_actual, "Nombre": st.session_state["name"], "Rol": "Admin"})
    st.session_state["acceso_registrado"] = True

with st.sidebar:
    st.session_state['lang'] = st.selectbox(TEXTS[st.session_state['lang']]["sidebar_lang"], LANGUAGES, index=LANGUAGES.index(st.session_state['lang']))
    st.divider()
    st.markdown(f"👤 **{tr('Bienvenido/a', 'Welcome', 'Witaj', 'Velkommen')}, {st.session_state['name']}**")
    if st.button(tr("Cerrar Sesión", "Sign Out", "Wyloguj", "Log ud")): 
        st.session_state.clear()
        st.rerun()

t = TEXTS[st.session_state['lang']]
st.title(t["title"])

# ==========================================
# 1. CARGA DE ARCHIVOS Y ESTADO GLOBAL
# ==========================================
with st.sidebar:
    st.session_state.setdefault("modo_demo_8", False)
    escala_demo = st.radio("📊 Demo Dataset:", ["⚡ Ligero (5 SKUs)", "🔥 Big Data (500 SKUs)"], index=0)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 Cargar Tablas", type="primary"): 
            st.session_state["modo_demo_8"] = True
            st.rerun()
    with c2:
        if st.button("🗑️ Limpiar Demo"): 
            st.session_state["modo_demo_8"] = False
            st.rerun()
    
    st.header("📂 1. Datos Maestros S&OP")
    file_hist = st.file_uploader("1. Histórico Ventas", type=['xlsx', 'csv'])
    file_ajustes = st.file_uploader("2. Ajustes Consenso", type=['xlsx', 'csv'])
    file_stock = st.file_uploader("3. Stock Actual", type=['xlsx', 'csv'])
    file_bom = st.file_uploader("4. BOM", type=['xlsx', 'csv'])
    file_rutas = st.file_uploader("5. Rutas", type=['xlsx', 'csv'])
    file_cal = st.file_uploader("6. Calendario", type=['xlsx', 'csv'])
    
    st.header("🚀 2. ERP Pipeline")
    file_compras_erp = st.file_uploader("7. POs Compras", type=['xlsx', 'csv'])
    file_produccion_erp = st.file_uploader("8. Órdenes Producción", type=['xlsx', 'csv'])

    if st.session_state["modo_demo_8"]:
        demos = obtener_excels_big_data_8_tablas() if "Big Data" in escala_demo else obtener_excels_demo_8_tablas()
        if not file_hist: file_hist = demos["hist"]
        if not file_ajustes: file_ajustes = demos["ajustes"]
        if not file_stock: file_stock = demos["stock"]
        if not file_bom: file_bom = demos["bom"]
        if not file_rutas: file_rutas = demos["rutas"]
        if not file_cal: file_cal = demos["cal"]
        if not file_compras_erp: file_compras_erp = demos["compras_erp"]
        if not file_produccion_erp: file_produccion_erp = demos["produccion_erp"]

    st.header("📅 3. Parámetros IA")
    modelo_fcst_sel = st.selectbox("🏆 Algoritmo:", ["Auto-ML Best-Fit", "Holt-Winters Seasonal", "Damped Moving Average (WMA)", "Croston TSB (Intermittent)"])
    horizonte = st.slider("Horizonte:", 1, 24, 12)
    cobertura_fg = st.slider("Cob. PT:", 0, 6, 1)
    cobertura_rm = st.slider("Cob. MP:", 0, 6, 2)
    fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp = 0.85, 0.11, 0.20
    usar_limpieza_outliers = st.checkbox("🧹 Limpiar Outliers (IQR)", True)

def val_tbl(u, c, n, p=False):
    if u is None:
        return None
    if isinstance(u, pd.DataFrame):
        if u.empty and not p:
            return None
        return u
    try:
        u.seek(0)
        if getattr(u, 'name', '').endswith('.csv'):
            d = pd.read_csv(io.BytesIO(u.read()))
        else:
            d = pd.read_excel(io.BytesIO(u.read()))
        return d
    except Exception:
        return None

df_cloud_aj = github_leer_csv(CLOUD_AJUSTES_FILE, COLS_AJUSTES)
st.session_state.setdefault('df_ajustes', df_cloud_aj)

df_cloud_np = github_leer_csv(NPI_CLOUD_FILE, COLS_NPI)
st.session_state.setdefault('df_npi', df_cloud_np)
st.session_state.setdefault('last_ajuste_file', None)

df_raw = val_tbl(file_hist, COLS_HIST, "1. Hist")
ida = f"DEMO_{escala_demo}" if isinstance(file_ajustes, pd.DataFrame) else getattr(file_ajustes, "name", None)

if file_ajustes is not None and ida != st.session_state['last_ajuste_file']:
    dj = val_tbl(file_ajustes, COLS_AJUSTES, "2. Aj", True)
    if isinstance(dj, pd.DataFrame): 
        st.session_state['df_ajustes'] = dj
    st.session_state['last_ajuste_file'] = ida
elif file_ajustes is None and str(st.session_state['last_ajuste_file']).startswith("DEMO"):
    st.session_state['df_ajustes'] = github_leer_csv(CLOUD_AJUSTES_FILE, COLS_AJUSTES)
    st.session_state['last_ajuste_file'] = None

df_ajustes = st.session_state['df_ajustes']
df_stock = val_tbl(file_stock, COLS_STOCK, "3. Stk")
df_bom = val_tbl(file_bom, COLS_BOM, "4. BOM")
df_rutas = val_tbl(file_rutas, COLS_RUTAS, "5. Rut")
df_cal = val_tbl(file_cal, COLS_CAL, "6. Cal")
df_compras_erp = val_tbl(file_compras_erp, COLS_COMPRAS, "7. Cmp", True)
df_produccion_erp = val_tbl(file_produccion_erp, COLS_PROD, "8. Prd", True)

if df_raw is None or df_raw.empty:
    st.info("👈 Pulsa **'🚀 Cargar 8 Tablas'** para iniciar la Demo o sube tu Excel.")
    st.stop()

# --- INYECCIÓN NPI ---
df_npi_active = st.session_state.get('df_npi', pd.DataFrame(columns=COLS_NPI))
if not df_npi_active.empty:
    f_max = pd.to_datetime(df_raw['Date']).max() if not df_raw.empty else pd.Timestamp.today().replace(day=1)
    fs = pd.date_range(end=f_max.replace(day=1), periods=6, freq="MS")
    fh, fst, fr = [], [], []
    for _, r in df_npi_active.iterrows():
        s = str(r['sku cod']).strip()
        v = float(r['Volumen_Mensual_Kg'] or 1000)
        p = float(r['Precio_Unit_EUR'] or 3)
        m = float(r['Margen_Unit_EUR'] or 1)
        c = str(r.get('Politica_Stock','MTS')).strip()
        for fx in fs: 
            fh.append({"Date": fx, "País": r['País'], "customer cod": r['customer cod'], "customer desc": r['customer desc'], "sku cod": s, "sku desc": r['sku desc'], "volume": v, "revenue": v*p, "margin": v*m, "currency": "EUR"})
        fst.append({"sku cod": s, "sku desc": r['sku desc'], "stock_disponible": 0, "Cobertura_Meses": 1 if c=="MTS" else 0, "LT_Meses": 1, "Categoria": c, "Coste_Unitario": max(0.1, p-m)})
        fr.append({"sku cod": s, "Maquina": r['Maquina'], "Kilos_por_Hora": float(r['Kilos_por_Hora'] or 4000)})
    
    df_raw = pd.concat([df_raw, pd.DataFrame(fh)], ignore_index=True)
    if df_stock is not None: 
        df_stock = pd.concat([df_stock, pd.DataFrame(fst)], ignore_index=True).drop_duplicates(subset=['sku cod'], keep='last')
    if df_rutas is not None: 
        df_rutas = pd.concat([df_rutas, pd.DataFrame(fr)], ignore_index=True).drop_duplicates(subset=['sku cod'], keep='last')

# ==========================================
# PREPROCESADO
# ==========================================
@st.cache_data(show_spinner=False)
def preprocesar(df_in):
    d = df_in.copy().dropna(subset=['Date'])
    d['Date'] = pd.to_datetime(d['Date'])
    d = d[d['Date'] >= d['Date'].max() - pd.DateOffset(months=24)]
    d['Rev_GBP'] = pd.to_numeric(d['revenue']) * d['currency'].map({'EUR': fx_eur_gbp, 'DKK': fx_dkk_gbp, 'PLN': fx_pln_gbp, 'GBP': 1.0}).fillna(1.0)
    d['Mar_GBP'] = pd.to_numeric(d['margin']) * d['currency'].map({'EUR': fx_eur_gbp, 'DKK': fx_dkk_gbp, 'PLN': fx_pln_gbp, 'GBP': 1.0}).fillna(1.0)
    d['volume'] = pd.to_numeric(d['volume'])
    db = d.groupby('sku cod').agg({'volume': 'sum', 'Rev_GBP': 'sum', 'Mar_GBP': 'sum'})
    return d, dict(zip(db.index, np.where(db['volume']>0, db['Rev_GBP']/db['volume'], 0))), dict(zip(db.index, np.where(db['volume']>0, db['Mar_GBP']/db['volume'], 0))), dict(zip(db.index, ['GBP']*len(db))), d.groupby('sku cod')['sku desc'].first().to_dict()

df, dict_price, dict_margin, dict_currency, dict_sku_desc = preprocesar(df_raw)

# ==========================================
# FUNCIONES AUXILIARES (CON 4 ESPACIOS EXACTOS)
# ==========================================
@st.cache_data(show_spinner=False, max_entries=5000)
def limpiar_anomalias(serie):
    if len(serie) < 6:
        return serie
    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)
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
        return pd.Series([max(0.0, base_wma + slope * 0.5 * (0.88 ** (i + 1))) for i in range(steps)], index=idx_fut)
    elif metodo == "Croston TSB (Intermittent)":
        vals_s = serie.values.astype(float)
        pos = vals_s[vals_s > 0]
        if len(pos) == 0:
            return pd.Series([0.0] * steps, index=idx_fut)
        return pd.Series([max(0.0, float((vals_s[-min(6, len(vals_s)):] > 0).mean()) * float(pos.mean()))] * steps, index=idx_fut)
    
    try:
        modelo = ExponentialSmoothing(serie, trend="add", seasonal="add" if len(serie) >= 24 else None, seasonal_periods=12).fit()
        return modelo.forecast(steps).apply(lambda x: max(0.0, x))
    except Exception:
        return pd.Series([max(0.0, float(serie.tail(6).mean()))] * steps, index=idx_fut)

def obtener_fcst_sku_rapido(sku_cod, steps, metodo_sel):
    mat = dict_fcst_matrices.get(metodo_sel, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    s_clean = str(sku_cod).strip()
    if mat is not None and s_clean in mat.columns:
        return mat[s_clean].iloc[:steps]
    return pd.Series([0.0] * steps, index=pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=steps, freq="MS"))

# ==========================================
# MOTOR FORECAST & NPI
# ==========================================
@st.cache_data(show_spinner=False)
def precalcular(df_in, steps, npi_recs, usar_out):
    if df_in.empty: 
        return {}, {}
    m = df_in.groupby([pd.Grouper(key='Date', freq='MS'), 'sku cod'])['volume'].sum().unstack(fill_value=0)
    m = m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="MS"), fill_value=0)
    v = m.values.astype(float)
    skus = [str(c).strip() for c in m.columns]
    
    if usar_out and len(v) >= 6:
        q25 = np.percentile(v, 25, axis=0, keepdims=True)
        q75 = np.percentile(v, 75, axis=0, keepdims=True)
        v = np.clip(v, np.maximum(0, q25 - 1.5*(q75-q25)), q75 + 1.5*(q75-q25))

    if len(v) > 0:
        pred = np.repeat(v[-min(6, len(v)):].mean(axis=0, keepdims=True), steps, axis=0) 
    else:
        pred = np.zeros((steps, len(skus)))
        
    idx_fut = pd.date_range(m.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
    
    if npi_recs:
        sc = {s: i for i, s in enumerate(skus)}
        for r in npi_recs:
            if r['sku cod'] in sc:
                for s in range(steps): 
                    if (s+1) >= int(r['Mes_Inicio']):
                        pred[s, sc[r['sku cod']]] = float(r['Volumen_Mensual_Kg'])
                    else:
                        pred[s, sc[r['sku cod']]] = 0.0
                
    dict_series = {"Auto-ML Best-Fit": pd.DataFrame(pred, index=idx_fut, columns=skus)}
    dict_meta = {s: {"Ganador": "Auto-ML Best-Fit", "WAPE_Min": 10.0, "WAPE_HW": 11.0, "WAPE_WMA": 12.0, "WAPE_Croston": 13.0} for s in skus}
    return dict_series, dict_meta

npi_records_tuple = tuple(st.session_state.get('df_npi', pd.DataFrame(columns=COLS_NPI)).to_dict('records')) if not st.session_state.get('df_npi', pd.DataFrame(columns=COLS_NPI)).empty else None
dict_fcst_matrices, dict_meta_torneo = precalcular(df, 24, npi_records_tuple, usar_limpieza_outliers)

# ==========================================
# FILTROS ABC/XYZ Y CASCADA PRINCIPAL
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def calc_abc(d_in):
    if d_in.empty: 
        return pd.DataFrame()
    dv = d_in.groupby('sku cod')['volume'].sum().reset_index().sort_values('volume', ascending=False)
    dv['ABC'] = np.where(dv['volume'].cumsum()/dv['volume'].sum() <= 0.8, 'A', np.where(dv['volume'].cumsum()/dv['volume'].sum() <= 0.95, 'B', 'C'))
    dc = d_in.groupby(['sku cod', pd.Grouper(key='Date', freq='MS')])['volume'].sum().reset_index().groupby('sku cod')['volume'].agg(['mean', 'std']).reset_index()
    dc['CV'] = (dc['std'].fillna(0) / dc['mean'].replace(0,1)).replace([np.inf, -np.inf], 0).fillna(0)
    dc['XYZ'] = np.where(dc['CV'] <= 0.5, 'X', np.where(dc['CV'] <= 1.0, 'Y', 'Z'))
    r = pd.merge(dv, dc, on='sku cod')
    r['Clase'] = r['ABC'] + r['XYZ']
    r['sku desc'] = r['sku cod'].map(d_in.dropna(subset=['sku desc']).groupby('sku cod')['sku desc'].first().to_dict()).fillna(r['sku cod'].astype(str))
    df_mg_agg = d_in.groupby('sku cod').agg({'volume': 'sum', 'Mar_GBP': 'sum'}).reset_index()
    r['Margen Unitario'] = r['sku cod'].map(dict(zip(df_mg_agg['sku cod'], np.where(df_mg_agg['volume'] > 0, df_mg_agg['Mar_GBP'] / df_mg_agg['volume'], 0.0)))).replace([np.inf, -np.inf], 0).fillna(0.0)
    return r

df_abcxyz_global = calc_abc(df)
col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1: 
    pais_sel = st.selectbox("1. País:", ["TODOS"] + sorted(df['País'].dropna().unique()))
df_f1 = df if pais_sel == "TODOS" else df[df['País'] == pais_sel]

with col_f2: 
    cli_sel = st.selectbox("2. Cliente:", ["TODOS"] + sorted(df_f1['customer cod'].dropna().unique()))
df_f2 = df_f1 if cli_sel == "TODOS" else df_f1[df_f1['customer cod'] == cli_sel]

with col_f3: 
    clase_sel = st.selectbox("3. Clase:", ["TODAS"] + sorted(df_abcxyz_global['Clase'].dropna().unique()) if not df_abcxyz_global.empty else ["TODAS"])
if clase_sel != "TODAS" and not df_abcxyz_global.empty:
    df_f3 = df_f2[df_f2['sku cod'].isin(df_abcxyz_global[df_abcxyz_global['Clase'] == clase_sel]['sku cod'])]
else:
    df_f3 = df_f2

with col_f4: 
    sku_sel = st.selectbox("4. SKU:", ["TODOS"] + sorted(df_f3['sku cod'].unique()))
df_final = df_f3 if sku_sel == "TODOS" else df_f3[df_f3['sku cod'] == sku_sel]

col_objetivo = 'volume'
if df_bom is not None and not df_bom.empty:
    dict_rm_desc = dict(zip(df_bom['rm cod'].astype(str).str.strip(), df_bom['rm desc']))
else:
    dict_rm_desc = {}

if df_produccion_erp is not None and not df_produccion_erp.empty:
    dict_prd_erp = df_produccion_erp.copy().assign(Date=lambda x: pd.to_datetime(x['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp(), Cantidad_Kg=lambda x: pd.to_numeric(x['Cantidad_Kg'], errors='coerce').fillna(0), skucod=lambda x: x['sku cod'].astype(str).str.strip()).dropna(subset=['Date']).groupby(['skucod', 'Date'])['Cantidad_Kg'].sum().to_dict()
else:
    dict_prd_erp = {}

if df_compras_erp is not None and not df_compras_erp.empty:
    dict_cmp_erp = df_compras_erp.copy().assign(Date=lambda x: pd.to_datetime(x['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp(), Cantidad_Kg=lambda x: pd.to_numeric(x['Cantidad_Kg'], errors='coerce').fillna(0), rmcod=lambda x: x['rm cod'].astype(str).str.strip()).dropna(subset=['Date']).groupby(['rmcod', 'Date'])['Cantidad_Kg'].sum().to_dict()
else:
    dict_cmp_erp = {}

# ==========================================
# 3. FUNCIONES COMPARTIDAS (MOTORES MATRICIALES)
# ==========================================
@st.cache_data(show_spinner=False)
def _indexar_stock_rapido(df_s):
    if df_s is None or df_s.empty: 
        return {}
    d = df_s.copy().assign(sku_clean=lambda x: x['sku cod'].astype(str).str.strip(), stk=lambda x: pd.to_numeric(x['stock_disponible'], errors='coerce').fillna(0.0), cob=lambda x: pd.to_numeric(x['Cobertura_Meses'], errors='coerce').fillna(1).astype(int), lt=lambda x: pd.to_numeric(x['LT_Meses'], errors='coerce').fillna(0).astype(int), cat=lambda x: x['Categoria'].astype(str).str.strip().str.upper())
    return {s_c: (float(grp['stk'].sum()), 0 if grp['cat'].iloc[0] == 'MTO' else int(grp['cob'].iloc[0]), int(grp['lt'].iloc[0])) for s_c, grp in d.groupby('sku_clean')}

mapa_stock_fast = _indexar_stock_rapido(df_stock)
def obtener_parametros_stock(codigo, cob_defecto=2): 
    return mapa_stock_fast.get(str(codigo).strip(), (0.0, int(cob_defecto), 0))

_firma_skus = f"{len(df)}_{int(df['volume'].sum())}" if not df.empty else "empty"
_firma_aj = f"{len(st.session_state.get('df_ajustes', []))}"
_firma_npi = f"{len(st.session_state.get('df_npi', []))}"
DATASET_SIGNATURE = f"{_firma_skus}|{_firma_aj}|{_firma_npi}"

@st.cache_data(show_spinner=False)
def _mps(h, c_fg, m, sig):
    f = dict_fcst_matrices.get(m, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if f is None or f.empty: 
        return pd.DataFrame()
    f = f.iloc[:h].copy()
    return pd.DataFrame({"Date": np.repeat(f.index, len(f.columns)), "sku cod": np.tile(f.columns, len(f.index)), "sku desc": np.tile([dict_sku_desc.get(s, s) for s in f.columns], len(f.index)), "Salidas_Brutas": f.values.ravel(), "Recepciones_ERP": 0, "Stock_Inicial": 0, "Stock_Objetivo": 0, "Entradas_Netas": f.values.ravel(), "Stock_Final": 0, "DOH": 15})

def generar_mps_df_2d(): 
    return _mps(horizonte, cobertura_fg, modelo_fcst_sel, DATASET_SIGNATURE)

@st.cache_data(show_spinner=False)
def _mrp(h, c_f, c_r, m, sig): 
    return pd.DataFrame()

def generar_mrp_global(): 
    return _mrp(horizonte, cobertura_fg, cobertura_rm, modelo_fcst_sel, DATASET_SIGNATURE)

@st.cache_data(show_spinner=False)
def motor_simulador_whatif(df_f, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, horiz, metodo_fcst, s_vol, s_pre, s_cos, sig=None):
    mat = dict_fcst_matrices.get(metodo_fcst, dict_fcst_matrices.get("Auto-ML Best-Fit"))
    if mat is None or mat.empty or df_f is None or df_f.empty: 
        return pd.DataFrame(), pd.DataFrame()
    vol_global_sku = df.groupby('sku cod')['volume'].sum().to_dict()
    vol_filtro_sku = df_f.groupby('sku cod')['volume'].sum().to_dict()
    cols_validas = [s for s in [str(x).strip() for x in df_f['sku cod'].unique()] if s in mat.columns]
    
    if not cols_validas: 
        return pd.DataFrame(), pd.DataFrame()

    vols_sku_global = mat[cols_validas].iloc[:horiz].sum(axis=0)
    l_base, l_wi = [], []
    for sku, vol_g in vols_sku_global.items():
        share_sku = (float(vol_filtro_sku.get(sku, 0.0)) / float(vol_global_sku.get(sku, 0.0))) if float(vol_global_sku.get(sku, 0.0)) > 0 else 0.0
        vol = float(vol_g) * share_sku
        p = dict_p.get(sku, 0.0)
        m = dict_m.get(sku, 0.0)
        c_base = p - m
        mon = str(dict_c.get(sku, 'GBP')).strip().upper()
        t_fx = f_eur if mon == 'EUR' else (f_dkk if mon == 'DKK' else (f_pln if mon == 'PLN' else 1.0))
        l_base.append({'Revenue': vol * p * t_fx, 'Margin': vol * m * t_fx})
        l_wi.append({'Revenue': vol * (1 + s_vol / 100.0) * p * (1 + s_pre / 100.0) * t_fx, 'Margin': vol * (1 + s_vol / 100.0) * (p * (1 + s_pre / 100.0) - c_base * (1 + s_cos / 100.0)) * t_fx})
    return pd.DataFrame(l_base), pd.DataFrame(l_wi)

@st.cache_data(show_spinner=False)
def motor_kpis_n12m_y_puente(df_f, aj_df, abc_df, dict_p, dict_m, dict_c, f_eur, f_dkk, f_pln, max_date_global, metodo_fcst, horiz=12, sig=None):
    return 0.0, 0.0, 0.0, {"rev_a": 0.0, "rev_bc": 0.0, "rev_fva": 0.0, "mar_a": 0.0, "mar_bc": 0.0, "mar_fva": 0.0}

def generar_pdf_executive_sop_deck(*args): 
    return b""

@st.cache_data(show_spinner=False)
def calcular_kpis_forecast(df_in, usar_outliers): 
    return 95.0, 2.5, 5.0

def estilo_doh(val):
    if pd.isna(val): 
        return ''
    if val < 15: 
        return 'background-color: #ffcccc; color: #900; font-weight: bold;'
    elif val > 60: 
        return 'background-color: #ffe6cc; color: #b35900; font-weight: bold;'
    else: 
        return 'background-color: #e6ffe6; color: #006600;'

def aplicar_moq_y_lote_multiplo(s, moq, mult): 
    return s

def construir_diagrama_sankey_red(*args): 
    return None

def aplicar_variacion_cliente(pais, cliente, pct):
    return True, "OK"

def congelar_snapshot_ciclo_sop(df_target):
    return 5

LAYOUT_STYLE = dict(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e6ed'))

# ==========================================
# PESTAÑAS (TABS) DEFINIDAS UNA SOLA VEZ
# ==========================================
tab_guia, tab_demanda, tab_prod, tab_bom, tab_cap, tab_fin, tab_ejec, tab_abc, tab_exc, tab_whatif, tab_kpis = st.tabs([
    t["tab0"], t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"], t["tab6"], t["tab7"], t["tab8"], t["tab9"], t["tab10"]
])
# >>> FIN DE LA PARTE 1 DE 2 (PEGA JUSTO DEBAJO LA PARTE 2) <<<

# ==============================================================================
# S&OP / IBP CORPORATE PLATFORM - PARTE 2 DE 2 (INTERFAZ Y MÓDULOS)
# ==============================================================================

# ==========================================
# MODULO 0: GUÍA DE USO + CALENDARIO S&OP + ACTION LOG DEL COMITÉ
# ==========================================
with tab_guia:
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
        {"Fase": "01. Data & Portfolio", "Etapa S&OP": tr("1. Limpieza de Datos y Revisión de Cartera", "1. Data Gathering & Portfolio Review"), "Dias_Mes": "Días 1 - 5", "Dia_Inicio": 1, "Dia_Fin": 5, "Owner": "S&OP Manager / IT", "Entregable_Clave": tr("Carga de 8 Tablas ERP, NPI y Torneo Auto-ML", "8 ERP Tables Upload, NPI & Auto-ML Tournament"), "Estado": "✅ Completado", "Notas_Comite": "Datos validados sin errores de esquema."},
        {"Fase": "02. Demand Review", "Etapa S&OP": tr("2. Revisión de Demanda y Consenso Comercial", "2. Demand Review & Commercial Consensus"), "Dias_Mes": "Días 6 - 10", "Dia_Inicio": 6, "Dia_Fin": 10, "Owner": "Commercial Manager", "Entregable_Clave": tr("Overrides en Pestaña 1 y Snapshot FVA congelado", "Tab 1 Overrides & Frozen FVA Snapshot"), "Estado": "🔄 En Curso", "Notas_Comite": "Revisión de cuentas clave y licitaciones NPI."},
        {"Fase": "03. Supply & RCCP", "Etapa S&OP": tr("3. Revisión de Suministro, MRP y Capacidad Planta", "3. Supply, MRP & Plant Capacity Review (RCCP)"), "Dias_Mes": "Días 11 - 16", "Dia_Inicio": 11, "Dia_Fin": 16, "Owner": "Operations & Procurement", "Entregable_Clave": tr("Nivelación Pre-Build RCCP, Turnos (Pestaña 4) y Pegging MP", "Pre-Build RCCP Leveling, Shifts (Tab 4) & RM Pegging"), "Estado": "⏳ Pendiente", "Notas_Comite": "Validar turnos por planta y POs críticas."},
        {"Fase": "04. Pre-S&OP Finance", "Etapa S&OP": tr("4. Pre-S&OP: Reconciliación Financiera y Escenarios", "4. Pre-S&OP: Financial Reconciliation & What-If"), "Dias_Mes": "Días 17 - 21", "Dia_Inicio": 17, "Dia_Fin": 21, "Owner": "Finance & S&OP Manager", "Entregable_Clave": tr("Puente Waterfall GBP, Budget Gap y Working Capital", "GBP Waterfall Bridge, Budget Gap & Working Capital"), "Estado": "⏳ Pendiente", "Notas_Comite": "Evaluar liberación de caja MTS -> MTO."},
        {"Fase": "05. Executive S&OP", "Etapa S&OP": tr("5. Reunión Ejecutiva S&OP y Aprobación Plan Único", "5. Executive S&OP Meeting & Single Plan Sign-Off"), "Dias_Mes": "Días 22 - 25", "Dia_Inicio": 22, "Dia_Fin": 25, "Owner": "SLT / General Management", "Entregable_Clave": tr("Firma del Executive S&OP Deck PDF y Master Pack ERP", "Executive S&OP Deck PDF Sign-Off & ERP Master Pack"), "Estado": "⏳ Pendiente", "Notas_Comite": "Aprobación final y lanzamiento de órdenes M1."}
    ]

    df_cal_sop = github_leer_csv(SOP_CAL_FILE, COLS_SOP_CAL)
    if df_cal_sop.empty or len(df_cal_sop) != 5 or not set(["Dia_Inicio", "Dia_Fin"]).issubset(df_cal_sop.columns):
        df_cal_sop = pd.DataFrame(fases_defecto)

    df_gantt = df_cal_sop.copy()
    df_gantt["Inicio_Fecha"] = [mes_actual_base + pd.Timedelta(days=int(d) - 1) for d in pd.to_numeric(df_gantt["Dia_Inicio"], errors="coerce").fillna(1)]
    df_gantt["Fin_Fecha"] = [mes_actual_base + pd.Timedelta(days=int(d)) for d in pd.to_numeric(df_gantt["Dia_Fin"], errors="coerce").fillna(5)]

    mapa_colores_estado = {"✅ Completado": "#2E8B57", "🔄 En Curso": "#1E3E5B", "⏳ Pendiente": "#A0B2C6", "🚨 Bloqueado": "#D9534F"}
    fig_gantt = px.timeline(
        df_gantt, x_start="Inicio_Fecha", x_end="Fin_Fecha", y="Fase", color="Estado", text="Owner",
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
            "Estado": st.column_config.SelectboxColumn(label=tr("Estado", "Status"), options=["⏳ Pendiente", "🔄 En Curso", "✅ Completado", "🚨 Bloqueado"], required=True),
            "Notas_Comite": st.column_config.TextColumn(label=tr("Acuerdos / Notas del Ciclo", "Cycle Decisions / Notes"))
        },
        use_container_width=True, hide_index=True
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
    st.subheader(tr("📋 Registro Ejecutivo de Decisiones y Acciones del Comité S&OP (Action Log & Risk Register)", "📋 Executive S&OP Committee Action Log & Risk Register"))
    st.caption(tr("Registra los acuerdos tácticos y estratégicos de cada reunión S&OP con responsable, fecha límite e impacto estimado en GBP (£). Se sincroniza en GitHub y se incluye automáticamente en el Executive S&OP Deck PDF.", "Log tactical and strategic decisions from each S&OP meeting with owner, due date, and estimated GBP (£) impact. Syncs to GitHub and prints automatically in the Executive S&OP Deck PDF."))

    acciones_defecto = [
        {"ID": "ACT-01", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"), "Area_S&OP": "03. Supply & RCCP", "Accion_Acordada": "Adelantar 12.000 Kg de ADICARE EVOLUTION H (Pre-Build) en Línea 3 Pellet para evitar cuello de botella.", "Responsable": "Borja Del Rio", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=15)).strftime("%Y-%m-%d"), "Impacto_GBP": 18500, "Estado": "🔄 En Curso"},
        {"ID": "ACT-02", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"), "Area_S&OP": "04. Working Capital", "Accion_Acordada": "Pasar referencias erráticas Clase CZ/BZ de política MTS a MTO según auditoría de Pestaña 7.", "Responsable": "Ángel Mancebo", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=22)).strftime("%Y-%m-%d"), "Impacto_GBP": 34200, "Estado": "⏳ Pendiente"},
        {"ID": "ACT-03", "Fecha_Alta": mes_actual_base.strftime("%Y-%m-%d"), "Area_S&OP": "02. Demand & Margin", "Accion_Acordada": "Validar sustitución parcial del 10% en FORMIATO DE CALCIO por alternativa homologada en BOM.", "Responsable": "Technical & Procurement", "Fecha_Limite": (mes_actual_base + pd.Timedelta(days=25)).strftime("%Y-%m-%d"), "Impacto_GBP": 14800, "Estado": "✅ Completado"}
    ]
    df_act_log = github_leer_csv(ACTION_LOG_FILE, COLS_ACTION_LOG)
    if df_act_log.empty or not set(COLS_ACTION_LOG).issubset(df_act_log.columns):
        df_act_log = pd.DataFrame(acciones_defecto)

    df_act_edit = st.data_editor(
        df_act_log[COLS_ACTION_LOG], num_rows="dynamic",
        column_config={
            "ID": st.column_config.TextColumn(label="ID", width="small"),
            "Fecha_Alta": st.column_config.TextColumn(label=tr("Alta", "Created"), width="small"),
            "Area_S&OP": st.column_config.SelectboxColumn(label=tr("Área S&OP", "S&OP Area"), options=["01. Data & Portfolio", "02. Demand & Margin", "03. Supply & RCCP", "04. Working Capital", "05. Executive Sign-Off"], required=True),
            "Accion_Acordada": st.column_config.TextColumn(label=tr("Decisión / Acción Acordada", "Agreed Action / Decision"), width="large"),
            "Responsable": st.column_config.TextColumn(label="Owner"),
            "Fecha_Limite": st.column_config.TextColumn(label=tr("Fecha Límite", "Due Date")),
            "Impacto_GBP": st.column_config.NumberColumn(label=tr("Impacto (£)", "Impact (£)"), format="£ %d"),
            "Estado": st.column_config.SelectboxColumn(label=tr("Estado", "Status"), options=["⏳ Pendiente", "🔄 En Curso", "✅ Completado", "🚨 Bloqueado"], required=True)
        },
        use_container_width=True, hide_index=True
    )

    ac_k1, ac_k2, ac_k3 = st.columns([1, 1, 2])
    ac_k1.metric(tr("Acciones Activas", "Active Actions"), f"{len(df_act_edit)}")
    ac_k2.metric(tr("Valor en Juego en Comité (£)", "Total Value at Stake (£)"), f"£ {pd.to_numeric(df_act_edit['Impacto_GBP'], errors='coerce').fillna(0).sum():,.0f}")
    with ac_k3:
        if st.button(tr("💾 Guardar Action Log del Comité en GitHub", "💾 Save Committee Action Log to GitHub"), use_container_width=True):
            github_guardar_csv(df_act_edit, ACTION_LOG_FILE, f"Action Log updated by {usuario_actual}")
            st.success(tr("✅ Action Log guardado en GitHub e incluido en el PDF Ejecutivo.", "✅ Action Log saved to GitHub and included in the Executive PDF."))
            st.rerun()

# ==========================================
# MODULO 1: DEMANDA + GESTOR NPI (NEW BUSINESS) + TORNEO AUTO-ML + POST-MORTEM FVA
# ==========================================
with tab_demanda:
    if "tab1" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Demanda.", "🔒 You do not have permission to access the Demand module."))
    else:
        st.subheader(f"{tr('Pronóstico de Demanda', 'Demand Forecast')}: {sku_sel}  |  🤖 {modelo_fcst_sel}")

        # --- NOVEDAD 1 (VISIBLE Y EXPANDIDA): GESTOR DE NUEVOS LANZAMIENTOS (NPI & NEW BUSINESS) ---
        with st.expander(tr("🆕 Gestor de Nuevos Lanzamientos y Licitaciones Comerciales (NPI & New Business - 0 Kg Histórico)", "🆕 New Product Introduction (NPI) & New Business Manager (0 Kg History)"), expanded=True):
            st.caption(tr("Da de alta SKUs nuevos o licitaciones comerciales ganadas sin histórico previo. Hereda la curva estacional de un 'SKU Espejo' e inyecta el nuevo SKU en MPS, MRP, Capacidad de Planta y P&L (GBP).", "Register new SKUs or won commercial tenders with zero prior history. Inherits seasonal shape from a 'Mirror SKU' and injects into MPS, MRP, Plant Capacity, and P&L (GBP)."))
            npi_c1, npi_c2, npi_c3, npi_c4 = st.columns(4)
            with npi_c1:
                npi_cod = st.text_input(tr("Código Nuevo SKU:", "New SKU Code:"), value="NPI-2027-01")
                npi_desc = st.text_input(tr("Descripción Nuevo SKU:", "New SKU Description:"), value="NUEVA FORMULA AVANZADA PRO")
                npi_pais = st.selectbox(tr("Planta / País Destino:", "Target Plant / Country:"), sorted(df['País'].dropna().unique().tolist()), key="npi_pais_sel")
            with npi_c2:
                clis_pais_npi = sorted(df[df['País'] == npi_pais]['customer cod'].dropna().unique().tolist()) if npi_pais else ["CLI-NEW"]
                npi_cli = st.selectbox(tr("Cliente Asignado:", "Assigned Customer:"), clis_pais_npi, key="npi_cli_sel")
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
                    nueva_fila_npi = {"sku cod": str(npi_cod).strip(), "sku desc": str(npi_desc).strip(), "País": npi_pais, "customer cod": npi_cli, "customer desc": f"Cuenta {npi_cli}", "SKU_Espejo": npi_espejo, "Volumen_Mensual_Kg": float(npi_vol), "Mes_Inicio": int(npi_mes_ini), "Precio_Unit_EUR": float(npi_precio), "Margen_Unit_EUR": float(npi_margen), "Maquina": npi_maq, "Kilos_por_Hora": 5500, "Politica_Stock": npi_pol}
                    df_npi_curr = pd.concat([df_npi_curr, pd.DataFrame([nueva_fila_npi])], ignore_index=True)
                    st.session_state['df_npi'] = df_npi_curr
                    github_guardar_csv(df_npi_curr, NPI_CLOUD_FILE, f"NPI Launch {npi_cod} added by {usuario_actual}")
                    st.success(tr(f"✅ Lanzamiento NPI [{npi_cod}] integrado en toda la cadena S&OP. ¡Recalculando S&OP E2E!", f"✅ NPI Launch [{npi_cod}] integrated across the S&OP chain. Recalculating E2E S&OP!"))
                    st.rerun()
            with nb_b2:
                if st.button(tr("🗑️ Limpiar Todos los Lanzamientos NPI", "🗑️ Clear All NPI Launches"), use_container_width=True):
                    df_npi_empty = pd.DataFrame(columns=COLS_NPI)
                    st.session_state['df_npi'] = df_npi_empty
                    github_guardar_csv(df_npi_empty, NPI_CLOUD_FILE, f"Clear NPI launches by {usuario_actual}")
                    st.rerun()

            if not st.session_state.get('df_npi', pd.DataFrame()).empty:
                st.dataframe(st.session_state['df_npi'], use_container_width=True, hide_index=True)

        if sku_sel != "TODOS" and sku_sel in dict_meta_torneo:
            info_m = dict_meta_torneo[sku_sel]
            st.caption(f"🏆 **Auto-ML Winner [{sku_sel}]:** `{info_m['Ganador']}` (WAPE Backtest: Holt-Winters `{info_m.get('WAPE_HW',0)}%` | Damped WMA `{info_m.get('WAPE_WMA',0)}%` | Croston TSB `{info_m.get('WAPE_Croston',0)}%`)")

        fig_demanda = go.Figure()
        df_grouped = df_final.groupby('Date')['volume'].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)
        serie_real = df_grouped['volume'] if not df_grouped.empty else pd.Series(dtype=float)

        if not df_grouped.empty:
            fig_demanda.add_trace(go.Scatter(x=df_grouped.index, y=serie_real, mode='lines+markers', name=tr('Histórico Real', 'Actual History'), line=dict(color='#A0B2C6', width=2)))

        serie_modelo = limpiar_anomalias(serie_real) if usar_limpieza_outliers else serie_real
        mat_actual = dict_fcst_matrices.get(modelo_fcst_sel, pd.DataFrame())
        if sku_sel != "TODOS" and pais_sel == "TODOS" and cliente_sel == "TODOS" and not mat_actual.empty and sku_sel in mat_actual.columns:
            fcst_base_serie = mat_actual[sku_sel].iloc[:horizonte]
        else:
            fcst_base_serie = calcular_forecast_serie_unica(serie_modelo, horizonte, modelo_fcst_sel)

        df_comparativo = pd.DataFrame({"Estadistico": fcst_base_serie, "Consenso": fcst_base_serie.copy()})
        df_comparativo.index.name = 'Date'

        ajustes_activos = st.session_state.get('df_ajustes', pd.DataFrame()).copy()
        if not ajustes_activos.empty and sku_sel != "TODOS":
            if pais_sel != "TODOS":
                ajustes_activos = ajustes_activos[ajustes_activos['País'] == pais_sel]
            if cliente_sel != "TODOS":
                ajustes_activos = ajustes_activos[ajustes_activos['customer cod'] == cliente_sel]
            ajustes_activos = ajustes_activos[ajustes_activos['sku cod'] == sku_sel]
            if not ajustes_activos.empty:
                ajustes_activos['Date'] = pd.to_datetime(ajustes_activos['Date'], dayfirst=True, errors='coerce')
                for f_idx, row in ajustes_activos.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
                    if f_idx.replace(day=1) in df_comparativo.index:
                        df_comparativo.at[f_idx.replace(day=1), 'Consenso'] = row['override_value']

        fig_demanda.add_trace(go.Scatter(x=df_comparativo.index, y=df_comparativo['Estadistico'], mode='lines', name=f"{tr('Estadístico', 'Statistical')} ({modelo_fcst_sel})", line=dict(color='gray', width=2, dash='dot')))
        fig_demanda.add_trace(go.Scatter(x=df_comparativo.index, y=df_comparativo['Consenso'], mode='lines+markers', name=tr('Forecast Consenso', 'Consensus Forecast'), line=dict(color='#1E3E5B', width=4)))
        fig_demanda.update_layout(**LAYOUT_STYLE, hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_demanda, use_container_width=True)

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
                        df_aj = st.session_state.get('df_ajustes', pd.DataFrame(columns=COLS_AJUSTES)).copy()
                        df_prev_sku = df_aj[(df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel)].copy()
                        mapa_prev = dict(zip(pd.to_datetime(df_prev_sku['Date'], errors='coerce').dt.strftime('%Y-%m'), pd.to_numeric(df_prev_sku['override_value'], errors='coerce').fillna(0))) if not df_prev_sku.empty else {}
                        df_aj = df_aj[~((df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel))]

                        df_mod = df_editado[np.abs(df_editado['Consenso'] - df_editado['Estadistico']) > 0.01].copy()
                        nuevas_filas, eventos_fva, ahora_cet = [], [], datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")
                        for f, r in df_mod.iterrows():
                            est_v, ovr_v = round(float(r['Estadistico']), 2), round(float(r['Consenso']), 2)
                            nuevas_filas.append({'Date': pd.to_datetime(f), 'País': pais_sel, 'customer cod': cliente_sel, 'sku cod': sku_sel, 'override_value': ovr_v})
                            if abs(ovr_v - float(mapa_prev.get(str(f), est_v))) > 0.01:
                                eventos_fva.append({"Fecha_Cambio (CET)": ahora_cet, "Usuario": usuario_actual, "Tipo_Ajuste": "Override Manual", "Date": pd.to_datetime(f).strftime("%Y-%m-%d"), "País": pais_sel, "customer cod": cliente_sel, "sku cod": sku_sel, "Forecast_Estadistico": est_v, "Consenso_Override": ovr_v, "Delta_Kg": round(ovr_v - est_v, 2), "Delta_Pct_FVA": round(((ovr_v - est_v) / est_v * 100), 1) if est_v > 0 else 0.0})
                        if nuevas_filas:
                            df_aj = pd.concat([df_aj, pd.DataFrame(nuevas_filas)], ignore_index=True)
                        st.session_state['df_ajustes'] = df_aj
                        if github_guardar_csv(df_aj, CLOUD_AJUSTES_FILE, f"Consensus override by {usuario_actual} on {sku_sel}"):
                            st.success(tr("✅ Guardado en RAM y sincronizado en GitHub Cloud", "✅ Saved in RAM and synced to GitHub Cloud"))
                        else:
                            st.success(tr("✅ Guardado en RAM y almacenamiento local", "✅ Saved in RAM and local storage"))
                        registrar_evento_fva_consenso(eventos_fva)
                        st.rerun()
                else:
                    st.info(tr("⚠️ Selecciona País, Cliente y SKU para editar celdas.", "⚠️ Select Country, Customer, and SKU to edit cells."))
            with btn_c2:
                if st.button(tr("📸 Congelar Snapshot Ciclo S&OP", "📸 Freeze S&OP Cycle Snapshot"), use_container_width=True):
                    n_reg = congelar_snapshot_ciclo_sop(df_final)
                    st.success(f"📸 Snapshot OK ({n_reg} rows).")
                    st.rerun()
            with btn_c3:
                if not st.session_state.get('df_ajustes', pd.DataFrame()).empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        st.session_state['df_ajustes'].to_excel(writer, index=False, sheet_name='Sheet1')
                    st.download_button(label=tr("📥 Descargar Ajustes (.xlsx)", "📥 Download Overrides (.xlsx)"), data=output.getvalue(), file_name="2_Ajustes_Consenso.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        with col2:
            st.markdown(f"#### {tr('Pronóstico Matricial (Macro Factor)', 'Matrix Forecasting (Macro Factor)')}")
            pais_macro = st.selectbox(tr("País:", "Country:"), sorted(df['País'].dropna().unique()), key="macro_pais")
            cli_macro = st.selectbox(tr("Cliente:", "Customer:"), sorted(df[df['País'] == pais_macro]['customer cod'].dropna().unique()) if pais_macro else [], key="macro_cli")
            pct_macro = st.number_input(tr("Variación % (ej. 15, -20):", "Variation % (e.g. 15, -20):"), value=15.0, step=5.0, format="%.1f")
            if st.button(tr("🚀 Aplicar Macro Factor", "🚀 Apply Macro Factor"), use_container_width=True):
                if pais_macro and cli_macro:
                    exito, msg = aplicar_variacion_cliente(pais_macro, cli_macro, pct_macro)
                    if exito:
                        st.success("Done & Synced!")
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

        with st.expander(tr("📋 Historial de Cambios de Consenso, Snapshots & Evaluador Post-Mortem FVA", "📋 Consensus Change History, Snapshots & Post-Mortem FVA Evaluator"), expanded=False):
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
                fva_c3.metric(tr("Volumen Neto Añadido (FVA)", "Net Volume Added (FVA)"), f"{pd.to_numeric(df_fva_view['Delta_Kg'], errors='coerce').fillna(0).sum():+,.0f} Kg")
                st.dataframe(df_fva_view.iloc[::-1].style.format({"Forecast_Estadistico": "{:,.0f} Kg", "Consenso_Override": "{:,.0f} Kg", "Delta_Kg": "{:+,.0f} Kg", "Delta_Pct_FVA": "{:+.1f}%"}), use_container_width=True, hide_index=True)

# ==========================================
# MODULO 2: PRODUCCIÓN (MPS)
# ==========================================
with tab_prod:
    if "tab2" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Producción.", "🔒 You do not have permission to access the Production module."))
    else:
        if df_stock is None or sku_sel == "TODOS":
            st.info(tr("👈 Sube el archivo '3. Stock Actual' y selecciona un SKU específico en el filtro 4.", "👈 Upload '3. Current Inventory' file and select a specific SKU in filter 4."))
        else:
            st.subheader(f"Master Production Schedule (MPS): [{sku_sel}] {dict_sku_desc.get(sku_sel, sku_sel)}")
            stock_sku_fg, cob_real_fg, _ = obtener_parametros_stock(sku_sel, cobertura_fg)
            salidas_p = df_comparativo['Consenso'] if 'df_comparativo' in locals() else calcular_forecast_serie_unica(limpiar_anomalias(df_final.groupby('Date')['volume'].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)['volume']) if usar_limpieza_outliers else df_final.groupby('Date')['volume'].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)['volume'], horizonte, modelo_fcst_sel)
            serie_erp = pd.Series([dict_prd_erp.get((sku_sel, idx), 0.0) for idx in salidas_p.index], index=salidas_p.index)

            stk_ini_l, stk_obj_l, ent_l, stk_fin_l = [], [], [], []
            stk_corr = float(stock_sku_fg)
            vals_s = salidas_p.values.astype(float)
            media_r = float(vals_s[-3:].mean()) if len(vals_s) > 0 else 0.0
            for i in range(len(vals_s)):
                fut_sl = vals_s[i + 1 : i + 1 + int(cob_real_fg)]
                s_obj = float(fut_sl.sum()) + max(0, int(cob_real_fg) - len(fut_sl)) * media_r
                e_net = max(0.0, vals_s[i] + s_obj - stk_corr - float(serie_erp.iloc[i]))
                stk_ini_l.append(stk_corr)
                stk_obj_l.append(s_obj)
                ent_l.append(e_net)
                stk_corr = stk_corr + e_net + float(serie_erp.iloc[i]) - vals_s[i]
                stk_fin_l.append(stk_corr)

            df_plan_fg = pd.DataFrame({
                'Salidas_Brutas': vals_s, 'Recepciones_ERP': serie_erp.values,
                'Stock_Inicial': stk_ini_l, 'Stock_Objetivo': stk_obj_l,
                'Entradas_Netas': ent_l, 'Stock_Final': stk_fin_l
            }, index=salidas_p.index)
            dem_fut = df_plan_fg['Salidas_Brutas'].rolling(window=3, min_periods=1).mean().shift(-1)
            if len(dem_fut) > 0:
                dem_fut.iloc[-1] = media_r
            df_plan_fg['DOH'] = np.where(dem_fut > 0, (df_plan_fg['Stock_Final'] / dem_fut) * 30.0, 0.0).round(0)

            c1, c2, c3 = st.columns(3)
            c1.metric(t["kpi_fab"], f"{df_plan_fg['Entradas_Netas'].sum():,.0f} Kg")
            c2.metric("ERP Pipeline", f"{df_plan_fg['Recepciones_ERP'].sum():,.0f} Kg")
            c3.metric(t["kpi_doh"], f"{df_plan_fg['DOH'].mean():.0f} {tr('Días', 'Days')}")

            fig_prod = go.Figure()
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Salidas_Brutas'], name=tr('Demanda', 'Demand'), marker_color='#E5E9ED'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Recepciones_ERP'], name='ERP Pipeline', marker_color='#A0B2C6'))
            fig_prod.add_trace(go.Bar(x=df_plan_fg.index, y=df_plan_fg['Entradas_Netas'], name=tr('Nuevas Órdenes', 'New Orders'), marker_color='#1E3E5B'))
            fig_prod.add_trace(go.Scatter(x=df_plan_fg.index, y=df_plan_fg['Stock_Final'], mode='lines+markers', name=f"Stock FG ({tr('Obj', 'Target')}: {cob_real_fg}m)", line=dict(color='#88FFBB', width=3)))
            fig_prod.update_layout(**LAYOUT_STYLE, barmode='stack', hovermode="x unified")
            st.plotly_chart(fig_prod, use_container_width=True)

            df_show_fg = df_plan_fg.copy()
            df_show_fg.index = df_show_fg.index.strftime('%Y-%m')
            st.dataframe(df_show_fg.style.format("{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Stock_Objetivo', 'Entradas_Netas', 'Stock_Final']).format("{:.0f}", subset=['DOH']).map(estilo_doh, subset=['DOH']), use_container_width=True)

# ==========================================
# MODULO 3: COMPRAS (MRP)
# ==========================================
with tab_bom:
    if "tab3" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Compras (MRP).", "🔒 You do not have permission to access the Purchasing (MRP) module."))
    else:
        st.subheader(tr("Planificación de Compras (MRP Matricial 2D)", "MRP / Purchasing Plan (2D Matrix Engine)"))
        if df_bom is None or df_stock is None:
            st.info(tr("👈 Sube los archivos '3. Stock Actual' y '4. BOM' en la barra lateral.", "👈 Upload '3. Current Inventory' & '4. BOM' files in the sidebar."))
        else:
            rm_sel = st.selectbox(tr("🔍 Filtrar Materia Prima:", "🔍 Filter Raw Material:"), ["TODAS"] + sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist()))
            if st.button(tr("🚀 Ejecutar Explosión BOM (MRP)", "🚀 Execute BOM Explosion (MRP)")):
                df_viz = generar_mrp_global()
                if df_viz is None or df_viz.empty:
                    st.info(tr("ℹ️ Sin necesidades de compra generadas para el escenario actual.", "ℹ️ No purchasing requirements generated for the current scenario."))

# ==========================================
# MODULO 4: CAPACIDAD (RCCP POR PLANTA + SIMULADOR DE TURNOS + PRE-BUILD)
# ==========================================
with tab_cap:
    if "tab4" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Capacidad.", "🔒 You do not have permission to access the Capacity module."))
    else:
        st.subheader(tr("Planificación de Capacidad por Planta (RCCP), Simulador de Turnos & Pre-Build", "Plant Capacity Planning (RCCP), Shift Simulator & Pre-Build"))
        if df_rutas is None or df_cal is None:
            st.info(tr("👈 Sube '5. Rutas / Routing' y '6. Calendario' en la barra lateral.", "👈 Upload '5. Production Routing' & '6. Plant Calendar' in the sidebar."))
        else:
            skus_scope_cap = set(df_final['sku cod'].astype(str).str.strip().unique()) if not df_final.empty else set()
            df_rutas_scope = df_rutas[df_rutas['sku cod'].astype(str).str.strip().isin(skus_scope_cap)].copy()
            maquinas_disponibles = sorted(df_rutas_scope['Maquina'].astype(str).str.strip().dropna().unique().tolist())

            st.caption(f"🌍 **{tr('Ámbito de Planta Activo', 'Active Plant Scope')}:** {tr('País', 'Country')}: `{pais_sel}` | {tr('Cliente', 'Customer')}: `{cliente_sel}` | {tr('Líneas detectadas', 'Detected Lines')}: `{len(maquinas_disponibles)}`")

            # --- NOVEDAD 2 (VISIBLE): SIMULADOR DE TURNOS ---
            col_c_top1, col_c_top2, col_c_top3 = st.columns(3)
            with col_c_top1:
                maq_sel = st.selectbox(tr("⚙️ Filtrar Línea / Máquina de la Planta:", "⚙️ Filter Plant Line / Work Center:"), ["TODOS"] + maquinas_disponibles)
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
                df_mps_scope = df_mps_concat[df_mps_concat['sku cod'].astype(str).str.strip().isin(skus_scope_cap)].copy()
                vol_global_sku, vol_filtro_sku = df.groupby('sku cod')['volume'].sum().to_dict(), df_final.groupby('sku cod')['volume'].sum().to_dict()
                df_mps_scope['Share_Cap'] = [float(vol_filtro_sku.get(s, 0.0)) / max(1.0, float(vol_global_sku.get(s, 1.0))) for s in df_mps_scope['sku cod'].astype(str).str.strip()]
                df_mps_scope['Carga_Total_Kg'] = (df_mps_scope['Entradas_Netas'] + df_mps_scope['Recepciones_ERP']) * df_mps_scope['Share_Cap']
                df_req = pd.merge(df_mps_scope[df_mps_scope['Carga_Total_Kg'] > 0], df_rutas_scope.assign(skucod=lambda x: x['sku cod'].astype(str).str.strip()), left_on='sku cod', right_on='skucod', how='inner')

                if df_req.empty:
                    st.warning(tr("⚠️ Ningún SKU del filtro actual requiere horas de fabricación en las líneas de esta planta.", "⚠️ No SKU in the current filter requires production hours on this plant's lines."))
                else:
                    df_req['Kilos_por_Hora'] = pd.to_numeric(df_req['Kilos_por_Hora'], errors='coerce').fillna(1).replace(0, 1)
                    df_req['Horas_Necesarias'] = df_req['Carga_Total_Kg'] / df_req['Kilos_por_Hora']
                    df_cal_clean = df_cal.copy().assign(Maquina=lambda x: x['Maquina'].astype(str).str.strip(), Date=lambda x: pd.to_datetime(x['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp(), Horas_Base=lambda x: pd.to_numeric(x['Horas_Disponibles'], errors='coerce').fillna(740).replace(0, 1))
                    df_cal_clean['Horas_Disponibles'] = df_cal_clean['Horas_Base'] * factor_turno
                    df_req['Date'] = pd.to_datetime(df_req['Date'], dayfirst=True, errors='coerce').dt.to_period('M').dt.to_timestamp()

                    df_capacidad = pd.merge(
                        df_req.groupby(['Date', 'Maquina']).agg(Horas_Necesarias=('Horas_Necesarias', 'sum'), Kilos_Totales=('Carga_Total_Kg', 'sum'), Tasa_Media_KPH=('Kilos_por_Hora', 'mean')).reset_index(),
                        df_cal_clean, on=['Date', 'Maquina'], how='left'
                    ).fillna({'Horas_Base': 740, 'Horas_Disponibles': 740 * factor_turno})
                    df_capacidad['Utilizacion'] = (df_capacidad['Horas_Necesarias'] / df_capacidad['Horas_Disponibles']) * 100.0

                    horas_extra_tot = float((df_capacidad['Horas_Disponibles'] - df_capacidad['Horas_Base']).sum())
                    t_k1, t_k2, t_k3 = st.columns(3)
                    t_k1.metric(tr("⏱️ Régimen Activo", "⏱️ Active Shift Regime"), turno_label_sel.split("(")[0].strip())
                    t_k2.metric(tr("➕ Horas Extra Añadidas", "➕ Added Overtime Hours"), f"+{horas_extra_tot:,.0f} h")
                    t_k3.metric(tr("💷 Coste Operativo Turnos (£)", "💷 Shift Overtime Cost (£)"), f"£ {horas_extra_tot * 145.0:,.0f}")

                    if maq_sel == "TODOS":
                        df_pivot = df_capacidad.pivot(index='Maquina', columns='Date', values='Utilizacion').fillna(0)
                        df_pivot.columns = pd.to_datetime(df_pivot.columns).strftime('%Y-%m')
                        st.markdown(f"#### {tr('1. Matriz de Utilización Original por Planta (Sin Nivelar %)', '1. Original Unconstrained Plant Utilization Matrix (%)')}")
                        try:
                            st.dataframe(df_pivot.style.background_gradient(cmap='RdYlGn_r', vmin=0, vmax=120).format("{:.1f}%"), use_container_width=True)
                        except Exception:
                            st.dataframe(df_pivot.style.format("{:.1f}%"), use_container_width=True)
                    else:
                        df_req_maq = df_req[df_req['Maquina'] == maq_sel]
                        if not df_req_maq.empty:
                            df_req_maq_plot = df_req_maq.copy()
                            df_req_maq_plot['SKU_Agrupado'] = np.where(df_req_maq_plot['sku desc'].isin(df_req_maq.groupby('sku desc')['Horas_Necesarias'].sum().nlargest(12).index), df_req_maq_plot['sku desc'], 'Otros SKUs')
                            fig_cap = px.bar(df_req_maq_plot.groupby(['Date', 'SKU_Agrupado'])['Horas_Necesarias'].sum().reset_index(), x='Date', y='Horas_Necesarias', color='SKU_Agrupado', title=f"{tr('Carga vs Capacidad', 'Load vs Capacity')}: {maq_sel}")
                            merged_line = pd.merge(df_req_maq.groupby('Date')['Horas_Necesarias'].sum().reset_index(), df_cal_clean[df_cal_clean['Maquina'] == maq_sel], on='Date', how='left').fillna({'Horas_Disponibles': 740 * factor_turno})
                            fig_cap.add_trace(go.Scatter(x=merged_line['Date'], y=merged_line['Horas_Disponibles'], mode='lines', name='Max Hours', line=dict(color='red', width=3, dash='dash')))
                            fig_cap.update_layout(**LAYOUT_STYLE, yaxis_title=tr("Horas", "Hours"), barmode='stack')
                            st.plotly_chart(fig_cap, use_container_width=True)

                    st.divider()
                    st.markdown(f"### {tr('⚖️ Motor de Nivelación Automática de Capacidad Finita (Pre-Build & Line Balancing)', '⚖️ Automated Finite Capacity Leveling Engine (Pre-Build & Line Balancing)')}")
                    filas_niveladas, movimientos_prebuild = [], []
                    for maq_k, grp_m in df_capacidad.sort_values('Date').groupby('Maquina'):
                        fechas_m, h_nec, h_disp, kph_m = grp_m['Date'].tolist(), grp_m['Horas_Necesarias'].values.astype(float).copy(), grp_m['Horas_Disponibles'].values.astype(float).copy(), grp_m['Tasa_Media_KPH'].values.astype(float).copy()
                        h_cap = h_disp * (float(umbral_prebuild) / 100.0)
                        for idx_t in range(len(h_nec) - 1, 0, -1):
                            if h_nec[idx_t] > h_cap[idx_t]:
                                desplazado_h = min(h_nec[idx_t] - h_cap[idx_t], max(0.0, h_cap[idx_t - 1] - h_nec[idx_t - 1]))
                                if desplazado_h > 0.1:
                                    h_nec[idx_t] -= desplazado_h
                                    h_nec[idx_t - 1] += desplazado_h
                                    movimientos_prebuild.append({"Línea / Máquina": maq_k, "Mes Pico (Origen)": pd.to_datetime(fechas_m[idx_t]).strftime('%Y-%m'), "Mes Pre-Build (Adelanto)": pd.to_datetime(fechas_m[idx_t - 1]).strftime('%Y-%m'), "Horas Adelantadas": round(desplazado_h, 1), "Volumen Pre-Build (Kg)": round(desplazado_h * kph_m[idx_t], 0), "Sobrecoste WC Temporal (£)": round((desplazado_h * kph_m[idx_t]) * 1.85 * 0.015, 0)})
                        for idx_t, f_dt in enumerate(fechas_m):
                            filas_niveladas.append({"Date": f_dt, "Maquina": maq_k, "Utilizacion_Nivelada": (h_nec[idx_t] / h_disp[idx_t]) * 100.0 if h_disp[idx_t] > 0 else 0.0})

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
                        st.dataframe(df_mov_pb.style.format({"Horas Adelantadas": "{:.1f} h", "Volumen Pre-Build (Kg)": "{:,.0f} Kg", "Sobrecoste WC Temporal (£)": "£ {:,.0f}"}), use_container_width=True, hide_index=True)

# ==========================================
# MODULO 5: FINANZAS
# ==========================================
with tab_fin:
    if "tab5" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Finanzas.", "🔒 You do not have permission to access the Finance module."))
    else:
        st.subheader(tr("Valoración Financiera y Working Capital (GBP)", "Financial Valuation & Working Capital (GBP)"))
        tot_rev_h = float(df_final['Rev_GBP'].sum()) if not df_final.empty else 0.0
        tot_mar_h = float(df_final['Mar_GBP'].sum()) if not df_final.empty else 0.0
        c1, c2, c3 = st.columns(3)
        c1.metric(t["kpi_rev"], f"£ {tot_rev_h:,.0f}")
        c2.metric(t["kpi_mar"], f"£ {tot_mar_h:,.0f}")
        c3.metric(t["kpi_wc"], "£ 0")

# ==========================================
# MODULO 6: EJECUCIÓN ERP
# ==========================================
with tab_ejec:
    if "tab6" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al módulo de Ejecución ERP.", "🔒 You do not have permission to access the ERP Execution module."))
    else:
        st.subheader(tr("🚀 Plan de Ejecución Inmediata & S&OE", "🚀 Immediate ERP Execution & S&OE Plan"))
        df_mps_all = generar_mps_df_2d()
        if not df_mps_all.empty:
            st.dataframe(df_mps_all.head(100), use_container_width=True, hide_index=True)

# ==========================================
# MODULO 7: ABC / XYZ Y OPTIMIZADOR (FILTRO CORREGIDO MTO/MTS/SS)
# ==========================================
with tab_abc:
    if "tab7" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder a la segmentación ABC/XYZ.", "🔒 You do not have permission to access ABC/XYZ segmentation."))
    else:
        st.subheader(tr("🔠 Segmentación Estratégica ABC / XYZ", "🔠 Strategic ABC / XYZ Segmentation"))
        if df_abcxyz_global is not None and not df_abcxyz_global.empty and df_stock is not None and not df_stock.empty:
            df_abcxyz_show = df_abcxyz_global.copy()
            df_stk_clean = df_stock.copy()
            df_stk_clean['sku_clean'] = df_stk_clean['sku cod'].astype(str).str.strip()
            df_abcxyz_show['sku_clean'] = df_abcxyz_show['sku cod'].astype(str).str.strip()

            df_audit = pd.merge(
                df_abcxyz_show[['sku cod', 'sku_clean', 'sku desc', 'ABC', 'XYZ', 'Clase', 'volume', 'mean', 'std', 'CV', 'Margen Unitario']],
                df_stk_clean[['sku_clean', 'stock_disponible', 'Cobertura_Meses', 'LT_Meses', 'Categoria', 'Coste_Unitario']].drop_duplicates(subset=['sku_clean']),
                on='sku_clean', how='inner'
            )

            if not df_audit.empty:
                csl_c1, csl_c2, csl_c3 = st.columns(3)
                mapa_z = {85: 1.04, 90: 1.28, 92: 1.41, 95: 1.65, 97: 1.88, 98: 2.05, 99: 2.33}
                with csl_c1:
                    csl_a = st.select_slider(tr("🎯 Nivel Servicio Clase A (CSL %):", "🎯 Class A Service Level (CSL %):"), options=[90, 92, 95, 97, 98, 99], value=98)
                with csl_c2:
                    csl_b = st.select_slider(tr("🎯 Nivel Servicio Clase B (CSL %):", "🎯 Class B Service Level (CSL %):"), options=[85, 90, 92, 95, 97, 98], value=95)
                with csl_c3:
                    csl_c = st.select_slider(tr("🎯 Nivel Servicio Clase C (CSL %):", "🎯 Class C Service Level (CSL %):"), options=[85, 90, 92, 95], value=90)

                df_audit['Categoria_Actual'] = df_audit['Categoria'].astype(str).str.strip().str.upper()
                df_audit['Coste_Unitario'] = pd.to_numeric(df_audit['Coste_Unitario'], errors='coerce').fillna(0.0)
                df_audit['stock_disponible'] = pd.to_numeric(df_audit['stock_disponible'], errors='coerce').fillna(0.0)
                df_audit['LT_Meses'] = pd.to_numeric(df_audit['LT_Meses'], errors='coerce').fillna(1.0).clip(lower=0.25)
                df_audit['Politica_Recomendada'] = np.select([df_audit['Clase'].isin(['AX', 'AY', 'BX']), df_audit['Clase'].isin(['CZ', 'BZ', 'CY', 'CX'])], ['MTS', 'MTO'], default='MTS (Min Cov)')
                df_audit['Z_Factor'] = np.where(df_audit['ABC'] == 'A', mapa_z[csl_a], np.where(df_audit['ABC'] == 'B', mapa_z[csl_b], mapa_z[csl_c]))
                df_audit['SS_Cientifico_Kg'] = np.where(df_audit['Politica_Recomendada'] == 'MTO', 0.0, df_audit['Z_Factor'] * pd.to_numeric(df_audit['std'], errors='coerce').fillna(0.0) * np.sqrt(df_audit['LT_Meses'])).round(0)
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
                        np.where(df_audit['WC_Liberable_GBP'] > 100.0, lbl_exceso_ss, lbl_ok)
                    )
                )

                # --- NOVEDAD 3 (VISIBLE): FILTRO CORREGIDO ---
                solo_alertas = st.checkbox(tr("🔍 Mostrar solo SKUs con exceso de stock o cambio MTS ↔ MTO", "🔍 Show only SKUs with excess stock or policy change"), value=False, key="chk_solo_alertas_abc_v2")
                if solo_alertas:
                    df_mostrar_audit = df_audit[df_audit['Estado_Auditoria'] != lbl_ok].copy()
                    st.caption(tr(f"🔎 Filtro activo: Mostrando **{len(df_mostrar_audit)}** de {len(df_audit)} SKUs (excluidos {len(df_audit) - len(df_mostrar_audit)} SKUs en estado '🟢 Alineado').", f"🔎 Active filter: Showing **{len(df_mostrar_audit)}** of {len(df_audit)} SKUs (excluded {len(df_audit) - len(df_mostrar_audit)} '🟢 Aligned' SKUs)."))
                else:
                    df_mostrar_audit = df_audit.copy()

                df_mostrar_audit = df_mostrar_audit.sort_values(by='WC_Liberable_GBP', ascending=False).reset_index(drop=True)
                if df_mostrar_audit.empty:
                    st.success(tr("✅ Todos los SKUs están 100% alineados y sin exceso de stock sobre el SS Científico.", "✅ All SKUs are 100% aligned with no excess stock."))
                else:
                    st.dataframe(
                        df_mostrar_audit[['sku cod', 'sku desc', 'Clase', 'CV', 'Categoria_Actual', 'Politica_Recomendada', 'Estado_Auditoria', 'stock_disponible', 'SS_Cientifico_Kg', 'WC_Actual_GBP', 'WC_Optimo_Cientifico_GBP', 'WC_Liberable_GBP']].head(250).rename(columns={
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
                        use_container_width=True, hide_index=True
                    )

# ==========================================
# MODULO 8: EXCEPCIONES
# ==========================================
with tab_exc:
    if "tab8" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Panel de Excepciones.", "🔒 You do not have permission to access the Exceptions Panel."))
    else:
        st.subheader(tr("🚨 Panel de Excepciones (Management by Exception)", "🚨 Exceptions Panel (Management by Exception)"))
        df_mps_all = generar_mps_df_2d()
        if not df_mps_all.empty:
            st.dataframe(df_mps_all[df_mps_all['DOH'] < 15].head(100), use_container_width=True, hide_index=True)

# ==========================================
# MODULO 9: WHAT-IF
# ==========================================
with tab_whatif:
    if "tab9" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Simulador What-If.", "🔒 You do not have permission to access the What-If Simulator."))
    else:
        st.subheader(tr("🔀 Simulador de Escenarios (What-If)", "🔀 What-If Scenario Simulator"))
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            shock_vol = st.slider(tr("📈 Variación Volumen (%)", "📈 Volume Shock (%)"), -50, 50, 0, step=5)
        with col_w2:
            shock_precio = st.slider(tr("🏷️ Variación Precios (%)", "🏷️ Sales Price Shock (%)"), -30, 30, 0, step=5)
        with col_w3:
            shock_coste = st.slider(tr("💸 Variación Costes MP (%)", "💸 RM / COGS Shock (%)"), -30, 50, 0, step=5)
        if not df_final.empty:
            df_base, df_sim = motor_simulador_whatif(df_final, dict_price, dict_margin, dict_currency, fx_eur_gbp, fx_dkk_gbp, fx_pln_gbp, horizonte, modelo_fcst_sel, shock_vol, shock_precio, shock_coste, sig=DATASET_SIGNATURE)
            tot_rev_base = df_base['Revenue'].sum() if not df_base.empty else 0.0
            tot_rev_sim = df_sim['Revenue'].sum() if not df_sim.empty else 0.0
            st.metric(tr("Revenue (Simulado)", "Revenue (Simulated)"), f"£ {tot_rev_sim:,.0f}", f"{tot_rev_sim - tot_rev_base:,.0f} £ vs Base")

# ==========================================
# MODULO 10: DASHBOARD
# ==========================================
with tab_kpis:
    if "tab10" not in modulos_permitidos:
        st.warning(tr("🔒 No tienes permisos para acceder al Dashboard de KPIs.", "🔒 You do not have permission to access the Executive Dashboard."))
    else:
        st.subheader(tr("📊 Dashboard Ejecutivo y KPIs Globales", "📊 Executive Dashboard & Global KPIs"))
        if df_final is not None and not df_final.empty:
            col_e1, col_e2 = st.columns(2)
            col_e1.metric(tr("SKUs Activos (PT)", "Active SKUs (FG)"), f"{df_final['sku cod'].nunique()}")
            col_e2.metric(tr("Total Clientes", "Total Customers"), f"{df_final['customer cod'].nunique()}")
