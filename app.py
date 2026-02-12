import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import glob
import time
import json
import requests
import base64
import plotly.express as px
from fpdf import FPDF
from contextlib import contextmanager
from PIL import Image

import unicodedata
import re
from difflib import get_close_matches

def pdf_safe(txt):
    """FPDF (pyfpdf) usa latin-1: sanitizamos texto para evitar errores (•, comillas raras, emojis)."""
    if txt is None:
        return ""
    s = str(txt)
    # reemplazos comunes
    s = s.replace("•", "- ").replace("\u2022", "- ")
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    # forzar latin-1
    return s.encode("latin-1", "replace").decode("latin-1")

def _table_columns(table_name: str) -> set:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = {row[1] for row in cur.fetchall()}
        return cols
    except Exception:
        return set()

def get_choferes_lista() -> list:
    """Compatibilidad: algunas DB viejas tenían nombre_chofer en vez de nombre."""
    cols = _table_columns("choferes")
    try:
        if "nombre" in cols:
            df = get_data("SELECT nombre FROM choferes WHERE estado IS NULL OR estado='Activo' OR estado='' ORDER BY nombre")
            return df["nombre"].tolist() if not df.empty and "nombre" in df.columns else []
        if "nombre_chofer" in cols:
            df = get_data("SELECT nombre_chofer AS nombre FROM choferes ORDER BY nombre_chofer")
            return df["nombre"].tolist() if not df.empty and "nombre" in df.columns else []
    except Exception:
        pass
    return []

def get_flota_lista() -> list:
    cols = _table_columns("flota")
    try:
        if "nombre_movil" in cols:
            df = get_data("SELECT nombre_movil FROM flota ORDER BY nombre_movil")
            return df["nombre_movil"].tolist() if not df.empty else []
        if "movil" in cols:
            df = get_data("SELECT movil AS nombre_movil FROM flota ORDER BY movil")
            return df["nombre_movil"].tolist() if not df.empty else []
    except Exception:
        pass
    return []


# ==========================================
# 1. CONFIGURACIÓN DEL SISTEMA
# ==========================================
# 👇 TU API KEY
CLAVE_IA = "AIzaSyDI2v9E35MP6wgaHfFud-OoXNC0bG6iiCc"

def _resolver_db_path():
    """Usa CHIRO_DB si está seteado. Si no, intenta:
    1) chiro_master_v67.db
    2) el .db más reciente que matchee chiro_master_v67*.db
    """
    env = os.getenv("CHIRO_DB", "").strip()
    if env:
        return env

    base = "chiro_master_v67.db"
    if os.path.exists(base):
        return base

    try:
        import glob
        cands = glob.glob("chiro_master_v67*.db")
        if cands:
            cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return cands[0]
    except Exception:
        pass

    # fallback: crea/usa el base
    return base

DEFAULT_DB = _resolver_db_path()
DB_PATH_DEFAULT = DEFAULT_DB  # alias (compat)
BACKUP_DIR = "backups"
FILES_DIR = "archivos_ots"

# =============================
# MIGRACIÓN AUTOMÁTICA DE BASE DE DATOS
# =============================
def actualizar_columnas_db():
    """Función 'Taladro' - Crea columnas faltantes en la tabla mantenimientos"""
    try:
        # Conectar a la base de datos actual
        conn = sqlite3.connect(DEFAULT_DB)
        cursor = conn.cursor()
        
        # Lista de columnas a agregar (si no existen)
        migraciones = [
            "ALTER TABLE mantenimientos ADD COLUMN responsable TEXT",
            "ALTER TABLE mantenimientos ADD COLUMN tipo_taller TEXT", 
            "ALTER TABLE mantenimientos ADD COLUMN nombre_taller TEXT",
            "ALTER TABLE mantenimientos ADD COLUMN costo_estimado REAL",
            "ALTER TABLE mantenimientos ADD COLUMN costo REAL DEFAULT 0.0"  # ¡Columna crítica que faltaba!
        ]
        
        columnas_agregadas = []
        
        for sql in migraciones:
            try:
                cursor.execute(sql)
                columnas_agregadas.append(sql.split("ADD COLUMN ")[1])
                print(f"✅ Columna agregada: {sql.split('ADD COLUMN ')[1]}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    # La columna ya existe, está bien
                    pass
                else:
                    print(f"⚠️ Error en migración: {e}")
        
        conn.commit()
        conn.close()
        
        if columnas_agregadas:
            print(f"🎯 Migración completada. Columnas agregadas: {', '.join(columnas_agregadas)}")
        else:
            print("📋 Todas las columnas ya existen. Sin cambios necesarios.")
            
        return True
        
    except Exception as e:
        print(f"❌ Error crítico en migración: {e}")
        return False

# Ejecutar migración al iniciar
actualizar_columnas_db()

# =============================
# SCRIPT DE ACTUALIZACIÓN TOTAL - "THE HEALER"
# =============================
def healer_mantenimientos_table():
    """Reparación masiva - crea todas las columnas faltantes en mantenimientos"""
    try:
        import sqlite3
        conn = sqlite3.connect(DEFAULT_DB)
        c = conn.cursor()
        
        st.info("🔧 Ejecutando reparación masiva de tabla mantenimientos...")
        
        # Lista COMPLETA de todas las columnas que podrían faltar
        columnas_reparacion = [
            ("repuestos", "TEXT DEFAULT ''"),
            ("checklist", "TEXT DEFAULT ''"),
            ("proveedor", "TEXT DEFAULT ''"),
            ("costo_terceros", "REAL DEFAULT 0"),
            ("aprobado_por", "TEXT DEFAULT ''"),
            ("costo", "REAL DEFAULT 0"),
            ("responsable", "TEXT DEFAULT 'Sin Asignar'"),
            ("tipo_taller", "TEXT DEFAULT 'No'"),
            ("nombre_taller", "TEXT DEFAULT ''"),
            ("costo_estimado", "REAL DEFAULT 0"),
            ("km_momento", "INTEGER DEFAULT 0"),
            ("fecha_cierre", "TEXT DEFAULT ''"),
            ("fecha_aprobacion", "TEXT DEFAULT ''"),
            ("proveedor_taller", "TEXT DEFAULT ''"),
            ("repuestos_json", "TEXT DEFAULT ''")
        ]
        
        columnas_creadas = []
        
        for nombre, definicion in columnas_reparacion:
            try:
                c.execute(f"ALTER TABLE mantenimientos ADD COLUMN {nombre} {definicion}")
                columnas_creadas.append(nombre)
                print(f"✅ Columna '{nombre}' creada")
            except Exception as e:
                # La columna ya existe o hay otro error, continuar
                pass
        
        # Agregar columna 'tipo' a la tabla flota
        try:
            c.execute("ALTER TABLE flota ADD COLUMN tipo TEXT DEFAULT 'Tractor'")
            columnas_creadas.append("flota.tipo")
            print(f"✅ Columna 'tipo' creada en tabla flota")
        except Exception as e:
            # La columna ya existe, está bien
            pass
        
        # Commit final
        conn.commit()
        conn.close()
        
        if columnas_creadas:
            st.success(f"🎯 Reparación completada. {len(columnas_creadas)} columnas creadas: {', '.join(columnas_creadas)}")
        else:
            st.info("✅ Todas las columnas ya existen. Sin reparaciones necesarias.")
            
        return True
        
    except Exception as e:
        st.error(f"❌ Error en reparación masiva: {e}")
        return False

# Ejecutar el healer al iniciar
healer_mantenimientos_table()

# Sistema de usuarios con roles
USUARIOS = {
    "admin": {"password": "CHIRO2026", "role": "Administrador"},
    "Chiro": {"password": "CHIRO2026", "role": "Operario"},
}

st.set_page_config(
    page_title="Transporte Chiro SRL", layout="wide", initial_sidebar_state="expanded"
)
# =========================
# Selector de Base de Datos
# =========================
def _db_candidates():
    cands = []
    # En la carpeta actual
    cands += glob.glob("*.db")
    # También en backups (si existe)
    if os.path.isdir(BACKUP_DIR):
        cands += glob.glob(os.path.join(BACKUP_DIR, "*.db"))
    # Deduplicar manteniendo orden
    seen = set()
    out = []
    for p in cands:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            out.append(ap)
    return out

def _db_has_table(db_path: str, table: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            return cur.fetchone() is not None
    except Exception:
        return False

def _db_count(db_path: str, table: str) -> int:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            return int(cur.fetchone()[0])
    except Exception:
        return 0

def _autopick_db():
    # si DEFAULT_DB existe y tiene mantenimientos, priorizarlo
    if os.path.exists(DEFAULT_DB) and _db_has_table(DEFAULT_DB, "mantenimientos"):
        return DEFAULT_DB
    best = DEFAULT_DB
    best_score = -1
    for p in _db_candidates():
        if _db_has_table(p, "mantenimientos"):
            score = _db_count(p, "mantenimientos")
            if score > best_score:
                best_score = score
                best = p
    return best

if "db_path" not in st.session_state:
    st.session_state["db_path"] = _autopick_db()

with st.sidebar:
    st.markdown("### 🗄️ Base de Datos")
    cands = _db_candidates()
    # asegurar que la seleccion actual esté en la lista
    if st.session_state["db_path"] not in cands and os.path.exists(st.session_state["db_path"]):
        cands = [st.session_state["db_path"]] + cands
    if cands:
        labels = []
        for p in cands:
            base = os.path.basename(p)
            n_ot = _db_count(p, "mantenimientos") if _db_has_table(p, "mantenimientos") else 0
            labels.append(f"{base}  —  OTs: {n_ot}")
        idx = cands.index(st.session_state["db_path"]) if st.session_state["db_path"] in cands else 0
        chosen = st.selectbox("Elegí la DB (si no ves OTs, probá otra):", cands, index=idx, format_func=lambda p: labels[cands.index(p)])
        if chosen != st.session_state["db_path"]:
            st.session_state["db_path"] = chosen
            st.rerun()
    st.caption(f"DB en uso: `{os.path.basename(st.session_state['db_path'])}`")


def _db_path():
    return st.session_state.get('db_path', DEFAULT_DB)


# ESTILOS CSS CORPORATIVO - TRANSPORTE CHIRO
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. MOTOR DE BASE DE DATOS
# ==========================================
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)


@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(st.session_state.get('db_path', DEFAULT_DB))
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        # Algunos errores de migración son esperables (p. ej. "duplicate column name")
        # y no queremos ensuciar la UI con mensajes rojos.
        msg = str(e).lower()
        if ("duplicate column name" in msg) or ("already exists" in msg):
            pass
        else:
            st.error(f"Error DB: {e}")
    finally:
        if conn:
            conn.close()


def run_query(q, p=()):
    with get_db() as conn:
        conn.execute(q, p)


def get_data(q, p=()):
    try:
        conn = sqlite3.connect(st.session_state.get('db_path', DEFAULT_DB))
        return pd.read_sql(q, conn, params=p)
    except:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def get_users_map():
    """Mapa username -> nombre para mostrar responsables."""
    df = get_data("SELECT username, nombre FROM users")
    if df is None or df.empty:
        return {}
    if "username" not in df.columns:
        return {}
    if "nombre" not in df.columns:
        # fallback si no existe columna nombre
        return {u: u for u in df["username"].astype(str).tolist()}
    return dict(zip(df["username"].astype(str), df["nombre"].astype(str)))



def _ensure_column(conn, table: str, col: str, coldef: str):
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
            conn.commit()
    except Exception:
        pass




def _table_columns(table: str):
    """Devuelve lista de columnas de una tabla (si existe) sin romper en DBs viejas."""
    try:
        conn = get_conn()
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        conn.close()
        return cols
    except Exception:
        return []
def get_conn():
    """Compat: algunos módulos usan get_conn()"""
    dbp = st.session_state.get("db_path") or os.path.abspath(DB_PATH_DEFAULT)
    return sqlite3.connect(dbp)

def ensure_schema():
    """Asegura columnas nuevas sin romper DBs viejas."""
    try:
        conn = get_conn()
        # novedades: prioridad
        _ensure_column(conn, "novedades", "prioridad", "TEXT")
        # mantenimientos: aprobado_por (responsable) por compatibilidad
        _ensure_column(conn, "mantenimientos", "aprobado_por", "TEXT")
        _ensure_column(conn, "mantenimientos", "costo_terceros", "REAL")
        _ensure_column(conn, "mantenimientos", "proveedor", "TEXT")
        _ensure_column(conn, "mantenimientos", "km_momento", "INTEGER")
        conn.close()
    except Exception:
        pass


def table_columns(table: str):
    """Devuelve lista de columnas existentes de una tabla (SQLite)."""
    try:
        with get_db() as conn:
            cur = conn.execute(f"PRAGMA table_info({table})")
            return [r[1] for r in cur.fetchall()]
    except Exception:
        return []

def safe_select(table: str, cols_pref: list[str]) -> str:
    """Arma SELECT solo con columnas existentes (evita errores por migraciones)."""
    existing = set(table_columns(table))
    cols = [c for c in cols_pref if c in existing]
    if not cols:
        cols = ["*"]
    return "SELECT " + ", ".join(cols) + f" FROM {table} "
# ------------------------------
# Helpers: esquema y lecturas seguras
# ------------------------------
def _table_columns(table: str):
    try:
        df = get_data(f"PRAGMA table_info({table})")
        if df is None or df.empty or "name" not in df.columns:
            return []
        return df["name"].astype(str).tolist()
    except Exception:
        return []

def get_tareas_estandar_df(only_active: bool = True):
    """Devuelve DataFrame con columna 'nombre' siempre presente."""
    cols = _table_columns("tareas_estandar")
    if "nombre" not in cols:
        # tabla inesperada o corrupta -> devolvemos estructura vacía
        return pd.DataFrame({"nombre": []})
    if only_active and "activa" in cols:
        q = "SELECT nombre FROM tareas_estandar WHERE COALESCE(activa,1)=1 ORDER BY nombre ASC"
    else:
        q = "SELECT nombre FROM tareas_estandar ORDER BY nombre ASC"
    df = get_data(q)
    if df is None or df.empty or "nombre" not in df.columns:
        return pd.DataFrame({"nombre": []})
    return df

# ------------------------------
# Auditoría simple (logs)
# ------------------------------
def log_event(usuario: str, accion: str, detalle: str = ""):
    try:
        run_query(
            """CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                usuario TEXT,
                accion TEXT,
                detalle TEXT
            )"""
        )
        run_query(
            "INSERT INTO logs (fecha, usuario, accion, detalle) VALUES (?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), usuario or "", accion or "", detalle or ""),
        )
    except Exception:
        pass

# ------------------------------
# Backup automático de la DB (1 por día)
# ------------------------------
def auto_backup_db():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        hoy = datetime.now().strftime("%Y%m%d")
        target = os.path.join(BACKUP_DIR, f"{os.path.splitext(_db_path())[0]}_{hoy}.db")
        if not os.path.exists(target) and os.path.exists(_db_path()):
            import shutil as _sh
            _sh.copy2(_db_path(), target)
    except Exception:
        pass





# ==========================================
# 2.1 UTILIDADES PARA NORMALIZAR TAREAS (OT)
# ==========================================
import re
import unicodedata
import difflib
import glob

def _norm_text(s: str) -> str:
    """Normaliza texto para comparar (minusculas, sin tildes, solo alfanumerico y espacios)."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    # Reemplazamos separadores por espacio y colapsamos
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sugerir_similares_ui(nombre_ingresado: str, lista_existentes: list, n: int = 5, cutoff: float = 0.72):
    """Devuelve lista de nombres existentes parecidos al texto ingresado."""
    if not nombre_ingresado or not lista_existentes:
        return []
    base = _norm_text(nombre_ingresado)
    # Mapeo original -> norm
    norms = {str(x): _norm_text(str(x)) for x in lista_existentes}
    inv = {}
    for orig_name, norm in norms.items():
        if norm and norm not in inv:
            inv[norm] = orig_name
    candidatos = list(inv.keys())
    matches = difflib.get_close_matches(base, candidatos, n=n, cutoff=cutoff)
    return [inv[m] for m in matches if m in inv]

def _ensure_tareas_tables():
    # Tabla principal (catálogo). 'activa' permite ocultar tareas viejas sin perder historial.
    run_query(
        "CREATE TABLE IF NOT EXISTS tareas_estandar (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, activa INTEGER DEFAULT 1)"
    )
    # Migración: si venías de una versión vieja, agregamos la columna 'activa'
    try:
        run_query("ALTER TABLE tareas_estandar ADD COLUMN activa INTEGER DEFAULT 1")
    except Exception:
        pass

    run_query(
        "CREATE TABLE IF NOT EXISTS tareas_alias (id INTEGER PRIMARY KEY AUTOINCREMENT, alias TEXT UNIQUE, tarea_id INTEGER)"
    )
    run_query(
        "CREATE TABLE IF NOT EXISTS ot_tareas (id INTEGER PRIMARY KEY AUTOINCREMENT, ot_id INTEGER, tarea_id INTEGER, detalle TEXT, fecha TEXT, usuario TEXT)"
    )
def _get_tarea_by_nombre(nombre: str):
    df = get_data(
        "SELECT id, nombre, COALESCE(activa, 1) AS activa FROM tareas_estandar WHERE lower(nombre)=lower(?)",
        (nombre.strip(),),
    )
    if df.empty:
        return None
    return int(df.iloc[0]["id"]), str(df.iloc[0]["nombre"]), int(df.iloc[0]["activa"])

def _get_tarea_id_from_alias(alias_norm: str):
    df = get_data("SELECT tarea_id FROM tareas_alias WHERE alias=?", (alias_norm,))
    if df.empty:
        return None
    return int(df.iloc[0]["tarea_id"])

def _insert_tarea(nombre: str) -> int:
    """Inserta tarea_estandar y devuelve id."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO tareas_estandar (nombre) VALUES (?)", (nombre.strip(),))
        return int(cur.lastrowid)

