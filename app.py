import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import time
import json
import requests
import base64
import plotly.express as px
from fpdf import FPDF
from contextlib import contextmanager
from PIL import Image

# ==========================================
# 1. CONFIGURACIÓN DEL SISTEMA
# ==========================================
# 👇 TU API KEY
CLAVE_IA = "AIzaSyDI2v9E35MP6wgaHfFud-OoXNC0bG6iiCc" 

NOMBRE_DB = 'chiro_master_v67.db'
BACKUP_DIR = 'backups'
FILES_DIR = 'archivos_ots'
# Sistema de usuarios con roles
USUARIOS = {
    "admin": {"password": "CHIRO2026", "role": "Administrador"},
    "Chiro": {"password": "CHIRO2026", "role": "Operario"}
}

st.set_page_config(page_title="Transporte Chiro SRL", layout="wide", initial_sidebar_state="expanded")

# ESTILOS CSS CORPORATIVO - TRANSPORTE CHIRO
st.markdown("""
<style>
    /* Fondo Principal */
    .stApp { 
        background-color: #0E1117; 
        color: #FAFAFA; 
        font-family: 'Inter', 'Segoe UI', sans-serif; 
    }
    
    /* Botones Primarios - ROJO CORPORATIVO */
    div.stButton > button[kind="primary"],
    button[kind="primary"],
    .stButton > button:first-child {
        background-color: #D81E28 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(216, 30, 40, 0.3) !important;
    }
    
    div.stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover,
    .stButton > button:first-child:hover {
        background-color: #B81A22 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(216, 30, 40, 0.4) !important;
    }
    
    /* Botones Secundarios */
    div.stButton > button[kind="secondary"],
    button[kind="secondary"] {
        background-color: transparent !important;
        color: #FAFAFA !important;
        border: 1px solid rgba(250, 250, 250, 0.3) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button[kind="secondary"]:hover,
    button[kind="secondary"]:hover {
        background-color: rgba(250, 250, 250, 0.1) !important;
        border-color: rgba(250, 250, 250, 0.5) !important;
    }
    
    /* Métricas (KPIs) - Estilo Corporativo */
    [data-testid="stMetricValue"],
    .stMetric {
        background-color: #1E1E1E !important;
        border-left: 5px solid #D81E28 !important;
        border-radius: 8px !important;
        padding: 15px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    
    .kpi-card { 
        background: #1E1E1E !important; 
        border: 1px solid #262730 !important; 
        border-left: 5px solid #D81E28 !important;
        border-radius: 12px !important; 
        padding: 20px !important; 
        text-align: center !important; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
        transition: transform 0.2s ease !important;
    }
    
    .kpi-card:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 12px rgba(0,0,0,0.4) !important;
    }
    
    .kpi-val { 
        font-size: 32px !important; 
        font-weight: 800 !important; 
        color: #D81E28 !important; 
        margin-bottom: 5px !important;
    }
    
    .kpi-lbl { 
        font-size: 11px !important; 
        text-transform: uppercase !important; 
        color: #B0B0B0 !important; 
        letter-spacing: 1.5px !important; 
        font-weight: 500 !important;
    }
    
    /* Sidebar - Más Aireado */
    [data-testid="stSidebar"] {
        background-color: #262730 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 1rem !important;
    }
    
    [data-testid="stSidebar"] .stRadio > div {
        gap: 0.75rem !important;
    }
    
    [data-testid="stSidebar"] label {
        padding: 0.5rem 0 !important;
        margin-bottom: 0.25rem !important;
    }
    
    /* Stock Visual */
    .stock-card { 
        background: #1E1E1E !important; 
        padding: 15px !important; 
        border-radius: 10px !important; 
        border: 1px solid #262730 !important; 
        margin-bottom: 10px !important; 
        text-align: center !important; 
        transition: all 0.2s ease !important; 
    }
    
    .stock-card:hover { 
        transform: translateY(-2px) !important; 
        border-color: #D81E28 !important; 
        box-shadow: 0 4px 8px rgba(216, 30, 40, 0.2) !important;
    }
    
    .stock-ok { border-left: 4px solid #22c55e !important; }
    .stock-low { border-left: 4px solid #D81E28 !important; }
    
    /* Alertas */
    .alert-box { 
        padding: 12px !important; 
        border-radius: 8px !important; 
        margin-bottom: 8px !important; 
        background: #262730 !important; 
        border-left: 4px solid #f59e0b !important; 
        font-size: 13px !important; 
    }
    
    .alert-red { border-left-color: #D81E28 !important; }

    /* Inputs */
    .stTextInput>div>div>input, 
    .stSelectbox>div>div>div, 
    .stNumberInput>div>div>input, 
    .stTextArea>div>div>textarea {
        background-color: #1E1E1E !important; 
        color: #FAFAFA !important; 
        border: 1px solid #262730 !important; 
        border-radius: 6px !important;
    }
    
    .stTextInput>div>div>input:focus,
    .stSelectbox>div>div>div:focus,
    .stNumberInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus {
        border-color: #D81E28 !important;
        box-shadow: 0 0 0 2px rgba(216, 30, 40, 0.2) !important;
    }
    
    /* Títulos y Texto */
    h1, h2, h3 {
        color: #FAFAFA !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 20px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #D81E28 !important;
        color: #FFFFFF !important;
    }
    
    /* Cards y Containers */
    [data-testid="stExpander"] {
        background-color: #1E1E1E !important;
        border: 1px solid #262730 !important;
        border-radius: 8px !important;
    }
    
    /* Scrollbar personalizado */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1E1E1E;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #D81E28;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #B81A22;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS
# ==========================================
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)

@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(NOMBRE_DB)
        yield conn
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Error DB: {e}")
    finally:
        if conn: conn.close()

def run_query(q, p=()):
    with get_db() as conn: conn.execute(q, p)

def get_data(q, p=()):
    try:
        conn = sqlite3.connect(NOMBRE_DB)
        return pd.read_sql(q, conn, params=p)
    except: return pd.DataFrame()

def init_db():
    # Estructura completa de tablas
    tablas = [
        "flota (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_movil TEXT, patente TEXT, modelo TEXT, km_actual INTEGER DEFAULT 0, km_service_interval INTEGER DEFAULT 15000, km_ultimo_service INTEGER DEFAULT 0)",
        "choferes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, dni TEXT, telefono TEXT, estado TEXT DEFAULT 'Activo')",
        "neumaticos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, marca TEXT, modelo TEXT, estado TEXT, ubicacion_movil TEXT, km_instalacion INTEGER, vida INTEGER DEFAULT 1)",
        "stock (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nombre TEXT, cantidad INTEGER, minimo INTEGER, precio REAL, rubro TEXT, proveedor TEXT)",
        "mantenimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, movil TEXT, chofer TEXT, descripcion TEXT, checklist TEXT, repuesto TEXT, cantidad INTEGER, costo_total REAL, estado TEXT)",
        "combustible (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, movil TEXT, chofer TEXT, litros REAL, costo REAL, km_momento INTEGER)",
        "documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_carga TEXT, nombre_archivo TEXT, descripcion TEXT, tipo TEXT, ot_id INTEGER DEFAULT 0)",
        "proveedores (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, contacto TEXT, telefono TEXT, direccion TEXT, rubro TEXT)",
        "novedades (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, movil TEXT, descripcion TEXT, estado TEXT DEFAULT 'Activa')",
        "stock_cubiertas (id INTEGER PRIMARY KEY AUTOINCREMENT, marca TEXT, modelo TEXT, medida TEXT, dot TEXT, estado TEXT, cantidad INTEGER, ubicacion TEXT)"
    ]
    with get_db() as conn:
        for t in tablas: conn.execute(f"CREATE TABLE IF NOT EXISTS {t}")
        # Agregar columna proveedor a stock si no existe (migración)
        try:
            conn.execute("ALTER TABLE stock ADD COLUMN proveedor TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        # Agregar columna fecha_actualizacion_km a flota si no existe (migración)
        try:
            conn.execute("ALTER TABLE flota ADD COLUMN fecha_actualizacion_km TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        # Agregar columnas nuevas a mantenimientos si no existen (migración)
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN categoria TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN costo_terceros REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN repuestos_json TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN proveedor_taller TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN observaciones TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN responsable TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN fecha_cierre TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE stock ADD COLUMN fecha_ingreso TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe

if 'init' not in st.session_state:
    init_db()
    st.session_state['init'] = True

# ==========================================
# 3. FUNCIONES ESPECIALES (PDF, IA, ARCHIVOS, SEGURIDAD)
# ==========================================
def borrado_seguro(tipo_registro, nombre_registro, id_registro, tabla, callback_success=None):
    """Función general para borrado seguro con confirmación"""
    confirm_key = f"confirm_delete_{tipo_registro}_{id_registro}"
    
    if st.session_state.get(confirm_key, False):
        st.warning(f"⚠️ **¿Está seguro de eliminar {tipo_registro}: '{nombre_registro}'?**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Sí, estoy seguro", key=f"yes_{id_registro}"):
                run_query(f"DELETE FROM {tabla} WHERE id=?", (id_registro,))
                st.session_state[confirm_key] = False
                if callback_success:
                    callback_success()
                st.success(f"✅ {tipo_registro} eliminado exitosamente")
                time.sleep(0.5)
                st.rerun()
        with col2:
            if st.button("❌ Cancelar", key=f"no_{id_registro}"):
                st.session_state[confirm_key] = False
                st.rerun()
    else:
        if st.button("🗑️ Borrar", key=f"del_{id_registro}"):
            st.session_state[confirm_key] = True
            st.rerun()
def guardar_archivo(file, ot_id=0):
    try:
        name = f"DOC_{ot_id}_{int(time.time())}_{file.name}"
        path = os.path.join(FILES_DIR, name)
        with open(path, "wb") as f: f.write(file.getbuffer())
        run_query("INSERT INTO documentos (fecha_carga, nombre_archivo, descripcion, tipo, ot_id) VALUES (?,?,?,?,?)", 
                  (date.today(), name, "Adjunto", file.type, ot_id))
        return True
    except: return False

def generar_pdf_ot(ot_id):
    # Generador de PDF Reporte - Diseño Ejecutivo
    try:
        ot = get_data("SELECT * FROM mantenimientos WHERE id=?", (ot_id,)).iloc[0]
        pdf = FPDF()
        pdf.add_page()
        
        # Encabezado con fondo gris claro
        pdf.set_fill_color(240, 240, 240)  # Gris claro
        pdf.rect(0, 0, 210, 40, 'F')  # Rectángulo de fondo
        
        # Datos de la empresa formales
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, 8)
        pdf.cell(0, 8, "TRANSPORTE CHIRO S.R.L.", 0, 1, 'L')
        pdf.set_font("Arial", '', 9)
        pdf.set_xy(10, 15)
        pdf.cell(0, 6, "Sistema de Gestión de Mantenimiento", 0, 1, 'L')
        pdf.set_xy(10, 21)
        pdf.cell(0, 6, f"Generado el {date.today().strftime('%d/%m/%Y')}", 0, 1, 'L')
        
        # Título alineado a la derecha
        pdf.set_font("Arial", 'B', 18)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, 30)
        pdf.cell(0, 10, f"ORDEN DE TRABAJO N° {ot_id}", 0, 1, 'R')
        
        # Línea separadora
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, 45, 200, 45)
        
        pdf.ln(15)
        
        # Información de la OT
        pdf.set_font("Arial", 'B', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, "INFORMACIÓN DE LA ORDEN", 0, 1, 'L')
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 6, f"Móvil: {ot['movil']}", 0, 1, 'L')
        pdf.cell(0, 6, f"Chofer: {ot['chofer']}", 0, 1, 'L')
        pdf.cell(0, 6, f"Fecha: {ot['fecha']}", 0, 1, 'L')
        pdf.cell(0, 6, f"Estado: {ot['estado']}", 0, 1, 'L')
        
        pdf.ln(8)
        
        # Trabajo realizado
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, "TRABAJO REALIZADO:", 0, 1, 'L')
        pdf.set_font("Arial", '', 10)
        pdf.multi_cell(0, 6, f"{ot['descripcion']}")
        
        # Checklist si existe
        if ot['checklist'] and str(ot['checklist']).strip():
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "CHECKLIST:", 0, 1, 'L')
            pdf.set_font("Arial", 'I', 9)
            pdf.multi_cell(0, 6, f"{ot['checklist']}")
        
        # Repuestos si existen
        if ot.get('repuesto') and str(ot['repuesto']).strip():
            pdf.ln(8)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "REPUESTOS UTILIZADOS:", 0, 1, 'L')
            
            # Tabla simple de repuestos
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(120, 7, "Repuesto", 1, 0, 'L', True)
            pdf.cell(30, 7, "Cantidad", 1, 0, 'C', True)
            pdf.cell(40, 7, "Observaciones", 1, 1, 'L', True)
            
            pdf.set_font("Arial", '', 9)
            pdf.set_fill_color(255, 255, 255)
            repuesto = str(ot['repuesto']).strip()
            cantidad = ot.get('cantidad', 0) or 0
            pdf.cell(120, 6, repuesto, 1, 0, 'L', True)
            pdf.cell(30, 6, str(cantidad), 1, 0, 'C', True)
            pdf.cell(40, 6, "-", 1, 1, 'L', True)
        
        # Costo total
        if ot['costo_total'] and ot['costo_total'] > 0:
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 10, f"COSTO TOTAL: ${ot['costo_total']:,.2f}", 0, 1, 'R', True)
        
        # Pie de página
        pdf.set_y(-15)
        pdf.set_font("Arial", 'I', 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, f"Documento generado automáticamente por Transporte Chiro SRL", 0, 0, 'C')
        
        filename = f"OT_{ot_id}.pdf"
        filepath = os.path.join(FILES_DIR, filename)
        pdf.output(filepath)
        return filepath
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")
        return None

def procesar_ia(txt):
    if "TU_API_KEY" in CLAVE_IA: return pd.DataFrame()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={CLAVE_IA}"
    prompt = """Eres mecánico experto. Analiza el texto y devuelve SOLO JSON válido en este formato array: 
    [{"descripcion": "...", "repuesto": "...", "cantidad": 1, "movil": "..."}]"""
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt + "\n" + txt}]}]}, headers={'Content-Type': 'application/json'}, timeout=10)
        clean_json = res.json()['candidates'][0]['content']['parts'][0]['text'].replace("```json","").replace("```","").strip()
        return pd.DataFrame(json.loads(clean_json))
    except: return pd.DataFrame()

def procesar_ia_imagen(imagen_bytes):
    """Procesa una imagen con IA para detectar fallas y repuestos"""
    if "TU_API_KEY" in CLAVE_IA or not CLAVE_IA: return pd.DataFrame()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={CLAVE_IA}"
    
    # Convertir imagen a base64
    imagen_b64 = base64.b64encode(imagen_bytes).decode('utf-8')
    
    prompt = """Eres mecánico experto. Analiza esta imagen de un vehículo o repuesto y devuelve SOLO JSON válido en este formato array:
    [{"descripcion": "descripción de la falla o trabajo detectado", "repuesto": "nombre del repuesto si se detecta", "cantidad": 1}]
    
    Si no detectas nada específico, devuelve un array con un objeto con descripcion general de lo que ves."""
    
    try:
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": imagen_b64
                        }
                    }
                ]
            }]
        }
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        respuesta = res.json()['candidates'][0]['content']['parts'][0]['text']
        clean_json = respuesta.replace("```json","").replace("```","").strip()
        return pd.DataFrame(json.loads(clean_json))
    except Exception as e:
        st.error(f"Error al procesar imagen: {e}")
        return pd.DataFrame()

# ==========================================
# 4. LOGIN & NAVEGACIÓN
# ==========================================
# Inicializar session state
if 'login' not in st.session_state: 
    st.session_state['login'] = False
    st.session_state['username'] = None
    st.session_state['role'] = None

# Pantalla de Login (Gatekeeper)
if not st.session_state['login']:
    st.markdown("<br><h1 style='text-align:center; color:#D81E28;'>Transporte Chiro SRL</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; color:#FAFAFA; margin-bottom:30px;'>Sistema de Gestión</h3>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        with st.container(border=True):
            st.markdown("### 🔐 Inicio de Sesión")
            u = st.text_input("Usuario", key="login_user")
            p = st.text_input("Contraseña", type="password", key="login_pass")
            
            if st.button("🚀 ENTRAR", use_container_width=True, type="primary"):
                if u in USUARIOS and USUARIOS[u]['password'] == p:
                    st.session_state['login'] = True
                    st.session_state['username'] = u
                    st.session_state['role'] = USUARIOS[u]['role']
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# Obtener rol del usuario
user_role = st.session_state.get('role', 'Operario')
user_username = st.session_state.get('username', 'Usuario')

# Navegación según rol
if user_role == "Administrador":
    # Vista completa para Administrador
    OPCIONES = ["🏠 DASHBOARD", "🔧 TALLER & OTS", "📦 STOCK VISUAL", "🚛 FLOTA", "⛽ COMBUSTIBLE", "👥 CHOFERES", "🤝 PROVEEDORES", "📂 DOCS"]
    with st.sidebar:
        st.title("🚛 MENU")
        st.caption(f"👤 {user_username} - {user_role}")
        nav = st.radio("Navegación", OPCIONES, label_visibility="collapsed")
        
        st.markdown("---")
        st.caption("Buscador Rápido")
        q_global = st.text_input("🔍 Buscar...", label_visibility="collapsed")
        if q_global:
            st.info(f"Resultados para '{q_global}':")
            res1 = get_data(f"SELECT * FROM stock WHERE nombre LIKE '%{q_global}%'")
            if not res1.empty: st.write(f"📦 Stock: {len(res1)}")
            res2 = get_data(f"SELECT * FROM mantenimientos WHERE descripcion LIKE '%{q_global}%'")
            if not res2.empty: st.write(f"🔧 OTs: {len(res2)}")
        
        st.markdown("---")
        # Botón de Backup
        if os.path.exists(NOMBRE_DB):
            with open(NOMBRE_DB, "rb") as f:
                st.download_button(
                    "📥 Descargar Copia de Seguridad (.db)",
                    f,
                    file_name=f"backup_{date.today().strftime('%Y%m%d')}_{NOMBRE_DB}",
                    mime="application/x-sqlite3",
                    use_container_width=True
                )
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True): 
            st.session_state['login'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            st.rerun()
else:
    # Vista simplificada para Operario - Sin sidebar
    nav = "TALLER_OPERARIO"  # Vista especial para operarios

# ==========================================
# 5. SECCIONES DEL SISTEMA
# ==========================================

# --- VISTA OPERARIO (TALLER SIMPLIFICADO) ---
if nav == "TALLER_OPERARIO":
    st.title("👋 Hola Equipo - Reporte de Taller")
    st.markdown(f"**Usuario:** {user_username} | **Fecha:** {date.today().strftime('%d/%m/%Y')}")
    
    # Botón de cerrar sesión en la parte superior
    col_header, col_logout = st.columns([4, 1])
    with col_logout:
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state['login'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            st.rerun()
    
    st.markdown("---")
    
    # Formulario de Nueva OT (simplificado para operarios)
    st.markdown("### 📝 Nueva Orden de Trabajo")
    
    # Selector de modo: Solo Manual para operarios (más simple)
    modo_trabajo = st.radio("Modo de Trabajo", ["📝 Modo Manual"], horizontal=True)
    
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha")
    movil = c1.selectbox("Móvil", get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist())
    chofer = c2.selectbox("Chofer", [""] + get_data("SELECT nombre FROM choferes")['nombre'].tolist())
    
    # Realizado por / Responsable
    responsable = c2.selectbox("Realizado por / Responsable", 
                                 ['Maxi', 'Cristian', 'Chofer Asignado', 'Taller Externo', 'Otro'],
                                 help="Identifique quién realizó el trabajo")
    
    # Categoría
    categorias = ['Mecánica General', 'Mecánica Pesada (Motor/Caja)', 'Electricidad', 'Frenos', 'Neumáticos / Gomería', 'Carrocería', 'Pintura', 'Aire Acondicionado', 'Sistema de Combustible', 'Lavadero', 'Servicios / Lubricación', 'Conductores', 'Reparaciones Generales']
    categoria = c1.selectbox("Categoría *", categorias)
    
    desc = c2.text_area("Descripción de la Falla / Trabajo")
    
    # Costo Mano de Obra / Terceros (solo si es Taller Externo)
    if responsable == "Taller Externo":
        costo_terceros = st.number_input("Costo Mano de Obra / Terceros ($)", min_value=0.0, value=0.0, step=0.01, 
                                         help="Si el trabajo lo hizo un taller externo, ingresa el costo aquí.")
        
        # Proveedor / Taller Externo (obligatorio si es externo)
        proveedores_lista = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
        st.markdown("**⚠️ Taller Externo seleccionado - Especifique el Proveedor:**")
        proveedor_taller = st.selectbox("Proveedor / Taller Externo *", 
                                         [""] + proveedores_lista + ["➕ Nuevo / No listado"],
                                         help="Nombre del taller o mecánico que realizó el trabajo (obligatorio para trabajos externos).")
        
        # Si seleccionó "➕ Nuevo / No listado", mostrar campo de texto
        proveedor_taller_final = None
        nuevo_proveedor_nombre = None
        if proveedor_taller == "➕ Nuevo / No listado":
            nuevo_proveedor_nombre = st.text_input("Nombre del Nuevo Proveedor / Taller", key="proveedor_operario_texto",
                                                   placeholder="Ingrese el nombre del taller o mecánico")
            if nuevo_proveedor_nombre and nuevo_proveedor_nombre.strip():
                proveedor_taller_final = nuevo_proveedor_nombre.strip()
        elif proveedor_taller and proveedor_taller != "":
            proveedor_taller_final = proveedor_taller
    else:
        costo_terceros = 0.0
        proveedor_taller_final = None
        nuevo_proveedor_nombre = None
    
    # Sección de Consumo de Repuestos
    st.markdown("### 📦 Consumo de Repuestos (Stock)")
    st.caption("Seleccione los repuestos utilizados y especifique la cantidad de cada uno")
    
    # Obtener stock disponible
    stock_disponible = get_data("SELECT id, codigo, nombre, cantidad FROM stock WHERE cantidad > 0 ORDER BY nombre")
    
    repuestos_seleccionados = {}
    if not stock_disponible.empty:
        # Crear opciones para multiselect
        opciones_repuestos = [f"{row['id']} - {row['nombre']} (Stock: {row['cantidad']})" for _, row in stock_disponible.iterrows()]
        repuestos_multiselect = st.multiselect("Seleccionar Repuestos", opciones_repuestos, key="repuestos_operario")
        
        # Para cada repuesto seleccionado, pedir cantidad
        if repuestos_multiselect:
            st.markdown("**Especificar Cantidad por Repuesto:**")
            for rep_sel in repuestos_multiselect:
                rep_id = int(rep_sel.split(" - ")[0])
                rep_nombre = rep_sel.split(" - ")[1].split(" (Stock:")[0]
                stock_actual = stock_disponible[stock_disponible['id'] == rep_id].iloc[0]['cantidad']
                
                col_rep, col_cant = st.columns([3, 1])
                with col_rep:
                    st.text(f"• {rep_nombre} (Stock disponible: {stock_actual})")
                with col_cant:
                    cantidad_rep = st.number_input(f"Cantidad", min_value=1, max_value=int(stock_actual), value=1, 
                                                  key=f"cant_rep_operario_{rep_id}")
                    repuestos_seleccionados[rep_id] = {
                        'nombre': rep_nombre,
                        'cantidad': cantidad_rep,
                        'stock_actual': stock_actual
                    }
    else:
        st.info("📭 No hay repuestos disponibles en stock")
    
    # Observaciones / Notas Adicionales
    observaciones = st.text_area("Observaciones / Notas Adicionales", 
                                 placeholder="Detalle fallas específicas o comentarios sobre la reparación...",
                                 height=100)
    
    st.info("📋 Checklist de Servicio (Solo marcar si corresponde)")
    ck1, ck2, ck3, ck4 = st.columns(4)
    c_aceite = ck1.checkbox("Aceite/Filtros")
    c_frenos = ck2.checkbox("Frenos/Aire")
    c_luces = ck3.checkbox("Luces/Elec")
    c_neu = ck4.checkbox("Neumáticos")
    
    check_str = f"Aceite:{c_aceite}, Frenos:{c_frenos}, Luces:{c_luces}, Neu:{c_neu}"
    
    if st.button("🚀 Crear Orden de Trabajo", use_container_width=True, type="primary"):
        # Validar categoría
        if not categoria:
            st.error("❌ La categoría es obligatoria")
        # Validar proveedor si es Taller Externo
        elif responsable == "Taller Externo" and (not proveedor_taller or proveedor_taller == "" or proveedor_taller == "➕ Nuevo / No listado" and (not nuevo_proveedor_nombre or not nuevo_proveedor_nombre.strip())):
            st.error("❌ Si el trabajo fue realizado por un Taller Externo, debe especificar el Proveedor / Taller")
        else:
            # Convertir repuestos a JSON
            repuestos_json_str = json.dumps(repuestos_seleccionados) if repuestos_seleccionados else None
            
            # Si es un proveedor nuevo, insertarlo en la tabla proveedores primero
            if nuevo_proveedor_nombre and nuevo_proveedor_nombre.strip():
                proveedor_nombre_limpio = nuevo_proveedor_nombre.strip()
                # Verificar si ya existe para evitar duplicados
                existe_proveedor = get_data("SELECT id FROM proveedores WHERE empresa = ?", (proveedor_nombre_limpio,))
                if existe_proveedor.empty:
                    # Insertar nuevo proveedor (solo con el nombre/empresa)
                    run_query("INSERT INTO proveedores (empresa) VALUES (?)", (proveedor_nombre_limpio,))
            
            # Insertar OT
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mantenimientos (fecha, movil, chofer, descripcion, checklist, estado, costo_total, categoria, costo_terceros, repuestos_json, proveedor_taller, observaciones, responsable)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (fecha, movil, chofer, desc, check_str, 'Pendiente', 0, categoria, costo_terceros, repuestos_json_str, proveedor_taller_final, observaciones if observaciones else None, responsable))
                ot_id = cursor.lastrowid
                
                # Restar stock de repuestos utilizados
                alertas_stock = []
                for rep_id, rep_data in repuestos_seleccionados.items():
                    cantidad_usada = rep_data['cantidad']
                    stock_anterior = rep_data['stock_actual']
                    
                    # Restar del stock
                    cursor.execute("UPDATE stock SET cantidad = cantidad - ? WHERE id=?", (cantidad_usada, rep_id))
                    
                    # Verificar si llegó a 0 (usar cursor para obtener el valor actualizado)
                    cursor.execute("SELECT cantidad FROM stock WHERE id=?", (rep_id,))
                    stock_nuevo = cursor.fetchone()[0]
                    if stock_nuevo <= 0:
                        alertas_stock.append(f"{rep_data['nombre']} (Stock: {stock_nuevo})")
                
                conn.commit()
            
            # Mostrar alertas si hay stock en 0
            if alertas_stock:
                st.warning(f"⚠️ **ALERTA:** Los siguientes repuestos quedaron con stock en 0 o negativo:\n" + "\n".join([f"• {a}" for a in alertas_stock]))
            
            st.success("✅ Orden Creada Exitosamente")
            st.rerun()
    
    st.markdown("---")
    
    # Últimas 5 OTs cargadas hoy
    st.markdown("### 📋 Últimas 5 OTs Cargadas Hoy")
    fecha_hoy_str = date.today().strftime("%Y-%m-%d")
    ots_hoy = get_data("""
        SELECT id, movil, descripcion, categoria, responsable, estado 
        FROM mantenimientos 
        WHERE fecha = ? 
        ORDER BY id DESC 
        LIMIT 5
    """, (fecha_hoy_str,))
    
    if not ots_hoy.empty:
        for _, ot in ots_hoy.iterrows():
            estado_color = {"Pendiente": "#f59e0b", "Cerrada": "#22c55e"}.get(ot.get('estado', 'Pendiente'), "#94a3b8")
            st.markdown(f"""
            <div style='background: #1e293b; padding: 10px; border-radius: 6px; border-left: 3px solid {estado_color}; margin-bottom: 8px;'>
                <div style='font-weight: bold; color: #f8fafc;'>OT #{ot['id']} | {ot['movil']} | <span style='color: {estado_color};'>{ot.get('estado', 'Pendiente')}</span></div>
                <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>📂 {ot.get('categoria', 'N/A')} | 👤 {ot.get('responsable', 'N/A')}</div>
                <div style='font-size: 11px; color: #64748b; margin-top: 3px;'>{str(ot['descripcion'])[:60]}{'...' if len(str(ot['descripcion'])) > 60 else ''}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📭 No hay OTs cargadas hoy")

# --- DASHBOARD ---
elif nav == "🏠 DASHBOARD":
    # Título de Bienvenida
    st.title("🚛 Tablero de Control - Transporte Chiro SRL")
    st.markdown(f"**Fecha:** {date.today().strftime('%d/%m/%Y')}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Cálculo de KPIs
    # KPI 1: Unidades Operativas (Flota Activa)
    flota_df = get_data("SELECT * FROM flota")
    unidades_activas = len(flota_df) if not flota_df.empty else 0
    
    # KPI 2: Alertas de Mantenimiento (Servicios vencidos)
    alertas_mantenimiento = 0
    if not flota_df.empty:
        for _, r in flota_df.iterrows():
            act = r.get('km_actual', 0) or 0
            ult = r.get('km_ultimo_service', 0) or 0
            inte = r.get('km_service_interval', 15000) or 15000
            if inte > 0 and (act - ult) >= inte:
                alertas_mantenimiento += 1
    
    # KPI 3: Valor de Pañol (Capital en Repuestos)
    stock_data = get_data("SELECT cantidad, precio FROM stock WHERE cantidad IS NOT NULL AND precio IS NOT NULL")
    valor_stock = 0
    if not stock_data.empty:
        stock_data['valor_item'] = stock_data['cantidad'] * stock_data['precio']
        valor_stock = stock_data['valor_item'].sum() or 0
    
    # Fila de KPIs (Métricas) - 3 Columnas
    kpi1, kpi2, kpi3 = st.columns(3)
    
    with kpi1:
        st.metric(
            label="🚛 Unidades Operativas",
            value=unidades_activas,
            delta="Flota Total"
        )
    
    with kpi2:
        delta_color = "inverse" if alertas_mantenimiento > 0 else "normal"
        st.metric(
            label="⚠️ Alertas Vencidas",
            value=alertas_mantenimiento,
            delta=f"{alertas_mantenimiento} servicio(s) vencido(s)" if alertas_mantenimiento > 0 else "Sin alertas",
            delta_color=delta_color
        )
    
    with kpi3:
        st.metric(
            label="💰 Capital en Repuestos",
            value=f"${valor_stock:,.0f}",
            delta="Valor total en stock"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Gráficos Visuales - Layout 2 Columnas (Ancha y Angosta)
    col_grafico, col_lista = st.columns([2, 1])
    
    with col_grafico:
        with st.container(border=True):
            st.subheader("📊 Stock por Rubro")
            # Gráfico de barras: Stock por Rubro (suma de cantidades)
            stock_rubro = get_data("""
                SELECT rubro, SUM(cantidad) as total_cantidad 
                FROM stock 
                WHERE rubro IS NOT NULL AND rubro != '' AND cantidad IS NOT NULL 
                GROUP BY rubro 
                ORDER BY total_cantidad DESC 
                LIMIT 10
            """)
            
            if not stock_rubro.empty:
                st.bar_chart(stock_rubro.set_index('rubro')['total_cantidad'], height=350)
            else:
                # Fallback: Stock total si no hay rubros
                stock_total = get_data("SELECT SUM(cantidad) as total FROM stock WHERE cantidad IS NOT NULL")
                if not stock_total.empty and stock_total.iloc[0]['total']:
                    st.info(f"📦 **Stock Total:** {int(stock_total.iloc[0]['total'])} unidades")
                else:
                    st.info("📊 No hay datos de stock para mostrar. Agregue artículos al inventario.")
    
    with col_lista:
        with st.container(border=True):
            st.subheader("📋 Próximos Vencimientos")
            
            # Lista de próximos servicios (próximos 1000 km)
            proximos_services = []
            if not flota_df.empty:
                for _, r in flota_df.iterrows():
                    act = r.get('km_actual', 0) or 0
                    ult = r.get('km_ultimo_service', 0) or 0
                    inte = r.get('km_service_interval', 15000) or 15000
                    km_recorridos = act - ult
                    km_restantes = inte - km_recorridos
                    
                    if 0 < km_restantes <= 1000:
                        proximos_services.append({
                            'Móvil': r.get('nombre_movil', 'N/A'),
                            'KM Restantes': f"{int(km_restantes):,}"
                        })
            
            if proximos_services:
                df_proximos = pd.DataFrame(proximos_services)
                st.dataframe(df_proximos, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No hay servicios próximos a vencer")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📦 Stock Bajo Mínimo")
            
            # Lista de stock bajo mínimo
            low_stock = get_data("SELECT nombre, cantidad, minimo FROM stock WHERE cantidad <= minimo ORDER BY cantidad ASC LIMIT 5")
            if not low_stock.empty:
                df_low = pd.DataFrame({
                    'Artículo': low_stock['nombre'],
                    'Stock': low_stock['cantidad'],
                    'Mínimo': low_stock['minimo']
                })
                st.dataframe(df_low, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Todo el stock está por encima del mínimo")
    
    # Sección de Resumen Rápido
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("📈 Resumen Ejecutivo")
        
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        
        with col_res1:
            g_taller = get_data("SELECT SUM(costo_total) FROM mantenimientos").iloc[0,0] or 0
            st.metric("🔧 Gasto Taller", f"${g_taller:,.0f}")
        
        with col_res2:
            g_comb = get_data("SELECT SUM(costo) FROM combustible").iloc[0,0] or 0
            st.metric("⛽ Gasto Combustible", f"${g_comb:,.0f}")
        
        with col_res3:
            total_gasto = g_taller + g_comb
            st.metric("💸 Total Gastos", f"${total_gasto:,.0f}")
        
        with col_res4:
            ots_pendientes = get_data("SELECT COUNT(*) as total FROM mantenimientos WHERE estado != 'Cerrada'").iloc[0,0] or 0
            st.metric("📋 OTs Pendientes", ots_pendientes)

# --- TALLER ---
elif nav == "🔧 TALLER & OTS":
    st.title("Gestión de Mantenimiento")
    t1, t2, t3 = st.tabs(["📝 NUEVA ORDEN", "📋 HISTORIAL", "📢 NOVEDADES"])
    
    with t1:
        # Selector de modo: Manual o IA
        modo_trabajo = st.radio("Modo de Trabajo", ["📝 Modo Manual", "🤖 Modo IA (Cámara)"], horizontal=True)
        
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha")
        movil = c1.selectbox("Móvil", get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist())
        chofer = c2.selectbox("Chofer", [""] + get_data("SELECT nombre FROM choferes")['nombre'].tolist())
        
        # Realizado por / Responsable
        responsable = c2.selectbox("Realizado por / Responsable", 
                                     ['Maxi', 'Cristian', 'Chofer Asignado', 'Taller Externo', 'Otro'],
                                     help="Identifique quién realizó el trabajo")
        
        # Modo Manual
        if modo_trabajo == "📝 Modo Manual":
            # Categoría
            categorias = ['Mecánica General', 'Mecánica Pesada (Motor/Caja)', 'Electricidad', 'Frenos', 'Neumáticos / Gomería', 'Carrocería', 'Pintura', 'Aire Acondicionado', 'Sistema de Combustible', 'Lavadero', 'Servicios / Lubricación', 'Conductores', 'Reparaciones Generales']
            categoria = c1.selectbox("Categoría *", categorias)
            
            desc = c2.text_area("Descripción de la Falla / Trabajo")
            
            # Costo Mano de Obra / Terceros
            costo_terceros = st.number_input("Costo Mano de Obra / Terceros ($)", min_value=0.0, value=0.0, step=0.01, 
                                             help="Si el trabajo lo hizo un taller externo, ingresa el costo aquí. Si fue interno, dejar en 0.")
            
            # Proveedor / Taller Externo (más visible si es Taller Externo)
            proveedores_lista = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
            if responsable == "Taller Externo":
                st.markdown("**⚠️ Taller Externo seleccionado - Especifique el Proveedor:**")
                proveedor_taller = st.selectbox("Proveedor / Taller Externo *", 
                                                 [""] + proveedores_lista + ["➕ Nuevo / No listado"],
                                                 help="Nombre del taller o mecánico que realizó el trabajo (obligatorio para trabajos externos).")
            else:
                proveedor_taller = st.selectbox("Proveedor / Taller Externo", 
                                                 [""] + proveedores_lista + ["➕ Nuevo / No listado"],
                                                 help="Nombre del taller o mecánico que realizó el trabajo (si fue externo).")
            
            # Si seleccionó "➕ Nuevo / No listado", mostrar campo de texto
            proveedor_taller_final = None
            nuevo_proveedor_nombre = None
            if proveedor_taller == "➕ Nuevo / No listado":
                nuevo_proveedor_nombre = st.text_input("Nombre del Nuevo Proveedor / Taller", key="proveedor_manual_texto",
                                                       placeholder="Ingrese el nombre del taller o mecánico")
                if nuevo_proveedor_nombre and nuevo_proveedor_nombre.strip():
                    proveedor_taller_final = nuevo_proveedor_nombre.strip()
            elif proveedor_taller and proveedor_taller != "":
                proveedor_taller_final = proveedor_taller
            
            # Sección de Consumo de Repuestos
            st.markdown("### 📦 Consumo de Repuestos (Stock)")
            st.caption("Seleccione los repuestos utilizados y especifique la cantidad de cada uno")
            
            # Obtener stock disponible
            stock_disponible = get_data("SELECT id, codigo, nombre, cantidad FROM stock WHERE cantidad > 0 ORDER BY nombre")
            
            repuestos_seleccionados = {}
            if not stock_disponible.empty:
                # Crear opciones para multiselect
                opciones_repuestos = [f"{row['id']} - {row['nombre']} (Stock: {row['cantidad']})" for _, row in stock_disponible.iterrows()]
                repuestos_multiselect = st.multiselect("Seleccionar Repuestos", opciones_repuestos, key="repuestos_manual")
                
                # Para cada repuesto seleccionado, pedir cantidad
                if repuestos_multiselect:
                    st.markdown("**Especificar Cantidad por Repuesto:**")
                    for rep_sel in repuestos_multiselect:
                        rep_id = int(rep_sel.split(" - ")[0])
                        rep_nombre = rep_sel.split(" - ")[1].split(" (Stock:")[0]
                        stock_actual = stock_disponible[stock_disponible['id'] == rep_id].iloc[0]['cantidad']
                        
                        col_rep, col_cant = st.columns([3, 1])
                        with col_rep:
                            st.text(f"• {rep_nombre} (Stock disponible: {stock_actual})")
                        with col_cant:
                            cantidad_rep = st.number_input(f"Cantidad", min_value=1, max_value=int(stock_actual), value=1, 
                                                          key=f"cant_rep_{rep_id}")
                            repuestos_seleccionados[rep_id] = {
                                'nombre': rep_nombre,
                                'cantidad': cantidad_rep,
                                'stock_actual': stock_actual
                            }
            else:
                st.info("📭 No hay repuestos disponibles en stock")
            
            # Observaciones / Notas Adicionales
            observaciones = st.text_area("Observaciones / Notas Adicionales", 
                                         placeholder="Detalle fallas específicas o comentarios sobre la reparación...",
                                         height=100)
            
            st.info("📋 Checklist de Servicio (Solo marcar si corresponde)")
            ck1, ck2, ck3, ck4 = st.columns(4)
            c_aceite = ck1.checkbox("Aceite/Filtros")
            c_frenos = ck2.checkbox("Frenos/Aire")
            c_luces = ck3.checkbox("Luces/Elec")
            c_neu = ck4.checkbox("Neumáticos")
            
            check_str = f"Aceite:{c_aceite}, Frenos:{c_frenos}, Luces:{c_luces}, Neu:{c_neu}"
            
            if st.button("🚀 Crear Orden de Trabajo"):
                # Validar categoría
                if not categoria:
                    st.error("❌ La categoría es obligatoria")
                else:
                    # Convertir repuestos a JSON
                    repuestos_json_str = json.dumps(repuestos_seleccionados) if repuestos_seleccionados else None
                    
                    # Si es un proveedor nuevo, insertarlo en la tabla proveedores primero
                    if nuevo_proveedor_nombre and nuevo_proveedor_nombre.strip():
                        proveedor_nombre_limpio = nuevo_proveedor_nombre.strip()
                        # Verificar si ya existe para evitar duplicados
                        existe_proveedor = get_data("SELECT id FROM proveedores WHERE empresa = ?", (proveedor_nombre_limpio,))
                        if existe_proveedor.empty:
                            # Insertar nuevo proveedor (solo con el nombre/empresa)
                            run_query("INSERT INTO proveedores (empresa) VALUES (?)", (proveedor_nombre_limpio,))
                    
                    # Insertar OT
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO mantenimientos (fecha, movil, chofer, descripcion, checklist, estado, costo_total, categoria, costo_terceros, repuestos_json, proveedor_taller, observaciones, responsable)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (fecha, movil, chofer, desc, check_str, 'Pendiente', 0, categoria, costo_terceros, repuestos_json_str, proveedor_taller_final, observaciones if observaciones else None, responsable))
                        ot_id = cursor.lastrowid
                        
                        # Restar stock de repuestos utilizados
                        alertas_stock = []
                        for rep_id, rep_data in repuestos_seleccionados.items():
                            cantidad_usada = rep_data['cantidad']
                            stock_anterior = rep_data['stock_actual']
                            
                            # Restar del stock
                            cursor.execute("UPDATE stock SET cantidad = cantidad - ? WHERE id=?", (cantidad_usada, rep_id))
                            
                            # Verificar si llegó a 0 (usar cursor para obtener el valor actualizado)
                            cursor.execute("SELECT cantidad FROM stock WHERE id=?", (rep_id,))
                            stock_nuevo = cursor.fetchone()[0]
                            if stock_nuevo <= 0:
                                alertas_stock.append(f"{rep_data['nombre']} (Stock: {stock_nuevo})")
                        
                        conn.commit()
                    
                    # Mostrar alertas si hay stock en 0
                    if alertas_stock:
                        st.warning(f"⚠️ **ALERTA:** Los siguientes repuestos quedaron con stock en 0 o negativo:\n" + "\n".join([f"• {a}" for a in alertas_stock]))
                    
                    st.success("✅ Orden Creada Exitosamente")
                    st.rerun()
        
        # Modo IA con Cámara
        else:
            # Categoría
            categorias = ['Mecánica General', 'Mecánica Pesada (Motor/Caja)', 'Electricidad', 'Frenos', 'Neumáticos / Gomería', 'Carrocería', 'Pintura', 'Aire Acondicionado', 'Sistema de Combustible', 'Lavadero', 'Servicios / Lubricación', 'Conductores', 'Reparaciones Generales']
            categoria_ia = c1.selectbox("Categoría *", categorias, key="categoria_ia")
            
            # Costo Mano de Obra / Terceros
            costo_terceros_ia = st.number_input("Costo Mano de Obra / Terceros ($)", min_value=0.0, value=0.0, step=0.01, 
                                                 help="Si el trabajo lo hizo un taller externo, ingresa el costo aquí. Si fue interno, dejar en 0.", key="costo_terceros_ia")
            
            # Proveedor / Taller Externo (más visible si es Taller Externo)
            proveedores_lista_ia = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
            if responsable == "Taller Externo":
                st.markdown("**⚠️ Taller Externo seleccionado - Especifique el Proveedor:**")
                proveedor_taller_ia = st.selectbox("Proveedor / Taller Externo *", 
                                                    [""] + proveedores_lista_ia + ["➕ Nuevo / No listado"],
                                                    help="Nombre del taller o mecánico que realizó el trabajo (obligatorio para trabajos externos).",
                                                    key="proveedor_taller_ia")
            else:
                proveedor_taller_ia = st.selectbox("Proveedor / Taller Externo", 
                                                    [""] + proveedores_lista_ia + ["➕ Nuevo / No listado"],
                                                    help="Nombre del taller o mecánico que realizó el trabajo (si fue externo).",
                                                    key="proveedor_taller_ia")
            
            # Si seleccionó "➕ Nuevo / No listado", mostrar campo de texto
            proveedor_taller_final_ia = None
            nuevo_proveedor_nombre_ia = None
            if proveedor_taller_ia == "➕ Nuevo / No listado":
                nuevo_proveedor_nombre_ia = st.text_input("Nombre del Nuevo Proveedor / Taller", key="proveedor_ia_texto",
                                                          placeholder="Ingrese el nombre del taller o mecánico")
                if nuevo_proveedor_nombre_ia and nuevo_proveedor_nombre_ia.strip():
                    proveedor_taller_final_ia = nuevo_proveedor_nombre_ia.strip()
            elif proveedor_taller_ia and proveedor_taller_ia != "":
                proveedor_taller_final_ia = proveedor_taller_ia
            
            st.info("📸 **Modo IA:** Tome una foto de la falla o repuesto para que la IA detecte automáticamente los detalles")
            
            foto = st.camera_input("Capturar Imagen", key="camera_ot")
            
            if foto:
                with st.spinner("🤖 Procesando imagen con IA..."):
                    imagen_bytes = foto.getvalue()
                    df_ia = procesar_ia_imagen(imagen_bytes)
                    
                    if not df_ia.empty:
                        st.success("✅ Análisis completado. Revise y edite los resultados:")
                        
                        # Preparar DataFrame para edición
                        if 'descripcion' not in df_ia.columns:
                            df_ia['descripcion'] = ''
                        if 'repuesto' not in df_ia.columns:
                            df_ia['repuesto'] = ''
                        if 'cantidad' not in df_ia.columns:
                            df_ia['cantidad'] = 1
                        
                        # Formulario para editar resultados (sin data_editor)
                        st.subheader("📝 Editar Detecciones")
                        descripciones_editadas = []
                        repuestos_editados = []
                        cantidades_editadas = []
                        
                        for idx, row in df_ia.iterrows():
                            with st.container():
                                col_d, col_r, col_c = st.columns([3, 2, 1])
                                with col_d:
                                    desc = st.text_input(f"Descripción {idx+1}", value=row.get('descripcion', ''), key=f"desc_ia_{idx}")
                                    descripciones_editadas.append(desc)
                                with col_r:
                                    rep = st.text_input(f"Repuesto {idx+1}", value=row.get('repuesto', ''), key=f"rep_ia_{idx}")
                                    repuestos_editados.append(rep)
                                with col_c:
                                    cant = st.number_input(f"Cant {idx+1}", min_value=1, value=int(row.get('cantidad', 1)), key=f"cant_ia_{idx}")
                                    cantidades_editadas.append(cant)
                        
                        # Combinar descripciones y repuestos
                        descripcion_final = " | ".join([d for d in descripciones_editadas if d])
                        repuestos_final = " | ".join([r for r in repuestos_editados if r])
                        cantidad_total = sum(cantidades_editadas)
                        
                        # Sección de Consumo de Repuestos (Stock)
                        st.markdown("### 📦 Consumo de Repuestos (Stock)")
                        st.caption("Seleccione los repuestos utilizados y especifique la cantidad de cada uno")
                        
                        # Obtener stock disponible
                        stock_disponible_ia = get_data("SELECT id, codigo, nombre, cantidad FROM stock WHERE cantidad > 0 ORDER BY nombre")
                        
                        repuestos_seleccionados_ia = {}
                        if not stock_disponible_ia.empty:
                            # Crear opciones para multiselect
                            opciones_repuestos_ia = [f"{row['id']} - {row['nombre']} (Stock: {row['cantidad']})" for _, row in stock_disponible_ia.iterrows()]
                            repuestos_multiselect_ia = st.multiselect("Seleccionar Repuestos", opciones_repuestos_ia, key="repuestos_ia")
                            
                            # Para cada repuesto seleccionado, pedir cantidad
                            if repuestos_multiselect_ia:
                                st.markdown("**Especificar Cantidad por Repuesto:**")
                                for rep_sel in repuestos_multiselect_ia:
                                    rep_id = int(rep_sel.split(" - ")[0])
                                    rep_nombre = rep_sel.split(" - ")[1].split(" (Stock:")[0]
                                    stock_actual = stock_disponible_ia[stock_disponible_ia['id'] == rep_id].iloc[0]['cantidad']
                                    
                                    col_rep, col_cant = st.columns([3, 1])
                                    with col_rep:
                                        st.text(f"• {rep_nombre} (Stock disponible: {stock_actual})")
                                    with col_cant:
                                        cantidad_rep = st.number_input(f"Cantidad", min_value=1, max_value=int(stock_actual), value=1, 
                                                                      key=f"cant_rep_ia_{rep_id}")
                                        repuestos_seleccionados_ia[rep_id] = {
                                            'nombre': rep_nombre,
                                            'cantidad': cantidad_rep,
                                            'stock_actual': stock_actual
                                        }
                        else:
                            st.info("📭 No hay repuestos disponibles en stock")
                        
                        # Observaciones / Notas Adicionales
                        observaciones_ia = st.text_area("Observaciones / Notas Adicionales", 
                                                         placeholder="Detalle fallas específicas o comentarios sobre la reparación...",
                                                         height=100,
                                                         key="observaciones_ia")
                        
                        st.info("📋 Checklist de Servicio (Solo marcar si corresponde)")
                        ck1, ck2, ck3, ck4 = st.columns(4)
                        c_aceite = ck1.checkbox("Aceite/Filtros", key="ia_aceite")
                        c_frenos = ck2.checkbox("Frenos/Aire", key="ia_frenos")
                        c_luces = ck3.checkbox("Luces/Elec", key="ia_luces")
                        c_neu = ck4.checkbox("Neumáticos", key="ia_neu")
                        
                        check_str = f"Aceite:{c_aceite}, Frenos:{c_frenos}, Luces:{c_luces}, Neu:{c_neu}"
                        
                        if st.button("🚀 Crear Orden de Trabajo con IA"):
                            # Validar categoría
                            if not categoria_ia:
                                st.error("❌ La categoría es obligatoria")
                            # Validar proveedor si es Taller Externo
                            elif responsable == "Taller Externo" and (not proveedor_taller_ia or proveedor_taller_ia == "" or proveedor_taller_ia == "➕ Nuevo / No listado" and (not nuevo_proveedor_nombre_ia or not nuevo_proveedor_nombre_ia.strip())):
                                st.error("❌ Si el trabajo fue realizado por un Taller Externo, debe especificar el Proveedor / Taller")
                            else:
                                # Convertir repuestos a JSON
                                repuestos_json_str = json.dumps(repuestos_seleccionados_ia) if repuestos_seleccionados_ia else None
                                
                                # Si es un proveedor nuevo, insertarlo en la tabla proveedores primero
                                if nuevo_proveedor_nombre_ia and nuevo_proveedor_nombre_ia.strip():
                                    proveedor_nombre_limpio_ia = nuevo_proveedor_nombre_ia.strip()
                                    # Verificar si ya existe para evitar duplicados
                                    existe_proveedor_ia = get_data("SELECT id FROM proveedores WHERE empresa = ?", (proveedor_nombre_limpio_ia,))
                                    if existe_proveedor_ia.empty:
                                        # Insertar nuevo proveedor (solo con el nombre/empresa)
                                        run_query("INSERT INTO proveedores (empresa) VALUES (?)", (proveedor_nombre_limpio_ia,))
                                
                                # Insertar OT
                                with get_db() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        INSERT INTO mantenimientos (fecha, movil, chofer, descripcion, checklist, repuesto, cantidad, estado, costo_total, categoria, costo_terceros, repuestos_json, proveedor_taller, observaciones, responsable)
                                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                    """, (fecha, movil, chofer, descripcion_final, check_str, repuestos_final, cantidad_total, 'Pendiente', 0, categoria_ia, costo_terceros_ia, repuestos_json_str, proveedor_taller_final_ia, observaciones_ia if observaciones_ia else None, responsable))
                                    ot_id = cursor.lastrowid
                                    
                                    # Restar stock de repuestos utilizados
                                    alertas_stock = []
                                    for rep_id, rep_data in repuestos_seleccionados_ia.items():
                                        cantidad_usada = rep_data['cantidad']
                                        stock_anterior = rep_data['stock_actual']
                                        
                                        # Restar del stock
                                        cursor.execute("UPDATE stock SET cantidad = cantidad - ? WHERE id=?", (cantidad_usada, rep_id))
                                        
                                        # Verificar si llegó a 0 (usar cursor para obtener el valor actualizado)
                                        cursor.execute("SELECT cantidad FROM stock WHERE id=?", (rep_id,))
                                        stock_nuevo = cursor.fetchone()[0]
                                        if stock_nuevo <= 0:
                                            alertas_stock.append(f"{rep_data['nombre']} (Stock: {stock_nuevo})")
                                    
                                    conn.commit()
                                
                                # Mostrar alertas si hay stock en 0
                                if alertas_stock:
                                    st.warning(f"⚠️ **ALERTA:** Los siguientes repuestos quedaron con stock en 0 o negativo:\n" + "\n".join([f"• {a}" for a in alertas_stock]))
                                
                                st.success("✅ Orden Creada Exitosamente con datos de IA")
                                st.rerun()
                    else:
                        st.warning("⚠️ No se pudieron detectar elementos en la imagen. Intente con otra foto o use el Modo Manual.")
            else:
                st.info("👆 Capture una imagen para comenzar el análisis con IA")

    with t2:
        # Filtros de estado
        col_filtro1, col_filtro2 = st.columns([2, 1])
        with col_filtro1:
            filtro = st.text_input("🔍 Filtrar por Móvil o ID...")
        with col_filtro2:
            filtro_estado = st.selectbox("📊 Estado", ["Todas", "Solo Pendientes", "Solo Cerradas"], key="filtro_estado_ot")
        
        # Construir query base
        base_q = "SELECT * FROM mantenimientos WHERE 1=1"
        
        # Aplicar filtro de estado
        if filtro_estado == "Solo Pendientes":
            base_q += " AND (estado = 'Pendiente' OR estado IS NULL OR estado = '')"
        elif filtro_estado == "Solo Cerradas":
            base_q += " AND estado = 'Cerrada'"
        
        # Aplicar filtro de texto
        if filtro:
            base_q += f" AND (movil LIKE '%{filtro}%' OR id LIKE '%{filtro}%')"
        
        base_q += " ORDER BY id DESC"
        
        df = get_data(base_q)
        
        if not df.empty:
            st.subheader("📋 Lista de Órdenes de Trabajo")
            for _, r in df.iterrows():
                # Fila interactiva
                col_info, col_acciones = st.columns([4, 2])
                
                with col_info:
                    estado_color = {"Pendiente": "#f59e0b", "En Proceso": "#3b82f6", "Cerrada": "#22c55e"}.get(r['estado'], "#94a3b8")
                    st.markdown(f"""
                    <div style='background: #1e293b; padding: 12px; border-radius: 8px; border-left: 4px solid {estado_color}; margin-bottom: 10px;'>
                        <div style='font-size: 16px; font-weight: bold; color: #f8fafc;'>OT #{r['id']} | {r['movil']} | <span style='color: {estado_color};'>{r['estado']}</span></div>
                        <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>📅 {r['fecha']} | 👤 {r['chofer'] or 'Sin chofer'}</div>
                        <div style='font-size: 11px; color: #64748b; margin-top: 3px;'>{r['descripcion'][:80]}{'...' if len(str(r['descripcion'])) > 80 else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_acciones:
                    # Mostrar fecha de cierre si está cerrada
                    estado_actual = r.get('estado', 'Pendiente') or 'Pendiente'
                    fecha_cierre_actual = r.get('fecha_cierre', '') or ''
                    
                    if estado_actual == 'Cerrada' and fecha_cierre_actual:
                        st.caption(f"✅ Cerrada el: {fecha_cierre_actual}")
                    
                    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                    
                    with btn_col1:
                        if st.button("✏️", key=f"edit_{r['id']}", help="Editar OT"):
                            st.session_state[f"editing_ot_{r['id']}"] = True
                            st.rerun()
                    
                    with btn_col2:
                        path_pdf = generar_pdf_ot(r['id'])
                        if path_pdf and os.path.exists(path_pdf):
                            with open(path_pdf, "rb") as f:
                                st.download_button("📄", f, file_name=f"OT_{r['id']}.pdf", key=f"pdf_{r['id']}", help="Descargar PDF")
                    
                    with btn_col3:
                        # Botón Cerrar OT (solo si está pendiente)
                        if estado_actual != 'Cerrada':
                            if st.button("✅ Cerrar", key=f"cerrar_{r['id']}", help="Cerrar esta OT", type="primary"):
                                fecha_hoy = date.today().strftime("%Y-%m-%d")
                                run_query("UPDATE mantenimientos SET estado=?, fecha_cierre=? WHERE id=?", 
                                         ('Cerrada', fecha_hoy, r['id']))
                                st.success(f"✅ OT #{r['id']} cerrada exitosamente")
                                time.sleep(0.5)
                                st.rerun()
                        else:
                            st.caption("✅ Cerrada")
                    
                    with btn_col4:
                        borrado_seguro("OT", f"OT #{r['id']} - {r['movil']}", r['id'], "mantenimientos")
                
                # Modal de edición
                if st.session_state.get(f"editing_ot_{r['id']}", False):
                    with st.popover("✏️ Editar OT", use_container_width=True):
                        with st.form(f"form_edit_ot_{r['id']}"):
                            edit_fecha = st.date_input("Fecha", value=datetime.strptime(r['fecha'], '%Y-%m-%d').date() if r['fecha'] else date.today())
                            edit_movil = st.selectbox("Móvil", get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist(), 
                                                      index=get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist().index(r['movil']) if r['movil'] in get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist() else 0)
                            edit_chofer = st.selectbox("Chofer", [""] + get_data("SELECT nombre FROM choferes")['nombre'].tolist(),
                                                      index=([""] + get_data("SELECT nombre FROM choferes")['nombre'].tolist()).index(r['chofer']) if r['chofer'] in [""] + get_data("SELECT nombre FROM choferes")['nombre'].tolist() else 0)
                            edit_desc = st.text_area("Descripción", value=r['descripcion'])
                            edit_estado = st.selectbox("Estado", ["Pendiente", "En Proceso", "Cerrada"], 
                                                       index=["Pendiente", "En Proceso", "Cerrada"].index(r['estado']) if r['estado'] in ["Pendiente", "En Proceso", "Cerrada"] else 0)
                            edit_costo = st.number_input("Costo Total", value=float(r['costo_total']) if r['costo_total'] else 0.0)
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Guardar"):
                                    # Si se cambia a Cerrada y no tiene fecha_cierre, agregarla
                                    fecha_cierre_val = None
                                    if edit_estado == 'Cerrada':
                                        fecha_cierre_actual = r.get('fecha_cierre', '') or ''
                                        if not fecha_cierre_actual:
                                            fecha_cierre_val = date.today().strftime("%Y-%m-%d")
                                        else:
                                            fecha_cierre_val = fecha_cierre_actual
                                    
                                    if fecha_cierre_val:
                                        run_query("UPDATE mantenimientos SET fecha=?, movil=?, chofer=?, descripcion=?, estado=?, costo_total=?, fecha_cierre=? WHERE id=?",
                                                 (str(edit_fecha), edit_movil, edit_chofer, edit_desc, edit_estado, edit_costo, fecha_cierre_val, r['id']))
                                    else:
                                        run_query("UPDATE mantenimientos SET fecha=?, movil=?, chofer=?, descripcion=?, estado=?, costo_total=? WHERE id=?",
                                                 (str(edit_fecha), edit_movil, edit_chofer, edit_desc, edit_estado, edit_costo, r['id']))
                                    st.session_state[f"editing_ot_{r['id']}"] = False
                                    st.success("✅ OT actualizada")
                                    st.rerun()
                            with col_cancel:
                                if st.form_submit_button("❌ Cancelar"):
                                    st.session_state[f"editing_ot_{r['id']}"] = False
                                    st.rerun()
        else:
            st.info("📭 No hay órdenes de trabajo registradas")
    
    with t3:
        st.subheader("📢 Gestión de Novedades")
        
        col_nueva, col_lista = st.columns([1, 2])
        
        with col_nueva:
            st.info("➕ Nueva Novedad")
            with st.form("nueva_novedad"):
                nov_fecha = st.date_input("Fecha")
                nov_movil = st.selectbox("Móvil", get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist())
                nov_desc = st.text_area("Descripción de la Novedad", placeholder="Ej: Ruido en puerta, Luz parpadea...")
                if st.form_submit_button("📝 Registrar Novedad"):
                    run_query("INSERT INTO novedades (fecha, movil, descripcion, estado) VALUES (?,?,?,?)",
                             (nov_fecha, nov_movil, nov_desc, 'Activa'))
                    st.success("✅ Novedad registrada")
                    st.rerun()
        
        with col_lista:
            st.subheader("📋 Novedades Activas")
            df_nov = get_data("SELECT * FROM novedades WHERE estado='Activa' ORDER BY id DESC")
            
            if not df_nov.empty:
                for _, nov in df_nov.iterrows():
                    with st.container():
                        col_nov_info, col_nov_acc = st.columns([3, 1])
                        with col_nov_info:
                            st.markdown(f"""
                            <div style='background: #1e293b; padding: 10px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #f59e0b;'>
                                <div style='font-weight: bold; color: #f8fafc;'>{nov['movil']} - {nov['fecha']}</div>
                                <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>{nov['descripcion']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_nov_acc:
                            if st.button("📋 Pasar a OT", key=f"to_ot_{nov['id']}"):
                                # Crear OT desde novedad (con valores por defecto para nuevos campos)
                                categorias = ['Mecánica General', 'Mecánica Pesada (Motor/Caja)', 'Electricidad', 'Frenos', 'Neumáticos / Gomería', 'Carrocería', 'Pintura', 'Aire Acondicionado', 'Sistema de Combustible', 'Lavadero', 'Servicios / Lubricación', 'Conductores', 'Reparaciones Generales']
                                categoria_default = categorias[0]  # Primera categoría por defecto
                                run_query("INSERT INTO mantenimientos (fecha, movil, descripcion, estado, categoria, costo_terceros, repuestos_json, proveedor_taller, observaciones, responsable) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                         (nov['fecha'], nov['movil'], nov['descripcion'], 'Pendiente', categoria_default, 0.0, None, None, None, 'Otro'))
                                run_query("UPDATE novedades SET estado='Archivada' WHERE id=?", (nov['id'],))
                                st.success("✅ Novedad convertida a OT")
                                st.rerun()
                            if st.button("📁 Archivar", key=f"arch_{nov['id']}"):
                                run_query("UPDATE novedades SET estado='Archivada' WHERE id=?", (nov['id'],))
                                st.success("✅ Novedad archivada")
                                st.rerun()
            else:
                st.info("📭 No hay novedades activas")

# --- STOCK VISUAL ---
elif nav == "📦 STOCK VISUAL":
    st.title("Almacén de Repuestos")
    
    # Función de búsqueda inteligente
    def buscar_inteligente(df, query, columna='nombre'):
        if not query or query.strip() == '':
            return df
        palabras_clave = [palabra.strip().lower() for palabra in query.split() if palabra.strip()]
        if not palabras_clave:
            return df
        def contiene_todas_palabras(nombre):
            nombre_lower = str(nombre).lower()
            return all(palabra in nombre_lower for palabra in palabras_clave)
        return df[df[columna].apply(contiene_todas_palabras)]
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👁️ VISOR", "➕ NUEVO/EDITAR", "📥 INGRESOS (+)", "📤 EGRESOS (-)", "🛞 GESTIÓN DE CUBIERTAS"])
    
    # PESTAÑA 1: VISOR
    with tab1:
        q = st.text_input("🔍 Buscar repuesto...")
        df = get_data("SELECT * FROM stock")
        if q: df = buscar_inteligente(df, q)
        
        cols = st.columns(4)
        for i, r in df.iterrows():
            with cols[i % 4]:
                border_cls = "stock-low" if r['cantidad'] <= r['minimo'] else "stock-ok"
                codigo_val = r.get('codigo', '') if 'codigo' in r else ''
                codigo_display = codigo_val if codigo_val and str(codigo_val).strip() else 'Sin código'
                proveedor_val = r.get('proveedor', '') if 'proveedor' in r else ''
                proveedor_display = proveedor_val if proveedor_val and str(proveedor_val).strip() else 'Sin proveedor'
                precio_val = r.get('precio', 0) or 0
                precio_display = f"${precio_val:,.2f}" if precio_val > 0 else "Sin precio"
                fecha_ingreso_val = r.get('fecha_ingreso', '') if 'fecha_ingreso' in r else ''
                fecha_ingreso_display = fecha_ingreso_val if fecha_ingreso_val and str(fecha_ingreso_val).strip() else '-'
                st.markdown(f"""
                <div class='stock-card {border_cls}'>
                    <div style='color:#38bdf8; font-size:11px; font-weight:600; margin-bottom:5px;'>Código: {codigo_display}</div>
                    <div style='font-weight:bold; font-size:16px'>{r['nombre']}</div>
                    <div style='font-size:30px; font-weight:800'>{r['cantidad']}</div>
                    <div style='color:#22c55e; font-size:14px; font-weight:700; margin:8px 0;'>💰 {precio_display}</div>
                    <div style='color:#94a3b8; font-size:12px'>Mínimo: {r['minimo']}</div>
                    <div style='color:#64748b; font-size:10px; margin-top:5px; font-style:italic;'>🤝 {proveedor_display}</div>
                    <div style='color:#64748b; font-size:9px; margin-top:3px;'>📅 Ingreso: {fecha_ingreso_display}</div>
                </div>
                """, unsafe_allow_html=True)
    
    # PESTAÑA 2: NUEVO/EDITAR
    with tab2:
        col_crear, col_editar = st.columns(2)
        
        with col_crear:
            st.subheader("➕ Nuevo Artículo")
            with st.form("new_item"):
                n_cod = st.text_input("Código")
                n_nom = st.text_input("Nombre *", placeholder="Nombre del repuesto")
                n_cant = st.number_input("Cantidad Inicial", min_value=0, value=0)
                n_min = st.number_input("Stock Mínimo", min_value=0, value=2)
                n_precio = st.number_input("Precio Unitario $", min_value=0.0, value=0.0, step=0.01)
                n_rubro = st.text_input("Rubro")
                proveedores_lista = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
                n_prov = st.selectbox("Proveedor", [""] + proveedores_lista)
                if st.form_submit_button("💾 Guardar Artículo"):
                    if n_nom:
                        fecha_hoy = date.today().strftime("%Y-%m-%d")
                        run_query("INSERT INTO stock (codigo, nombre, cantidad, minimo, precio, rubro, proveedor, fecha_ingreso) VALUES (?,?,?,?,?,?,?,?)", 
                                 (n_cod, n_nom, n_cant, n_min, n_precio, n_rubro, n_prov if n_prov else None, fecha_hoy))
                        st.success("✅ Artículo creado")
                        st.rerun()
                    else:
                        st.error("❌ El nombre es obligatorio")
        
        with col_editar:
            st.subheader("✏️ Editar/Borrar Artículo")
            items_lista = get_data("SELECT id, nombre FROM stock ORDER BY nombre")
            if not items_lista.empty:
                item_seleccionado = st.selectbox("Seleccionar Artículo", 
                                                options=[f"{row['id']} - {row['nombre']}" for _, row in items_lista.iterrows()])
                if item_seleccionado:
                    item_id = int(item_seleccionado.split(" - ")[0])
                    item_data = get_data("SELECT * FROM stock WHERE id=?", (item_id,)).iloc[0]
                    
                    with st.form(f"edit_item_{item_id}"):
                        e_cod = st.text_input("Código", value=item_data.get('codigo', ''))
                        e_nom = st.text_input("Nombre *", value=item_data.get('nombre', ''))
                        e_cant = st.number_input("Cantidad", min_value=0, value=int(item_data.get('cantidad', 0)))
                        e_min = st.number_input("Stock Mínimo", min_value=0, value=int(item_data.get('minimo', 2)))
                        e_precio = st.number_input("Precio Unitario $", min_value=0.0, value=float(item_data.get('precio', 0)), step=0.01)
                        e_rubro = st.text_input("Rubro", value=item_data.get('rubro', ''))
                        proveedores_lista = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
                        e_prov = st.selectbox("Proveedor", [""] + proveedores_lista,
                                             index=([""] + proveedores_lista).index(item_data.get('proveedor', '')) if item_data.get('proveedor', '') in [""] + proveedores_lista else 0)
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 Guardar Cambios"):
                                run_query("UPDATE stock SET codigo=?, nombre=?, cantidad=?, minimo=?, precio=?, rubro=?, proveedor=? WHERE id=?",
                                         (e_cod, e_nom, e_cant, e_min, e_precio, e_rubro, e_prov if e_prov else None, item_id))
                                st.success("✅ Artículo actualizado")
                                st.rerun()
                        with col_del:
                            if st.form_submit_button("🗑️ Borrar"):
                                borrado_seguro("Artículo", e_nom, item_id, "stock")
            else:
                st.info("📭 No hay artículos para editar")
    
    # PESTAÑA 3: INGRESOS (+)
    with tab3:
        st.subheader("📥 Registrar Ingreso de Stock")
        with st.form("ingreso_stock"):
            ing_fecha = st.date_input("Fecha de Compra")
            proveedores_lista = get_data("SELECT empresa FROM proveedores ORDER BY empresa")['empresa'].tolist()
            ing_prov = st.selectbox("Proveedor *", [""] + proveedores_lista)
            items_lista = get_data("SELECT id, nombre FROM stock ORDER BY nombre")
            if not items_lista.empty:
                ing_item = st.selectbox("Artículo *", 
                                       options=[f"{row['id']} - {row['nombre']}" for _, row in items_lista.iterrows()])
                ing_cant = st.number_input("Cantidad", min_value=1, value=1)
                ing_comp = st.text_input("Nro. Comprobante")
                if st.form_submit_button("📥 Registrar Ingreso"):
                    if ing_prov and ing_item:
                        item_id = int(ing_item.split(" - ")[0])
                        # Sumar al stock
                        run_query("UPDATE stock SET cantidad = cantidad + ? WHERE id=?", (ing_cant, item_id))
                        st.success(f"✅ Ingreso registrado: +{ing_cant} unidades")
                        st.rerun()
                    else:
                        st.error("❌ Proveedor y Artículo son obligatorios")
            else:
                st.warning("⚠️ No hay artículos en stock. Cree uno primero en la pestaña NUEVO/EDITAR")
    
    # PESTAÑA 4: EGRESOS (-)
    with tab4:
        st.subheader("📤 Registrar Egreso de Stock")
        with st.form("egreso_stock"):
            eg_fecha = st.date_input("Fecha")
            items_lista = get_data("SELECT id, nombre, cantidad FROM stock WHERE cantidad > 0 ORDER BY nombre")
            if not items_lista.empty:
                eg_item = st.selectbox("Artículo *", 
                                      options=[f"{row['id']} - {row['nombre']} (Stock: {row['cantidad']})" for _, row in items_lista.iterrows()])
                eg_cant = st.number_input("Cantidad a Retirar", min_value=1, value=1)
                eg_destino = st.selectbox("Destino", ["Taller", "Mecánico", "Otro"])
                if eg_destino == "Otro":
                    eg_destino_otro = st.text_input("Especificar destino")
                    eg_destino = eg_destino_otro
                moviles_lista = get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist()
                eg_movil = st.selectbox("Móvil (si aplica)", [""] + moviles_lista)
                
                if st.form_submit_button("📤 Registrar Egreso"):
                    if eg_item:
                        item_id = int(eg_item.split(" - ")[0])
                        item_data = get_data("SELECT cantidad FROM stock WHERE id=?", (item_id,)).iloc[0]
                        if eg_cant <= item_data['cantidad']:
                            # Restar del stock
                            run_query("UPDATE stock SET cantidad = cantidad - ? WHERE id=?", (eg_cant, item_id))
                            st.success(f"✅ Egreso registrado: -{eg_cant} unidades a {eg_destino}")
                            st.rerun()
                        else:
                            st.error(f"❌ No hay suficiente stock. Disponible: {item_data['cantidad']}")
            else:
                st.warning("⚠️ No hay artículos con stock disponible")
    
    # PESTAÑA 5: GESTIÓN DE CUBIERTAS
    with tab5:
        st.subheader("🛞 Gestión de Cubiertas por Lotes")
        
        # KPI: Total de Cubiertas en Stock
        df_cubiertas_kpi = get_data("SELECT SUM(cantidad) as total FROM stock_cubiertas")
        total_cubiertas = int(df_cubiertas_kpi.iloc[0]['total']) if not df_cubiertas_kpi.empty and df_cubiertas_kpi.iloc[0]['total'] is not None else 0
        st.metric("📊 Total de Cubiertas en Stock", f"{total_cubiertas:,} unidades")
        
        st.divider()
        
        # FORMULARIO DE CARGA
        st.markdown("### ➕ Alta de Cubiertas")
        with st.form("form_cubiertas", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                marca = st.text_input("Marca *", placeholder="Ej: Michelin, Fate, Bridgestone")
                modelo = st.text_input("Modelo *", placeholder="Ej: Multi Z 2 Evolution")
                
                # Medida con selectbox y opción de texto libre
                medidas_comunes = [
                    "295/80 R22.5",
                    "275/80 R22.5",
                    "11 R22.5",
                    "315/80 R22.5",
                    "12 R22.5",
                    "385/65 R22.5",
                    "Otra (especificar)"
                ]
                medida_sel = st.selectbox("Medida *", medidas_comunes)
                if medida_sel == "Otra (especificar)":
                    medida = st.text_input("Especificar medida", placeholder="Ej: 295/75 R22.5")
                else:
                    medida = medida_sel
                
                dot = st.text_input("DOT (Año/Semana)", placeholder="Ej: 3523 (Opcional)", max_chars=4)
            
            with col2:
                estado = st.selectbox("Estado *", ["Nueva", "Recapada", "Usada"])
                cantidad = st.number_input("Cantidad *", min_value=1, value=1, step=1)
                
                ubicaciones = ["Pañol", "Auxilio", "Almacén", "Taller", "Otro"]
                ubicacion_sel = st.selectbox("Ubicación *", ubicaciones)
                if ubicacion_sel == "Otro":
                    ubicacion = st.text_input("Especificar ubicación", placeholder="Ej: Depósito externo")
                else:
                    ubicacion = ubicacion_sel
            
            if st.form_submit_button("✅ Guardar Lote de Cubiertas", use_container_width=True):
                # Validar medida (obligatorio)
                medida_valida = medida.strip() if medida and medida.strip() else ""
                if medida_sel == "Otra (especificar)" and not medida_valida:
                    st.error("❌ El campo 'Medida' es obligatorio. Por favor especifique la medida.")
                elif marca and modelo and medida_valida and estado and cantidad and ubicacion:
                    try:
                        dot_valor = dot.strip() if dot and dot.strip() else None
                        run_query("""
                            INSERT INTO stock_cubiertas (marca, modelo, medida, dot, estado, cantidad, ubicacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (marca.strip(), modelo.strip(), medida_valida, dot_valor, estado, cantidad, ubicacion.strip()))
                        st.success(f"✅ Lote de {cantidad} cubiertas {marca} {modelo} guardado exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")
                else:
                    st.error("❌ Por favor complete todos los campos obligatorios (*)")
        
        st.divider()
        
        # GRILLA EDITABLE
        st.markdown("### 📋 Stock de Cubiertas (Editable)")
        df_cubiertas = get_data("SELECT * FROM stock_cubiertas ORDER BY marca, modelo, medida")
        
        if not df_cubiertas.empty:
            # Preparar DataFrame para edición (ocultar id en la visualización pero mantenerlo)
            df_edit = df_cubiertas.copy()
            
            # Mostrar data_editor
            df_edited = st.data_editor(
                df_edit[['marca', 'modelo', 'medida', 'dot', 'estado', 'cantidad', 'ubicacion']],
                column_config={
                    "marca": st.column_config.TextColumn("Marca", width="medium"),
                    "modelo": st.column_config.TextColumn("Modelo", width="medium"),
                    "medida": st.column_config.TextColumn("Medida", width="medium"),
                    "dot": st.column_config.TextColumn("DOT", width="small"),
                    "estado": st.column_config.SelectboxColumn(
                        "Estado",
                        options=["Nueva", "Recapada", "Usada"],
                        width="small"
                    ),
                    "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, width="small"),
                    "ubicacion": st.column_config.TextColumn("Ubicación", width="medium")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_cubiertas"
            )
            
            # Botón para guardar cambios
            col_guardar, col_info = st.columns([1, 3])
            with col_guardar:
                if st.button("💾 Guardar Cambios", use_container_width=True, type="primary"):
                    try:
                        # Comparar cambios y actualizar
                        cambios_realizados = False
                        for idx, row_edit in df_edited.iterrows():
                            if idx < len(df_cubiertas):
                                row_original = df_cubiertas.iloc[idx]
                                id_cubierta = row_original['id']
                                
                                # Verificar si hubo cambios
                                if (row_edit['marca'] != row_original['marca'] or
                                    row_edit['modelo'] != row_original['modelo'] or
                                    row_edit['medida'] != row_original['medida'] or
                                    row_edit['dot'] != row_original['dot'] or
                                    row_edit['estado'] != row_original['estado'] or
                                    row_edit['cantidad'] != row_original['cantidad'] or
                                    row_edit['ubicacion'] != row_original['ubicacion']):
                                    
                                    run_query("""
                                        UPDATE stock_cubiertas 
                                        SET marca=?, modelo=?, medida=?, dot=?, estado=?, cantidad=?, ubicacion=?
                                        WHERE id=?
                                    """, (
                                        row_edit['marca'], row_edit['modelo'], row_edit['medida'],
                                        row_edit['dot'], row_edit['estado'], int(row_edit['cantidad']),
                                        row_edit['ubicacion'], id_cubierta
                                    ))
                                    cambios_realizados = True
                        
                        # Manejar filas nuevas (si se agregaron)
                        if len(df_edited) > len(df_cubiertas):
                            nuevas_filas = df_edited.iloc[len(df_cubiertas):]
                            for _, nueva_fila in nuevas_filas.iterrows():
                                run_query("""
                                    INSERT INTO stock_cubiertas (marca, modelo, medida, dot, estado, cantidad, ubicacion)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    nueva_fila['marca'], nueva_fila['modelo'], nueva_fila['medida'],
                                    nueva_fila['dot'], nueva_fila['estado'], int(nueva_fila['cantidad']),
                                    nueva_fila['ubicacion']
                                ))
                                cambios_realizados = True
                        
                        if cambios_realizados:
                            st.success("✅ Cambios guardados exitosamente")
                            st.rerun()
                        else:
                            st.info("ℹ️ No se detectaron cambios")
                    except Exception as e:
                        st.error(f"❌ Error al guardar cambios: {e}")
            
            with col_info:
                st.caption("💡 Puede editar directamente en la grilla y hacer clic en 'Guardar Cambios' para aplicar las modificaciones")
        else:
            st.info("📭 No hay cubiertas cargadas. Use el formulario superior para agregar el primer lote.")

# --- FLOTA ---
elif nav == "🚛 FLOTA":
    st.title("Gestión de Flota")
    st.subheader("Estado de Unidades")
    df_f = get_data("SELECT * FROM flota")
    
    # Función para calcular estado del service y color
    def calcular_estado_service(km_actual, km_ultimo, km_interval):
        km_actual = km_actual or 0
        km_ultimo = km_ultimo or 0
        km_interval = km_interval or 15000
        
        km_recorridos = km_actual - km_ultimo
        km_restantes = km_interval - km_recorridos
        porcentaje = min(100, max(0, (km_recorridos / km_interval) * 100)) if km_interval > 0 else 0
        
        if km_recorridos >= km_interval:
            estado = "vencido"
            color = "#ef4444"  # ROJO
            texto = f"Service Vencido (+{km_recorridos - km_interval:,} km)"
        elif km_restantes <= 1000:
            estado = "proximo"
            color = "#f59e0b"  # AMARILLO
            texto = f"Service Próximo ({km_restantes:,} km restantes)"
        else:
            estado = "ok"
            color = "#22c55e"  # VERDE
            texto = f"Service OK ({km_restantes:,} km restantes)"
        
        return estado, color, texto, porcentaje, km_restantes
    
    # Grilla de Tarjetas (3 por fila)
    if not df_f.empty:
        for i in range(0, len(df_f), 3):
            fila = df_f.iloc[i:i+3]
            cols = st.columns(3)
            
            for idx, (col, (_, unidad)) in enumerate(zip(cols, fila.iterrows())):
                with col:
                    # Calcular estado
                    estado, color_borde, texto_estado, porcentaje, km_restantes = calcular_estado_service(
                        unidad.get('km_actual', 0),
                        unidad.get('km_ultimo_service', 0),
                        unidad.get('km_service_interval', 15000)
                    )
                    
                    # Calcular CPK (Costo por KM)
                    movil_nombre = unidad.get('nombre_movil', '')
                    km_total = unidad.get('km_actual', 0) or 0
                    gasto_taller = get_data("SELECT SUM(costo_total) FROM mantenimientos WHERE movil=?", (movil_nombre,)).iloc[0,0] or 0
                    gasto_comb = get_data("SELECT SUM(costo) FROM combustible WHERE movil=?", (movil_nombre,)).iloc[0,0] or 0
                    gasto_total = gasto_taller + gasto_comb
                    cpk = gasto_total / km_total if km_total > 0 else 0
                    
                    # Tarjeta con borde de color según estado
                    st.markdown(f"""
                    <div style='background: #1e293b; border: 3px solid {color_borde}; border-radius: 12px; padding: 15px; margin-bottom: 15px;'>
                        <div style='font-size: 18px; font-weight: bold; color: #f8fafc; margin-bottom: 8px;'>{unidad['nombre_movil'] or 'Sin nombre'}</div>
                        <div style='font-size: 12px; color: #94a3b8; margin-bottom: 10px;'>
                            🚛 Patente: {unidad.get('patente', 'N/A')} | Modelo: {unidad.get('modelo', 'N/A')}
                        </div>
                        <div style='font-size: 32px; font-weight: 800; color: #38bdf8; margin: 15px 0; text-align: center;'>
                            {unidad.get('km_actual', 0):,} km
                        </div>
                        <div style='font-size: 10px; color: #64748b; text-align: center; margin-bottom: 10px; font-style: italic;'>
                            📅 Última actualización: {unidad.get('fecha_actualizacion_km', 'N/A') or 'N/A'}
                        </div>
                        <div style='background: #334155; padding: 8px; border-radius: 6px; margin: 10px 0; text-align: center;'>
                            <div style='font-size: 10px; color: #94a3b8; margin-bottom: 3px;'>COSTO POR KM (CPK)</div>
                            <div style='font-size: 18px; font-weight: bold; color: #f59e0b;'>${cpk:.2f}</div>
                        </div>
                        <div style='margin: 10px 0;'>
                            <div style='font-size: 11px; color: #94a3b8; margin-bottom: 5px;'>{texto_estado}</div>
                            <div style='background: #334155; border-radius: 5px; height: 8px; overflow: hidden;'>
                                <div style='background: {color_borde}; height: 100%; width: {min(100, porcentaje)}%; transition: width 0.3s;'></div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Botones de acción
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        with st.popover("✏️ Editar KM"):
                            st.caption(f"Actualizar kilometraje de {unidad['nombre_movil']}")
                            with st.form(f"edit_km_{unidad['id']}"):
                                nuevo_km = st.number_input("Kilometraje Actual", min_value=0, value=int(unidad.get('km_actual', 0)), key=f"km_{unidad['id']}")
                                if st.form_submit_button("💾 Actualizar KM"):
                                    fecha_hoy = date.today().strftime("%Y-%m-%d")
                                    run_query("UPDATE flota SET km_actual=?, fecha_actualizacion_km=? WHERE id=?", (nuevo_km, fecha_hoy, unidad['id']))
                                    st.success("✅ KM actualizado")
                                    time.sleep(0.3)
                                    st.rerun()
                    with btn_col2:
                        if st.button("✏️", key=f"edit_flota_{unidad['id']}", help="Editar Móvil"):
                            st.session_state[f"editing_flota_{unidad['id']}"] = True
                            st.rerun()
                    with btn_col3:
                        borrado_seguro("Móvil", unidad['nombre_movil'], unidad['id'], "flota")
                    
                    # Modal de edición completa
                    if st.session_state.get(f"editing_flota_{unidad['id']}", False):
                        with st.popover("✏️ Editar Móvil", use_container_width=True):
                            with st.form(f"form_edit_flota_{unidad['id']}"):
                                e_nom = st.text_input("Nombre Móvil", value=unidad.get('nombre_movil', ''))
                                e_pat = st.text_input("Patente", value=unidad.get('patente', ''))
                                e_modelo = st.text_input("Modelo", value=unidad.get('modelo', ''))
                                e_km = st.number_input("KM Actual", min_value=0, value=int(unidad.get('km_actual', 0)))
                                e_km_ultimo = st.number_input("KM Último Service", min_value=0, value=int(unidad.get('km_ultimo_service', 0)))
                                e_km_interval = st.number_input("Intervalo Service", min_value=0, value=int(unidad.get('km_service_interval', 15000)))
                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.form_submit_button("💾 Guardar"):
                                        # Si el KM cambió, actualizar fecha_actualizacion_km
                                        km_anterior = unidad.get('km_actual', 0) or 0
                                        fecha_hoy = date.today().strftime("%Y-%m-%d")
                                        if e_km != km_anterior:
                                            run_query("UPDATE flota SET nombre_movil=?, patente=?, modelo=?, km_actual=?, km_ultimo_service=?, km_service_interval=?, fecha_actualizacion_km=? WHERE id=?",
                                                     (e_nom, e_pat, e_modelo, e_km, e_km_ultimo, e_km_interval, fecha_hoy, unidad['id']))
                                        else:
                                            run_query("UPDATE flota SET nombre_movil=?, patente=?, modelo=?, km_actual=?, km_ultimo_service=?, km_service_interval=? WHERE id=?",
                                                     (e_nom, e_pat, e_modelo, e_km, e_km_ultimo, e_km_interval, unidad['id']))
                                        st.session_state[f"editing_flota_{unidad['id']}"] = False
                                        st.success("✅ Móvil actualizado")
                                        st.rerun()
                                with col_cancel:
                                    if st.form_submit_button("❌ Cancelar"):
                                        st.session_state[f"editing_flota_{unidad['id']}"] = False
                                        st.rerun()
    else:
        st.info("📭 No hay unidades en la flota. Agregue una usando el formulario a continuación.")
    
    with st.expander("📝 Editar / Agregar Camión"):
        with st.form("edit_flota"):
            f_nom = st.text_input("Nombre Móvil (Ej: MB 1620)")
            f_pat = st.text_input("Patente")
            f_modelo = st.text_input("Modelo")
            f_km = st.number_input("KM Actual", 0)
            f_km_ultimo = st.number_input("KM Último Service", 0)
            f_km_interval = st.number_input("Intervalo de Service (km)", 15000)
            if st.form_submit_button("Guardar / Actualizar"):
                # Logica simple de insert (en prod usar UPDATE si existe)
                run_query("INSERT INTO flota (nombre_movil, patente, modelo, km_actual, km_ultimo_service, km_service_interval) VALUES (?,?,?,?,?,?)", 
                         (f_nom, f_pat, f_modelo, f_km, f_km_ultimo, f_km_interval))
                st.success("Guardado"); st.rerun()

# --- COMBUSTIBLE ---
elif nav == "⛽ COMBUSTIBLE":
    st.title("Control de Combustible")
    with st.form("fuel_load"):
        c1, c2 = st.columns(2)
        f_date = c1.date_input("Fecha")
        f_mov = c1.selectbox("Móvil", get_data("SELECT nombre_movil FROM flota")['nombre_movil'].tolist())
        
        # Mostrar km_actual como referencia visual
        if f_mov:
            km_actual_data = get_data("SELECT km_actual FROM flota WHERE nombre_movil=?", (f_mov,))
            if not km_actual_data.empty:
                km_actual = km_actual_data.iloc[0]['km_actual'] or 0
                c1.info(f"📊 **KM Actual del Móvil:** {km_actual:,} km")
        
        f_chof = c2.selectbox("Chofer", get_data("SELECT nombre FROM choferes")['nombre'].tolist())
        f_litros = c1.number_input("Litros")
        f_costo = c2.number_input("Costo Total $")
        f_km = c1.number_input("Odómetro Actual", min_value=0)
        
        if st.form_submit_button("Registrar Carga"):
            # Validación bloqueante: verificar que el km ingresado no sea menor al actual
            if f_mov:
                km_actual_data = get_data("SELECT km_actual FROM flota WHERE nombre_movil=?", (f_mov,))
                if not km_actual_data.empty:
                    km_actual = km_actual_data.iloc[0]['km_actual'] or 0
                    if f_km < km_actual:
                        st.error(f"❌ **Error de Validación:** El kilometraje ingresado ({f_km:,} km) es MENOR al kilometraje actual del móvil ({km_actual:,} km). Por favor, verifique el dato.")
                    else:
                        # Si la validación pasa, guardar en la base de datos
                        run_query("INSERT INTO combustible (fecha, movil, chofer, litros, costo, km_momento) VALUES (?,?,?,?,?,?)", 
                                  (f_date, f_mov, f_chof, f_litros, f_costo, f_km))
                        # Actualiza KM del camion automaticamente con fecha de actualización
                        fecha_hoy = date.today().strftime("%Y-%m-%d")
                        run_query("UPDATE flota SET km_actual=?, fecha_actualizacion_km=? WHERE nombre_movil=?", (f_km, fecha_hoy, f_mov))
                        st.success("✅ Carga registrada exitosamente")
                        st.rerun()
                else:
                    # Si no hay datos del móvil, guardar igual
                    run_query("INSERT INTO combustible (fecha, movil, chofer, litros, costo, km_momento) VALUES (?,?,?,?,?,?)", 
                              (f_date, f_mov, f_chof, f_litros, f_costo, f_km))
                    # Actualiza KM del camion automaticamente con fecha de actualización
                    fecha_hoy = date.today().strftime("%Y-%m-%d")
                    run_query("UPDATE flota SET km_actual=?, fecha_actualizacion_km=? WHERE nombre_movil=?", (f_km, fecha_hoy, f_mov))
                    st.success("✅ Carga registrada exitosamente")
                    st.rerun()
            else:
                st.error("❌ Por favor, seleccione un móvil")
            
    st.subheader("📋 Historial de Cargas")
    df_comb = get_data("SELECT * FROM combustible ORDER BY id DESC")
    if not df_comb.empty:
        for _, carga in df_comb.iterrows():
            st.markdown(f"""
            <div style='background: #1e293b; padding: 10px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #3b82f6;'>
                <div style='font-weight: bold; color: #f8fafc;'>{carga['fecha']} | {carga['movil']} | {carga['chofer']}</div>
                <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>⛽ {carga['litros']}L | 💰 ${carga['costo']:,.2f} | 📊 {carga['km_momento']:,} km</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📭 No hay registros de combustible")

# --- CHOFERES ---
elif nav == "👥 CHOFERES":
    st.title("Directorio de Choferes")
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("add_chof"):
            nm = st.text_input("Nombre y Apellido")
            dn = st.text_input("DNI")
            tl = st.text_input("Teléfono")
            if st.form_submit_button("Agregar"):
                run_query("INSERT INTO choferes (nombre, dni, telefono) VALUES (?,?,?)", (nm, dn, tl))
                st.success("Agregado"); st.rerun()
    with c2:
        st.dataframe(get_data("SELECT * FROM choferes"), use_container_width=True)
        
    st.markdown("### 🏆 Ranking de Consumo")
    rank = get_data("SELECT chofer, COUNT(*) as cargas, SUM(litros) as total_litros FROM combustible GROUP BY chofer ORDER BY total_litros DESC")
    if not rank.empty:
        st.bar_chart(rank, x="chofer", y="total_litros")

# --- PROVEEDORES ---
elif nav == "🤝 PROVEEDORES":
    st.title("Gestión de Proveedores")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("➕ Nuevo Proveedor")
        with st.form("add_prov"):
            p_empresa = st.text_input("Empresa")
            p_contacto = st.text_input("Contacto")
            p_telefono = st.text_input("Teléfono")
            p_direccion = st.text_area("Dirección")
            p_rubro = st.text_input("Rubro")
            if st.form_submit_button("Guardar Proveedor"):
                if p_empresa:
                    run_query("INSERT INTO proveedores (empresa, contacto, telefono, direccion, rubro) VALUES (?,?,?,?,?)",
                              (p_empresa, p_contacto, p_telefono, p_direccion, p_rubro))
                    st.success("✅ Proveedor agregado exitosamente")
                    st.rerun()
                else:
                    st.error("❌ El nombre de la empresa es obligatorio")
    
    with c2:
        st.subheader("📋 Lista de Proveedores")
        df_prov = get_data("SELECT * FROM proveedores ORDER BY empresa")
        
        if not df_prov.empty:
            # Mostrar tabla con información
            for idx, prov in df_prov.iterrows():
                col_info, col_acc = st.columns([4, 1])
                with col_info:
                    st.markdown(f"""
                    <div style='background: #1e293b; padding: 12px; border-radius: 8px; border-left: 4px solid #38bdf8; margin-bottom: 10px;'>
                        <div style='font-size: 16px; font-weight: bold; color: #f8fafc;'>🏢 {prov['empresa']} - {prov['rubro'] or 'Sin rubro'}</div>
                        <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>👤 {prov['contacto'] or 'N/A'} | 📞 {prov['telefono'] or 'N/A'}</div>
                        <div style='font-size: 11px; color: #64748b; margin-top: 3px;'>📍 {prov['direccion'] or 'Sin dirección'}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_acc:
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        if prov['telefono'] and str(prov['telefono']).strip():
                            telefono_limpio = ''.join(filter(str.isdigit, str(prov['telefono'])))
                            if telefono_limpio:
                                whatsapp_url = f"https://wa.me/{telefono_limpio}"
                                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 8px; border-radius: 5px; cursor: pointer;">📱</button></a>', unsafe_allow_html=True)
                    with btn_col2:
                        if st.button("✏️", key=f"edit_prov_{prov['id']}", help="Editar"):
                            st.session_state[f"editing_prov_{prov['id']}"] = True
                            st.rerun()
                    with btn_col3:
                        borrado_seguro("Proveedor", prov['empresa'], prov['id'], "proveedores")
                
                # Modal de edición
                if st.session_state.get(f"editing_prov_{prov['id']}", False):
                    with st.popover("✏️ Editar Proveedor", use_container_width=True):
                        with st.form(f"form_edit_prov_{prov['id']}"):
                            e_empresa = st.text_input("Empresa", value=prov['empresa'])
                            e_contacto = st.text_input("Contacto", value=prov['contacto'] or '')
                            e_telefono = st.text_input("Teléfono", value=prov['telefono'] or '')
                            e_direccion = st.text_area("Dirección", value=prov['direccion'] or '')
                            e_rubro = st.text_input("Rubro", value=prov['rubro'] or '')
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Guardar"):
                                    run_query("UPDATE proveedores SET empresa=?, contacto=?, telefono=?, direccion=?, rubro=? WHERE id=?",
                                             (e_empresa, e_contacto, e_telefono, e_direccion, e_rubro, prov['id']))
                                    st.session_state[f"editing_prov_{prov['id']}"] = False
                                    st.success("✅ Proveedor actualizado")
                                    st.rerun()
                            with col_cancel:
                                if st.form_submit_button("❌ Cancelar"):
                                    st.session_state[f"editing_prov_{prov['id']}"] = False
                                    st.rerun()
        else:
            st.info("📭 No hay proveedores registrados. Agregue uno usando el formulario a la izquierda.")

# --- DOCS ---
elif nav == "📂 DOCS":
    st.title("Documentación General")
    up = st.file_uploader("Subir PDF/Imagen/Excel")
    if up:
        if guardar_archivo(up): st.success("Archivo guardado con éxito"); st.rerun()
    
    st.markdown("### Archivos Disponibles")
    docs = get_data("SELECT * FROM documentos ORDER BY id DESC")
    for _, d in docs.iterrows():
        st.text(f"📄 {d['fecha_carga']} - {d['nombre_archivo']}")