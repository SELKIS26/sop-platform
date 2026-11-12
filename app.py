import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io
import qrcode
import warnings
import streamlit_authenticator as stauth

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
        /* 1. Reduce los espacios laterales y superiores de la app */
        .block-container {
            padding-top: 1.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        /* 2. Hace las tarjetas de KPIs (Revenue, DOH) más finas */
        div[data-testid="metric-container"] {
            padding: 10px 10px !important;
        }
        /* 3. Reduce el tamaño de los números grandes de los KPIs */
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
        }
        /* 4. Ajusta las pestañas (tabs) para que el texto quepa mejor */
        button[data-baseweb="tab"] {
            font-size: 0.9rem !important;
            padding: 5px 10px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

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

# Encriptación automática
stauth.Hasher.hash_passwords(credenciales)

authenticator = stauth.Authenticate(
    credentials=credenciales,
    cookie_name="sop_abagri_token",
    key="abcdef12345", 
    cookie_expiry_days=30
)

authenticator.login("main")

if st.session_state["authentication_status"] is False:
    st.error("❌ Usuario o contraseña incorrectos")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("🔒 Por favor, introduce tus credenciales para acceder a la plataforma S&OP")
    st.stop()
elif st.session_state["authentication_status"]:
    
    usuario_actual = st.session_state["username"]
    
    # --- SISTEMA DE PERMISOS (ROLES) ---
    # tab0: Guía | tab1: Demanda | tab2: Producción | tab3: Compras
    # tab4: Capacidad | tab5: Finanzas | tab6: Ejecución
PERMISOS = {
        "amancebo": ["tab0", "tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7", "tab8", "tab9"], 
        "borja": ["tab0", "tab2"] 
    }
    modulos_permitidos = PERMISOS.get(usuario_actual, ["tab0"])
    
    with st.sidebar:
        st.markdown(f"👤 **Bienvenido/a, {st.session_state['name']}**")
        if usuario_actual == "borja":
            st.caption("🔹 Rol: Manager de Producción")
        else:
            st.caption("🔹 Rol: Administrador Global")
            
        authenticator.logout("Cerrar Sesión", "main")
        st.divider()
        
with st.sidebar.expander("📲 Compartir App (QR)"):
        st.caption("Escanea para entrar desde móvil:")
        enlace_app = "https://sop-mancew.streamlit.app/"
        img_qr = qrcode.make(enlace_app)
        buf = io.BytesIO()
        img_qr.save(buf, format="PNG")
        st.image(buf.getvalue(), use_container_width=True)

# ==========================================
# 0. DICCIONARIO DE IDIOMAS 
# ==========================================
LANGUAGES = ["Español", "English", "Polski", "Dansk"]
TEXTS = {
    "Español": {
        "title": "S&OP Execution & Planning Platform",
        "sidebar_lang": "🌐 Idioma / Language",
        "tab0": "📖 0. Guía", "tab1": "📊 1. Demanda", "tab2": "🏭 2. Producción", 
        "tab3": "🧩 3. Compras", "tab4": "⚙️ 4. Capacidad", "tab5": "💷 5. Finanzas", "tab6": "🚀 6. Ejecución ERP","tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Excepciones", "tab9": "🔀 9. What-If",
        "kpi_rev": "Ingresos (Revenue)", "kpi_mar": "Margen Bruto", "kpi_wc": "Working Capital Promedio",
        "kpi_fab": "Volumen a Fabricar", "kpi_doh": "Cobertura Media",
        "guide_title": "📖 Plataforma S&OP Corporativa (Estándar APICS)",
        "guide_desc": "El simulador cuenta ahora con un motor MRP integrado. Módulos:",
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
        "tab3": "🧩 3. Purchasing", "tab4": "⚙️ 4. Capacity", "tab5": "💷 5. Finance", "tab6": "🚀 6. ERP Execution","tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If",
        "kpi_rev": "Total Revenue", "kpi_mar": "Gross Margin", "kpi_wc": "Avg Working Capital",
        "kpi_fab": "Volume to Produce", "kpi_doh": "Avg Days on Hand",
        "guide_title": "📖 Corporate S&OP Platform (APICS Standard)",
        "guide_desc": "The simulator now runs a full integrated MRP engine. Modules:",
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
        "tab3": "🧩 3. Zakupy", "tab4": "⚙️ 4. Zdolności", "tab5": "💷 5. Finanse", "tab6": "🚀 6. Realizacja ERP","tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If",
        "kpi_rev": "Przychody", "kpi_mar": "Marża Brutto", "kpi_wc": "Śr. Kapitał Obrotowy",
        "kpi_fab": "Wolumen do Produkcji", "kpi_doh": "Średnie Pokrycie",
        "guide_title": "📖 Przewodnik (Standard APICS)",
        "guide_desc": "Symulator posiada pełny silnik MRP. Moduły:",
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
        "tab3": "🧩 3. Indkøb", "tab4": "⚙️ 4. Kapacitet", "tab5": "💷 5. Økonomi", "tab6": "🚀 6. ERP Udførelse","tab7": "🔠 7. ABC/XYZ", "tab8": "🚨 8. Exceptions", "tab9": "🔀 9. What-If",
        "kpi_rev": "Omsætning", "kpi_mar": "Bruttomargin", "kpi_wc": "Gns. Arbejdskapital",
        "kpi_fab": "Produktionsvolumen", "kpi_doh": "Gns. Dækning",
        "guide_title": "📖 Værktøjsguide (APICS Standard)",
        "guide_desc": "Simulatoren kører en fuld integreret MRP. Moduler:",
        "g_dem_t": "1. Efterspørgsel", "g_dem_d": "Holt-Winters. Manuelle justeringer prioriteres.",
        "g_pro_t": "2. Produktion (MPS)", "g_pro_d": "Absorberer ERP-ordrer. `Nye Ordrer = Behov + Mållager - Startlager - ERP-ordrer`.",
        "g_com_t": "3. Indkøb (MRP)", "g_com_d": "Eksploderer nye produktionsordrer. Absorberer ERP indkøbsordrer. Inkluderer Pegging.",
        "g_cap_t": "4. Kapacitet", "g_cap_d": "Konverterer kilo til timer og krydser mod kalendere.",
        "g_fin_t": "5. Økonomi", "g_fin_d": "Omsætning og Arbejdskapital i GBP.",
        "g_erp_t": "6. Udførelse", "g_erp_d": "Handlingsplan for Måned 1 med de ordrer, der skal udstedes."
    }
}

if 'lang' not in st.session_state: st.session_state['lang'] = 'Español'

with st.sidebar:
    st.markdown("### 🏢 **ManceW Supply Chain**")
    st.divider()
    st.session_state['lang'] = st.selectbox(TEXTS[st.session_state['lang']]["sidebar_lang"], LANGUAGES, index=LANGUAGES.index(st.session_state['lang']))
    
t = TEXTS[st.session_state['lang']]
st.title(t["title"])

# ==========================================
# 1. CONFIGURACIÓN Y CARGA DE ARCHIVOS
# ==========================================
with st.sidebar:
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
    
    st.divider()
    st.header("📅 3. Parameters")
    horizonte = st.slider("Horizon (Months):", 1, 24, 12)
    cobertura_fg = st.slider("Cov. PT (Months):", 0, 6, 1)
    cobertura_rm = st.slider("Cov. MP (Months):", 0, 6, 2)
    
    # Ocultamos opciones financieras si el usuario no tiene acceso a Finanzas
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

@st.cache_data(ttl=300) 
def cargar_datos(uploaded_file):
    if uploaded_file is None: return None
    try:
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'): d = pd.read_csv(uploaded_file)
        else: d = pd.read_excel(uploaded_file)
        if d is not None and not d.empty: d.columns = d.columns.str.strip()
        return d
    except Exception: return None

if 'df_ajustes' not in st.session_state: st.session_state['df_ajustes'] = pd.DataFrame(columns=['Date', 'País', 'customer cod', 'sku cod', 'override_value'])
if 'last_ajuste_file' not in st.session_state: st.session_state['last_ajuste_file'] = None

df = cargar_datos(file_hist)
if file_ajustes is not None and file_ajustes != st.session_state['last_ajuste_file']:
    st.session_state['df_ajustes'] = cargar_datos(file_ajustes)
    st.session_state['last_ajuste_file'] = file_ajustes

df_ajustes = st.session_state['df_ajustes']
df_stock, df_bom, df_rutas, df_cal = cargar_datos(file_stock), cargar_datos(file_bom), cargar_datos(file_rutas), cargar_datos(file_cal)
df_compras_erp, df_produccion_erp = cargar_datos(file_compras_erp), cargar_datos(file_produccion_erp)

if df is None or df.empty:
    st.info("👋 **Please upload '1. Histórico Ventas' in the sidebar to start.**")
    st.stop()

df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df = df.dropna(subset=['Date'])
if 'volume' in df.columns: df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)