def _insert_alias(alias_norm: str, tarea_id: int):
    try:
        run_query("INSERT INTO tareas_alias (alias, tarea_id) VALUES (?,?)", (alias_norm, tarea_id))
    except:
        # ya existe
        pass

def resolver_tarea(nombre_ingresado: str, force_new: bool = False):
    """Devuelve (tarea_id, nombre_canonico, fue_nueva). Auto-evita duplicados por variaciones."""
    _ensure_tareas_tables()
    raw = (nombre_ingresado or "").strip()
    if not raw:
        return None, None, False

    alias_norm = _norm_text(raw)

    # 1) Si el texto coincide con una tarea existente (case-insensitive)
    got = _get_tarea_by_nombre(raw)
    if got:
        tarea_id, canon, _act = got
        _insert_alias(alias_norm, tarea_id)
        return tarea_id, canon, False

    # 2) Si coincide con un alias ya conocido
    tarea_id = _get_tarea_id_from_alias(alias_norm)
    if tarea_id:
        df = get_data("SELECT nombre FROM tareas_estandar WHERE id=?", (tarea_id,))
        canon = str(df.iloc[0]["nombre"]) if not df.empty else raw
        return tarea_id, canon, False

    # 3) Buscar parecido entre tareas existentes (para evitar 'cambio' vs 'cambiar')
    if not force_new:
        existentes = get_data("SELECT id, nombre, COALESCE(activa,1) AS activa FROM tareas_estandar")
        if not existentes.empty:
            existentes["norm"] = existentes["nombre"].apply(_norm_text)
            candidatos = existentes["norm"].tolist()
            match = difflib.get_close_matches(alias_norm, candidatos, n=1, cutoff=0.87)
            if match:
                norm_match = match[0]
                row = existentes[existentes["norm"] == norm_match].iloc[0]
                tarea_id = int(row["id"])
                canon = str(row["nombre"])
                # guardamos el texto nuevo como alias del existente
                _insert_alias(alias_norm, tarea_id)
                return tarea_id, canon, False

    # 4) No existe -> crear nueva tarea canónica y registrar alias
    # Normalizamos un poco la presentación (sin tocar tu texto demasiado)
    canon = raw.strip()
    tarea_id = _insert_tarea(canon)
    _insert_alias(alias_norm, tarea_id)
    return tarea_id, canon, True

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
        "stock_cubiertas (id INTEGER PRIMARY KEY AUTOINCREMENT, marca TEXT, modelo TEXT, medida TEXT, dot TEXT, estado TEXT, cantidad INTEGER, ubicacion TEXT)",
        "tareas_estandar (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)",
        "tareas_alias (id INTEGER PRIMARY KEY AUTOINCREMENT, alias TEXT UNIQUE, tarea_id INTEGER)",
        "ot_tareas (id INTEGER PRIMARY KEY AUTOINCREMENT, ot_id INTEGER, tarea_id INTEGER, detalle TEXT, fecha TEXT, usuario TEXT)",
        "ot_repuestos (id INTEGER PRIMARY KEY AUTOINCREMENT, ot_id INTEGER, stock_id INTEGER, nombre TEXT, cantidad INTEGER, fecha TEXT, usuario TEXT)",
        "stock_movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, stock_id INTEGER, nombre TEXT, cantidad INTEGER, motivo TEXT, ot_id INTEGER, usuario TEXT)",
    ]
    with get_db() as conn:
        for t in tablas:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {t}")
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
            conn.execute(
                "ALTER TABLE mantenimientos ADD COLUMN costo_terceros REAL DEFAULT 0"
            )
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
        # Agregar columna responsable a mantenimientos si no existe (migración)
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN responsable TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe

        # Agregar columnas de aprobación (opcional) si no existen (migración)
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN aprobado_por TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE mantenimientos ADD COLUMN fecha_aprobacion TEXT")
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

        try:
            conn.execute("ALTER TABLE ot_repuestos ADD COLUMN estado TEXT DEFAULT 'Solicitado'")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE ot_repuestos ADD COLUMN aprobado_por TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        try:
            conn.execute("ALTER TABLE ot_repuestos ADD COLUMN fecha_aprobacion TEXT")
        except sqlite3.OperationalError:
            pass  # La columna ya existe


if "init" not in st.session_state:
    init_db()
    ensure_schema()
    auto_backup_db()
    st.session_state["init"] = True


# ==========================================
# 3. FUNCIONES ESPECIALES (PDF, IA, ARCHIVOS, SEGURIDAD)
# ==========================================
def borrado_seguro(
    tipo_registro, nombre_registro, id_registro, tabla, callback_success=None
):
    """Función general para borrado seguro con confirmación"""
    confirm_key = f"confirm_delete_{tipo_registro}_{id_registro}"

    if st.session_state.get(confirm_key, False):
        st.warning(
            f"⚠️ **¿Está seguro de eliminar {tipo_registro}: '{nombre_registro}'?**"
        )
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
        with open(path, "wb") as f:
            f.write(file.getbuffer())
        run_query(
            "INSERT INTO documentos (fecha_carga, nombre_archivo, descripcion, tipo, ot_id) VALUES (?,?,?,?,?)",
            (date.today(), name, "Adjunto", file.type, ot_id),
        )
        return True
    except:
        return False


def generar_pdf_ot(ot_id):
    # Generador de PDF Reporte - Diseño Ejecutivo
    try:
        ot = get_data("SELECT * FROM mantenimientos WHERE id=?", (ot_id,)).iloc[0]
        pdf = FPDF()
        pdf.add_page()

        # Encabezado con fondo gris claro
        pdf.set_fill_color(240, 240, 240)  # Gris claro
        pdf.rect(0, 0, 210, 40, "F")  # Rectángulo de fondo

        # Datos de la empresa formales
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, 8)
        pdf.cell(0, 8, "TRANSPORTE CHIRO S.R.L.", 0, 1, "L")
        pdf.set_font("Arial", "", 9)
        pdf.set_xy(10, 15)
        pdf.cell(0, 6, "Sistema de Gestión de Mantenimiento", 0, 1, "L")
        pdf.set_xy(10, 21)
        pdf.cell(0, 6, f"Generado el {date.today().strftime('%d/%m/%Y')}", 0, 1, "L")

        # Título alineado a la derecha
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, 30)
        pdf.cell(0, 10, f"ORDEN DE TRABAJO N° {ot_id}", 0, 1, "R")

        # Línea separadora
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, 45, 200, 45)

        pdf.ln(15)

        # Información de la OT
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, "INFORMACIÓN DE LA ORDEN", 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, pdf_safe(f"Móvil: {ot['movil']}"), 0, 1, "L")
        pdf.cell(0, 6, pdf_safe(f"Chofer: {ot['chofer']}"), 0, 1, "L")
        pdf.cell(0, 6, pdf_safe(f"Fecha: {ot['fecha']}"), 0, 1, "L")
        pdf.cell(0, 6, pdf_safe(f"Estado: {ot['estado']}"), 0, 1, "L")

        pdf.ln(8)

        # Trabajo realizado
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "TRABAJO REALIZADO:", 0, 1, "L")
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, pdf_safe(f"{ot['descripcion']}"))

        # Checklist si existe
        if ot["checklist"] and str(ot["checklist"]).strip():
            pdf.ln(5)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, "CHECKLIST:", 0, 1, "L")
            pdf.set_font("Arial", "I", 9)
            pdf.multi_cell(0, 6, pdf_safe(f"{ot['checklist']}"))

        # Repuestos si existen
        if ot.get("repuesto") and str(ot["repuesto"]).strip():
            pdf.ln(8)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, "REPUESTOS UTILIZADOS:", 0, 1, "L")

            # Tabla simple de repuestos
            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(120, 7, "Repuesto", 1, 0, "L", True)
            pdf.cell(30, 7, "Cantidad", 1, 0, "C", True)
            pdf.cell(40, 7, "Observaciones", 1, 1, "L", True)

            pdf.set_font("Arial", "", 9)
            pdf.set_fill_color(255, 255, 255)
            repuesto = str(ot["repuesto"]).strip()
            cantidad = ot.get("cantidad", 0) or 0
            pdf.cell(120, 6, pdf_safe(repuesto), 1, 0, "L", True)
            pdf.cell(30, 6, str(cantidad), 1, 0, "C", True)
            pdf.cell(40, 6, "-", 1, 1, "L", True)

        # Costo total
        if ot["costo_total"] and ot["costo_total"] > 0:
            pdf.ln(10)
            pdf.set_font("Arial", "B", 12)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 10, f"COSTO TOTAL: ${ot['costo_total']:,.2f}", 0, 1, "R", True)

        # Pie de página
        pdf.set_y(-15)
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(
            0,
            10,
            f"Documento generado automáticamente por Transporte Chiro SRL",
            0,
            0,
            "C",
        )

        filename = f"OT_{ot_id}.pdf"
        filepath = os.path.join(FILES_DIR, filename)
        pdf.output(filepath)
        return filepath
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")
        return None


def procesar_ia(txt):
    if "TU_API_KEY" in CLAVE_IA:
        return pd.DataFrame()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={CLAVE_IA}"
    prompt = """Eres mecánico experto. Analiza el texto y devuelve SOLO JSON válido en este formato array: 
    [{"descripcion": "...", "repuesto": "...", "cantidad": 1, "movil": "..."}]"""
    try:
        res = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt + "\n" + txt}]}]},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        clean_json = (
            res.json()["candidates"][0]["content"]["parts"][0]["text"]
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )
        return pd.DataFrame(json.loads(clean_json))
    except:
        return pd.DataFrame()


def procesar_ia_imagen(imagen_bytes):
    """Procesa una imagen con IA para detectar fallas y repuestos"""
    if "TU_API_KEY" in CLAVE_IA or not CLAVE_IA:
        return pd.DataFrame()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={CLAVE_IA}"

    # Convertir imagen a base64
    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")

    prompt = """Eres mecánico experto. Analiza esta imagen de un vehículo o repuesto y devuelve SOLO JSON válido en este formato array:
    [{"descripcion": "descripción de la falla o trabajo detectado", "repuesto": "nombre del repuesto si se detecta", "cantidad": 1}]
    
    Si no detectas nada específico, devuelve un array con un objeto con descripcion general de lo que ves."""

    try:
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": imagen_b64,
                            }
                        },
                    ]
                }
            ]
        }
        res = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}, timeout=15
        )
        respuesta = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        clean_json = respuesta.replace("```json", "").replace("```", "").strip()
        return pd.DataFrame(json.loads(clean_json))
    except Exception as e:
        st.error(f"Error al procesar imagen: {e}")
        return pd.DataFrame()


# ==========================================
# 4. LOGIN & NAVEGACIÓN
# ==========================================
# Inicializar session state
# ==========================================
# MÓDULO GESTIÓN DE CUBIERTAS (VERSIÓN SQLITE)
# ==========================================
def modulo_cubiertas_avanzado():
    st.title("🛞 Gestión Integral de Neumáticos")

    # KPIs Rápidos
    try:
        # Aseguramos que la tabla existe (Sintaxis SQLite)
        run_query(
            """CREATE TABLE IF NOT EXISTS cubiertas_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            fecha DATE, 
            tipo_movimiento TEXT, 
            codigo_producto TEXT, 
            marca TEXT, 
            modelo TEXT, 
            cantidad INTEGER, 
            precio_unitario NUMERIC, 
            nro_factura TEXT, 
            proveedor TEXT, 
            destino_camion TEXT, 
            nro_interno TEXT, 
            ubicacion_posicion TEXT, 
            kilometraje_colocacion INTEGER, 
            observaciones TEXT
        )"""
        )

        # Calcular Stock
        try:
            total_gomas = (
                get_data(
                    "SELECT SUM(cantidad) as t FROM cubiertas_movimientos WHERE tipo_movimiento='ENTRADA'"
                ).iloc[0, 0]
                or 0
            )
            total_puestas = (
                get_data(
                    "SELECT SUM(cantidad) as t FROM cubiertas_movimientos WHERE tipo_movimiento='SALIDA'"
                ).iloc[0, 0]
                or 0
            )
            stock_real = total_gomas - total_puestas
        except:
            stock_real = 0
    except Exception as e:
        st.error(f"Error al inicializar cubiertas: {e}")
        stock_real = 0

    col1, col2 = st.columns(2)
    col1.metric("📦 Stock en Pañol", f"{int(stock_real)}")
    col2.info(
        "💡 Este módulo registra entradas (compras) y salidas (colocaciones) para calcular el stock exacto."
    )

    tab1, tab2, tab3 = st.tabs(
        ["📊 STOCK (INVENTARIO)", "📥 REGISTRAR COMPRA", "🔧 REGISTRAR COLOCACIÓN"]
    )

    # --- TAB 1: STOCK ---
    with tab1:
        st.subheader("Inventario Valorizado")
        query = "SELECT * FROM cubiertas_movimientos"
        df = get_data(query)

        if not df.empty:
            # Lógica de Stock: Entradas (+) - Salidas (-)
            df["cantidad_calc"] = df.apply(
                lambda x: (
                    x["cantidad"]
                    if x["tipo_movimiento"] == "ENTRADA"
                    else -x["cantidad"]
                ),
                axis=1,
            )

            # Agrupar por Modelo
            stock = (
                df.groupby(["marca", "modelo"])
                .agg(
                    {
                        "cantidad_calc": "sum",
                        "precio_unitario": "mean",  # Precio promedio ref
                    }
                )
                .reset_index()
            )

            stock.rename(
                columns={
                    "cantidad_calc": "STOCK DISPONIBLE",
                    "precio_unitario": "PRECIO PROM.",
                },
                inplace=True,
            )

            # Alerta visual
            def color_stock(val):
                return (
                    "background-color: #fca5a5; color: black"
                    if val < 2
                    else "background-color: #86efac; color: black"
                )

            st.dataframe(
                stock.style.applymap(color_stock, subset=["STOCK DISPONIBLE"]),
                use_container_width=True,
            )

            with st.expander("Ver Historial de Movimientos"):
                st.dataframe(
                    df.sort_values(by="id", ascending=False), use_container_width=True
                )
        else:
            st.info("Aún no hay movimientos registrados.")

    # --- TAB 2: ENTRADAS ---
    with tab2:
        st.subheader("Ingreso de Mercadería")
        with st.form("entrada_cubierta"):
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha Compra")
            factura = c2.text_input("Nº Factura")
            prov = st.text_input("Proveedor", placeholder="Ej: Barceló")

            c3, c4, c5 = st.columns(3)
            marca = c3.text_input("Marca", "Michelin")
            modelo = c4.text_input("Modelo", "Multi D 2")
            cant = c5.number_input("Cantidad", 1, 100, 1)
            precio = st.number_input("Precio Unitario ($)", 0.0)
            obs = st.text_area("Notas")

            if st.form_submit_button("💾 Guardar Ingreso"):
                # Sintaxis SQLite usa ? en lugar de %s
                run_query(
                    """INSERT INTO cubiertas_movimientos 
                    (fecha, tipo_movimiento, nro_factura, proveedor, marca, modelo, cantidad, precio_unitario, observaciones)
                    VALUES (?, 'ENTRADA', ?, ?, ?, ?, ?, ?, ?)""",
                    (fecha, factura, prov, marca, modelo, cant, precio, obs),
                )
                st.success(f"✅ Ingresadas {cant} cubiertas {modelo}")
                time.sleep(1.5)
                st.rerun()

    # --- TAB 3: SALIDAS ---
    with tab3:
        st.subheader("Salida / Colocación en Camión")
        # Selector de modelos con stock > 0
        df_stock = get_data("SELECT modelo, marca FROM cubiertas_movimientos")
        lista_modelos = (
            df_stock["modelo"].unique().tolist() if not df_stock.empty else []
        )

        with st.form("salida_cubierta"):
            c1, c2 = st.columns(2)
            fecha_col = c1.date_input("Fecha Colocación")
            mod_sel = c2.selectbox("Modelo", lista_modelos)

            c3, c4 = st.columns(2)
            # Traemos la flota para el selector
            flota_data = get_data("SELECT nombre_movil FROM flota")
            flota_nombres = (
                flota_data["nombre_movil"].tolist() if not flota_data.empty else []
            )
            camion = c3.selectbox("Camión Destino", flota_nombres + ["Otro"])
            km = c4.number_input("KM del Camión al colocar", 0)

            c5, c6, c7 = st.columns(3)
            interno = c5.text_input("Nº Interno (Fuego)", placeholder="463-464")
            pos = c6.selectbox(
                "Posición", ["Dirección", "Tracción", "Eje Loco", "Acoplado"]
            )
            cant_sal = c7.number_input("Cantidad", 1, 20, 2)

            notas_sal = st.text_area("Observaciones")

            if st.form_submit_button("🔧 Registrar Salida"):
                run_query(
                    """INSERT INTO cubiertas_movimientos 
                    (fecha, tipo_movimiento, modelo, destino_camion, kilometraje_colocacion, nro_interno, ubicacion_posicion, cantidad, observaciones)
                    VALUES (?, 'SALIDA', ?, ?, ?, ?, ?, ?, ?)""",
                    (fecha_col, mod_sel, camion, km, interno, pos, cant_sal, notas_sal),
                )
                st.success("✅ Salida registrada correctamente")
                time.sleep(1.5)
                st.rerun()