dict_price, dict_margin, dict_currency = {}, {}, {}
if 'revenue' in df.columns and 'margin' in df.columns:
    df_fin_base = df.groupby('sku cod').agg({'volume':'sum', 'revenue':'sum', 'margin':'sum', 'currency':'first'}).reset_index()
    df_fin_base['unit_price'] = np.where(df_fin_base['volume']>0, df_fin_base['revenue']/df_fin_base['volume'], 0)
    df_fin_base['unit_margin'] = np.where(df_fin_base['volume']>0, df_fin_base['margin']/df_fin_base['volume'], 0)
    dict_price = dict(zip(df_fin_base['sku cod'], df_fin_base['unit_price']))
    dict_margin = dict(zip(df_fin_base['sku cod'], df_fin_base['unit_margin']))
    dict_currency = dict(zip(df_fin_base['sku cod'], df_fin_base['currency']))

# ==========================================
# 2. MOTOR ABC/XYZ Y FILTROS EN CASCADA
# ==========================================
@st.cache_data(ttl=300)
def calcular_abc_xyz_global(df_in):
    if df_in is None or df_in.empty or 'volume' not in df_in.columns: return pd.DataFrame()
    df_vol = df_in.groupby('sku cod')['volume'].sum().reset_index().sort_values('volume', ascending=False)
    if df_vol['volume'].sum() == 0: return pd.DataFrame()
    df_vol['cum_pct'] = df_vol['volume'].cumsum() / df_vol['volume'].sum()
    df_vol['ABC'] = np.where(df_vol['cum_pct'] <= 0.8, 'A', np.where(df_vol['cum_pct'] <= 0.95, 'B', 'C'))
    df_mes = df_in.groupby(['sku cod', pd.Grouper(key='Date', freq='MS')])['volume'].sum().reset_index()
    df_cv = df_mes.groupby('sku cod')['volume'].agg(['mean', 'std']).reset_index()
    df_cv['CV'] = df_cv['std'] / df_cv['mean'].replace(0, 1)
    df_cv['XYZ'] = np.where(df_cv['CV'] <= 0.5, 'X', np.where(df_cv['CV'] <= 1.0, 'Y', 'Z'))
    df_res = pd.merge(df_vol[['sku cod', 'volume', 'ABC']], df_cv[['sku cod', 'CV', 'XYZ']], on='sku cod')
    df_res['Clase'] = df_res['ABC'] + df_res['XYZ']
    return df_res

df_abcxyz_global = calcular_abc_xyz_global(df)

col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    lista_paises = ["TODOS"] + sorted(df['País'].dropna().unique().tolist())
    pais_sel = st.selectbox("1. Country / País:", lista_paises)
df_filtro1 = df if pais_sel == "TODOS" else df[df['País'] == pais_sel]

with col_f2:
    lista_clientes = ["TODOS"] + sorted(df_filtro1['customer cod'].dropna().unique().tolist())
    cliente_sel = st.selectbox("2. Customer / Cliente:", lista_clientes)
df_filtro2 = df_filtro1 if cliente_sel == "TODOS" else df_filtro1[df_filtro1['customer cod'] == cliente_sel]

with col_f3:
    lista_clases = ["TODAS"] + sorted(df_abcxyz_global['Clase'].dropna().unique().tolist()) if not df_abcxyz_global.empty else ["TODAS"]
    clase_sel = st.selectbox("3. Clase ABC/XYZ:", lista_clases)

if clase_sel != "TODAS" and not df_abcxyz_global.empty:
    skus_en_clase = df_abcxyz_global[df_abcxyz_global['Clase'] == clase_sel]['sku cod'].unique()
    df_filtro3 = df_filtro2[df_filtro2['sku cod'].isin(skus_en_clase)]
else:
    df_filtro3 = df_filtro2

with col_f4:
    lista_skus = ["TODOS"] + sorted(df_filtro3['sku cod'].dropna().unique().tolist())
    sku_sel = st.selectbox("4. Filter SKU (PT):", lista_skus)
df_final = df_filtro3 if sku_sel == "TODOS" else df_filtro3[df_filtro3['sku cod'] == sku_sel]

col_objetivo = 'volume'
dict_sku_desc = dict(zip(df['sku cod'], df['sku desc']))
dict_rm_desc = dict(zip(df_bom['rm cod'], df_bom['rm desc'])) if (df_bom is not None and 'rm cod' in df_bom.columns) else {}
# 3. FUNCIONES CORE
# ==========================================
def obtener_parametros_stock(codigo, cobertura_defecto):
    stk_inicial, cob_meses, lead_time = 0, cobertura_defecto, 0
    if df_stock is not None and not df_stock.empty and 'sku cod' in df_stock.columns:
        fila = df_stock[df_stock['sku cod'] == codigo]
        if not fila.empty:
            if 'stock_disponible' in fila.columns: stk_inicial = pd.to_numeric(fila['stock_disponible'], errors='coerce').fillna(0).sum()
            if 'Cobertura_Meses' in fila.columns and pd.notna(fila['Cobertura_Meses'].iloc[0]): cob_meses = int(fila['Cobertura_Meses'].iloc[0])
            if 'Categoria' in fila.columns and str(fila['Categoria'].iloc[0]).strip().upper() == 'MTO': cob_meses = 0
            if 'LT_Meses' in fila.columns and pd.notna(fila['LT_Meses'].iloc[0]): lead_time = int(fila['LT_Meses'].iloc[0])
    return stk_inicial, cob_meses, lead_time

def limpiar_anomalias(serie):
    if len(serie) < 6: return serie
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return serie.clip(lower=max(0, q1 - 1.5 * iqr), upper=q3 + 1.5 * iqr)