if "login" not in st.session_state:
    st.session_state["login"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None

# Pantalla de Login (Gatekeeper)
if not st.session_state["login"]:
    st.markdown(
        "<br><h1 style='text-align:center; color:#D81E28;'>Transporte Chiro SRL</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h3 style='text-align:center; color:#FAFAFA; margin-bottom:30px;'>Sistema de Gestión</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.container(border=True):
            st.markdown("### 🔐 Inicio de Sesión")
            u = st.text_input("Usuario", key="login_user")
            p = st.text_input("Contraseña", type="password", key="login_pass")

            if st.button("🚀 ENTRAR", use_container_width=True, type="primary"):
                if u in USUARIOS and USUARIOS[u]["password"] == p:
                    st.session_state["login"] = True
                    st.session_state["username"] = u
                    st.session_state["role"] = USUARIOS[u]["role"]
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# Obtener rol del usuario
user_role = st.session_state.get("role", "Operario")
user_username = st.session_state.get("username", "Usuario")

# Navegación según rol
if user_role == "Administrador":
    # Vista completa para Administrador
    OPCIONES = [
        "🏠 DASHBOARD",
        "🔧 TALLER & OTS",
        "📦 STOCK VISUAL",
        "🔘 CUBIERTAS",
        "🚛 FLOTA",
        "⛽ COMBUSTIBLE",
        "👥 CHOFERES",
        "🤝 PROVEEDORES",
        "📂 DOCS",
    ]
    if user_role == "Administrador":
        OPCIONES.append("📜 AUDITORÍA")
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
            if not res1.empty:
                st.write(f"📦 Stock: {len(res1)}")
            res2 = get_data(
                f"SELECT * FROM mantenimientos WHERE descripcion LIKE '%{q_global}%'"
            )
            if not res2.empty:
                st.write(f"🔧 OTs: {len(res2)}")

        st.markdown("---")
        # Botón de Backup
        if os.path.exists(_db_path()):
            with open(_db_path(), "rb") as f:
                st.download_button(
                    "📥 Descargar Copia de Seguridad (.db)",
                    f,
                    file_name=f"backup_{date.today().strftime('%Y%m%d')}_{os.path.basename(_db_path())}",
                    mime="application/x-sqlite3",
                    use_container_width=True,
                )
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state["login"] = False
            st.session_state["username"] = None
            st.session_state["role"] = None
            st.rerun()
else:
    # Vista simplificada para Operario - Sin sidebar
    nav = "TALLER_OPERARIO"  # Vista especial para operarios

# ==========================================

# ==========================================
# 5. SECCIONES DEL SISTEMA (ROUTER ARREGLADO)
# ==========================================

if nav == "TALLER_OPERARIO":
    # INICIALIZAR LA LISTA (Pegar esto justo al principio de TALLER_OPERARIO)
    if "lista_tareas_ot" not in st.session_state:
        st.session_state["lista_tareas_ot"] = []
    st.title("👋 Hola Equipo - Reporte de Taller")
    st.markdown(
        f"**Usuario:** {user_username} | **Fecha:** {date.today().strftime('%d/%m/%Y')}"
    )

    # Botón de cerrar sesión en la parte superior
    col_header, col_logout = st.columns([4, 1])
    with col_logout:
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state["login"] = False
            st.session_state["username"] = None
            st.session_state["role"] = None
            st.rerun()

    st.markdown("---")

    # Formulario de Nueva OT (simplificado para operarios)
    # INICIALIZAR LISTA TEMPORAL DE TAREAS
    if "lista_tareas_ot" not in st.session_state:
        st.session_state["lista_tareas_ot"] = []
    st.markdown("### 📝 Nueva Orden de Trabajo")

    # Selector de modo: Solo Manual para operarios (más simple)
    modo_trabajo = st.radio("Modo de Trabajo", ["📝 Modo Manual"], horizontal=True)

    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha")
    movil = c1.selectbox(
        "Móvil", get_flota_lista()
    )

    # Chofer - Multiselect para doble tripulación
    choferes_lista = get_choferes_lista()
    chofer_multiselect = c2.multiselect(
        "Chofer(es)",
        choferes_lista,
        help="Puede seleccionar más de un chofer para doble tripulación",
    )
    chofer = ", ".join(chofer_multiselect) if chofer_multiselect else "Sin asignar"

    # Realizado por / Responsable - Multiselect
    responsables_opciones = [
        "Maxi",
        "Cristian",
        "Chofer Asignado",
        "Taller Externo",
        "Otro",
    ]
    responsable_multiselect = c2.multiselect(
        "Realizado por / Responsable",
        responsables_opciones,
        help="Identifique quién(es) realizó el trabajo. Puede seleccionar varios.",
    )
    responsable = (
        ", ".join(responsable_multiselect) if responsable_multiselect else "Sin asignar"
    )

    # Categoría
    categorias = [
        "Mecánica General",
        "Mecánica Pesada (Motor/Caja)",
        "Electricidad",
        "Frenos",
        "Neumáticos / Gomería",
        "Carrocería",
        "Pintura",
        "Aire Acondicionado",
        "Sistema de Combustible",
        "Lavadero",
        "Servicios / Lubricación",
        "Conductores",
        "Reparaciones Generales",
    ]
    categoria = c1.selectbox("Categoría *", categorias)

    # --- BLOQUE MULTI-TAREAS (CARRITO) ---
    st.markdown("##### 🔧 Tareas a Realizar")

    # 1. Aseguramos tabla y traemos lista
    run_query(
        "CREATE TABLE IF NOT EXISTS tareas_estandar (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)"
    )
    tareas_df = get_tareas_estandar_df(only_active=True)
    lista_tareas = tareas_df['nombre'].tolist() if 'nombre' in tareas_df.columns else []

    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        # Selector de Tarea (solo catálogo - para evitar duplicados)
        t_input = (
            st.selectbox("Seleccionar Tarea", lista_tareas, key="sel_multi_op")
            if lista_tareas
            else None
        )
        t_detalles = st.text_input(
            "Detalles / Observación (Opcional)",
            placeholder="Ej: Usar grasa roja, revisar perno...",
            key="det_multi_op",
        )

    with col_t2:
        st.write("")  # Espacio para alinear
        st.write("")

        # --- Alta normal ---
        if st.button("➕ Agregar", use_container_width=True):
            if t_input:
                detalle = (t_detalles.strip() if t_detalles else "")
                tarea_id, canon, _ = resolver_tarea(t_input)
                if tarea_id:
                    st.session_state["lista_tareas_ot"].append(
                        {"tarea_id": tarea_id, "nombre": canon, "detalle": detalle}
                    )
                st.rerun()

# 2. VISOR DE LA LISTA (LA PIZARRA)
    if st.session_state["lista_tareas_ot"]:
        st.info("📋 **Tareas Cargadas en esta OT:**")
        for i, tarea in enumerate(st.session_state["lista_tareas_ot"]):
            col_lista, col_borrar = st.columns([8, 1])
            _det = tarea.get("detalle", "") if isinstance(tarea, dict) else ""
            _nom = tarea.get("nombre", str(tarea)) if isinstance(tarea, dict) else str(tarea)
            tarea_txt = _nom + (f" ({_det})" if _det else "")
            col_lista.markdown(f"**{i+1}.** {tarea_txt}")
            if col_borrar.button("❌", key=f"del_task_{i}"):
                st.session_state["lista_tareas_ot"].pop(i)
                st.rerun()

        # Botón para limpiar todo si se equivocó
        if st.button("🗑️ Borrar Todo", type="secondary"):
            st.session_state["lista_tareas_ot"] = []
            st.rerun()
    else:
        st.warning("⚠️ Aún no cargaste ninguna tarea. Agregá al menos una arriba.")

    # Convertimos la lista en un solo texto para la base de datos (para mostrar/archivar)
    desc_lines = []
    for _t in st.session_state.get("lista_tareas_ot", []):
        if isinstance(_t, dict):
            _line = _t.get("nombre", "").strip()
            _det = (_t.get("detalle", "") or "").strip()
            if _det:
                _line += f" ({_det})"
        else:
            _line = str(_t)
        if _line:
            desc_lines.append(f"• {_line}")
    desc = "\n".join(desc_lines)
    # -------------------------------------

    # Costo Mano de Obra / Terceros (solo si es Taller Externo)
    if "Taller Externo" in responsable:
        costo_terceros = st.number_input(
            "Costo Mano de Obra / Terceros ($)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            help="Si el trabajo lo hizo un taller externo, ingresa el costo aquí.",
        )

        # Proveedor / Taller Externo (obligatorio si es externo)
        proveedores_lista = get_data(
            "SELECT empresa FROM proveedores ORDER BY empresa"
        )["empresa"].tolist()
        st.markdown("**⚠️ Taller Externo seleccionado - Especifique el Proveedor:**")
        proveedor_taller = st.selectbox(
            "Proveedor / Taller Externo *",
            [""] + proveedores_lista + ["➕ Nuevo / No listado"],
            help="Nombre del taller o mecánico que realizó el trabajo (obligatorio para trabajos externos).",
        )

        # Si seleccionó "➕ Nuevo / No listado", mostrar campo de texto
        proveedor_taller_final = None
        nuevo_proveedor_nombre = None
        if proveedor_taller == "➕ Nuevo / No listado":
            nuevo_proveedor_nombre = st.text_input(
                "Nombre del Nuevo Proveedor / Taller",
                key="proveedor_operario_texto",
                placeholder="Ingrese el nombre del taller o mecánico",
            )
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
    st.caption(
        "Seleccione los repuestos utilizados y especifique la cantidad de cada uno"
    )

    # Obtener stock disponible
    stock_disponible = get_data(
        "SELECT id, codigo, nombre, cantidad FROM stock WHERE cantidad > 0 ORDER BY nombre"
    )

    repuestos_seleccionados = {}
    if not stock_disponible.empty:
        # Crear opciones para multiselect
        opciones_repuestos = [
            f"{row['id']} - {row['nombre']} (Stock: {row['cantidad']})"
            for _, row in stock_disponible.iterrows()
        ]
        repuestos_multiselect = st.multiselect(
            "Seleccionar Repuestos", opciones_repuestos, key="repuestos_operario"
        )

        # Para cada repuesto seleccionado, pedir cantidad
        if repuestos_multiselect:
            st.markdown("**Especificar Cantidad por Repuesto:**")
            for rep_sel in repuestos_multiselect:
                rep_id = int(rep_sel.split(" - ")[0])
                rep_nombre = rep_sel.split(" - ")[1].split(" (Stock:")[0]
                stock_actual = stock_disponible[stock_disponible["id"] == rep_id].iloc[
                    0
                ]["cantidad"]

                col_rep, col_cant = st.columns([3, 1])
                with col_rep:
                    st.text(f"• {rep_nombre} (Stock disponible: {stock_actual})")
                with col_cant:
                    cantidad_rep = st.number_input(
                        f"Cantidad",
                        min_value=1,
                        max_value=int(stock_actual),
                        value=1,
                        key=f"cant_rep_operario_{rep_id}",
                    )
                    repuestos_seleccionados[rep_id] = {
                        "nombre": rep_nombre,
                        "cantidad": cantidad_rep,
                        "stock_actual": stock_actual,
                    }
    else:
        st.info("📭 No hay repuestos disponibles en stock")

    # Observaciones / Notas Adicionales
    observaciones = st.text_area(
        "Observaciones / Notas Adicionales",
        placeholder="Detalle fallas específicas o comentarios sobre la reparación...",
        height=100,
    )

    st.info("📋 Checklist de Servicio (Solo marcar si corresponde)")
    ck1, ck2, ck3, ck4 = st.columns(4)
    c_aceite = ck1.checkbox("Aceite/Filtros")
    c_frenos = ck2.checkbox("Frenos/Aire")
    c_luces = ck3.checkbox("Luces/Elec")
    c_neu = ck4.checkbox("Neumáticos")

    check_str = f"Aceite:{c_aceite}, Frenos:{c_frenos}, Luces:{c_luces}, Neu:{c_neu}"
    if st.button("🚀 Crear Orden de Trabajo", use_container_width=True, type="primary"):
        # 1. Validar Lista de Tareas (Carrito)
        if not st.session_state.get("lista_tareas_ot"):
            st.error(
                "❌ ¡La lista de tareas está vacía! Agregá al menos una tarea arriba con el botón '➕ Agregar'."
            )

        # 2. Validar Categoría
        elif not categoria:
            st.error("❌ La categoría es obligatoria")

        # 3. Validar Proveedor (si es externo)
        elif "Taller Externo" in responsable and (
            not proveedor_taller
            or proveedor_taller == ""
            or proveedor_taller == "➕ Nuevo / No listado"
            and (not nuevo_proveedor_nombre or not nuevo_proveedor_nombre.strip())
        ):
            st.error(
                "❌ Si el trabajo fue realizado por un Taller Externo, debe especificar el Proveedor / Taller"
            )

        # 4. Si todo está bien, GUARDAR (conecta directo con el else)
        else:
            # Convertir repuestos a JSON
            repuestos_json_str = (
                json.dumps(repuestos_seleccionados) if repuestos_seleccionados else None
            )

            # ... (y aquí sigue tu código de guardado original)

            # Si es un proveedor nuevo, insertarlo en la tabla proveedores primero
            if nuevo_proveedor_nombre and nuevo_proveedor_nombre.strip():
                proveedor_nombre_limpio = nuevo_proveedor_nombre.strip()
                # Verificar si ya existe para evitar duplicados
                existe_proveedor = get_data(
                    "SELECT id FROM proveedores WHERE empresa = ?",
                    (proveedor_nombre_limpio,),
                )
                if existe_proveedor.empty:
                    # Insertar nuevo proveedor (solo con el nombre/empresa)
                    run_query(
                        "INSERT INTO proveedores (empresa) VALUES (?)",
                        (proveedor_nombre_limpio,),
                    )

            # Insertar OT
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                        INSERT INTO mantenimientos (fecha, movil, chofer, descripcion, checklist, estado, costo_total, categoria, costo_terceros, repuestos_json, proveedor_taller, observaciones, responsable)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        fecha,
                        movil,
                        chofer,
                        desc,
                        check_str,
                        "Pendiente",
                        0,
                        categoria,
                        costo_terceros,
                        repuestos_json_str,
                        proveedor_taller_final,
                        observaciones if observaciones else None,
                        responsable,
                    ),
                )
                ot_id = cursor.lastrowid

                # Guardar tareas normalizadas en tabla ot_tareas (para historial por camión)
                try:
                    _ensure_tareas_tables()
                    for _t in st.session_state.get("lista_tareas_ot", []):
                        if isinstance(_t, dict) and _t.get("tarea_id"):
                            cursor.execute(
                                "INSERT INTO ot_tareas (ot_id, tarea_id, detalle, fecha, usuario) VALUES (?,?,?,?,?)",
                                (
                                    ot_id,
                                    int(_t["tarea_id"]),
                                    (_t.get("detalle") or None),
                                    str(fecha),
                                    user_username,
                                ),
                            )
                except Exception as _e:
                    # No frenamos la creación de la OT si falla el registro de tareas
                    pass

                # Registrar repuestos solicitados para esta OT (NO descuenta stock aquí)
                # La baja real se hace desde 📦 STOCK VISUAL → 🧾 Solicitudes OT (Admin)
                try:
                    for rep_id, rep_data in repuestos_seleccionados.items():
                        cursor.execute(
                            "INSERT INTO ot_repuestos (ot_id, stock_id, nombre, cantidad, fecha, usuario, estado) VALUES (?,?,?,?,?,?,?)",
                            (
                                ot_id,
                                rep_id,
                                rep_data.get("nombre"),
                                int(rep_data.get("cantidad", 0)),
                                str(fecha),
                                user_username,
                                "Solicitado",
                            ),
                        )
                except Exception:
                    pass

                conn.commit()
            if repuestos_seleccionados:
                st.info("📦 Repuestos solicitados: el ADMIN debe aprobar/entregar desde 📦 STOCK VISUAL → 🧾 Solicitudes OT.")

            st.success("✅ Orden Creada Exitosamente")
            st.session_state["lista_tareas_ot"] = []  # Limpiamos la lista
            time.sleep(2)
            st.rerun()
    st.markdown("---")

    # Últimas 5 OTs cargadas hoy
    st.markdown("### 📋 Últimas 5 OTs Cargadas Hoy")
    fecha_hoy_str = date.today().strftime("%Y-%m-%d")
    ots_hoy = get_data(
        """
        SELECT id, movil, descripcion, categoria, responsable, estado 
        FROM mantenimientos 
        WHERE fecha = ? 
        ORDER BY id DESC 
        LIMIT 5
    """,
        (fecha_hoy_str,),
    )

    if not ots_hoy.empty:
        for _, ot in ots_hoy.iterrows():
            estado_color = {"Pendiente": "#f59e0b", "Cerrada": "#22c55e"}.get(
                ot.get("estado", "Pendiente"), "#94a3b8"
            )
            st.markdown(
                f"""
            <div style='background: #1e293b; padding: 10px; border-radius: 6px; border-left: 3px solid {estado_color}; margin-bottom: 8px;'>
                <div style='font-weight: bold; color: #f8fafc;'>OT #{ot['id']} | {ot['movil']} | <span style='color: {estado_color};'>{ot.get('estado', 'Pendiente')}</span></div>
                <div style='font-size: 12px; color: #94a3b8; margin-top: 5px;'>📂 {ot.get('categoria', 'N/A')} | 👤 {ot.get('responsable', 'N/A')}</div>
                <div style='font-size: 11px; color: #64748b; margin-top: 3px;'>{str(ot['descripcion'])[:60]}{'...' if len(str(ot['descripcion'])) > 60 else ''}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
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
            act = r.get("km_actual", 0) or 0
            ult = r.get("km_ultimo_service", 0) or 0
            inte = r.get("km_service_interval", 15000) or 15000
            if inte > 0 and (act - ult) >= inte:
                alertas_mantenimiento += 1

    # KPI 3: Valor de Pañol (Capital en Repuestos)
    stock_data = get_data(
        "SELECT cantidad, precio FROM stock WHERE cantidad IS NOT NULL AND precio IS NOT NULL"
    )
    valor_stock = 0
    if not stock_data.empty:
        stock_data["valor_item"] = stock_data["cantidad"] * stock_data["precio"]
        valor_stock = stock_data["valor_item"].sum() or 0

    # Fila de KPIs (Métricas) - 3 Columnas
    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        st.metric(
            label="🚛 Unidades Operativas", value=unidades_activas, delta="Flota Total"
        )

    with kpi2:
        delta_color = "inverse" if alertas_mantenimiento > 0 else "normal"
        st.metric(
            label="⚠️ Alertas Vencidas",
            value=alertas_mantenimiento,
            delta=(
                f"{alertas_mantenimiento} servicio(s) vencido(s)"
                if alertas_mantenimiento > 0
                else "Sin alertas"
            ),
            delta_color=delta_color,
        )

    with kpi3:
        st.metric(
            label="💰 Capital en Repuestos",
            value=f"${valor_stock:,.0f}",
            delta="Valor total en stock",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráficos Visuales - Layout 2 Columnas (Ancha y Angosta)
    col_grafico, col_lista = st.columns([2, 1])

    with col_grafico:
        with st.container(border=True):
            st.subheader("📊 Stock por Rubro")
            # Gráfico de barras: Stock por Rubro (suma de cantidades)
            stock_rubro = get_data(
                """
                SELECT rubro, SUM(cantidad) as total_cantidad 
                FROM stock 
                WHERE rubro IS NOT NULL AND rubro != '' AND cantidad IS NOT NULL 
                GROUP BY rubro 
                ORDER BY total_cantidad DESC 
                LIMIT 10
            """
            )

            if not stock_rubro.empty:
                st.bar_chart(
                    stock_rubro.set_index("rubro")["total_cantidad"], height=350
                )
            else:
                # Fallback: Stock total si no hay rubros
                stock_total = get_data(
                    "SELECT SUM(cantidad) as total FROM stock WHERE cantidad IS NOT NULL"
                )
                if not stock_total.empty and stock_total.iloc[0]["total"]:
                    st.info(
                        f"📦 **Stock Total:** {int(stock_total.iloc[0]['total'])} unidades"
                    )
                else:
                    st.info(
                        "📊 No hay datos de stock para mostrar. Agregue artículos al inventario."
                    )

    with col_lista:
        with st.container(border=True):
            st.subheader("📋 Próximos Vencimientos")

            # Lista de próximos servicios (próximos 1000 km)
            proximos_services = []
            if not flota_df.empty:
                for _, r in flota_df.iterrows():
                    act = r.get("km_actual", 0) or 0
                    ult = r.get("km_ultimo_service", 0) or 0
                    inte = r.get("km_service_interval", 15000) or 15000
                    km_recorridos = act - ult
                    km_restantes = inte - km_recorridos

                    if 0 < km_restantes <= 1000:
                        proximos_services.append(
                            {
                                "Móvil": r.get("nombre_movil", "N/A"),
                                "KM Restantes": f"{int(km_restantes):,}",
                            }
                        )

            if proximos_services:
                df_proximos = pd.DataFrame(proximos_services)
                st.dataframe(df_proximos, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No hay servicios próximos a vencer")

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📦 Stock Bajo Mínimo")

            # Lista de stock bajo mínimo
            low_stock = get_data(
                "SELECT nombre, cantidad, minimo FROM stock WHERE minimo > 0 AND cantidad <= minimo ORDER BY cantidad ASC LIMIT 5"
            )
            if not low_stock.empty:
                df_low = pd.DataFrame(
                    {
                        "Artículo": low_stock["nombre"],
                        "Stock": low_stock["cantidad"],
                        "Mínimo": low_stock["minimo"],
                    }
                )
                st.dataframe(df_low, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Todo el stock está por encima del mínimo")

    # Sección de Resumen Rápido
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("📈 Resumen Ejecutivo")

        col_res1, col_res2, col_res3, col_res4 = st.columns(4)

        with col_res1:
            g_taller = (
                get_data("SELECT SUM(costo_total) FROM mantenimientos").iloc[0, 0] or 0
            )
            st.metric("🔧 Gasto Taller", f"${g_taller:,.0f}")

        with col_res2:
            g_comb = get_data("SELECT SUM(costo) FROM combustible").iloc[0, 0] or 0
            st.metric("⛽ Gasto Combustible", f"${g_comb:,.0f}")

        with col_res3:
            total_gasto = g_taller + g_comb
            st.metric("💸 Total Gastos", f"${total_gasto:,.0f}")

        with col_res4:
            ots_pendientes = (
                get_data(
                    "SELECT COUNT(*) as total FROM mantenimientos WHERE estado != 'Cerrada'"
                ).iloc[0, 0]
                or 0
            )
            st.metric("📋 OTs Pendientes", ots_pendientes)

    # --- TALLER ---
elif nav == "🔧 TALLER & OTS":
    st.title("Gestión de Mantenimiento")

    # -----------------------------
    # Migración automática de esquema (si es necesario)
    # -----------------------------
    def _ensure_mantenimientos_schema():
        """Asegura que las columnas necesarias existan en la tabla mantenimientos."""
        try:
            cols = get_data("PRAGMA table_info(mantenimientos)")
            colnames = cols["name"].tolist() if not cols.empty and "name" in cols.columns else []
            
            # Columnas que necesitamos asegurar que existan
            required_columns = {
                'responsable': 'TEXT',  # Para el responsable/mecánico
                'taller_externo': 'INTEGER DEFAULT 0',  # 0=No, 1=Sí
                'nombre_taller_externo': 'TEXT',  # Nombre del taller externo
                'costo_estimado_externo': 'REAL DEFAULT 0',  # Costo estimado del taller
                'km_momento': 'INTEGER DEFAULT 0',  # Kilometraje al momento del mantenimiento
                'fecha_cierre': 'TEXT',  # Fecha de cierre de la OT
                'aprobado_por': 'TEXT',  # Quién aprobó la OT
                'fecha_aprobacion': 'TEXT',  # Fecha de aprobación
                'proveedor': 'TEXT',  # Proveedor general
                'repuestos_json': 'TEXT',  # Repuestos en formato JSON
                'proveedor_taller': 'TEXT'  # Proveedor del taller (compatibilidad)
            }
            
            columns_added = []
            for col, sql_def in required_columns.items():
                if col not in colnames:
                    try:
                        run_query(f"ALTER TABLE mantenimientos ADD COLUMN {col} {sql_def}")
                        columns_added.append(col)
                    except Exception as e:
                        st.toast(f"⚠️ Error al agregar columna {col}: {e}", icon="⚠️")
            
            # Notificar si se agregaron columnas
            if columns_added:
                st.success(f"✅ Se agregaron {len(columns_added)} columnas a la tabla: {', '.join(columns_added)}")
                st.rerun()  # Recargar para aplicar cambios
                
        except Exception as e:
            st.error(f"❌ Error en migración de mantenimientos: {e}")
            # No frenamos el sistema, pero mostramos el error

    _ensure_mantenimientos_schema()

    # -----------------------------
    # Verificación del estado de la tabla (solo para desarrollo)
    # -----------------------------
    if st.checkbox("🔍 Verificar estado de tabla mantenimientos (debug)", help="Muestra las columnas actuales de la tabla"):
        try:
            cols_df = get_data("PRAGMA table_info(mantenimientos)")
            if not cols_df.empty:
                st.write("**Columnas actuales en la tabla mantenimientos:**")
                # Corregir: usar 'dflt_value' en lugar de 'default_value'
                columns_to_show = ['name', 'type', 'notnull', 'dflt_value']
                available_columns = [col for col in columns_to_show if col in cols_df.columns]
                st.dataframe(cols_df[available_columns], use_container_width=True, hide_index=True)
                
                # Mostrar última OT para verificar
                ultima_ot = get_data("SELECT * FROM mantenimientos ORDER BY id DESC LIMIT 1")
                if not ultima_ot.empty:
                    st.write("**Última OT registrada:**")
                    st.dataframe(ultima_ot, use_container_width=True, hide_index=True)
            else:
                st.error("No se pudo obtener información de la tabla")
        except Exception as e:
            st.error(f"Error al verificar tabla: {e}")

    # -----------------------------
    # Helpers (solo para este módulo)
    # -----------------------------
    def _ensure_tareas_estandar_schema():
        """Asegura columna 'activa' en tareas_estandar sin romper DB."""
        try:
            cols = get_data("PRAGMA table_info(tareas_estandar)")
            colnames = cols["name"].tolist() if not cols.empty and "name" in cols.columns else []
            if "activa" not in colnames:
                run_query("ALTER TABLE tareas_estandar ADD COLUMN activa INTEGER DEFAULT 1")
        except Exception:
            # Si falla por 'duplicate column' u otra razón, no frenamos el sistema
            pass

    def _set_taller_force(tab_key: str):
        st.session_state["force_taller_tab"] = tab_key
        st.rerun()

    _ensure_tareas_estandar_schema()

    # -----------------------------
    # Tabs (reordenados para flujo óptimo)
    # -----------------------------
    _force = st.session_state.pop("force_taller_tab", None)
    # Simplificado: solo tabs necesarios, sin redirecciones complejas
    tab_nueva, tab_pendientes, tab_hist_movil, tab_hist = st.tabs(
        ["📝 Nueva Orden", "🚨 Gestión de Pendientes", "🚚 Hoja de Vida (Móvil)", "📊 Reportes Globales"]
    )

    # =============================
    # TAB: NUEVA ORDEN
    # =============================
    with tab_nueva:
        st.subheader("Crear Orden de Trabajo")

        # Estado temporal de tareas de la OT (ahora como DataFrame)
        if "lista_tareas_ot_df" not in st.session_state:
            st.session_state["lista_tareas_ot_df"] = pd.DataFrame(columns=["tarea", "acciones"])

        # Datos base
        flota_df = get_data("SELECT id, nombre_movil, patente FROM flota ORDER BY nombre_movil ASC")
        choferes_df = get_data("SELECT id, nombre FROM choferes WHERE COALESCE(estado,'Activo')='Activo' ORDER BY nombre ASC")

        col_a, col_b = st.columns([2, 2])
        with col_a:
            fecha = st.date_input("Fecha", value=date.today(), key="ot_fecha")
            movil_label = "Sin móviles cargados"
            movil_id = None
            if not flota_df.empty:
                opciones_movil = [
                    f"{r['nombre_movil']} - {r['patente']}" if str(r.get('patente','')) not in ['None','nan',''] else r['nombre_movil']
                    for _, r in flota_df.iterrows()
                ]
                movil_sel = st.selectbox("Móvil", opciones_movil, key="ot_movil_sel")
                # Buscar el ID correspondiente al nombre seleccionado
                selected_row = flota_df[flota_df['nombre_movil'] + ' - ' + flota_df['patente'] == movil_sel]
                if selected_row.empty:
                    selected_row = flota_df[flota_df['nombre_movil'] == movil_sel]
                movil_id = selected_row.iloc[0]['id'] if not selected_row.empty else None
                movil_label = movil_sel
            categoria = st.selectbox("Categoría *", [
                "Mecánica General",
                "Mecánica Pesada (Motor/Caja)",
                "Electricidad",
                "Frenos",
                "Neumáticos / Gomería",
                "Carrocería",
                "Pintura",
                "Aire Acondicionado",
                "Sistema de Combustible",
                "Lavadero",
                "Servicios / Lubricación",
                "Conductores",
                "Reparaciones Generales",
            ], key="ot_categoria")

        with col_b:
            # Choferes (puede ser múltiple)
            chofer_ids = []
            if not choferes_df.empty:
                chofer_opts = [f"{int(r['id'])} | {r['nombre']}" for _, r in choferes_df.iterrows()]
                chofer_sel = st.multiselect("Chofer(es)", chofer_opts, key="ot_choferes")
                chofer_ids = [int(x.split("|")[0].strip()) for x in chofer_sel]
            else:
                st.info("No hay choferes cargados.")

            # Responsable / Mecánico (Opciones fijas)
            responsable_options = ["Sin Asignar", "Maxi", "Cristian", "Taller Externo", "Otro"]
            responsable_sel = st.selectbox("Responsable / Mecánico", responsable_options, key="ot_resp_sel", help="Opcional: Podés guardar la OT sin asignar un mecánico")
            
            # Taller Externo (se muestra si se seleccionó)
            es_externo = responsable_sel == "Taller Externo"
            nombre_taller_externo = ""
            costo_estimado_externo = 0
            
            if es_externo:
                nombre_taller_externo = st.text_input("Nombre del Taller Externo", key="ot_nombre_taller")
                costo_estimado_externo = st.number_input("Costo Estimado ($)", min_value=0.0, value=0.0, step=0.01, key="ot_costo_externo")
            elif responsable_sel == "Otro":
                responsable = st.text_input("Especificar responsable", key="ot_responsable_otro")
            elif responsable_sel == "Sin Asignar":
                responsable = ""
            else:
                responsable = responsable_sel

        st.divider()

        # ---------- Tareas ----------
        st.markdown("### 🔧 Tareas a Realizar")
        
        # Expansor para gestión del catálogo
        with st.expander("📚 Gestión de Catálogo de Tareas"):
            st.caption("Aquí podés crear o modificar las tareas estándar que aparecen en el selector.")
            
            col_cat1, col_cat2 = st.columns([2, 1])
            with col_cat1:
                nueva_tarea_cat = st.text_input("Nueva tarea estándar", placeholder="Ej: Cambiar filtro de aceite", key="cat_nueva_tarea_exp")
            with col_cat2:
                if st.button("➕ Agregar al catálogo", use_container_width=True, key="cat_add_exp"):
                    if nueva_tarea_cat and nueva_tarea_cat.strip():
                        try:
                            nombre_norm = " ".join(nueva_tarea_cat.strip().lower().split())
                            nombre_guardar = nombre_norm.title()
                            run_query("INSERT OR IGNORE INTO tareas_estandar (nombre, activa) VALUES (?,1)", (nombre_guardar,))
                            st.success("Tarea agregada ✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            # Mostrar catálogo actual con opción de eliminar
            cat_df_actual = get_data("SELECT id, nombre, COALESCE(activa,1) as activa FROM tareas_estandar ORDER BY nombre ASC")
            if not cat_df_actual.empty:
                st.markdown("**Catálogo actual:**")
                for _, row in cat_df_actual.iterrows():
                    col_item, col_del = st.columns([4, 1])
                    with col_item:
                        estado = "✅" if row['activa'] == 1 else "❌"
                        st.write(f"{estado} {row['nombre']}")
                    with col_del:
                        if st.button("🗑️", key=f"del_cat_{row['id']}", help="Eliminar tarea"):
                            run_query("DELETE FROM tareas_estandar WHERE id=?", (row['id'],))
                            st.rerun()
        
        st.caption("Elegí tareas del catálogo para evitar duplicados. Si falta una, agregala desde el expansor arriba.")
        
        # Selector de tareas y gestión con data_editor
        tareas_df = get_data("SELECT id, nombre FROM tareas_estandar WHERE COALESCE(activa,1)=1 ORDER BY nombre ASC")
        lista_tareas_disponibles = tareas_df["nombre"].tolist() if (not tareas_df.empty and "nombre" in tareas_df.columns) else []
        
        # Agregar opción para tarea personalizada
        lista_tareas_disponibles.append("--- TAREA PERSONALIZADA (escribir abajo) ---")
        
        col_t1, col_t2 = st.columns([4, 1])
        with col_t1:
            tarea_sel = st.selectbox("Seleccionar tarea", lista_tareas_disponibles if lista_tareas_disponibles else ["(No hay tareas en el catálogo)"], key="ot_tarea_sel")
            
            # Si selecciona tarea personalizada, mostrar campo para escribir
            if tarea_sel == "--- TAREA PERSONALIZADA (escribir abajo) ---":
                tarea_personalizada = st.text_input("Escribir tarea personalizada", key="ot_tarea_personalizada")
            else:
                tarea_personalizada = ""
            
            detalle = st.text_input("Detalle (opcional)", placeholder="Ej: lado derecho / eje 2 / etc.", key="ot_tarea_detalle")
        with col_t2:
            st.write("")
            st.write("")
            if st.button("➕ Agregar", use_container_width=True, disabled=(not lista_tareas_disponibles or (tarea_sel.startswith("(") and tarea_sel != "--- TAREA PERSONALIZADA (escribir abajo) ---"))):
                
                # Determinar la tarea a agregar
                if tarea_sel == "--- TAREA PERSONALIZADA (escribir abajo) ---":
                    if not tarea_personalizada or not tarea_personalizada.strip():
                        st.error("Por favor, escribí una tarea personalizada.")
                        st.stop()
                    item = tarea_personalizada.strip()
                else:
                    item = tarea_sel.strip()
                
                if detalle and detalle.strip():
                    item = f"{item} ({detalle.strip()})"
                
                # Agregar a session_state como dataframe para data_editor
                if "lista_tareas_ot_df" not in st.session_state:
                    st.session_state["lista_tareas_ot_df"] = pd.DataFrame(columns=["tarea", "acciones"])
                
                new_row = pd.DataFrame({"tarea": [item], "acciones": ["🗑️"]})
                st.session_state["lista_tareas_ot_df"] = pd.concat([st.session_state["lista_tareas_ot_df"], new_row], ignore_index=True)
                st.rerun()
        
        # Data Editor para gestión de tareas
        if "lista_tareas_ot_df" not in st.session_state:
            st.session_state["lista_tareas_ot_df"] = pd.DataFrame(columns=["tarea", "acciones"])
        
        if not st.session_state["lista_tareas_ot_df"].empty:
            st.info("🧾 **Tareas cargadas en esta OT (podés editarlas directamente):**")
            
            # Configurar el data editor
            def eliminar_tarea(row):
                st.session_state["lista_tareas_ot_df"] = st.session_state["lista_tareas_ot_df"].drop(row)
                st.rerun()
            
            # Crear una copia para editar
            edited_df = st.data_editor(
                st.session_state["lista_tareas_ot_df"],
                column_config={
                    "tarea": st.column_config.TextColumn("Tarea", width="large"),
                    "acciones": st.column_config.TextColumn("Acciones", width="small", disabled=True)
                },
                hide_index=True,
                num_rows="dynamic",
                use_container_width=True,
                key="tareas_editor"
            )
            
            # Actualizar el dataframe con los cambios
            st.session_state["lista_tareas_ot_df"] = edited_df
            
            if st.button("🧹 Limpiar todas las tareas", type="secondary"):
                st.session_state["lista_tareas_ot_df"] = pd.DataFrame(columns=["tarea", "acciones"])
                st.rerun()
        else:
            st.warning("La lista de tareas está vacía. Agregá al menos una tarea con el botón **➕ Agregar**.")

        st.divider()

        # ---------- Guardar OT ----------
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            descripcion = st.text_area("Observaciones / Descripción (opcional)", height=80, key="ot_desc")
        with col_s2:
            prioridad = st.selectbox("Prioridad", ["Normal", "Alta", "Urgente"], key="ot_prio")
            estado = st.selectbox("Estado", ["Pendiente", "En Proceso", "Cerrada"], key="ot_estado")

        # =============================
        # GUARDAR ORDEN DE TRABAJO - VERSIÓN FINAL LIMPIA
        # =============================
        if st.button("🚀 Crear Orden", type="primary", use_container_width=True, disabled=(st.session_state["lista_tareas_ot_df"].empty)):
            try:
                # Conexión directa a la base de datos
                import sqlite3
                db_path = st.session_state.get('db_path', DEFAULT_DB)
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                
                # Preparar datos
                tareas_lista = st.session_state["lista_tareas_ot_df"]["tarea"].tolist()
                tareas_txt = " • ".join(tareas_lista)
                chofer_txt = ",".join(map(str, chofer_ids)) if chofer_ids else ""
                
                # Determinar responsable final
                if responsable_sel == "Otro":
                    responsable_final = responsable
                elif responsable_sel == "Taller Externo":
                    responsable_final = nombre_taller_externo or "Taller Externo"
                elif responsable_sel == "Sin Asignar":
                    responsable_final = ""
                else:
                    responsable_final = responsable_sel
                
                # INSERT INTO con construcción dinámica infalible
                # 1. LISTA EXPLÍCITA DE VARIABLES
                valores = (
                    str(fecha),                                    # 1. fecha
                    str(movil_id) if movil_id is not None else "", # 2. movil
                    chofer_txt,                                    # 3. chofer
                    (tareas_txt + ("\n" + descripcion.strip() if descripcion and descripcion.strip() else "")), # 4. descripcion
                    categoria,                                     # 5. categoria
                    0,                                             # 6. km_momento
                    costo_estimado_externo if es_externo else 0,  # 7. costo
                    estado,                                        # 8. estado
                    "",                                            # 9. checklist
                    "",                                            # 10. repuestos
                    nombre_taller_externo if es_externo else "",  # 11. proveedor
                    costo_estimado_externo if es_externo else 0,  # 12. costo_terceros
                    responsable_final or "",                      # 13. aprobado_por
                    responsable_final or "",                      # 14. responsable
                    1 if es_externo else 0,                       # 15. taller_externo
                    nombre_taller_externo if es_externo else "",  # 16. nombre_taller
                    costo_estimado_externo if es_externo else 0,  # 17. costo_estimado
                    "Externo" if es_externo else "Interno",       # 18. tipo_taller
                    str(date.today())                             # 19. fecha_creacion (la que faltaba)
                )
                
                # 2. CONSTRUCCIÓN DINÁMICA DEL SQL
                cols = [
                    "fecha", "movil", "chofer", "descripcion", "categoria", "km_momento", 
                    "costo", "estado", "checklist", "repuestos", "proveedor", "costo_terceros", 
                    "aprobado_por", "responsable", "taller_externo", "nombre_taller", 
                    "costo_estimado", "tipo_taller", "fecha_creacion"
                ]
                
                placeholders = ",".join(["?"] * len(cols))
                columns_str = ",".join(cols)
                
                sql_insert = f"INSERT INTO mantenimientos ({columns_str}) VALUES ({placeholders})"
                
                # Debug: mostrar conteo
                st.write(f"🔍 Debug: {len(cols)} columnas = {len(valores)} valores")
                st.write(f"Columnas: {cols}")
                
                # 3. VERIFICACIÓN DE COLUMNAS (crear si no existe)
                try:
                    c.execute("ALTER TABLE mantenimientos ADD COLUMN fecha_creacion TEXT DEFAULT ''")
                    conn.commit()
                except:
                    pass  # Ya existe
                
                # Ejecutar y guardar
                c.execute(sql_insert, valores)
                conn.commit()  # ¡VITAL!
                
                # Obtener ID generado
                c.execute("SELECT last_insert_rowid()")
                last_id = c.fetchone()[0]
                conn.close()
                
                # 3. FEEDBACK VISUAL - SOLO ÉXITO
                st.balloons()
                st.success(f"✅ Orden creada correctamente (ID: {last_id})")
                
                # Limpiar y recargar
                st.session_state["lista_tareas_ot_df"] = pd.DataFrame(columns=["tarea", "acciones"])
                time.sleep(2)
                st.rerun()
                
            except Exception as e:
                # 4. MANEJO DE ERRORES SIMPLE
                st.error(f"❌ Error al guardar la orden: {e}")

        # =============================
        # TAB: GESTIÓN DE PENDIENTES (Operativa)
        # =============================
        with tab_pendientes:
            st.subheader("🚨 Gestión de Pendientes y En Proceso")
            st.caption("Aquí podés ver y cerrar todas las OTs que aún no están finalizadas (Pendientes + En Proceso).")
            
            # Obtener OTs pendientes y en proceso (todas las que no estén cerradas)
            df_pendientes = get_data("""
                SELECT m.id, m.fecha, m.movil, f.patente, f.nombre_movil, 
                       m.descripcion, m.categoria, m.estado, m.costo_terceros, 
                       m.responsable, m.nombre_taller_externo
                FROM mantenimientos m
                LEFT JOIN flota f ON m.movil = f.id
                WHERE COALESCE(m.estado, 'Pendiente') != 'Cerrada'
                ORDER BY m.fecha ASC, m.id ASC
            """)
            
            if df_pendientes.empty:
                st.success("✅ No hay órdenes pendientes ni en proceso. ¡Todo está al día!")
            else:
                st.markdown(f"### 📋 Hay {len(df_pendientes)} órdenes por gestionar (Pendientes + En Proceso):")
                
                for idx, row in df_pendientes.iterrows():
                    ot_id = int(row["id"])
                    movil_info = f"{row['patente']} ({row['nombre_movil']})" if row['patente'] else f"Móvil {row['movil']}"
                    descripcion_corta = row['descripcion'][:50] + "..." if len(str(row['descripcion'])) > 50 else str(row['descripcion'])
                    titulo_expander = f"🔧 OT #{ot_id} - {movil_info} - {descripcion_corta}"
                    
                    with st.expander(titulo_expander, expanded=False):
                        col_info, col_acciones = st.columns([2, 1])
                        
                        with col_info:
                            # Información de la OT
                            st.write(f"**📅 Fecha:** {row['fecha']}")
                            st.write(f"**🚛 Móvil:** {movil_info}")
                            st.write(f"**📂 Categoría:** {row['categoria']}")
                            st.write(f"**👤 Responsable:** {row['responsable'] or 'No asignado'}")
                            if row['nombre_taller_externo']:
                                st.write(f"**🏢 Taller Externo:** {row['nombre_taller_externo']}")
                            
                            st.write("**🔧 Tareas de esta OT:**")
                            # Separar las tareas por " • "
                            tareas = str(row['descripcion']).split(" • ")
                            for i, tarea in enumerate(tareas, 1):
                                if tarea.strip():
                                    st.write(f"  {i}. {tarea.strip()}")
                        
                        with col_acciones:
                            st.markdown("**⚙️ Acciones de Cierre:**")
                            
                            # Campo para costo final
                            costo_final = st.number_input(
                                "💰 Costo Final ($)",
                                min_value=0.0,
                                value=float(row['costo_terceros'] or 0),
                                step=0.01,
                                key=f"costo_final_{ot_id}"
                            )
                            
                            # Campo para observaciones de cierre
                            obs_cierre = st.text_area(
                                "📝 Observaciones de Cierre",
                                placeholder="Detalles finales del trabajo realizado...",
                                key=f"obs_cierre_{ot_id}",
                                height=100
                            )
                            
                            # Botón de cierre
                            if st.button(
                                "✅ CERRAR ORDEN",
                                type="primary",
                                use_container_width=True,
                                key=f"cerrar_ot_{ot_id}"
                            ):
                                try:
                                    # Actualizar la OT
                                    update_query = """
                                        UPDATE mantenimientos 
                                        SET estado = 'Cerrada',
                                            costo_terceros = ?,
                                            observaciones = COALESCE(observaciones, '') || ?,
                                            fecha_cierre = ?
                                        WHERE id = ?
                                    """
                                    
                                    obs_text = f"\n\n--- CIERRE ---\n{obs_cierre}" if obs_cierre.strip() else ""
                                    
                                    run_query(update_query, (
                                        costo_final,
                                        obs_text,
                                        str(date.today()),
                                        ot_id
                                    ))
                                    
                                    st.success(f"✅ OT #{ot_id} cerrada correctamente!")
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error al cerrar OT: {e}")
                        
                        st.divider()

        # =============================
        # TAB: HOJA DE VIDA (Móvil)
        # =============================
        with tab_hist_movil:
            st.subheader("🚛 Hoja de Vida del Vehículo")
            flota_df = get_data("SELECT id, nombre_movil, patente FROM flota ORDER BY nombre_movil ASC")
            if flota_df.empty:
                st.info("Cargá móviles en el módulo FLOTA para usar este historial.")
            else:
                opciones_movil = [
                    f"{r['nombre_movil']} - {r['patente']}" if str(r.get('patente','')) not in ['None','nan',''] else r['nombre_movil']
                    for _, r in flota_df.iterrows()
                ]
                movil_sel = st.selectbox("Seleccionar Móvil", opciones_movil, key="hm_movil")
                # Buscar el ID correspondiente al nombre seleccionado
                selected_row = flota_df[flota_df['nombre_movil'] + ' - ' + flota_df['patente'] == movil_sel]
                if selected_row.empty:
                    selected_row = flota_df[flota_df['nombre_movil'] == movil_sel]
                movil_id = selected_row.iloc[0]['id'] if not selected_row.empty else None
                movil_info = movil_sel
                
                # Obtener historial completo con costos
                df = get_data(
                    """SELECT id, fecha, movil, descripcion, categoria, estado, costo_terceros, responsable, nombre_taller_externo
                       FROM mantenimientos
                       WHERE movil=?
                       ORDER BY date(fecha) ASC, id ASC""",
                    (movil_id,),
                )
                
                if df.empty:
                    st.info("No hay OTs para ese móvil.")
                else:
                    # KPIs para este móvil específico
                    st.markdown("### 📊 Métricas del Vehículo")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    
                    with col_m1:
                        costo_total = df['costo_terceros'].sum()
                        st.metric("💰 Costo Total Acumulado", f"${costo_total:,.2f}")
                    
                    with col_m2:
                        total_ots = len(df)
                        st.metric("🔧 Total de OTs", total_ots)
                    
                    with col_m3:
                        ots_cerradas = len(df[df['estado'] == 'Cerrada'])
                        st.metric("✅ OTs Cerradas", ots_cerradas)
                    
                    st.divider()
                    
                    # Línea de tiempo / Tabla cronológica mejorada
                    st.markdown("### 📅 Línea de Tiempo de Reparaciones")
                    
                    # Configurar columnas para mejor visualización
                    column_config_movil = {
                        "id": st.column_config.TextColumn("OT #", width="small"),
                        "fecha": st.column_config.TextColumn("Fecha", width="small"),
                        "categoria": st.column_config.TextColumn("Categoría", width="medium"),
                        "descripcion": st.column_config.TextColumn("Descripción", width="large"),
                        "estado": st.column_config.TextColumn("Estado", width="small"),
                        "costo_terceros": st.column_config.NumberColumn(
                            "Costo ($)",
                            format="$ %.2f",
                            width="small"
                        ),
                        "responsable": st.column_config.TextColumn("Responsable", width="medium"),
                        "nombre_taller_externo": st.column_config.TextColumn("Taller", width="medium"),
                    }
                    
                    # Aplicar colores a la columna estado
                    def color_estado_movil(val):
                        if val == "Cerrada":
                            return "background-color: #d4edda; color: #155724; padding: 3px; border-radius: 3px;"
                        elif val == "Pendiente":
                            return "background-color: #f8d7da; color: #721c24; padding: 3px; border-radius: 3px;"
                        elif val == "En Proceso":
                            return "background-color: #fff3cd; color: #856404; padding: 3px; border-radius: 3px;"
                        return ""
                    
                    # Aplicar estilos
                    styled_df_movil = df.style.applymap(color_estado_movil, subset=['estado'])
                    
                    st.dataframe(
                        styled_df_movil,
                        column_config=column_config_movil,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.caption(f"Se muestran {len(df)} órdenes de trabajo en orden cronológico para {movil_info}.")

        # =============================
        # TAB: HISTORIAL (Dashboard Mejorado)
        # =============================
        with tab_hist:
            st.subheader("📊 Reportes Globales de Mantenimiento")
            
            # Obtener datos para filtros
            flota_df = get_data("SELECT id, nombre_movil, patente FROM flota ORDER BY nombre_movil ASC")
            
            # Filtros en la parte superior
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                # Filtro por Patente
                patentes = ["Todas"]
                if not flota_df.empty:
                    patentes.extend([f"{r['patente']} ({r['nombre_movil']})" for _, r in flota_df.iterrows()])
                filtro_patente = st.selectbox("Filtrar por Patente", patentes, key="hist_patente")
            
            with col_f2:
                # Filtro por Estado
                filtro_estado = st.selectbox("Filtrar por Estado", ["Todas", "Pendiente", "En Proceso", "Cerrada"], key="hist_estado")
            
            with col_f3:
                # Rango de Fechas
                col_f3a, col_f3b = st.columns(2)
                with col_f3a:
                    fecha_inicio = st.date_input("Desde", value=date.today().replace(day=1), key="hist_fecha_inicio")
                with col_f3b:
                    fecha_fin = st.date_input("Hasta", value=date.today(), key="hist_fecha_fin")
            
            # Construir WHERE dinámico
            where_conditions = []
            params = []
            
            # Filtro de fechas
            where_conditions.append("date(fecha) BETWEEN ? AND ?")
            params.extend([str(fecha_inicio), str(fecha_fin)])
            
            # Filtro de patente
            if filtro_patente != "Todas":
                patente_seleccionada = filtro_patente.split(" (")[0]
                where_conditions.append("m.movil IN (SELECT id FROM flota WHERE patente = ?)")
                params.append(patente_seleccionada)
            
            # Filtro de estado
            if filtro_estado != "Todas":
                where_conditions.append("COALESCE(m.estado, 'Pendiente') = ?")
                params.append(filtro_estado)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Consulta principal con JOIN para obtener patentes
            query = f"""
                SELECT m.id, m.fecha, m.movil, f.patente, f.nombre_movil, m.categoria, m.descripcion, 
                       m.estado, m.costo_terceros, m.responsable, m.nombre_taller_externo, m.costo_estimado_externo
                FROM mantenimientos m
                LEFT JOIN flota f ON m.movil = f.id
                {where_clause}
                ORDER BY date(m.fecha) DESC, m.id DESC
            """
            
            df_hist = get_data(query, tuple(params))
            
            if df_hist.empty:
                st.info("No se encontraron OTs con los filtros seleccionados.")
            else:
                # KPIs
                st.markdown("### 📈 Métricas Clave")
                col_k1, col_k2, col_k3 = st.columns(3)
                
                with col_k1:
                    # Total gastado mes actual
                    mes_actual = date.today().strftime("%Y-%m")
                    gasto_mes = df_hist[df_hist['fecha'].str.startswith(mes_actual)]['costo_terceros'].sum()
                    st.metric("💰 Total Gastado (Mes Actual)", f"${gasto_mes:,.2f}")
                
                with col_k2:
                    # OTs abiertas
                    ots_abiertas = len(df_hist[df_hist['estado'].isin(['Pendiente', 'En Proceso'])])
                    st.metric("🔧 OTs Abiertas", ots_abiertas)
                
                with col_k3:
                    # Vehículo con más fallas
                    if not df_hist.empty:
                        vehiculo_fallas = df_hist.groupby('patente').size().sort_values(ascending=False)
                        if not vehiculo_fallas.empty:
                            veh_top = vehiculo_fallas.index[0]
                            cant_fallas = vehiculo_fallas.iloc[0]
                            st.metric("🚛 Vehículo con más reparaciones", f"{veh_top} ({cant_fallas})")
                
                st.divider()
                
                # Tabla mejorada con configuración de columnas
                st.markdown("### 📋 Historial de Órdenes de Trabajo")
                
                # Configurar columnas para mejor visualización
                column_config = {
                    "id": st.column_config.TextColumn("ID", width="small"),
                    "fecha": st.column_config.TextColumn("Fecha", width="small"),
                    "patente": st.column_config.TextColumn("Patente", width="small"),
                    "nombre_movil": st.column_config.TextColumn("Móvil", width="medium"),
                    "categoria": st.column_config.TextColumn("Categoría", width="medium"),
                    "descripcion": st.column_config.TextColumn("Descripción", width="large"),
                    "estado": st.column_config.TextColumn(
                        "Estado",
                        width="small",
                        help="Estado actual de la OT"
                    ),
                    "costo_terceros": st.column_config.NumberColumn(
                        "Costo ($)",
                        format="$ %.2f",
                        width="small"
                    ),
                    "responsable": st.column_config.TextColumn("Responsable", width="medium"),
                    "nombre_taller_externo": st.column_config.TextColumn("Taller Externo", width="medium"),
                }
                
                # Aplicar colores a la columna estado
                def color_estado(val):
                    if val == "Cerrada":
                        return "background-color: #d4edda; color: #155724; padding: 3px; border-radius: 3px;"
                    elif val == "Pendiente":
                        return "background-color: #f8d7da; color: #721c24; padding: 3px; border-radius: 3px;"
                    elif val == "En Proceso":
                        return "background-color: #fff3cd; color: #856404; padding: 3px; border-radius: 3px;"
                    return ""
                
                # Aplicar estilos
                styled_df = df_hist.style.applymap(color_estado, subset=['estado'])
                
                st.dataframe(
                    styled_df,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Se encontraron {len(df_hist)} OTs con los filtros aplicados.")


elif nav == "📦 STOCK VISUAL":
    st.title("📊 Dashboard de Inventario")
    st.caption("Control profesional y visual de stock en tiempo real")
    
    # Función de búsqueda tipo Google
    def buscar_google(df, query):
        if not query or query.strip() == "":
            return df
        palabras_clave = [palabra.strip().lower() for palabra in query.split() if palabra.strip()]
        if not palabras_clave:
            return df
        
        def contiene_palabras(nombre):
            nombre_lower = str(nombre).lower()
            return all(palabra in nombre_lower for palabra in palabras_clave)
        
        return df[df['nombre'].apply(contiene_palabras)]
    
    # Función para colores de stock (semáforo vibrante)
    def color_stock(val):
        try:
            cantidad = int(val)
            if cantidad == 0:
                return "background-color: #dc2626; color: white; font-weight: bold; padding: 5px; border-radius: 4px;"
            elif cantidad <= 2:
                return "background-color: #f59e0b; color: white; font-weight: bold; padding: 5px; border-radius: 4px;"
            elif cantidad <= 5:
                return "background-color: #eab308; color: black; font-weight: bold; padding: 5px; border-radius: 4px;"
            else:
                return "background-color: #22c55e; color: white; font-weight: bold; padding: 5px; border-radius: 4px;"
        except:
            return "background-color: #6b7280; color: white; padding: 5px; border-radius: 4px;"
    
    # Obtener y filtrar datos
    try:
        df_stock = get_data("SELECT * FROM stock ORDER BY cantidad ASC, nombre ASC")
        if df_stock.empty:
            st.warning("📭 No hay artículos en el inventario")
            st.stop()
            
        # NIVEL 1: TABLERO DE MÉTRICAS (Arriba de todo)
        st.markdown("### 📈 Métricas del Inventario")
        
        # Calcular KPIs
        total_articulos = len(df_stock)
        stock_critico = len(df_stock[df_stock['cantidad'] == 0])
        stock_bajo = len(df_stock[(df_stock['cantidad'] > 0) & (df_stock['cantidad'] <= df_stock['minimo'])])
        valor_total = (df_stock["cantidad"] * df_stock.get("precio", 0)).sum()
        
        # Crear 4 columnas para métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📦 Total Artículos", 
                total_articulos,
                delta=None,
                delta_color="normal"
            )
        
        with col2:
            st.metric(
                "🔴 Stock Crítico", 
                stock_critico,
                delta=None,
                delta_color="inverse"
            )
            if stock_critico > 0:
                st.caption("⚠️ Necesita reposición urgente")
        
        with col3:
            st.metric(
                "🟡 Stock Bajo", 
                stock_bajo,
                delta=None,
                delta_color="inverse"
            )
            if stock_bajo > 0:
                st.caption("📉 Por debajo del mínimo")
        
        with col4:
            st.metric(
                "💰 Valor Total", 
                f"${valor_total:,.2f}",
                delta=None,
                delta_color="normal"
            )
        
        st.markdown("---")
        
        # BUSCADOR TIPO GOOGLE
        st.markdown("### 🔍 Búsqueda Inteligente")
        query_busqueda = st.text_input(
            "🔍 Buscar Repuesto...", 
            placeholder="Ej: Filtro 1620, Aceite 15W40, Bateria...",
            key="buscador_stock_google"
        )
        
        if query_busqueda:
            df_filtrado = buscar_google(df_stock, query_busqueda)
            if not df_filtrado.empty:
                st.success(f"🎯 {len(df_filtrado)} resultados encontrados para: '{query_busqueda}'")
            else:
                st.warning(f"🔍 No se encontraron resultados para: '{query_busqueda}'")
                st.info("💡 Intenta con otros términos o crea un nuevo artículo abajo")
                df_filtrado = df_stock
        else:
            df_filtrado = df_stock
            
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        st.stop()
    
    # NIVEL 2: LA TABLA CON SEMÁFORO VIBRANTE
    if not df_filtrado.empty:
        st.markdown("### 📋 Inventario (Semáforo de Disponibilidad)")
        
        # Configurar columnas para visualización profesional
        column_config = {
            "id": st.column_config.NumberColumn("ID", width="small", format="%d", disabled=True),
            "nombre": st.column_config.TextColumn("Artículo", width="large", disabled=True),
            "cantidad": st.column_config.NumberColumn("Stock", width="small", format="%d", disabled=True),
            "minimo": st.column_config.NumberColumn("Mínimo", width="small", format="%d", disabled=True),
            "precio": st.column_config.NumberColumn("Precio", width="small", format="$ %.2f", disabled=True),
            "categoria": st.column_config.TextColumn("Categoría", width="medium", disabled=True),
            "proveedor": st.column_config.TextColumn("Proveedor", width="medium", disabled=True),
        }
        
        # Aplicar colores de semáforo vibrante
        styled_df = df_filtrado.style.applymap(color_stock, subset=['cantidad'])
        
        # RENDERIZADO DE TABLA (Sin tocar estilos)
        event = st.dataframe(
            styled_df,
            column_config=column_config,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            hide_index=True,
            key="tabla_stock_main"
        )
        
        # LÓGICA DE EXTRACCIÓN DE FILA (A prueba de fallos)
        fila_index = None
        try:
            # Intenta obtener las filas seleccionadas de forma segura
            seleccion = event.selection
            if seleccion and "rows" in seleccion:
                rows = seleccion["rows"]
                if rows:
                    fila_index = rows[0]
        except Exception as e:
            st.error(f"Debug Info: {e}")
        
        # PANEL DE GESTIÓN (FUERA DE LA TABLA)
        if fila_index is not None:
            try:
                # Recuperar datos de la fila seleccionada
                producto_seleccionado = df_filtrado.iloc[fila_index]
                stock_actual = int(producto_seleccionado['cantidad'])
                
                # Contenedor con borde para gestión
                with st.container(border=True):
                    st.markdown(f"### 📦 Gestión de: **{producto_seleccionado['nombre']}**")
                    
                    # Información del producto
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("Stock Actual", stock_actual)
                    with col_info2:
                        st.metric("Stock Mínimo", int(producto_seleccionado['minimo']))
                    with col_info3:
                        st.metric("Precio Unitario", f"${producto_seleccionado.get('precio', 0):.2f}")
                    
                    st.markdown("---")
                    
                    # Dos Columnas para formularios
                    col_izq, col_der = st.columns(2)
                    
                    # COLUMNA IZQUIERDA: FORMULARIO DE ENTRADA
                    with col_izq:
                        st.markdown("#### 📥 ENTRADA DE STOCK")
                        with st.form(f"entrada_stock_{producto_seleccionado['id']}"):
                            cant_entrada = st.number_input(
                                "Cantidad a agregar", 
                                min_value=0, 
                                value=1, 
                                key=f"cant_ent_{producto_seleccionado['id']}"
                            )
                            nuevo_precio = st.number_input(
                                "Nuevo precio unitario (opcional)", 
                                min_value=0.0, 
                                value=float(producto_seleccionado.get('precio', 0)), 
                                step=0.01,
                                key=f"precio_ent_{producto_seleccionado['id']}"
                            )
                            
                            # Selector de proveedores
                            try:
                                proveedores = get_data("SELECT empresa FROM proveedores ORDER BY empresa")
                                lista_proveedores = proveedores['empresa'].tolist() if not proveedores.empty else []
                                proveedor_sel = st.selectbox(
                                    "Proveedor", 
                                    [""] + lista_proveedores,
                                    key=f"prov_ent_{producto_seleccionado['id']}"
                                )
                            except:
                                proveedor_sel = st.text_input("Proveedor", key=f"prov_ent_text_{producto_seleccionado['id']}")
                            
                            if st.form_submit_button("🟢 Confirmar Entrada", type="primary"):
                                if cant_entrada > 0:
                                    try:
                                        # Actualizar stock
                                        nuevo_stock = stock_actual + cant_entrada
                                        run_query("UPDATE stock SET cantidad = ?, precio = ? WHERE id = ?", 
                                                (nuevo_stock, nuevo_precio, producto_seleccionado['id']))
                                        
                                        # Registrar en kardex
                                        fecha_hoy = date.today().strftime("%Y-%m-%d")
                                        run_query("""
                                            INSERT INTO kardex (id_articulo, fecha, tipo_movimiento, cantidad, usuario, proveedor) 
                                            VALUES (?, ?, 'ENTRADA', ?, ?, ?)
                                        """, (producto_seleccionado['id'], fecha_hoy, cant_entrada, 
                                             st.session_state.get('username', 'Sistema'), proveedor_sel))
                                        
                                        st.success(f"✅ Entrada confirmada: +{cant_entrada} {producto_seleccionado['nombre']}")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error al registrar entrada: {e}")
                                else:
                                    st.error("❌ La cantidad debe ser mayor a 0")
                    
                    # COLUMNA DERECHA: FORMULARIO DE SALIDA CON MANEJO DE STOCK CERO
                    with col_der:
                        st.markdown("#### 📤 SALIDA / USO")
                        
                        # MANEJO DE STOCK CERO
                        if stock_actual > 0:
                            # Hay stock disponible - mostrar formulario completo
                            
                            # --- INICIO BLOQUE SALIDA ---
                            
                            # 1. Cantidad a sacar
                            cant_sacar = st.number_input(
                                "Cantidad", 
                                min_value=1, 
                                max_value=stock_actual, 
                                value=1, 
                                key=f"cant_out_{producto_seleccionado['id']}"
                            )
                            
                            # 2. Selector de Tipo (CON KEY ÚNICA)
                            tipo_salida = st.radio(
                                "¿Para quién es?", 
                                ["🚛 A Móvil", "🏢 Uso Interno"], 
                                horizontal=True,
                                key=f"radio_tipo_{producto_seleccionado['id']}"  # <--- CLAVE ÚNICA IMPORTANTE
                            )
                            
                            # 3. Lógica Condicional EXPLÍCITA
                            destino_final = ""
                            
                            if tipo_salida == "🚛 A Móvil":
                                # Muestra SELECTBOX
                                try:
                                    flota_lista = get_data("SELECT nombre_movil, patente FROM flota ORDER BY nombre_movil")
                                    opciones_moviles = [
                                        f"{row['nombre_movil']} - {row['patente']}" if row.get('patente') else f"{row['nombre_movil']}"
                                        for _, row in flota_lista.iterrows()
                                    ]
                                    movil_elegido = st.selectbox(
                                        "Seleccionar Móvil:", 
                                        [""] + opciones_moviles, 
                                        key=f"sel_movil_{producto_seleccionado['id']}"
                                    )
                                    destino_final = movil_elegido
                                except:
                                    movil_elegido = st.text_input("Móvil (manual):", key=f"mov_manual_{producto_seleccionado['id']}")
                                    destino_final = movil_elegido
                            else:
                                # Muestra TEXT INPUT
                                detalle_uso = st.text_input(
                                    "Detalle del trabajo / Destino:", 
                                    placeholder="Ej: Mantenimiento Taller, Oficina Administración, Reparación Portón...", 
                                    key=f"text_uso_{producto_seleccionado['id']}"
                                )
                                destino_final = detalle_uso
                            
                            # Responsable
                            responsable_salida = st.text_input(
                                "Responsable:", 
                                key=f"resp_{producto_seleccionado['id']}"
                            )
                            
                            # 4. Botón de Confirmar
                            if st.button(f"Confirmar Salida", key=f"btn_out_{producto_seleccionado['id']}", type="primary"):
                                if cant_sacar > 0 and destino_final and responsable_salida:
                                    try:
                                        if cant_sacar <= stock_actual:
                                            # Actualizar stock
                                            nuevo_stock = stock_actual - cant_sacar
                                            run_query("UPDATE stock SET cantidad = ? WHERE id = ?", 
                                                    (nuevo_stock, producto_seleccionado['id']))
                                            
                                            # Registrar en kardex
                                            fecha_hoy = date.today().strftime("%Y-%m-%d")
                                            run_query("""
                                                INSERT INTO kardex (id_articulo, fecha, tipo_movimiento, cantidad, usuario, destino) 
                                                VALUES (?, ?, 'SALIDA', ?, ?, ?)
                                            """, (producto_seleccionado['id'], fecha_hoy, cant_sacar, 
                                                 st.session_state.get('username', 'Sistema'), destino_final))
                                            
                                            mensaje = f"✅ Salida confirmada: -{cant_sacar} {producto_seleccionado['nombre']}"
                                            if tipo_salida == "🚛 A Móvil":
                                                mensaje += f" para {destino_final}"
                                            else:
                                                mensaje += f" para uso interno: {destino_final}"
                                            
                                            st.success(mensaje)
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Stock insuficiente. Disponible: {stock_actual}")
                                    except Exception as e:
                                        st.error(f"❌ Error al registrar salida: {e}")
                                else:
                                    st.error("❌ Completar todos los campos")
                            
                            # --- FIN BLOQUE ---
                        else:
                            # Stock es cero - mostrar mensaje informativo
                            st.warning("🚫 No hay stock disponible para realizar salidas.")
                            st.caption("💡 Puedes agregar stock usando el formulario de entrada a la izquierda.")
                
                # Historial del producto
                st.markdown("---")
                st.markdown("### 📜 Últimos Movimientos")
                try:
                    historial = get_data("""
                        SELECT k.*, s.nombre as articulo_nombre 
                        FROM kardex k 
                        LEFT JOIN stock s ON k.id_articulo = s.id 
                        WHERE k.id_articulo = ? 
                        ORDER BY k.fecha DESC, k.id DESC 
                        LIMIT 5
                    """, (producto_seleccionado['id'],))
                    
                    if not historial.empty:
                        st.dataframe(
                            historial[['fecha', 'tipo_movimiento', 'cantidad', 'usuario', 'destino']], 
                            use_container_width=True, 
                            hide_index=True
                        )
                    else:
                        st.info("📭 No hay movimientos registrados para este artículo")
                except Exception as e:
                    st.warning(f"⚠️ No se pudo cargar el historial: {e}")
            
            except Exception as e:
                # LIMPIEZA DE ERRORES VISUALES
                st.error("Hubo un problema mostrando este artículo. Intenta recargar.")
                st.caption(f"Error técnico: {str(e)[:100]}...")  # Mostrar solo parte del error para debug
        else:
            # Mensaje sutil cuando no hay selección
            st.info("👆 Selecciona un repuesto en la lista para registrar movimientos.")
    
    # 4. CREACIÓN INTELIGENTE
    st.markdown("---")
    st.markdown("### ✨ Creación Inteligente de Artículos")
    
    # Mostrar botón de creación si no hay resultados exactos o si el usuario quiere
    mostrar_crear = True
    if query_busqueda and not df_filtrado.empty and len(df_filtrado) == 1:
        st.success("✅ Artículo encontrado. Puedes gestionarlo arriba.")
        mostrar_crear = False
    
    if mostrar_crear:
        with st.expander("➕ Crear Nuevo Artículo", expanded=not query_busqueda):
            with st.form("crear_articulo_inteligente"):
                nombre_nuevo = st.text_input(
                    "Nombre del Artículo *", 
                    value=query_busqueda if query_busqueda else "",
                    placeholder="Ej: Filtro de Aire MB 1620",
                    key="nombre_articulo_nuevo"
                )
                
                # Validación anti-duplicados en tiempo real
                if nombre_nuevo:
                    try:
                        duplicados = get_data("""
                            SELECT id, nombre, cantidad 
                            FROM stock 
                            WHERE LOWER(nombre) LIKE LOWER(?) AND id != ?
                        """, (f"%{nombre_nuevo}%", 0))
                        
                        if not duplicados.empty:
                            st.warning(f"⚠️ Ya existen {len(duplicados)} artículos similares:")
                            st.dataframe(duplicados[['nombre', 'cantidad']], use_container_width=True, hide_index=True)
                    except:
                        pass
                
                col1, col2 = st.columns(2)
                with col1:
                    categoria = st.selectbox(
                        "Categoría *", 
                        ["Filtros", "Aceites", "Frenos", "Suspensión", "Electricidad", "Neumáticos", "Varios"],
                        key="categoria_articulo"
                    )
                    stock_inicial = st.number_input("Stock Inicial *", min_value=0, value=1)
                    stock_minimo = st.number_input("Stock Mínimo *", min_value=0, value=2)
                
                with col2:
                    costo_unitario = st.number_input(
                        "Costo Unitario *", 
                        min_value=0.0, 
                        value=0.0, 
                        step=0.01
                    )
                    try:
                        proveedores = get_data("SELECT empresa FROM proveedores ORDER BY empresa")
                        lista_proveedores = proveedores['empresa'].tolist() if not proveedores.empty else []
                        proveedor_nuevo = st.selectbox(
                            "Proveedor", 
                            [""] + lista_proveedores,
                            key="proveedor_articulo"
                        )
                    except:
                        proveedor_nuevo = st.text_input("Proveedor", key="proveedor_articulo_text")
                
                if st.form_submit_button("✨ Crear Nuevo Artículo", type="primary"):
                    if nombre_nuevo and categoria and stock_inicial >= 0 and stock_minimo >= 0 and costo_unitario >= 0:
                        try:
                            # Validación final de duplicados
                            duplicado_exacto = get_data("""
                                SELECT id FROM stock WHERE LOWER(nombre) = LOWER(?)
                            """, (nombre_nuevo.strip(),))
                            
                            if not duplicado_exacto.empty:
                                st.error(f"❌ Ya existe un artículo llamado '{nombre_nuevo}'. No se puede duplicar.")
                            else:
                                # Crear nuevo artículo
                                fecha_hoy = date.today().strftime("%Y-%m-%d")
                                run_query("""
                                    INSERT INTO stock (nombre, categoria, cantidad, minimo, precio, proveedor, fecha_ingreso) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (nombre_nuevo.strip(), categoria, stock_inicial, stock_minimo, costo_unitario, proveedor_nuevo, fecha_hoy))
                                
                                # Registrar creación en kardex
                                articulo_id = get_data("SELECT last_insert_rowid()").iloc[0, 0]
                                run_query("""
                                    INSERT INTO kardex (id_articulo, fecha, tipo_movimiento, cantidad, usuario, proveedor) 
                                    VALUES (?, ?, 'CREACION', ?, ?, ?)
                                """, (articulo_id, fecha_hoy, stock_inicial, st.session_state.get('username', 'Sistema'), proveedor_nuevo))
                                
                                st.success(f"✅ Artículo '{nombre_nuevo}' creado exitosamente")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al crear artículo: {e}")
                    else:
                        st.error("❌ Completar todos los campos obligatorios (*)")
    else:
        st.info("💡 Usa el buscador arriba para encontrar artículos rápidamente")

elif nav == "🛞 CUBIERTAS":
    modulo_cubiertas_avanzado()

elif nav == "⛽ COMBUSTIBLE":
    st.title("Control de Combustible")
    with st.form("fuel_load"):
        c1, c2 = st.columns(2)
        f_date = c1.date_input("Fecha")
        f_mov = c1.selectbox(
            "Móvil", get_flota_lista()
        )

        # Mostrar km_actual como referencia visual
        if f_mov:
            km_actual = get_data(
                "SELECT km_actual FROM flota WHERE nombre_movil=?", (f_mov,)
            ).iloc[0]["km_actual"]
            c2.info(f"📏 KM Actual: {km_actual:,}")

        f_litros = c2.number_input("Litros cargados", min_value=0.0, step=0.1)
        f_kilometros = c2.number_input(
            "Kilometros recorridos", min_value=0, step=1
        )
        f_costo = c1.number_input("Costo total $", min_value=0.0, step=0.01)
        f_proveedor = c1.text_input("Proveedor/Estación")

        if st.form_submit_button("⛽ Cargar Combustible"):
            if f_mov and f_litros > 0 and f_kilometros > 0:
                # Calcular rendimiento
                rendimiento = f_kilometros / f_litros if f_litros > 0 else 0
                costo_litro = f_costo / f_litros if f_litros > 0 else 0

                # Insertar registro
                run_query(
                    "INSERT INTO combustible (fecha, movil, litros, kilometros, costo, proveedor, rendimiento, costo_litro) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        f_date,
                        f_mov,
                        f_litros,
                        f_kilometros,
                        f_costo,
                        f_proveedor,
                        rendimiento,
                        costo_litro,
                    ),
                )

                # Actualizar km del móvil
                nuevo_km = km_actual + f_kilometros
                run_query(
                    "UPDATE flota SET km_actual=? WHERE nombre_movil=?",
                    (nuevo_km, f_mov),
                )

                st.success(
                    f"✅ Carga registrada: {f_litros}L para {f_mov} | Rendimiento: {rendimiento:.2f} km/L"
                )
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("❌ Completar móvil, litros y kilómetros")

    # Historial de cargas
    st.markdown("### 📊 Historial de Cargas")
    df_comb = get_data(
        "SELECT * FROM combustible ORDER BY fecha DESC, id DESC LIMIT 50"
    )
    if not df_comb.empty:
        st.dataframe(df_comb, use_container_width=True, hide_index=True)
    else:
        st.info("📭 No hay cargas registradas")

# --- FUNCIONES AUXILIARES ---
def get_flota_lista():
    """Devuelve lista de móviles para selectboxes"""
    df = get_data("SELECT nombre_movil FROM flota ORDER BY nombre_movil")
    return df["nombre_movil"].tolist() if not df.empty else []