def calcular_forecast(serie, steps):
    if len(serie) == 0: return pd.Series([0.0]*steps, index=pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=steps, freq="MS"))
    if len(serie) < 6: return pd.Series([serie.mean()]*steps, index=pd.date_range(start=serie.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS"))
    try: return ExponentialSmoothing(serie, trend="add", seasonal="add" if len(serie)>=24 else None, seasonal_periods=12).fit().forecast(steps).apply(lambda x: max(0, x))
    except: return pd.Series([serie.tail(6).mean()]*steps, index=pd.date_range(start=serie.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS"))

def calcular_necesidades_netas(serie_salidas, stock_inicial, cobertura_meses, serie_erp=None):
    plan = pd.DataFrame(index=serie_salidas.index)
    plan['Salidas_Brutas'] = serie_salidas
    plan['Recepciones_ERP'] = serie_erp if serie_erp is not None else 0.0
    plan['Recepciones_ERP'] = plan['Recepciones_ERP'].fillna(0)
    
    plan['Stock_Inicial'], plan['Stock_Objetivo'], plan['Entradas_Netas'], plan['Stock_Final'] = 0.0, 0.0, 0.0, 0.0
    stock_corriente = stock_inicial
    
    for i in range(len(plan)):
        salida_futura = plan['Salidas_Brutas'].iloc[i+1 : min(i+1+cobertura_meses, len(plan))].sum() if i + 1 < len(plan) else plan['Salidas_Brutas'].iloc[i] * cobertura_meses 
        plan.iloc[i, plan.columns.get_loc('Stock_Inicial')] = stock_corriente
        plan.iloc[i, plan.columns.get_loc('Stock_Objetivo')] = salida_futura
        
        rec_erp = plan['Recepciones_ERP'].iloc[i]
        necesidad_real = plan['Salidas_Brutas'].iloc[i] + salida_futura - stock_corriente - rec_erp
        entradas_sugeridas = max(0, necesidad_real)
        
        plan.iloc[i, plan.columns.get_loc('Entradas_Netas')] = entradas_sugeridas
        stock_corriente = stock_corriente + entradas_sugeridas + rec_erp - plan['Salidas_Brutas'].iloc[i]
        plan.iloc[i, plan.columns.get_loc('Stock_Final')] = stock_corriente
        
    demanda_futura_media = plan['Salidas_Brutas'].rolling(window=3, min_periods=1).mean().shift(-1)
    if len(plan) > 0: demanda_futura_media.iloc[-1] = plan['Salidas_Brutas'].iloc[-1]
    plan['DOH'] = np.where(demanda_futura_media > 0, (plan['Stock_Final'] / demanda_futura_media) * 30, 0)
    plan['DOH'] = np.where((demanda_futura_media <= 0) & (plan['Stock_Final'] > 0), 999, plan['DOH'])
    plan['DOH'] = plan['DOH'].fillna(0).round(0)
    return plan

def estilo_doh(val):
    if pd.isna(val): return ''
    if val == 999 or val < 15: return 'background-color: #ffcccc; color: #900; font-weight: bold;'
    if val > 90: return 'background-color: #ffe6cc; color: #b35900; font-weight: bold;'
    return 'background-color: #e6ffe6; color: #006600;'

def aplicar_variacion_cliente(pais, cliente, porcentaje):
    try:
        df_aj = st.session_state['df_ajustes'].copy()
        df_cli = df[(df['País'] == pais) & (df['customer cod'] == cliente)]
        if df_cli.empty: return False, "No histórico."
        factor = max(0.0, 1.0 + (porcentaje / 100.0))
        skus_cliente = df_cli['sku cod'].unique()
        nuevos_registros = []
        for sku in skus_cliente:
            serie_sku = df_cli[df_cli['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
            fcst_base = calcular_forecast(limpiar_anomalias(serie_sku) if usar_limpieza_outliers else serie_sku, horizonte)
            for fecha, val_base in fcst_base.items(): nuevos_registros.append({'Date': fecha, 'País': pais, 'customer cod': cliente, 'sku cod': sku, 'override_value': round(val_base * factor, 2)})
        df_aj = df_aj[~((df_aj['País'] == pais) & (df_aj['customer cod'] == cliente))]
        st.session_state['df_ajustes'] = pd.concat([df_aj, pd.DataFrame(nuevos_registros)], ignore_index=True)
        return True, "Factor aplicado."
    except Exception as e: return False, str(e)

# ==========================================
# PIPELINES DEL ERP
# ==========================================
dict_prd_erp, dict_cmp_erp = {}, {}
if df_produccion_erp is not None and not df_produccion_erp.empty:
    df_prd_tmp = df_produccion_erp.copy()
    df_prd_tmp['Date'] = pd.to_datetime(df_prd_tmp['Date']).apply(lambda x: x.replace(day=1) if pd.notnull(x) else x)
    dict_prd_erp = df_prd_tmp.groupby(['sku cod', 'Date'])['Cantidad_Kg'].sum().to_dict()

if df_compras_erp is not None and not df_compras_erp.empty:
    df_cmp_tmp = df_compras_erp.copy()
    df_cmp_tmp['Date'] = pd.to_datetime(df_cmp_tmp['Date']).apply(lambda x: x.replace(day=1) if pd.notnull(x) else x)
    dict_cmp_erp = df_cmp_tmp.groupby(['rm cod', 'Date'])['Cantidad_Kg'].sum().to_dict()

@st.cache_data(ttl=60)
def generar_mps_global():
    mps_dict = {}
    ajustes_agg = st.session_state['df_ajustes'].dropna(subset=['Date']).copy() if not st.session_state['df_ajustes'].empty else None
    if ajustes_agg is not None:
        ajustes_agg['Date'] = pd.to_datetime(ajustes_agg['Date'], dayfirst=True)
        ajustes_agg = ajustes_agg.groupby(['sku cod', 'Date'])['override_value'].sum().reset_index()

    for sku in df['sku cod'].unique():
        serie_vol_bruta = df[df['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
        df_fcst = pd.DataFrame({'Consenso': calcular_forecast(limpiar_anomalias(serie_vol_bruta) if usar_limpieza_outliers else serie_vol_bruta, horizonte)})
        if ajustes_agg is not None:
            aj_sku = ajustes_agg[ajustes_agg['sku cod'] == sku].set_index('Date')
            for f, r in aj_sku.iterrows():
                if f.replace(day=1) in df_fcst.index: df_fcst.at[f.replace(day=1), 'Consenso'] = r['override_value']
        stk, cob, _ = obtener_parametros_stock(sku, cobertura_fg)
        serie_erp = pd.Series(0.0, index=df_fcst.index)
        for idx in df_fcst.index: serie_erp[idx] = dict_prd_erp.get((sku, idx), 0.0)
        df_plan = calcular_necesidades_netas(df_fcst['Consenso'], stk, cob, serie_erp)
        df_plan['sku cod'], df_plan['sku desc'] = sku, dict_sku_desc.get(sku, sku)
        mps_dict[sku] = df_plan
    return mps_dict

@st.cache_data(ttl=60)
def generar_mrp_global():
    mps_g = generar_mps_global()
    if df_bom is None or df_stock is None: return pd.DataFrame()
    lista_req = [pd.DataFrame({'Date': mps_g[sku].index, 'Necesidad_Bruta': mps_g[sku]['Entradas_Netas'] * row.get('Cantidad', 0), 'rm cod': row.get('rm cod')}) for sku in mps_g for _, row in df_bom[df_bom['sku cod'] == sku].iterrows() if pd.notna(row.get('rm cod'))]
    if not lista_req: return pd.DataFrame()
    lista_compras_g = []
    for rm_cod, df_rm in pd.concat(lista_req).groupby(['Date', 'rm cod'])['Necesidad_Bruta'].sum().reset_index().groupby('rm cod'):
        stk, cob, lt = obtener_parametros_stock(rm_cod, cobertura_rm)
        serie_erp = pd.Series(0.0, index=df_rm['Date'])
        for idx in df_rm['Date']: serie_erp[idx] = dict_cmp_erp.get((rm_cod, idx), 0.0)
        plan = calcular_necesidades_netas(df_rm.set_index('Date')['Necesidad_Bruta'], stk, cob, serie_erp)
        plan['Lanzamiento_Pedidos'] = plan['Entradas_Netas'].shift(-lt).fillna(0)
        plan['rm cod'], plan['rm desc'], plan['LT_Meses'] = rm_cod, dict_rm_desc.get(rm_cod, rm_cod), lt
        lista_compras_g.append(plan.reset_index())
    return pd.concat(lista_compras_g)

# ==========================================
# PREPARACIÓN DATOS BASE
# ==========================================
df_grouped = df_final.groupby('Date')[col_objetivo].sum().reset_index().set_index('Date').resample("MS").sum().fillna(0)
serie_real = df_grouped[col_objetivo] if not df_grouped.empty else pd.Series(dtype=float)
serie_modelo = limpiar_anomalias(serie_real) if usar_limpieza_outliers else serie_real
df_comparativo = pd.DataFrame({"Estadistico": calcular_forecast(serie_modelo, horizonte), "Consenso": calcular_forecast(serie_modelo, horizonte)})
df_comparativo.index.name = 'Date'

ajustes_activos = st.session_state['df_ajustes'].copy()
if not ajustes_activos.empty and sku_sel != "TODOS":
    if 'País' in ajustes_activos.columns and pais_sel != "TODOS": ajustes_activos = ajustes_activos[ajustes_activos['País'] == pais_sel]
    if 'customer cod' in ajustes_activos.columns and cliente_sel != "TODOS": ajustes_activos = ajustes_activos[ajustes_activos['customer cod'] == cliente_sel]
    if 'sku cod' in ajustes_activos.columns: ajustes_activos = ajustes_activos[ajustes_activos['sku cod'] == sku_sel]
    if not ajustes_activos.empty and 'override_value' in ajustes_activos.columns:
        ajustes_activos['Date'] = pd.to_datetime(ajustes_activos['Date'], dayfirst=True, errors='coerce')
        for fecha, row in ajustes_activos.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
            if fecha.replace(day=1) in df_comparativo.index: df_comparativo.at[fecha.replace(day=1), 'Consenso'] = row['override_value']

LAYOUT_STYLE = dict(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Arial, sans-serif"),
    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e0e6ed')
)

# ==========================================
# PESTAÑAS (TABS) CON CONTROL DE ACCESO
# ==========================================
tab_guia, tab_demanda, tab_prod, tab_bom, tab_cap, tab_fin, tab_ejec, tab_abc, tab_exc, tab_whatif = st.tabs([
    t["tab0"], t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"], t["tab6"], t.get("tab7", "🔠 7. ABC/XYZ"), t.get("tab8", "🚨 8. Excepciones"), t.get("tab9", "🔀 9. What-If")
])

with tab_guia:
    st.header(t["guide_title"])
    st.write(t["guide_desc"])
    st.markdown(f"**{t['g_dem_t']}**: {t['g_dem_d']}")
    st.markdown(f"**{t['g_pro_t']}**: {t['g_pro_d']}")
    st.markdown(f"**{t['g_com_t']}**: {t['g_com_d']}")
    st.markdown(f"**{t['g_cap_t']}**: {t['g_cap_d']}")
    st.markdown(f"**{t['g_fin_t']}**: {t['g_fin_d']}")
    st.markdown(f"**{t['g_erp_t']}**: {t['g_erp_d']}")

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
                df_editado = st.data_editor(df_display, column_config={"Estadistico": st.column_config.NumberColumn(disabled=True, format="%.2f"), "Consenso": st.column_config.NumberColumn(step=1, format="%.2f")}, use_container_width=True)
            else:
                st.dataframe(df_display.style.format("{:,.2f}"), use_container_width=True)
                
            st.markdown("---")
            
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if pais_sel != "TODOS" and cliente_sel != "TODOS" and sku_sel != "TODOS":
                    if st.button("💾 Guardar / Save (RAM)", use_container_width=True):
                        if st.session_state['df_ajustes'] is not None:
                            try:
                                df_aj = st.session_state['df_ajustes'].copy()
                                df_aj = df_aj[~((df_aj['País'] == pais_sel) & (df_aj['customer cod'] == cliente_sel) & (df_aj['sku cod'] == sku_sel))]
                                df_mod = df_editado[df_editado['Consenso'] != df_editado['Estadistico']].copy()
                                nuevas_filas = [{'Date': pd.to_datetime(f), 'País': pais_sel, 'customer cod': cliente_sel, 'sku cod': sku_sel, 'override_value': r['Consenso']} for f, r in df_mod.iterrows()]
                                if nuevas_filas: df_aj = pd.concat([df_aj, pd.DataFrame(nuevas_filas)], ignore_index=True)
                                st.session_state['df_ajustes'] = df_aj
                                st.success("Guardado Temporal"); st.rerun()
                            except: pass
                else:
                    st.info("⚠️ Selecciona País, Cliente y SKU para editar.")
                    
            with btn_c2:
                if not st.session_state['df_ajustes'].empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        st.session_state['df_ajustes'].to_excel(writer, index=False, sheet_name='Ajustes_Consenso')
                    st.download_button(
                        label="📥 Descargar Ajustes (Excel Final)", 
                        data=output.getvalue(), 
                        file_name="2_Ajustes_Consenso_Actualizado.xlsx", 
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
                        if exito: st.success("Done!"); st.rerun()
                        else: st.error("Error")

with tab_prod:
    if "tab2" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Producción.")
    else:
        if df_stock is None or sku_sel == "TODOS": st.info("👈 Upload Stock file and select SKU.")
        else:
            st.subheader(f"Master Production Schedule (MPS): [{sku_sel}] {dict_sku_desc.get(sku_sel, sku_sel)}")
            stock_sku_fg, cob_real_fg, _ = obtener_parametros_stock(sku_sel, cobertura_fg)
            
            serie_erp = pd.Series(0.0, index=df_comparativo.index)
            for idx in df_comparativo.index: serie_erp[idx] = dict_prd_erp.get((sku_sel, idx), 0.0)
                
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
            st.dataframe(df_show_fg.style.format("{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Stock_Objetivo', 'Entradas_Netas', 'Stock_Final']).format("{:.0f}", subset=['DOH']).map(estilo_doh, subset=['DOH']), use_container_width=True)

with tab_bom:
    if "tab3" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Compras (MRP).")
    else:
        st.subheader("MRP / Purchasing Plan")
        if df_bom is None or df_stock is None: st.info("👈 Upload BOM & Stock files.")
        else:
            lista_rms = ["TODAS"] + sorted(df_bom['rm cod'].dropna().astype(str).unique().tolist()) if 'rm cod' in df_bom.columns else ["TODAS"]
            rm_sel = st.selectbox("🔍 Filter Material:", lista_rms)
            if st.button("🚀 Execute BOM Explosion"):
                with st.spinner("Processing BOM..."):
                    df_viz = generar_mrp_global()
                    if rm_sel != "TODAS": df_viz = df_viz[df_viz['rm cod'] == rm_sel]
                    if df_viz.empty: st.warning("No demand.")
                    else:
                        df_viz['MP_Visual'] = "[" + df_viz['rm cod'].astype(str) + "] " + df_viz['rm desc']
                        
                        fig_rm = px.bar(pd.melt(df_viz, id_vars=['Date', 'MP_Visual'], value_vars=['Recepciones_ERP', 'Entradas_Netas'], var_name='Tipo', value_name='Volumen').replace({'Entradas_Netas': 'Nuevas (Teóricas)', 'Recepciones_ERP': 'ERP (Firme)'}), x='Date', y='Volumen', color='Tipo', facet_col='MP_Visual', facet_col_wrap=3, title="Llegadas a Fábrica (Firme + Teórico)", barmode='stack', color_discrete_sequence=['#1E3E5B', '#88FFBB'])
                        fig_rm.update_layout(**LAYOUT_STYLE)
                        st.plotly_chart(fig_rm, use_container_width=True)
                        
                        if rm_sel != "TODAS":
                            st.markdown("### 🔍 Trazabilidad del Material (Pegging)")
                            st.write(f"Desglose del origen de la demanda para **{rm_sel}** en todo el horizonte:")
                            
                            mps_g = generar_mps_global()
                            pegging_data = []
                            for sku, plan in mps_g.items():
                                bom_fila = df_bom[(df_bom['sku cod'] == sku) & (df_bom['rm cod'] == rm_sel)]
                                if not bom_fila.empty:
                                    qty = bom_fila['Cantidad'].values[0]
                                    necesidad_total_rm = plan['Entradas_Netas'].sum() * qty
                                    
                                    if necesidad_total_rm > 0:
                                        df_sku = df[df['sku cod'] == sku]
                                        if not df_sku.empty:
                                            mix_clientes = df_sku.groupby('customer cod')['volume'].sum()
                                            total_vol = mix_clientes.sum()
                                            for cli, vol in mix_clientes.items():
                                                pct = vol / total_vol if total_vol > 0 else 0
                                                pegging_data.append({
                                                    'SKU (Producto)': sku,
                                                    'Cliente': cli,
                                                    'Kilos_MP': necesidad_total_rm * pct
                                                })
                                        else:
                                            pegging_data.append({'SKU (Producto)': sku, 'Cliente': 'Desconocido', 'Kilos_MP': necesidad_total_rm})
                            
                            if pegging_data:
                                df_peg = pd.DataFrame(pegging_data)
                                col_p1, col_p2 = st.columns(2)
                                
                                with col_p1:
                                    df_peg_sku = df_peg.groupby('SKU (Producto)')['Kilos_MP'].sum().reset_index()
                                    fig_peg_sku = px.pie(df_peg_sku, values='Kilos_MP', names='SKU (Producto)', title="Consumo por Producto Terminado (SKU)", hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r)
                                    fig_peg_sku.update_traces(textposition='inside', textinfo='percent+label')
                                    fig_peg_sku.update_layout(**LAYOUT_STYLE)
                                    st.plotly_chart(fig_peg_sku, use_container_width=True)
                                    
                                with col_p2:
                                    df_peg_cli = df_peg.groupby('Cliente')['Kilos_MP'].sum().reset_index()
                                    fig_peg_cli = px.pie(df_peg_cli, values='Kilos_MP', names='Cliente', title="Consumo por Cliente (Customer Cod)", hole=0.4, color_discrete_sequence=px.colors.sequential.Mint_r)
                                    fig_peg_cli.update_traces(textposition='inside', textinfo='percent+label')
                                    fig_peg_cli.update_layout(**LAYOUT_STYLE)
                                    st.plotly_chart(fig_peg_cli, use_container_width=True)
                        
                        df_show = df_viz[['Date', 'rm cod', 'rm desc', 'LT_Meses', 'Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final', 'DOH']].copy()
                        df_show['Date'] = df_show['Date'].dt.strftime('%Y-%m')
                        st.dataframe(df_show.reset_index(drop=True).style.format("{:,.2f}", subset=['Salidas_Brutas', 'Stock_Inicial', 'Recepciones_ERP', 'Entradas_Netas', 'Lanzamiento_Pedidos', 'Stock_Final']).format("{:.0f}", subset=['DOH']).map(estilo_doh, subset=['DOH']), use_container_width=True)

with tab_cap:
    if "tab4" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Capacidad.")
    else:
        st.subheader("Capacity Planning (RCCP)")
        if df_rutas is None or df_cal is None: st.info("👈 Upload Rutas & Calendario.")
        else:
            lista_maquinas = ["TODAS"] + sorted(df_rutas['Maquina'].dropna().unique().tolist()) if 'Maquina' in df_rutas.columns else ["TODAS"]
            maq_sel = st.selectbox("⚙️ Filter Line / Línea:", lista_maquinas)
            if st.button("⚖️ Calculate Saturation"):
                with st.spinner("Processing..."):
                    mps_g = generar_mps_global()
                    if mps_g:
                        df_req = pd.merge(pd.concat(mps_g.values()).reset_index().rename(columns={'index': 'Date'})[lambda x: x['Entradas_Netas'] > 0], df_rutas, on='sku cod', how='inner')
                        df_req['Horas_Necesarias'] = df_req['Entradas_Netas'] / df_req['Kilos_por_Hora'].replace(0, 1)
                        df_cal['Date'] = pd.to_datetime(df_cal['Date'], dayfirst=True)
                        if maq_sel == "TODAS":
                            df_capacidad = pd.merge(df_req.groupby(['Date', 'Maquina'])['Horas_Necesarias'].sum().reset_index(), df_cal, on=['Date', 'Maquina'], how='left').fillna({'Horas_Disponibles': 1})
                            df_capacidad['Utilizacion'] = (df_capacidad['Horas_Necesarias'] / df_capacidad['Horas_Disponibles']) * 100
                            df_pivot = df_capacidad.pivot(index='Maquina', columns='Date', values='Utilizacion').fillna(0)
                            df_pivot.columns = df_pivot.columns.strftime('%Y-%m')
                            st.markdown("#### % Utilización / Utilization")
                            try: st.dataframe(df_pivot.style.background_gradient(cmap='RdYlGn_r', vmin=0, vmax=120).format("{:.0f}%"), use_container_width=True)
                            except: st.dataframe(df_pivot.style.format("{:.0f}%"), use_container_width=True)
                        else:
                            df_req_maq = df_req[df_req['Maquina'] == maq_sel]
                            if not df_req_maq.empty:
                                fig_cap = px.bar(df_req_maq.groupby(['Date', 'sku desc'])['Horas_Necesarias'].sum().reset_index(), x='Date', y='Horas_Necesarias', color='sku desc', title=f"Carga vs Capacidad: {maq_sel}")
                                fig_cap.add_trace(go.Scatter(x=pd.merge(df_req_maq.groupby('Date')['Horas_Necesarias'].sum().reset_index(), df_cal[df_cal['Maquina'] == maq_sel], on='Date', how='left').fillna({'Horas_Disponibles': 0})['Date'], y=pd.merge(df_req_maq.groupby('Date')['Horas_Necesarias'].sum().reset_index(), df_cal[df_cal['Maquina'] == maq_sel], on='Date', how='left').fillna({'Horas_Disponibles': 0})['Horas_Disponibles'], mode='lines', name='Max Hours', line=dict(color='red', width=3, dash='dash')))
                                fig_cap.update_layout(**LAYOUT_STYLE, yaxis_title="Horas", barmode='stack', colorway=['#1E3E5B', '#88FFBB', '#A0B2C6'])
                                st.plotly_chart(fig_cap, use_container_width=True)

with tab_fin:
    if "tab5" not in modulos_permitidos:
        st.warning("🔒 No tienes permisos para acceder al módulo de Finanzas.")
    else:
        st.subheader("Financial Valuation & Working Capital (GBP)")
        if not dict_price: st.warning("⚠️ No 'revenue' or 'margin' columns in history.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                nivel_pl = st.selectbox("📊 Level of Analysis:", ["Consolidado Global", "Por País", "Por Cliente", "Por SKU"])
                filtro_pl = None
                if nivel_pl == "Por País": filtro_pl = st.selectbox("Country:", sorted(df['País'].dropna().unique()))
                elif nivel_pl == "Por Cliente": filtro_pl = st.selectbox("Customer:", sorted(df['customer cod'].dropna().unique()))
                elif nivel_pl == "Por SKU": filtro_pl = st.selectbox("SKU:", sorted(df['sku cod'].dropna().unique()))
            with col2:
                vista_wc = st.selectbox("📦 Working Capital View:", ["Total (PT + MP)", "Producto Terminado (PT)", "Materia Prima (MP)"])
                
            if st.button("📈 Calculate Finance"):
                with st.spinner("Processing P&L..."):
                    lista_pl = []
                    for (pais, cli, sku), df_grupo in df.groupby(['País', 'customer cod', 'sku cod']):
                        serie_vol = df_grupo.groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
                        df_fcst = pd.DataFrame({'Consenso': calcular_forecast(limpiar_anomalias(serie_vol) if usar_limpieza_outliers else serie_vol, horizonte)})
                        aj_filtro = st.session_state['df_ajustes'][(st.session_state['df_ajustes']['País'] == pais) & (st.session_state['df_ajustes']['customer cod'] == cli) & (st.session_state['df_ajustes']['sku cod'] == sku)]
                        if not aj_filtro.empty:
                            aj_filtro['Date'] = pd.to_datetime(aj_filtro['Date'], dayfirst=True)
                            for f, r in aj_filtro.dropna(subset=['Date']).groupby('Date')['override_value'].sum().reset_index().set_index('Date').iterrows():
                                if f.replace(day=1) in df_fcst.index: df_fcst.at[f.replace(day=1), 'Consenso'] = r['override_value']
                        precio, margen, moneda = dict_price.get(sku, 0), dict_margin.get(sku, 0), str(dict_currency.get(sku, 'EUR')).strip().upper()
                        tasa_cambio = fx_eur_gbp if moneda == 'EUR' else (fx_dkk_gbp if moneda == 'DKK' else (fx_pln_gbp if moneda == 'PLN' else 1.0))
                        df_res = pd.DataFrame({'Date': df_fcst.index, 'País': pais, 'Cliente': cli, 'SKU': sku, 'Revenue_GBP': df_fcst['Consenso'].values * precio * tasa_cambio, 'Margin_GBP': df_fcst['Consenso'].values * margen * tasa_cambio})
                        lista_pl.append(df_res)
                        
                    df_plot_pl = pd.concat(lista_pl)
                    skus_validos = df['sku cod'].unique()
                    if nivel_pl == "Por País": df_plot_pl, skus_validos, titulo_estrategico = df_plot_pl[df_plot_pl['País'] == filtro_pl], df[df['País'] == filtro_pl]['sku cod'].unique(), filtro_pl
                    elif nivel_pl == "Por Cliente": df_plot_pl, skus_validos, titulo_estrategico = df_plot_pl[df_plot_pl['Cliente'] == filtro_pl], df[df['customer cod'] == filtro_pl]['sku cod'].unique(), filtro_pl
                    elif nivel_pl == "Por SKU": df_plot_pl, skus_validos, titulo_estrategico = df_plot_pl[df_plot_pl['SKU'] == filtro_pl], [filtro_pl], filtro_pl
                    else: titulo_estrategico = "Consolidado Global"
                    df_plot_pl = df_plot_pl.groupby('Date')[['Revenue_GBP', 'Margin_GBP']].sum().reset_index()
                    
                    mps_g = generar_mps_global()
                    lista_wc_pt = [pd.DataFrame({'Date': mps_g[sku].index, 'Elemento': sku, 'WorkingCapital_GBP': mps_g[sku]['Stock_Final'].values * (dict_price.get(sku, 0) - dict_margin.get(sku, 0)) * (fx_eur_gbp if str(dict_currency.get(sku, 'EUR')).strip().upper() == 'EUR' else (fx_dkk_gbp if str(dict_currency.get(sku, 'EUR')).strip().upper() == 'DKK' else (fx_pln_gbp if str(dict_currency.get(sku, 'EUR')).strip().upper() == 'PLN' else 1.0))), 'Categoria': 'Producto Terminado'}) for sku in mps_g]
                    df_wc_pt_filtrado = pd.concat(lista_wc_pt)[lambda x: x['Elemento'].isin(skus_validos)] if lista_wc_pt else pd.DataFrame()
                    
                    df_mrp = generar_mrp_global()
                    lista_wc_mp = []
                    if not df_mrp.empty and df_stock is not None and 'Coste_Unitario' in df_stock.columns:
                        for rm_cod, df_rm in df_mrp.groupby('rm cod'):
                            coste_rm_serie = df_stock.loc[df_stock['sku cod'] == rm_cod, 'Coste_Unitario'].values
                            val_coste = float(coste_rm_serie[0]) if len(coste_rm_serie) > 0 and pd.notna(coste_rm_serie[0]) else 0.0
                            lista_wc_mp.append(pd.DataFrame({'Date': df_rm['Date'], 'Elemento': rm_cod, 'WorkingCapital_GBP': df_rm['Stock_Final'].values * val_coste, 'Categoria': 'Materia Prima'}))
                    
                    df_wc_mp = pd.concat(lista_wc_mp) if lista_wc_mp else pd.DataFrame()
                    rms_validos = df_bom[df_bom['sku cod'].isin(skus_validos)]['rm cod'].unique() if (df_bom is not None and not df_bom.empty and 'sku cod' in df_bom.columns) else []
                    df_wc_mp_filtrado = df_wc_mp[df_wc_mp['Elemento'].isin(rms_validos)] if not df_wc_mp.empty else pd.DataFrame()
                    df_wc_total = pd.concat([df_wc_pt_filtrado, df_wc_mp_filtrado]) if not df_wc_pt_filtrado.empty or not df_wc_mp_filtrado.empty else pd.DataFrame()
                    
                    if not df_wc_total.empty:
                        df_wc_pivot = df_wc_total.pivot_table(index='Date', columns='Categoria', values='WorkingCapital_GBP', aggfunc='sum').reset_index().fillna(0)
                        if 'Producto Terminado' not in df_wc_pivot.columns: df_wc_pivot['Producto Terminado'] = 0
                        if 'Materia Prima' not in df_wc_pivot.columns: df_wc_pivot['Materia Prima'] = 0
                        df_plot_pl = pd.merge(df_plot_pl, df_wc_pivot.rename(columns={'Producto Terminado': 'WC_PT_GBP', 'Materia Prima': 'WC_MP_GBP'})[['Date', 'WC_PT_GBP', 'WC_MP_GBP']], on='Date', how='left').fillna(0)
                        df_plot_pl['WC_Total_GBP'] = df_plot_pl['WC_PT_GBP'] + df_plot_pl['WC_MP_GBP']
                    else: df_plot_pl['WC_PT_GBP'], df_plot_pl['WC_MP_GBP'], df_plot_pl['WC_Total_GBP'] = 0, 0, 0

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
                    st.dataframe(df_plot_pl.rename(columns={"Revenue_GBP": "Revenue (£)", "Margin_GBP": "Margin (£)", "WC_PT_GBP": "WC PT (£)", "WC_MP_GBP": "WC MP (£)", "WC_Total_GBP": "Total WC (£)"}).style.format({c: "£ {:,.0f}" for c in ["Revenue (£)", "Margin (£)", "WC PT (£)", "WC MP (£)", "Total WC (£)"]}), use_container_width=True)
# ==========================================
    # MODULO 6: EJECUCIÓN ERP (AUTOMATIZADO)
    # ==========================================
    with tab_ejec:
        if "tab6" not in modulos_permitidos:
            st.warning("🔒 No tienes permisos para acceder al módulo de Ejecución ERP.")
        else:
            st.subheader("Action Plan: S&OP Month 1 Execution")
            col_ej1, col_ej2 = st.columns(2)
            with col_ej1:
                st.markdown("#### 🛒 Pedidos Compra (Firme en ERP)")
                if df_compras_erp is not None and not df_compras_erp.empty: st.dataframe(df_compras_erp, use_container_width=True)
            with col_ej2:
                st.markdown("#### 🏭 Órdenes Producción (Firme en ERP)")
                if df_produccion_erp is not None and not df_produccion_erp.empty: st.dataframe(df_produccion_erp, use_container_width=True)
                    
            st.divider()
            
            mes_1_fecha = pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=1, freq="MS")[0]
            st.info(f"📅 **Mes Objetivo de Ejecución (Nuevos Lanzamientos):** {mes_1_fecha.strftime('%Y-%m')}")
            
            mps_g = generar_mps_global()
            df_sug_fab = pd.DataFrame()
            if mps_g:
                df_sug_fab = pd.concat(mps_g.values()).reset_index().rename(columns={'index': 'Date'})
                df_sug_fab = df_sug_fab[(df_sug_fab['Date'] == mes_1_fecha) & (df_sug_fab['Entradas_Netas'] > 0)][['Date', 'sku cod', 'sku desc', 'Entradas_Netas']]
            
            df_mrp = generar_mrp_global()
            df_sug_comp = pd.DataFrame()
            if not df_mrp.empty:
                df_sug_comp = df_mrp[(df_mrp['Date'] == mes_1_fecha) & (df_mrp['Lanzamiento_Pedidos'] > 0)][['Date', 'rm cod', 'rm desc', 'Lanzamiento_Pedidos']]

            st.markdown("### 🏭 NUEVAS Órdenes de Fabricación a lanzar en el ERP")
            if not df_sug_fab.empty: 
                df_sug_fab['Date'] = df_sug_fab['Date'].dt.strftime('%Y-%m')
                st.dataframe(df_sug_fab.rename(columns={'Entradas_Netas': 'Volumen a Lanzar (Kg)'}).style.format({"Volumen a Lanzar (Kg)": "{:,.0f}"}), use_container_width=True)
            else: st.success("✅ Todo cubierto. No necesitas lanzar nuevas órdenes de PT para el Mes 1.")
            
            st.markdown("### 🛒 NUEVOS Pedidos de Compra a lanzar a Proveedores")
            if not df_sug_comp.empty: 
                df_sug_comp['Date'] = df_sug_comp['Date'].dt.strftime('%Y-%m')
                st.dataframe(df_sug_comp.rename(columns={'Lanzamiento_Pedidos': 'Volumen a Pedir (Kg)'}).style.format({"Volumen a Pedir (Kg)": "{:,.0f}"}), use_container_width=True)
            else: st.success("✅ Todo cubierto. No necesitas emitir nuevos pedidos de Materia Prima para el Mes 1.")

    # ==========================================
    # MODULO 7: MATRIZ ABC / XYZ
    # ==========================================
    with tab_abc:
        if "tab7" not in modulos_permitidos:
            st.warning("🔒 No tienes permisos para acceder a la segmentación ABC/XYZ.")
        else:
            st.subheader("Segmentación Estratégica ABC / XYZ (Informativo)")
            st.markdown("Clasificación basada en **Volumen Acumulado (ABC)** y **Volatilidad de la Demanda (XYZ)**.")
            
            if 'df_abcxyz_global' in locals() and df_abcxyz_global is not None and not df_abcxyz_global.empty:
                df_abcxyz_show = pd.merge(df_abcxyz_global, df[['sku cod', 'sku desc']].drop_duplicates(), on='sku cod', how='left')
                
                col_mat1, col_mat2 = st.columns([1, 2])
                with col_mat1:
                    st.markdown("#### Matriz de Distribución")
                    resumen_matriz = df_abcxyz_show.groupby(['ABC', 'XYZ'])['sku cod'].count().unstack().fillna(0).astype(int)
                    resumen_matriz = resumen_matriz.reindex(index=['A','B','C'], columns=['X','Y','Z'], fill_value=0)
                    st.dataframe(resumen_matriz.style.background_gradient(cmap='Blues'), use_container_width=True)
                    st.caption("A: 80% Vol | B: 15% Vol | C: 5% Vol")
                    st.caption("X: Estable | Y: Variable | Z: Errático")
                    
                with col_mat2:
                    st.markdown("#### Detalle de SKUs")
                    filtro_clase = st.multiselect("Filtrar por Clase (ej. AX, CZ):", sorted(df_abcxyz_show['Clase'].unique()))
                    df_show_abc = df_abcxyz_show if not filtro_clase else df_abcxyz_show[df_abcxyz_show['Clase'].isin(filtro_clase)]
                    st.dataframe(df_show_abc[['sku cod', 'sku desc', 'Clase', 'volume', 'CV']].rename(columns={'volume': 'Volumen Total', 'CV': 'Coef. Variación'}).style.format({"Volumen Total": "{:,.0f}", "Coef. Variación": "{:.2f}"}), use_container_width=True)

    # ==========================================
    # MODULO 8: PANEL DE EXCEPCIONES (AUTOMATIZADO)
    # ==========================================
    with tab_exc:
        if "tab8" not in modulos_permitidos:
            st.warning("🔒 No tienes permisos para acceder al Panel de Excepciones.")
        else:
            st.subheader("🚨 Panel de Excepciones (Management by Exception)")
            st.markdown("Radar automático de **roturas inminentes** y **excesos de inventario** para el próximo ciclo.")
            
            mes_1_fecha = pd.date_range(start=pd.Timestamp.today().replace(day=1), periods=1, freq="MS")[0]
            
            mps_g = generar_mps_global()
            mrp_g = generar_mrp_global()
            
            alertas_pt, alertas_mp = [], []
            
            if mps_g:
                for sku, plan in mps_g.items():
                    if mes_1_fecha in plan.index:
                        datos_m1 = plan.loc[mes_1_fecha]
                        if datos_m1['Stock_Final'] <= 0 or datos_m1['DOH'] < 15:
                            alertas_pt.append({'SKU': sku, 'Alerta': '🔴 RIESGO ROTURA', 'DOH': datos_m1['DOH'], 'Stock Proyectado': datos_m1['Stock_Final']})
                        elif datos_m1['DOH'] > 90 and datos_m1['DOH'] != 999:
                            alertas_pt.append({'SKU': sku, 'Alerta': '🟡 EXCESO INVENTARIO', 'DOH': datos_m1['DOH'], 'Stock Proyectado': datos_m1['Stock_Final']})

            if not mrp_g.empty:
                mrp_m1 = mrp_g[mrp_g['Date'] == mes_1_fecha]
                for _, row in mrp_m1.iterrows():
                    if row['Stock_Final'] <= 0 or row['DOH'] < 15:
                        alertas_mp.append({'Material': row['rm cod'], 'Alerta': '🔴 RIESGO ROTURA MP', 'DOH': row['DOH'], 'Stock Proyectado': row['Stock_Final']})
                    elif row['DOH'] > 90 and row['DOH'] != 999:
                        alertas_mp.append({'Material': row['rm cod'], 'Alerta': '🟡 EXCESO STOCK MP', 'DOH': row['DOH'], 'Stock Proyectado': row['Stock_Final']})

            col_ex1, col_ex2 = st.columns(2)
            
            with col_ex1:
                st.markdown("#### 📦 Producto Terminado")
                if alertas_pt:
                    df_al_pt = pd.DataFrame(alertas_pt)
                    st.dataframe(df_al_pt.style.applymap(lambda x: 'background-color: #ffcccc; color: darkred; font-weight: bold;' if 'ROTURA' in str(x) else 'background-color: #ffe6cc; color: #b35900; font-weight: bold;', subset=['Alerta']).format({"Stock Proyectado": "{:,.0f}"}), use_container_width=True)
                else: st.success("✅ Sin alertas para M1.")
                    
            with col_ex2:
                st.markdown("#### 🧩 Materias Primas")
                if alertas_mp:
                    df_al_mp = pd.DataFrame(alertas_mp)
                    st.dataframe(df_al_mp.style.applymap(lambda x: 'background-color: #ffcccc; color: darkred; font-weight: bold;' if 'ROTURA' in str(x) else 'background-color: #ffe6cc; color: #b35900; font-weight: bold;', subset=['Alerta']).format({"Stock Proyectado": "{:,.0f}"}), use_container_width=True)
                else: st.success("✅ Sin alertas para M1.")

    # ==========================================
    # MODULO 9: WHAT-IF SCENARIOS (SIMULADOR)
    # ==========================================
    with tab_whatif:
        if "tab9" not in modulos_permitidos:
            st.warning("🔒 No tienes permisos para acceder al Simulador What-If.")
        else:
            st.subheader("🔀 Simulador de Escenarios (What-If)")
            st.markdown("Aplica macro-shocks (inflación, variaciones de volumen) para evaluar el impacto en el P&L consolidado para el horizonte S&OP.")
            
            if not dict_price:
                st.warning("⚠️ Necesitas cargar datos históricos que incluyan columnas de 'revenue' y 'margin' para simular finanzas.")
            else:
                st.markdown("### 1. Define tu Escenario")
                col_w1, col_w2, col_w3 = st.columns(3)
                with col_w1:
                    shock_vol = st.slider("📈 Variación de Volumen (%)", -50, 50, 0, step=5, help="Simula una caída o pico de demanda global.")
                with col_w2:
                    shock_precio = st.slider("🏷️ Variación Precios Venta (%)", -30, 30, 0, step=5, help="Simula una política de ajuste de tarifas de venta.")
                with col_w3:
                    shock_coste = st.slider("💸 Variación Costes/MP (%)", -30, 50, 0, step=5, help="Simula la inflación sobre las materias primas y producción.")
                    
                st.divider()
                
                lista_base, lista_whatif = [], []
                
                for sku in df['sku cod'].unique():
                    serie_vol = df[df['sku cod'] == sku].groupby('Date')['volume'].sum().resample("MS").sum().fillna(0)
                    fcst_base = calcular_forecast(limpiar_anomalias(serie_vol) if usar_limpieza_outliers else serie_vol, horizonte)
                    
                    precio = dict_price.get(sku, 0)
                    margen = dict_margin.get(sku, 0)
                    coste_base = precio - margen
                    
                    moneda = str(dict_currency.get(sku, 'EUR')).strip().upper()
                    tasa = fx_eur_gbp if moneda == 'EUR' else (fx_dkk_gbp if moneda == 'DKK' else (fx_pln_gbp if moneda == 'PLN' else 1.0))
                    
                    vol_base_total = fcst_base.sum()
                    
                    rev_base = vol_base_total * precio * tasa
                    mar_base = vol_base_total * margen * tasa
                    
                    vol_sim = vol_base_total * (1 + (shock_vol / 100))
                    precio_sim = precio * (1 + (shock_precio / 100))
                    coste_sim = coste_base * (1 + (shock_coste / 100))
                    
                    rev_sim = vol_sim * precio_sim * tasa
                    mar_sim = vol_sim * (precio_sim - coste_sim) * tasa
                    
                    lista_base.append({'Revenue': rev_base, 'Margin': mar_base})
                    lista_whatif.append({'Revenue': rev_sim, 'Margin': mar_sim})
                    
                df_base = pd.DataFrame(lista_base)
                df_sim = pd.DataFrame(lista_whatif)
                
                tot_rev_base = df_base['Revenue'].sum()
                tot_mar_base = df_base['Margin'].sum()
                
                tot_rev_sim = df_sim['Revenue'].sum()
                tot_mar_sim = df_sim['Margin'].sum()
                
                col_r1, col_r2, col_r3 = st.columns(3)
                col_r1.metric("Revenue (Escenario Simulado)", f"£ {tot_rev_sim:,.0f}", f"£ {tot_rev_sim - tot_rev_base:,.0f} vs Base")
                col_r2.metric("Margen (Escenario Simulado)", f"£ {tot_mar_sim:,.0f}", f"£ {tot_mar_sim - tot_mar_base:,.0f} vs Base")
                
                mar_pct_base = (tot_mar_base / tot_rev_base * 100) if tot_rev_base > 0 else 0
                mar_pct_sim = (tot_mar_sim / tot_rev_sim * 100) if tot_rev_sim > 0 else 0
                col_r3.metric("% Margen Bruto (Simulado)", f"{mar_pct_sim:.1f}%", f"{mar_pct_sim - mar_pct_base:.1f}% vs Base")
                
                fig_wi = go.Figure(data=[
                    go.Bar(name='Baseline (Plan Actual)', x=['Revenue (Ingresos)', 'Margin (Beneficio Bruto)'], y=[tot_rev_base, tot_mar_base], marker_color='#A0B2C6'),
                    go.Bar(name='What-If (Shock Aplicado)', x=['Revenue (Ingresos)', 'Margin (Beneficio Bruto)'], y=[tot_rev_sim, tot_mar_sim], marker_color='#1E3E5B')
                ])
                fig_wi.update_layout(**LAYOUT_STYLE, barmode='group', title="Impacto Financiero Consolidado en GBP", yaxis_title="GBP (£)")
                st.plotly_chart(fig_wi, use_container_width=True)

