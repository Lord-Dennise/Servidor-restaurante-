# -*- coding: utf-8 -*-
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.request
import urllib.parse
import sqlite3
import datetime
import os
import json
import socket
import csv
import subprocess
import tempfile
from datetime import timedelta
import sys

# ==========================================
# SISTEMA DE ACTUALIZACIÓN AUTOMÁTICA INTELIGENTE
# ==========================================
# Este archivo local lee y guarda dinámicamente su número de versión
ARCHIVO_VERSION_LOCAL = "version_local.json"

def obtener_version_local():
    if os.path.exists(ARCHIVO_VERSION_LOCAL):
        try:
            with open(ARCHIVO_VERSION_LOCAL, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "2.6")
        except Exception:
            pass
    return "2.6"

def guardar_version_local(ver):
    try:
        with open(ARCHIVO_VERSION_LOCAL, "w", encoding="utf-8") as f:
            json.dump({"version": ver}, f)
    except Exception:
        pass

VERSION_ACTUAL = obtener_version_local()
URL_VERSION_REMOTE = "https://raw.githubusercontent.com/Lord-Dennise/Servidor-restaurante-/main/version.json"

def verificar_y_actualizar_automaticamente():
    global VERSION_ACTUAL
    try:
        req = urllib.request.urlopen(URL_VERSION_REMOTE, timeout=5)
        data = json.loads(req.read().decode('utf-8'))
        version_remota = data.get("version")
        url_script_remoto = data.get("url_script")

        if version_remota and version_remota != VERSION_ACTUAL:
            print(f"\n[ACTUALIZACIÓN] ¡Nueva versión detectada ({version_remota})! Actualizando sistema...")
            
            # Descargar el nuevo código fuente
            codigo_nuevo = urllib.request.urlopen(url_script_remoto).read()
            
            # Sobrescribir directamente el archivo actual de forma segura
            nombre_archivo_actual = os.path.basename(__file__)
            with open(nombre_archivo_actual, "wb") as f:
                f.write(codigo_nuevo)
                
            # Guardar el nuevo número de versión localmente de forma automática
            guardar_version_local(version_remota)
            
            print("[ACTUALIZACIÓN] ¡Actualización aplicada con éxito! Reiniciando sistema...")
            
            # Reiniciar el script actual automáticamente para cargar los cambios nuevos
            python = sys.executable
            os.execl(python, python, *sys.argv)
            
    except Exception as e:
        print("[ACTUALIZACIÓN] Modo operativo normal (Sin conexión o servidor remoto sin cambios):", e)

# Ejecutar la verificación automática al arrancar el servidor
verificar_y_actualizar_automaticamente()

# ==========================================
# SISTEMA DE LICENCIA SEGURO (ANTITRAMPA)
# ==========================================
ARCHIVO_LICENCIA = "licencia.json"
DIAS_PRUEBA = 7

def verificar_licencia():
    if not os.path.exists(ARCHIVO_LICENCIA):
        print("\n" + "="*50)
        print(" ATENCIÓN: Archivo de licencia no encontrado.")
        print(" El sistema se encuentra bloqueado por seguridad.")
        print(" Comuníquese con el administrador para generar la licencia.")
        print("="*50 + "\n")
        return False

    try:
        with open(ARCHIVO_LICENCIA, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        print("[BLOQUEADO] El archivo de licencia está corrupto o manipulado.")
        return False

    if datos.get("activo") == "ilimitado":
        return True

    try:
        fecha_instalacion = datetime.datetime.strptime(datos["fecha_instalacion"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False

    fecha_limite = fecha_instalacion + timedelta(days=DIAS_PRUEBA)

    if datetime.datetime.now() > fecha_limite:
        print("[BLOQUEADO] El periodo de prueba de 7 días ha caducado.")
        return False
    
    return True

# Bloqueo estricto al arrancar si no hay licencia válida
if not verificar_licencia():
    sys.exit()

def obtener_impresoras_windows():
    try:
        cmd = "powershell -Command \"Get-WmiObject -Query 'Select * from Win32_Printer' | Select-Object -ExpandProperty Name\""
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        impresoras = [line.strip() for line in output.split('\r\n') if line.strip()]
        if impresoras:
            return impresoras
    except Exception:
        pass
    return ["POS-80", "POS-58", "Microsoft Print to PDF"]

def inicializar_bd():
    conn = sqlite3.connect("restaurante.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cant_mesas INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meseros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cajeros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas_rapidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa TEXT NOT NULL,
            mesero TEXT,
            cajero TEXT,
            detalle TEXT,
            total REAL,
            estado TEXT NOT NULL,
            fecha TEXT,
            piso_id INTEGER,
            tipo_comprobante TEXT,
            doc_cliente TEXT,
            razon_social TEXT,
            FOREIGN KEY (piso_id) REFERENCES pisos(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    
    config_defaults = [
        ('taper_menu', '1.00'),
        ('taper_entrada', '0.50'),
        ('empresa_nombre', 'MR. CUY RESTAURANTE'),
        ('empresa_ruc', '20123456789'),
        ('empresa_direccion', 'Av. Principal 123 - Lima'),
        ('empresa_telefono', '987654321'),
        ('impresora_cocina_ip', '192.168.1.100'),
        ('impresora_cocina_puerto', '9100'),
        ('impresora_caja_nombre', 'POS-80'),
        ('pc_caja_ip', '127.0.0.1')
    ]
    for c, v in config_defaults:
        cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (c, v))

    cursor.execute("SELECT COUNT(*) FROM categorias")
    if cursor.fetchone()[0] == 0:
        cats_iniciales = [
            ("MENU",), ("ENTRADAS",), ("CARTA",), ("CRIOLLOS",), ("REGIONALES",), 
            ("MR. CUY",), ("SOPAS",), ("CERVEZAS",), ("GASEOSAS",), ("POSTRES",)
        ]
        cursor.executemany("INSERT OR IGNORE INTO categorias (nombre) VALUES (?)", cats_iniciales)

    cursor.execute("SELECT COUNT(*) FROM notas_rapidas")
    if cursor.fetchone()[0] == 0:
        notas_init = [
            ("Sin ají / Sin picante",), ("Poco salado",), ("Salsa aparte",), 
            ("Bien frito",), ("Termino medio",), ("Para llevar caliente",)
        ]
        cursor.executemany("INSERT OR IGNORE INTO notas_rapidas (texto) VALUES (?)", notas_init)

    cursor.execute("SELECT COUNT(*) FROM pisos")
    if cursor.fetchone()[0] == 0:
        pisos_iniciales = [("Piso 1", 16), ("Piso 2", 17)]
        cursor.executemany("INSERT INTO pisos (nombre, cant_mesas) VALUES (?, ?)", pisos_iniciales)

    cursor.execute("SELECT COUNT(*) FROM cajeros")
    if cursor.fetchone()[0] == 0:
        cajeros_iniciales = [("Cajero Principal",), ("Ana Torres",)]
        cursor.executemany("INSERT INTO cajeros (nombre) VALUES (?)", cajeros_iniciales)

    cursor.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] == 0:
        menu_inicial = [
            ("ENTRADAS", "Papa a la Huancaína", 5.00), ("SOPAS", "Sopa Criolla", 12.00),
            ("SOPAS", "Caldo de Gallina", 14.00), ("CRIOLLOS", "Seco de Res con Frijoles", 18.00),
            ("CRIOLLOS", "Lomo Saltado", 20.00), ("MR. CUY", "Cuy Chactado con Papas", 25.00),
            ("MR. CUY", "Cuy Entero al Horno", 45.00), ("REGIONALES", "Juane de Gallina", 16.00),
            ("REGIONALES", "Cecina con Tacacho", 22.00), ("GASEOSAS", "Inca Kola 500ml", 6.00),
            ("GASEOSAS", "Coca Cola 500ml", 6.00), ("CERVEZAS", "Pilsen 650ml", 10.00),
            ("POSTRES", "Crema Volteada", 7.00)
        ]
        cursor.executemany("INSERT INTO productos (categoria, nombre, precio) VALUES (?, ?, ?)", menu_inicial)

    cursor.execute("SELECT COUNT(*) FROM meseros")
    if cursor.fetchone()[0] == 0:
        meseros_iniciales = [("Juan Pérez",), ("María Gómez",), ("Carlos Ruiz",)]
        cursor.executemany("INSERT INTO meseros (nombre) VALUES (?)", meseros_iniciales)

    conn.commit()
    conn.close()

inicializar_bd()

def obtener_configuracion():
    conn = sqlite3.connect("restaurante.db")
    cursor = conn.cursor()
    cursor.execute("SELECT clave, valor FROM configuracion")
    config = {row[0]: str(row[1]) for row in cursor.fetchall()}
    conn.close()
    return config

def es_pc_principal(client_address, cfg=None):
    if cfg is None:
        cfg = obtener_configuracion()
    ip_cliente = client_address[0] if client_address else ''
    ip_caja = cfg.get('pc_caja_ip', '127.0.0.1').strip()
    return ip_cliente in ['127.0.0.1', 'localhost', '::1', ip_caja]

def parsear_cookies(headers):
    cookie_header = headers.get('Cookie', '')
    cookies = {}
    if cookie_header:
        for part in cookie_header.split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                cookies[k] = urllib.parse.unquote(v)
    return cookies

def generar_html_cards_interactivas(items_cat):
    cards_html = ""
    for pid, nom, prec in items_cat:
        cards_html += f"""
        <div class="item-card" data-id="{pid}" onclick="toggleCard(this)">
            <div class="item-name">{nom}</div>
            <div class="item-price">S/ {prec:.2f}</div>
        </div>
        """
    if not cards_html:
        cards_html = "<p style='color:#777;'>No hay productos en esta categoría.</p>"
    return cards_html

def imprimir_silencioso_caja(texto_ticket):
    cfg = obtener_configuracion()
    printer_name = cfg.get('impresora_caja_nombre', '').strip()
    if not printer_name:
        return False, "Impresora de caja no configurada."
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as f:
            f.write(texto_ticket)
            temp_path = f.name
        cmd = f'powershell -Command "Get-Content \'{temp_path}\' -Raw | Out-Printer -Name \'{printer_name}\'"'
        subprocess.run(cmd, shell=True, check=True)
        os.unlink(temp_path)
        return True, "Ticket impreso correctamente."
    except Exception as e:
        return False, f"Error al imprimir en caja: {e}"

def generar_excel_cierre(cajero_actual):
    fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
    carpeta = f"./{fecha_hoy}"
    os.makedirs(carpeta, exist_ok=True)
    ruta_archivo = os.path.join(carpeta, "resumen de ventas.csv")
    conn = sqlite3.connect("restaurante.db")
    cursor = conn.cursor()
    cursor.execute("SELECT detalle, total FROM pedidos")
    pedidos = cursor.fetchall()
    cursor.execute("SELECT nombre, categoria, precio FROM productos")
    prod_info = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    conn.close()
    total_recaudado = sum(p[1] for p in pedidos)
    cantidad_pedidos = len(pedidos)
    conteo_productos = {}
    totales_categoria = {}
    for p in pedidos:
        texto_pedido = p[0]
        partes = texto_pedido.split(", ")
        for parte in partes:
            item_limpio = parte.split(" (Nota:")[0].replace(" [PARA LLEVAR]", "").replace(" [Incluida]", "").split(" [Táper")[0]
            if ": " in item_limpio:
                item_limpio = item_limpio.split(": ", 1)[-1]
            item_limpio = item_limpio.strip()
            if item_limpio:
                conteo_productos[item_limpio] = conteo_productos.get(item_limpio, 0) + 1
                if item_limpio in prod_info:
                    cat, prec = prod_info[item_limpio]
                    totales_categoria[cat] = totales_categoria.get(cat, 0.0) + prec

    with open(ruta_archivo, mode='w', newline='', encoding='utf-8-sig') as archivo_csv:
        writer = csv.writer(archivo_csv)
        writer.writerow(["REPORTE DE CIERRE DE CAJA - MR. CUY"])
        writer.writerow(["Fecha:", fecha_hoy])
        writer.writerow(["Cajero(a):", cajero_actual])
        writer.writerow([])
        writer.writerow(["RESUMEN POR CATEGORÍAS"])
        writer.writerow(["Categoría", "Monto Total (S/)"])
        for cat, monto in totales_categoria.items():
            writer.writerow([cat, f"{monto:.2f}"])
        writer.writerow([])
        writer.writerow(["DETALLE DE PRODUCTOS VENDIDOS"])
        writer.writerow(["Cantidad y Producto", "Subtotal (S/)"])
        for prod, cant in conteo_productos.items():
            precio_unit = prod_info[prod][1] if prod in prod_info else 0.0
            subtotal = cant * precio_unit
            writer.writerow([f"{cant}x {prod}", f"{subtotal:.2f}"])
        writer.writerow([])
        writer.writerow(["Total Cuentas Atendidas:", cantidad_pedidos])
        writer.writerow(["TOTAL RECAUDADO EN CAJA (S/):", f"{total_recaudado:.2f}"])

def imprimir_red_cocina(texto_comanda):
    cfg = obtener_configuracion()
    ip = cfg.get('impresora_cocina_ip', '')
    try:
        puerto = int(cfg.get('impresora_cocina_puerto', '9100'))
    except ValueError:
        puerto = 9100
    if not ip or ip == '127.0.0.1':
        return False, "IP de impresora de cocina no configurada."
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((ip, puerto))
        init_cmd = b'\x1b\x40'
        double_size_cmd = b'\x1d\x21\x11'
        normal_size_cmd = b'\x1d\x21\x00'
        cut_cmd = b'\x1d\x56\x41\x03'
        raw_bytes = init_cmd + double_size_cmd + texto_comanda.encode('latin-1', errors='replace') + normal_size_cmd + b'\n\n\n' + cut_cmd
        s.sendall(raw_bytes)
        s.close()
        return True, "Enviado a impresora de cocina correctamente."
    except Exception as e:
        return False, f"Error al conectar con la impresora de cocina ({ip}:{puerto}): {e}"

CSS_GLOBAL = """
<style>
    :root {
        --primary-bg: #ffffff;
        --card-bg: #fffdf0;
        --accent-yellow: #f1c40f;
        --accent-yellow-dark: #d4ac0d;
        --accent-green: #00FF66;
        --accent-green-dark: #00cc52;
        --accent-blue: #3498db;
        --accent-red: #e74c3c;
        --text-dark: #2c3e50;
    }
    * { box-sizing: border-box; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 20px; }
    body { background: #ffffff; color: var(--text-dark); margin: 0; padding: 0; }
    header { background: linear-gradient(135deg, #f1c40f 0%, #f39c12 100%); color: #2c3e50; padding: 22px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-bottom: 6px solid #00FF66; }
    .header-brand { display: flex; align-items: center; gap: 20px; }
    .header-logo { height: 65px; width: auto; border-radius: 50%; background: white; padding: 2px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    header h1 { margin: 0; font-size: 34px; color: #111; letter-spacing: 0.5px; font-weight: 900; }
    .nav-btn { color: #111; padding: 15px 24px; text-decoration: none; border-radius: 10px; font-weight: 900; font-size: 18px; transition: all 0.2s; display: inline-flex; align-items: center; gap: 10px; box-shadow: 0 3px 8px rgba(0,0,0,0.15); border: 3px solid rgba(0,0,0,0.1); }
    .nav-home { background: #ecf0f1; } .nav-home:hover { background: #d5dbdb; }
    .nav-piso { background: #00FF66; color: #004d1a; } .nav-piso:hover { background: #33ff85; }
    .nav-admin { background: #f1c40f; } .nav-admin:hover { background: #f39c12; }
</style>
"""

HTML_LOGIN_CAJERO = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Iniciar Sesión Cajero - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .welcome-card {{ background: #ffffff; padding: 55px 40px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); text-align: center; border: 5px solid #f1c40f; width: 100%; max-width: 580px; }}
        .logo-img {{ max-width: 180px; height: auto; border-radius: 50%; margin-bottom: 25px; border: 6px solid #00FF66; background: white; padding: 6px; box-shadow: 0 4px 15px rgba(0, 255, 102, 0.3); }}
        h1 {{ color: #2c3e50; font-size: 46px; margin: 0 0 15px 0; text-transform: uppercase; letter-spacing: 2px; font-weight: 900; }}
        p {{ color: #555; font-size: 22px; margin-bottom: 35px; font-weight: 700; }}
        select {{ width: 100%; padding: 22px; font-size: 22px; border-radius: 15px; border: 4px solid #f1c40f; margin-bottom: 30px; background: #fffdf0; font-weight: 900; color: #2c3e50; text-align: center; }}
        .btn-ingresar {{ width: 100%; display: flex; align-items: center; justify-content: center; gap: 12px; padding: 22px; text-decoration: none; font-size: 24px; font-weight: 900; border-radius: 15px; transition: all 0.25s ease; color: #004d1a; background: #00FF66; border: 3px solid #00cc52; box-shadow: 0 6px 18px rgba(0, 255, 102, 0.4); cursor: pointer; }}
        .btn-ingresar:hover {{ transform: translateY(-3px); background: #33ff85; box-shadow: 0 10px 25px rgba(0, 255, 102, 0.6); }}
    </style>
</head>
<body>
    <div class="welcome-card">
        <img src="/logo.png" alt="Mr. Cuy Logo" class="logo-img" onerror="this.style.display='none';">
        <h1>Mr. Cuy</h1>
        <p>Seleccione su nombre de cajero para iniciar turno</p>
        <form action="/login_cajero" method="POST">
            <select name="cajero" required>
                REPLACE_OPCIONES_CAJEROS
            </select>
            <button type="submit" class="btn-ingresar">🚀 ACCEDER AL SISTEMA</button>
        </form>
    </div>
</body>
</html>
"""

HTML_WELCOME = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mr. Cuy - Menú Principal</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .welcome-card {{ background: #ffffff; padding: 55px 40px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); text-align: center; border: 5px solid #f1c40f; width: 100%; max-width: 580px; }}
        .logo-img {{ max-width: 180px; height: auto; border-radius: 50%; margin-bottom: 25px; border: 6px solid #00FF66; background: white; padding: 6px; box-shadow: 0 4px 15px rgba(0, 255, 102, 0.3); }}
        h1 {{ color: #2c3e50; font-size: 46px; margin: 0 0 15px 0; text-transform: uppercase; letter-spacing: 2px; font-weight: 900; }}
        p {{ color: #555; font-size: 22px; margin-bottom: 30px; font-weight: 700; }}
        .btn-menu {{ display: flex; align-items: center; justify-content: center; gap: 15px; padding: 22px; text-decoration: none; font-size: 22px; font-weight: 900; border-radius: 15px; transition: all 0.25s ease; margin-bottom: 20px; color: #111; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
        .btn-ingresar {{ background: #00FF66; color: #004d1a; border: 3px solid #00cc52; font-size: 24px; }}
        .btn-ingresar:hover {{ transform: translateY(-3px); background: #33ff85; box-shadow: 0 8px 22px rgba(0, 255, 102, 0.5); }}
        .btn-historial {{ background: #3498db; color: white; border: 3px solid #2980b9; }}
        .btn-historial:hover {{ transform: translateY(-3px); box-shadow: 0 8px 22px rgba(52, 152, 219, 0.5); }}
        .btn-cierre {{ background: #e74c3c; color: white; border: 3px solid #c0392b; }}
        .btn-cierre:hover {{ transform: translateY(-3px); box-shadow: 0 8px 22px rgba(231, 76, 60, 0.5); }}
        .btn-admin {{ background: #f1c40f; color: #2c3e50; border: 3px solid #d4ac0d; font-size: 20px; margin-top: 20px; }}
        .btn-admin:hover {{ transform: translateY(-2px); background: #f39c12; }}
        .cajero-badge {{ background: #e8f8f5; border: 3px solid #00FF66; border-radius: 12px; padding: 14px; margin-bottom: 30px; color: #004d1a; font-weight: 900; font-size: 20px; }}
    </style>
</head>
<body>
    <div class="welcome-card">
        <img src="/logo.png" alt="Mr. Cuy Logo" class="logo-img" onerror="this.style.display='none'; document.getElementById('alt-logo').style.display='block';">
        <div id="alt-logo" style="display:none; font-size: 70px; margin-bottom: 20px;">🐾</div>
        <h1>Mr. Cuy</h1>
        <div class="cajero-badge">👤 Cajero(a): REPLACE_CAJERO</div>
        <p>Sistema POS & Control de Restaurante</p>
        <a href="/seleccion_piso" class="btn-menu btn-ingresar">🍽️ INGRESAR AL SISTEMA</a>
        <a href="/historial_ventas" class="btn-menu btn-historial">📅 HISTORIAL DE VENTAS</a>
        {{REPLACE_BOTON_CIERRE}}
        <a href="/admin" class="btn-menu btn-admin">⚙️ PANEL DE ADMINISTRACIÓN</a>
        <a href="/" class="btn-menu" style="background:#ecf0f1; font-size:18px; padding:16px; margin-top:20px;">🔄 Cambiar de Cajero</a>
    </div>
</body>
</html>
"""

HTML_SELECCION_PISO = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Seleccionar Piso - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .card {{ background: #ffffff; padding: 50px 35px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); text-align: center; border: 5px solid #f1c40f; width: 100%; max-width: 580px; }}
        .logo-img {{ max-width: 150px; height: auto; border-radius: 50%; margin-bottom: 25px; border: 5px solid #00FF66; background: white; padding: 6px; }}
        h1 {{ color: #2c3e50; font-size: 38px; margin-bottom: 30px; text-transform: uppercase; font-weight: 900; }}
        .btn-piso {{ display: block; padding: 28px; text-decoration: none; font-size: 26px; font-weight: 900; border-radius: 16px; transition: all 0.25s ease; margin-bottom: 22px; color: #004d1a; background: #00FF66; border: 3px solid #00cc52; box-shadow: 0 6px 18px rgba(0, 255, 102, 0.35); }}
        .btn-piso:hover {{ transform: translateY(-4px) scale(1.02); background: #33ff85; box-shadow: 0 10px 25px rgba(0, 255, 102, 0.55); }}
        .btn-volver {{ display: inline-block; margin-top: 25px; color: #555; text-decoration: none; font-size: 20px; font-weight: 900; }}
        .btn-volver:hover {{ color: #000; }}
    </style>
</head>
<body>
    <div class="card">
        <img src="/logo.png" alt="Mr. Cuy Logo" class="logo-img" onerror="this.style.display='none';">
        <h1>Seleccione el Piso</h1>
        REPLACE_BOTONES_PISOS
        <a href="/menu_principal" class="btn-volver">⬅️ Volver al Menú Principal</a>
    </div>
</body>
</html>
"""

HTML_MAPA_MESAS = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>REPLACE_TITULO_PISO - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        .container {{ max-width: 1400px; margin: 30px auto; padding: 0 20px; }}
        .page-title {{ color: #2c3e50; font-size: 34px; font-weight: 900; border-bottom: 5px solid #f1c40f; padding-bottom: 15px; margin-top: 0; display: flex; align-items: center; justify-content: space-between; }}
        .mesa-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 22px; margin-top: 30px; }}
        .mesa-btn {{ background: white; border: 4px solid #00FF66; border-radius: 20px; padding: 28px 15px; text-align: center; text-decoration: none; color: #004d1a; font-weight: 900; font-size: 24px; box-shadow: 0 6px 15px rgba(0,0,0,0.08); transition: all 0.25s ease; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; }}
        .mesa-btn:hover {{ background: #e8f8f5; transform: translateY(-5px); box-shadow: 0 10px 22px rgba(0, 255, 102, 0.4); }}
        .mesa-btn .subtext {{ font-size: 16px; font-weight: 900; color: #27ae60; text-transform: uppercase; }}
        .mesa-btn.ocupada {{ background: #f1c40f; border-color: #d4ac0d; color: #111; box-shadow: 0 6px 18px rgba(241, 196, 15, 0.45); }}
        .mesa-btn.ocupada:hover {{ transform: translateY(-5px); box-shadow: 0 10px 25px rgba(241, 196, 15, 0.65); }}
        .mesa-btn.ocupada .subtext {{ color: #7d6608; font-weight: 900; }}
        .active-orders {{ background: white; padding: 30px; border-radius: 20px; margin-top: 45px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); border-top: 8px solid #f1c40f; overflow-x: auto; }}
        .active-orders h3 {{ margin-top: 0; color: #2c3e50; font-size: 26px; font-weight: 900; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 22px; font-size: 19px; }}
        th, td {{ border: 2px solid #e8ecef; padding: 18px; text-align: left; }}
        th {{ background-color: #2c3e50; color: white; font-weight: 900; text-transform: uppercase; font-size: 16px; letter-spacing: 0.5px; }}
        tr:nth-child(even) {{ background-color: #fffdf0; }}
        .btn-action {{ padding: 12px 18px; text-decoration: none; font-weight: 900; border-radius: 10px; display: inline-block; font-size: 16px; transition: all 0.2s; color: white; margin-right: 6px; box-shadow: 0 3px 8px rgba(0,0,0,0.15); }}
        .btn-cobrar {{ background: #00FF66; color: #004d1a; font-size: 18px; }} .btn-cobrar:hover {{ background: #33ff85; }}
        .btn-precuenta {{ background: #f1c40f; color: #111; }} .btn-precuenta:hover {{ background: #f39c12; }}
        .btn-cambiar {{ background: #3498db; }} .btn-cambiar:hover {{ background: #2980b9; }}
        .btn-anular {{ background: #e74c3c; }} .btn-anular:hover {{ background: #c0392b; }}
    </style>
</head>
<body>
    <header>
        <div class="header-brand">
            <img src="/logo.png" alt="Logo" class="header-logo" onerror="this.style.display='none';">
            <h1>REPLACE_TITULO_PISO</h1>
        </div>
        <div>
            <a href="/menu_principal" class="nav-btn nav-home">🏠 Menú Principal</a>
            <a href="/seleccion_piso" class="nav-btn nav-piso">🔄 Cambiar Piso</a>
            <a href="/admin" class="nav-btn nav-admin">⚙️ Admin</a>
        </div>
    </header>
    <div class="container">
        <div class="page-title">
            <span>REPLACE_SUBTITULO_MESAS</span>
            <div style="font-size:20px; font-weight:900;">
                <span style="color:#00AA44;">🟢 Libre</span> &nbsp;|&nbsp; 
                <span style="color:#b7950b;">🟡 Ocupada</span>
            </div>
        </div>
        <div class="mesa-grid">
            REPLACE_MESAS_GRID
        </div>
        <div class="active-orders">
            <h3>📋 Cuentas Activas en Este Piso</h3>
            <meta http-equiv="refresh" content="5">
            <table>
                <tr>
                    <th>ID</th>
                    <th>Mesa</th>
                    <th>Mesero</th>
                    <th>Consumo</th>
                    <th>Total</th>
                    <th>Acciones</th>
                </tr>
                REPLACE_TABLA_PEDIDOS
            </table>
        </div>
    </div>
</body>
</html>
"""

HTML_MESA_ATENDIDA = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mesa Atendida - REPLACE_MESA</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .card {{ background: #ffffff; padding: 45px 35px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); text-align: center; border: 5px solid #f1c40f; width: 100%; max-width: 600px; }}
        h2 {{ color: #2c3e50; margin-top: 0; font-size: 36px; font-weight: 900; }}
        .info-box {{ background: #fffdf0; border-left: 8px solid #f1c40f; padding: 22px; border-radius: 12px; margin-bottom: 30px; font-size: 20px; text-align: left; color: #2c3e50; word-wrap: break-word; border: 3px solid #fef9e7; }}
        .btn-opcion {{ display: flex; align-items: center; justify-content: center; gap: 12px; padding: 22px; text-decoration: none; font-size: 20px; font-weight: 900; border-radius: 15px; margin-bottom: 18px; color: #111; text-align: center; transition: all 0.25s ease; box-shadow: 0 5px 12px rgba(0,0,0,0.1); }}
        .btn-cobrar {{ background: #00FF66; color: #004d1a; font-size: 24px; border: 3px solid #00cc52; }}
        .btn-cobrar:hover {{ transform: translateY(-3px); background: #33ff85; box-shadow: 0 8px 22px rgba(0, 255, 102, 0.5); }}
        .btn-agregar {{ background: #f1c40f; border: 3px solid #d4ac0d; }}
        .btn-agregar:hover {{ transform: translateY(-3px); background: #f39c12; }}
        .btn-precuenta {{ background: #f39c12; color: white; border: 3px solid #d68910; }}
        .btn-precuenta:hover {{ transform: translateY(-3px); }}
        .btn-cambiar {{ background: #3498db; color: white; border: 3px solid #2980b9; }}
        .btn-cambiar:hover {{ transform: translateY(-3px); }}
        .btn-anular {{ background: #e74c3c; color: white; border: 3px solid #c0392b; }}
        .btn-anular:hover {{ transform: translateY(-3px); }}
        .btn-volver {{ display: inline-block; margin-top: 20px; color: #555; text-decoration: none; font-size: 20px; font-weight: 900; }}
        .btn-volver:hover {{ color: #000; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🍽️ REPLACE_MESA (Atendida)</h2>
        <div class="info-box">
            <p style="margin:8px 0;"><b>Atendido por:</b> REPLACE_MESERO</p>
            <p style="margin:8px 0;"><b>Consumo en esta Mesa:</b><br><span style="color:#d35400; font-weight:900;">REPLACE_DETALLE</span></p>
            <p style="margin:16px 0 0 0; color:#008833; font-size:26px; font-weight:900;">Total Acumulado: S/ REPLACE_TOTAL</p>
        </div>
        <a href="/pantalla_cobrar?id=REPLACE_ID&piso=REPLACE_PISO" class="btn-opcion btn-cobrar" style="REPLACE_STYLE_COBRAR">💳 COBRAR MESA / FACTURA</a>
        <a href="/ordenar?mesa=REPLACE_MESA_ENC&mesero=REPLACE_MESERO_ENC&piso=REPLACE_PISO" class="btn-opcion btn-agregar">📝 Agregar más Personas / Pedidos</a>
        <a href="/precuenta?id=REPLACE_ID" target="_blank" class="btn-opcion btn-precuenta">🖨️ Imprimir Ticket / Precuenta</a>
        <a href="/cambiar_mesa?id=REPLACE_ID" class="btn-opcion btn-cambiar">🔄 Cambiar de Mesa</a>
        <a href="/anular_pedido?id=REPLACE_ID&piso=REPLACE_PISO" class="btn-opcion btn-anular" onclick="return confirm('¿Seguro que deseas anular esta cuenta?');">❌ Anular Pedido</a>
        <a href="/mapa_piso?piso=REPLACE_PISO" class="btn-volver">⬅️ Volver al Mapa</a>
    </div>
</body>
</html>
"""

HTML_PANTALLA_COBRAR = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cobrar - REPLACE_MESA</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .card {{ background: #ffffff; padding: 45px 35px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); border: 5px solid #00FF66; width: 100%; max-width: 620px; text-align: center; color: #2c3e50; }}
        h2 {{ color: #008833; margin-top: 0; font-size: 34px; text-transform: uppercase; font-weight: 900; }}
        .info-header {{ background: #fffdf0; padding: 18px; border-radius: 12px; font-size: 20px; text-align: left; margin-bottom: 25px; border: 3px solid #f1c40f; font-weight: 700; }}
        .tabla-resumen {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 18px; background: white; color: #333; border-radius: 12px; overflow: hidden; box-shadow: 0 5px 15px rgba(0,0,0,0.08); }}
        .tabla-resumen th {{ background: #00FF66; color: #004d1a; padding: 16px; text-align: left; text-transform: uppercase; font-size: 16px; font-weight: 900; }}
        .tabla-resumen td {{ padding: 15px 16px; border-bottom: 2px solid #f1c40f; text-align: left; }}
        .comprobante-box {{ background: #fffdf0; border: 3px solid #f1c40f; border-radius: 15px; padding: 22px; text-align: left; margin-bottom: 28px; }}
        .comprobante-box h4 {{ margin: 0 0 15px 0; color: #d35400; font-size: 20px; text-transform: uppercase; font-weight: 900; }}
        .comprobante-options {{ display: flex; gap: 15px; margin-bottom: 18px; }}
        .radio-btn {{ flex: 1; background: #ffffff; border: 3px solid #f1c40f; padding: 16px; border-radius: 10px; text-align: center; cursor: pointer; font-weight: 900; font-size: 18px; color: #2c3e50; }}
        .radio-btn input {{ display: none; }}
        .radio-btn.active {{ background: #f1c40f; color: #111; border-color: #d4ac0d; }}
        .field-group {{ margin-bottom: 15px; }}
        .field-group label {{ font-size: 17px; display: block; margin-bottom: 8px; font-weight: 900; color: #2c3e50; }}
        .field-group input {{ width: 100%; padding: 16px; border-radius: 10px; border: 3px solid #ccc; font-size: 18px; box-sizing: border-box; font-weight: bold; }}
        .total-box {{ background: #00FF66; padding: 25px; border-radius: 15px; margin-bottom: 28px; box-shadow: 0 6px 18px rgba(0,0,0,0.1); border: 3px solid #00cc52; text-align: center; }}
        .total-box label {{ font-size: 18px; text-transform: uppercase; letter-spacing: 1px; color: #004d1a; display: block; font-weight: 900; }}
        .total-box h1 {{ margin: 10px 0 0 0; font-size: 52px; color: #004d1a; font-weight: 900; }}
        .btn-liberar {{ display: block; width: 100%; padding: 22px; background: #00FF66; color: #004d1a; border: 3px solid #00cc52; font-size: 24px; font-weight: 900; border-radius: 15px; transition: all 0.25s ease; cursor: pointer; box-shadow: 0 6px 20px rgba(0, 255, 102, 0.45); }}
        .btn-liberar:hover {{ transform: translateY(-3px); background: #33ff85; box-shadow: 0 10px 25px rgba(0, 255, 102, 0.65); }}
        .btn-cancelar {{ display: inline-block; margin-top: 20px; color: #555; text-decoration: none; font-size: 20px; font-weight: 900; }}
        .btn-cancelar:hover {{ color: #000; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>💳 Resumen de Cuenta</h2>
        <div class="info-header">
            <p style="margin:6px 0;"><b>Ubicación:</b> REPLACE_MESA</p>
            <p style="margin:6px 0;"><b>Atendido por:</b> REPLACE_MESERO</p>
        </div>
        <table class="tabla-resumen">
            <thead>
                <tr>
                    <th>Consumo de la Mesa</th>
                    <th style="text-align:right;">Estado</th>
                </tr>
            </thead>
            <tbody>
                REPLACE_FILAS_CONSUMO
            </tbody>
        </table>
        <form action="/confirmar_cobro" method="POST">
            <input type="hidden" name="id" value="REPLACE_ID">
            <input type="hidden" name="piso" value="REPLACE_PISO">
            <div class="comprobante-box">
                <h4>🧾 Tipo de Comprobante</h4>
                <div class="comprobante-options">
                    <label class="radio-btn active" id="lblTicket" onclick="setTipoComprobante('TICKET')">
                        <input type="radio" name="tipo_comprobante" value="TICKET" checked> Ticket
                    </label>
                    <label class="radio-btn" id="lblBoleta" onclick="setTipoComprobante('BOLETA')">
                        <input type="radio" name="tipo_comprobante" value="BOLETA"> Boleta
                    </label>
                    <label class="radio-btn" id="lblFactura" onclick="setTipoComprobante('FACTURA')">
                        <input type="radio" name="tipo_comprobante" value="FACTURA"> Factura
                    </label>
                </div>
                <div id="boxCamposFactura" style="display:none;">
                    <div class="field-group">
                        <label>RUC del Cliente (11 dígitos):</label>
                        <input type="text" name="doc_cliente" id="doc_cliente" placeholder="Ej: 20601234567" maxlength="11">
                    </div>
                    <div class="field-group">
                        <label>Razón Social / Nombre Comercial:</label>
                        <input type="text" name="razon_social" id="razon_social" placeholder="Ej: Empresa SAC">
                    </div>
                </div>
            </div>
            <div class="total-box">
                <label>MONTO TOTAL A COBRAR</label>
                <h1>S/ REPLACE_TOTAL</h1>
            </div>
            <button type="submit" class="btn-liberar" onclick="return confirm('¿Confirmar cobro de S/ REPLACE_TOTAL y liberar la mesa?');">✅ CONFIRMAR PAGO Y LIBERAR MESA</button>
        </form>
        <a href="/ver_mesa?mesa=REPLACE_MESA_ENC&piso=REPLACE_PISO" class="btn-cancelar">⬅️ Volver a Opciones de Mesa</a>
    </div>
    <script>
        function setTipoComprobante(tipo) {{
            document.getElementById('lblTicket').classList.remove('active');
            document.getElementById('lblBoleta').classList.remove('active');
            document.getElementById('lblFactura').classList.remove('active');
            const boxFactura = document.getElementById('boxCamposFactura');
            if (tipo === 'TICKET') {{
                document.getElementById('lblTicket').classList.add('active');
                boxFactura.style.display = 'none';
            }} else if (tipo === 'BOLETA') {{
                document.getElementById('lblBoleta').classList.add('active');
                boxFactura.style.display = 'none';
            }} else if (tipo === 'FACTURA') {{
                document.getElementById('lblFactura').classList.add('active');
                boxFactura.style.display = 'block';
            }}
        }}
    </script>
</body>
</html>
"""

HTML_HISTORIAL = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Historial de Ventas - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        .container {{ max-width: 1300px; margin: 30px auto; padding: 0 20px; }}
        .filter-card {{ background: white; padding: 30px; border-radius: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); margin-bottom: 35px; text-align: center; border-top: 8px solid #3498db; }}
        .filter-card h2 {{ margin-top: 0; color: #2c3e50; font-size: 28px; font-weight: 900; }}
        .date-picker-form {{ display: flex; justify-content: center; align-items: center; gap: 20px; flex-wrap: wrap; margin-top: 22px; }}
        input[type="date"] {{ padding: 16px 20px; font-size: 20px; border: 3px solid #3498db; border-radius: 12px; font-family: inherit; font-weight: bold; color: #2c3e50; }}
        .btn-buscar {{ background: #3498db; color: white; border: none; padding: 16px 28px; font-size: 20px; font-weight: 900; border-radius: 12px; cursor: pointer; transition: all 0.2s; }}
        .btn-buscar:hover {{ background: #2980b9; transform: translateY(-2px); }}
        .btn-semana {{ background: #f1c40f; color: #111; border: none; padding: 16px 28px; font-size: 20px; font-weight: 900; border-radius: 12px; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.2s; }}
        .btn-semana:hover {{ background: #f39c12; transform: translateY(-2px); }}
        .btn-reiniciar-datos {{ background: #e74c3c; color: white; border: none; padding: 16px 28px; font-size: 20px; font-weight: 900; border-radius: 12px; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.2s; margin-top: 15px; }}
        .btn-reiniciar-datos:hover {{ background: #c0392b; transform: translateY(-2px); }}
        .summary-box {{ background: #fffdf0; border: 4px solid #f1c40f; border-radius: 20px; padding: 28px; text-align: center; margin-bottom: 35px; display: flex; justify-content: space-around; flex-wrap: wrap; box-shadow: 0 6px 18px rgba(0,0,0,0.06); }}
        .summary-box div {{ margin: 12px 25px; }}
        .summary-box h3 {{ margin: 10px 0 0 0; color: #d35400; font-size: 42px; font-weight: 900; }}
        .summary-box p {{ margin: 0; font-size: 18px; color: #555; font-weight: 900; text-transform: uppercase; letter-spacing: 0.5px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 6px 20px rgba(0,0,0,0.08); font-size: 18px; }}
        th, td {{ border: 2px solid #e8ecef; padding: 18px; text-align: left; }}
        th {{ background-color: #2c3e50; color: white; font-weight: 900; text-transform: uppercase; font-size: 16px; }}
        tr:nth-child(even) {{ background-color: #fffdf0; }}
    </style>
</head>
<body>
    <header>
        <div class="header-brand">
            <img src="/logo.png" alt="Logo" class="header-logo" onerror="this.style.display='none';">
            <h1>Historial de Ventas - Mr. Cuy</h1>
        </div>
        <a href="/menu_principal" class="nav-btn nav-home">🏠 Menú Principal</a>
    </header>
    <div class="container">
        <div class="filter-card">
            <h2>📅 Consulta de Ventas por Fecha</h2>
            <form action="/historial_ventas" method="GET" class="date-picker-form">
                <label style="font-weight:900;">Seleccione Día:</label>
                <input type="date" name="fecha" value="REPLACE_FECHA_VAL" onchange="this.form.submit()">
                <button type="submit" class="btn-buscar">🔍 Ver Historial</button>
                <a href="/historial_semana" class="btn-semana">📊 Comparar Ventas de la Semana</a>
            </form>
            <div style="margin-top: 22px;">
                <button type="button" class="btn-reiniciar-datos" onclick="pedirPasswordReinicio()">🗑️ Reiniciar Datos del Historial</button>
            </div>
        </div>
        <div class="summary-box">
            <div>
                <p>TOTAL RECAUDADO EL REPLACE_FECHA_FMT</p>
                <h3>S/ REPLACE_TOTAL_DIA</h3>
            </div>
            <div>
                <p>TOTAL VENTAS / MESAS ATENDIDAS</p>
                <h3>REPLACE_CANTIDAD_CUENTAS Cuentas</h3>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th># ID</th>
                    <th>Mesa</th>
                    <th>Personal (Mesero / Cajero)</th>
                    <th>Comprobante</th>
                    <th>Detalle de Consumo</th>
                    <th>Monto Cobrado</th>
                </tr>
            </thead>
            <tbody>
                REPLACE_FILAS_HISTORIAL
            </tbody>
        </table>
    </div>
    <script>
        function pedirPasswordReinicio() {{
            let pass = prompt("Ingrese la contraseña de seguridad para reiniciar los datos:");
            if (pass === "0000") {{
                window.location.href = "/reiniciar_historial";
            }} else if (pass !== null) {{
                alert("Contraseña incorrecta.");
            }}
        }}
    </script>
</body>
</html>
"""

HTML_SEMANA = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Semanal - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
        .card {{ background: white; padding: 35px; border-radius: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); border-top: 8px solid #f1c40f; }}
        h2 {{ color: #2c3e50; margin-top: 0; text-align: center; font-weight: 900; font-size: 32px; }}
        .total-box {{ background: #fffdf0; border: 4px solid #f1c40f; border-radius: 20px; padding: 28px; text-align: center; margin: 30px 0; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }}
        .total-box h2 {{ margin: 10px 0 0 0; color: #d35400; font-size: 48px; font-weight: 900; }}
        .tabla-semana {{ width: 100%; border-collapse: collapse; margin-top: 30px; font-size: 20px; background: white; border-radius: 12px; overflow: hidden; }}
        .tabla-semana th, .tabla-semana td {{ border: 2px solid #e8ecef; padding: 18px; text-align: left; }}
        .tabla-semana th {{ background-color: #f1c40f; color: #111; font-weight: 900; font-size: 18px; }}
    </style>
</head>
<body>
    <header>
        <div class="header-brand">
            <img src="/logo.png" alt="Logo" class="header-logo" onerror="this.style.display='none';">
            <h1>Reporte Semanal de Ventas</h1>
        </div>
        <a href="/historial_ventas" class="nav-btn nav-piso">⬅️ Volver al Historial</a>
    </header>
    <div class="container">
        <div class="card">
            <h2>📊 Resumen de Ventas (Últimos 7 Días)</h2>
            <div class="total-box">
                <p style="margin:0; font-size:18px; color:#555; font-weight:900; text-transform:uppercase;">RECAUDACIÓN TOTAL DE LA SEMANA</p>
                <h2>S/ REPLACE_TOTAL_SEMANA</h2>
            </div>
            <table class="tabla-semana">
                <tr>
                    <th>Fecha / Día</th>
                    <th style="text-align:right;">Monto Recaudado</th>
                </tr>
                REPLACE_FILAS_SEMANA
            </table>
        </div>
    </div>
</body>
</html>
"""

HTML_SELECCION_MESERO = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asignar Mesero - REPLACE_MESA</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .card {{ background: #ffffff; padding: 50px 35px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); text-align: center; border: 5px solid #f1c40f; width: 100%; max-width: 600px; }}
        .logo-img {{ max-width: 130px; height: auto; border-radius: 50%; margin-bottom: 20px; border: 4px solid #00FF66; background: white; padding: 5px; }}
        h2 {{ color: #2c3e50; font-size: 34px; margin-top: 0; margin-bottom: 10px; font-weight: 900; }}
        p {{ color: #555; font-size: 22px; margin-bottom: 30px; font-weight: 700; }}
        .meseros-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 18px; margin-bottom: 30px; }}
        .mesero-card {{ background: white; border: 4px solid #00FF66; border-radius: 16px; padding: 25px 15px; text-decoration: none; color: #004d1a; font-weight: 900; font-size: 22px; transition: all 0.25s ease; display: block; box-shadow: 0 5px 12px rgba(0,0,0,0.1); }}
        .mesero-card:hover {{ background: #e8f8f5; transform: translateY(-4px); border-color: #00cc52; box-shadow: 0 8px 20px rgba(0, 255, 102, 0.45); }}
        .btn-cancelar {{ display: inline-block; margin-top: 20px; color: #555; text-decoration: none; font-size: 20px; font-weight: 900; }}
        .btn-cancelar:hover {{ color: #000; }}
    </style>
</head>
<body>
    <div class="card">
        <img src="/logo.png" alt="Mr. Cuy Logo" class="logo-img" onerror="this.style.display='none';">
        <h2>Atendiendo: REPLACE_MESA</h2>
        <p>Toque el nombre del mesero responsable:</p>
        <div class="meseros-grid">
            REPLACE_CUADROS_MESEROS
        </div>
        <a href="REPLACE_CANCELAR_LINK" class="btn-cancelar">⬅️ Volver al Mapa</a>
    </div>
</body>
</html>
"""

HTML_ORDEN = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pedido - REPLACE_MESA</title>
    {CSS_GLOBAL}
    <style>
        .container {{ max-width: 1600px; margin: 25px auto; padding: 0 20px; }}
        .personas-bar {{ display: flex; align-items: center; gap: 12px; margin-bottom: 25px; overflow-x: auto; padding-bottom: 10px; }}
        .btn-persona-tab {{ background: #ecf0f1; color: #2c3e50; border: 3px solid #bdc3c7; padding: 16px 28px; font-size: 20px; font-weight: 900; border-radius: 30px; cursor: pointer; transition: all 0.2s; white-space: nowrap; box-shadow: 0 4px 8px rgba(0,0,0,0.08); }}
        .btn-persona-tab.active {{ background: #00FF66; color: #004d1a; border-color: #00cc52; box-shadow: 0 6px 15px rgba(0, 255, 102, 0.35); }}
        .btn-add-persona {{ background: #f1c40f; color: #111; border: 3px solid #d4ac0d; padding: 16px 28px; font-size: 20px; font-weight: 900; border-radius: 30px; cursor: pointer; white-space: nowrap; box-shadow: 0 4px 8px rgba(0,0,0,0.08); transition: all 0.2s; }}
        .btn-add-persona:hover {{ transform: translateY(-2px); background: #f39c12; }}
        .tabs-cat {{ display: flex; gap: 12px; overflow-x: auto; margin-bottom: 25px; background: #ffffff; padding: 18px; border-radius: 18px; box-shadow: 0 5px 18px rgba(0,0,0,0.08); border: 4px solid #f1c40f; }}
        .tab-btn {{ background: #fffdf0; color: #2c3e50; border: 3px solid #f1c40f; padding: 18px 26px; font-size: 20px; font-weight: 900; border-radius: 12px; cursor: pointer; transition: all 0.2s; white-space: nowrap; }}
        .tab-btn.active {{ background: #00FF66; color: #004d1a; border-color: #00cc52; box-shadow: 0 5px 12px rgba(0, 255, 102, 0.45); }}
        .layout-grid {{ display: flex; flex-wrap: wrap; gap: 30px; }}
        .left-content {{ flex: 2; min-width: 400px; }}
        .right-panel {{ flex: 1; min-width: 420px; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); height: fit-content; position: sticky; top: 20px; border-top: 8px solid #00FF66; border: 4px solid #e8ecef; }}
        .category-view {{ display: none; }}
        .category-view.active {{ display: block; }}
        .section-box {{ background: white; padding: 25px; border-radius: 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 3px solid #e1e8ed; }}
        .section-title {{ background: #f1c40f; color: #111; padding: 15px 20px; border-radius: 10px; font-weight: 900; font-size: 22px; margin-bottom: 22px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .items-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }}
        .item-card {{ background: #fffdf0; border: 4px solid #f1c40f; border-radius: 16px; padding: 22px 14px; text-align: center; cursor: pointer; transition: all 0.2s; user-select: none; box-shadow: 0 4px 8px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: space-between; min-height: 120px; }}
        .item-card:hover {{ border-color: #00FF66; background: #e8f8f5; transform: translateY(-3px); }}
        .item-card:active {{ transform: scale(0.97); }}
        .item-card.selected {{ background: #00FF66; border-color: #00cc52; box-shadow: 0 6px 16px rgba(0, 255, 102, 0.4); }}
        .item-card.selected .item-name {{ color: #004d1a; font-weight: 900; }}
        .item-card.selected .item-price {{ background: white; color: #004d1a; }}
        .item-name {{ font-weight: 900; font-size: 20px; margin-bottom: 10px; color: #2c3e50; line-height: 1.2; }}
        .item-price {{ color: #008833; font-weight: 900; font-size: 19px; background: #e8f8f5; padding: 6px 12px; border-radius: 8px; margin-top: 8px; border: 2px solid #00FF66; display: inline-block; }}
        .mesero-badge {{ background: #e8f8f5; border: 3px solid #00FF66; border-radius: 12px; padding: 16px; font-weight: 900; color: #004d1a; margin-bottom: 20px; font-size: 20px; }}
        .llevar-checkbox {{ background: #fffdf0; border: 3px solid #f1c40f; border-radius: 12px; padding: 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; cursor: pointer; font-weight: 900; color: #d35400; font-size: 18px; }}
        .nota-group {{ margin-bottom: 20px; position: relative; }}
        .nota-group label {{ display: flex; justify-content: space-between; align-items: center; font-weight: 900; margin-bottom: 10px; font-size: 18px; color: #2c3e50; }}
        .nota-group textarea {{ width: 100%; padding: 15px; border: 3px solid #ccc; border-radius: 10px; font-size: 18px; resize: vertical; height: 90px; font-family: inherit; font-weight: bold; }}
        .btn-nota-aux {{ color: white; border: none; padding: 10px 15px; font-size: 15px; border-radius: 8px; cursor: pointer; font-weight: 900; margin-left: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.12); }}
        .btn-teclado {{ background: #3498db; }} .btn-teclado:hover {{ background: #2980b9; }}
        .btn-rapidas {{ background: #f1c40f; color: #111; }} .btn-rapidas:hover {{ background: #f39c12; }}
        .notas-rapidas-popup {{ display: none; background: #fffdf0; border: 4px solid #f1c40f; border-radius: 12px; padding: 15px; margin-top: 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.15); }}
        .notas-rapidas-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .btn-chip-nota {{ background: white; border: 3px solid #f1c40f; color: #d35400; font-weight: 900; font-size: 16px; padding: 10px 15px; border-radius: 20px; cursor: pointer; transition: all 0.2s; }}
        .btn-chip-nota:hover {{ background: #f1c40f; color: #111; transform: scale(1.05); }}
        #virtualKeyboard {{ display: none; position: fixed; bottom: 0; left: 0; width: 100%; background: #2c3e50; border-top: 8px solid #00FF66; padding: 20px; box-shadow: 0 -8px 30px rgba(0,0,0,0.5); z-index: 9999; }}
        .vk-row {{ display: flex; justify-content: center; gap: 10px; margin-bottom: 10px; }}
        .vk-key {{ background: #fff; color: #333; border: none; border-radius: 10px; padding: 20px 0; font-size: 22px; font-weight: 900; flex: 1; max-width: 70px; cursor: pointer; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        .vk-key:active {{ background: #00FF66; color: #004d1a; }}
        .vk-key.wide {{ max-width: 140px; background: #ecf0f1; }}
        .vk-key.space {{ max-width: 350px; background: #ecf0f1; }}
        .vk-key.vk-close {{ background: #e74c3c; color: white; max-width: 140px; }}
        .pedidos-existentes-box {{ background: #fffdf0; border: 3px solid #f1c40f; border-radius: 12px; padding: 16px; margin-bottom: 22px; max-height: 180px; overflow-y: auto; font-size: 17px; }}
        .pedidos-existentes-box h4 {{ margin: 0 0 10px 0; color: #2c3e50; font-size: 18px; border-bottom: 3px solid #f1c40f; padding-bottom: 8px; font-weight: 900; }}
        .resumen-global-box {{ background: #e8f8f5; border: 4px solid #00FF66; border-radius: 15px; padding: 20px; margin-bottom: 25px; font-size: 18px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
        .resumen-global-box h4 {{ margin: 0 0 15px 0; color: #004d1a; font-size: 20px; font-weight: 900; text-transform: uppercase; border-bottom: 3px solid #00FF66; padding-bottom: 8px; }}
        .persona-bloque-resumen {{ margin-bottom: 15px; padding-bottom: 12px; border-bottom: 2px dashed #00FF66; }}
        .persona-bloque-resumen:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
        .persona-titulo-resumen {{ font-weight: 900; color: #2c3e50; display: flex; justify-content: space-between; font-size: 18px; }}
        .persona-nota-resumen {{ font-style: italic; color: #d35400; font-size: 16px; margin-top: 5px; font-weight: 900; background: #fff; padding: 6px 10px; border-radius: 8px; display: inline-block; border: 2px solid #f1c40f; }}
        .resumen-total-general {{ margin-top: 15px; padding-top: 12px; border-top: 4px solid #00FF66; font-weight: 900; color: #004d1a; font-size: 24px; text-align: right; }}
        .btn-enviar {{ background: #00FF66; color: #004d1a; width: 100%; padding: 22px; border: 3px solid #00cc52; border-radius: 15px; font-size: 24px; font-weight: 900; cursor: pointer; transition: all 0.25s ease; box-shadow: 0 6px 20px rgba(0, 255, 102, 0.45); }}
        .btn-enviar:hover {{ transform: translateY(-3px); background: #33ff85; box-shadow: 0 10px 25px rgba(0, 255, 102, 0.65); }}
    </style>
</head>
<body>
    <header>
        <div class="header-brand">
            <img src="/logo.png" alt="Logo" class="header-logo" onerror="this.style.display='none';">
            <h1>Mr. Cuy - Atendiendo: REPLACE_MESA</h1>
        </div>
        <a href="REPLACE_VOLVER" class="nav-btn nav-home">⬅️ Volver a Mesas</a>
    </header>
    <div class="container">
        <div class="personas-bar" id="barPersonas"></div>
        <div class="tabs-cat">
            REPLACE_TABS_CAT
        </div>
        <form id="formOrden" action="/enviar" method="POST" onsubmit="prepararEnvio(event)">
            <input type="hidden" name="mesa" value="REPLACE_MESA">
            <input type="hidden" name="mesero" value="REPLACE_MESERO">
            <input type="hidden" name="origen_piso" value="REPLACE_ORIGEN">
            <input type="hidden" name="datos_personas_json" id="datos_personas_json">
            <div class="layout-grid">
                <div class="left-content">
                    REPLACE_CATEGORY_VIEWS
                </div>
                <div class="right-panel">
                    <div class="mesero-badge">👤 Mesero: REPLACE_MESERO</div>
                    <div class="pedidos-existentes-box">
                        <h4>📋 Consumo Anterior en Mesa:</h4>
                        <div>REPLACE_PEDIDOS_ACTUALES</div>
                    </div>
                    <h4 style="margin: 10px 0; color:#2c3e50; font-size: 20px;">🛒 Editando: <span id="lblPersonaActual" style="color:#008833;">Persona 1</span></h4>
                    <label class="llevar-checkbox">
                        <input type="checkbox" id="chkLlevarPersona" onchange="toggleLlevarActual(this.checked)" style="width:24px; height:24px;">
                        🛍️ PARA LLEVAR (+ Táper Menú S/ REPLACE_TAPER_MENU / Entrada S/ REPLACE_TAPER_ENTRADA)
                    </label>
                    <div class="nota-group">
                        <label>
                            <span>📝 Nota u Observación:</span>
                            <div>
                                <button type="button" class="btn-nota-aux btn-rapidas" onclick="toggleNotasRapidasPopup()">⚡ Notas Rápidas</button>
                                <button type="button" class="btn-nota-aux btn-teclado" onclick="toggleVirtualKeyboard()">⌨️ Teclado</button>
                            </div>
                        </label>
                        <textarea id="txtNotaPersona" oninput="actualizarNotaActual(this.value)" placeholder="Ej: Sin cebolla, término medio..."></textarea>
                        <div id="popupNotasRapidas" class="notas-rapidas-popup">
                            <div style="font-size:15px; font-weight:900; color:#d35400; margin-bottom:10px;">Toca una opción para añadir:</div>
                            <div class="notas-rapidas-grid">
                                REPLACE_BOTONES_NOTAS_RAPIDAS
                            </div>
                        </div>
                    </div>
                    <div class="resumen-global-box">
                        <h4>📋 Resumen Completo de la Orden:</h4>
                        <div id="contenedorResumenGlobal">
                        </div>
                    </div>
                    <button type="submit" class="btn-enviar">🚀 ENVIAR COMANDA A COCINA</button>
                </div>
            </div>
        </form>
    </div>
    <div id="virtualKeyboard">
        <div class="vk-row">
            <button type="button" class="vk-key" onclick="vkPress('Q')">Q</button>
            <button type="button" class="vk-key" onclick="vkPress('W')">W</button>
            <button type="button" class="vk-key" onclick="vkPress('E')">E</button>
            <button type="button" class="vk-key" onclick="vkPress('R')">R</button>
            <button type="button" class="vk-key" onclick="vkPress('T')">T</button>
            <button type="button" class="vk-key" onclick="vkPress('Y')">Y</button>
            <button type="button" class="vk-key" onclick="vkPress('U')">U</button>
            <button type="button" class="vk-key" onclick="vkPress('I')">I</button>
            <button type="button" class="vk-key" onclick="vkPress('O')">O</button>
            <button type="button" class="vk-key" onclick="vkPress('P')">P</button>
            <button type="button" class="vk-key wide" onclick="vkBackspace()">⌫ Borrar</button>
        </div>
        <div class="vk-row">
            <button type="button" class="vk-key" onclick="vkPress('A')">A</button>
            <button type="button" class="vk-key" onclick="vkPress('S')">S</button>
            <button type="button" class="vk-key" onclick="vkPress('D')">D</button>
            <button type="button" class="vk-key" onclick="vkPress('F')">F</button>
            <button type="button" class="vk-key" onclick="vkPress('G')">G</button>
            <button type="button" class="vk-key" onclick="vkPress('H')">H</button>
            <button type="button" class="vk-key" onclick="vkPress('J')">J</button>
            <button type="button" class="vk-key" onclick="vkPress('K')">K</button>
            <button type="button" class="vk-key" onclick="vkPress('L')">L</button>
            <button type="button" class="vk-key" onclick="vkPress('Ñ')">Ñ</button>
        </div>
        <div class="vk-row">
            <button type="button" class="vk-key" onclick="vkPress('Z')">Z</button>
            <button type="button" class="vk-key" onclick="vkPress('X')">X</button>
            <button type="button" class="vk-key" onclick="vkPress('C')">C</button>
            <button type="button" class="vk-key" onclick="vkPress('V')">V</button>
            <button type="button" class="vk-key" onclick="vkPress('B')">B</button>
            <button type="button" class="vk-key" onclick="vkPress('N')">N</button>
            <button type="button" class="vk-key" onclick="vkPress('M')">M</button>
            <button type="button" class="vk-key" onclick="vkPress(',')">,</button>
            <button type="button" class="vk-key" onclick="vkPress('.')">.</button>
        </div>
        <div class="vk-row">
            <button type="button" class="vk-key space" onclick="vkPress(' ')">Espacio</button>
            <button type="button" class="vk-key vk-close" onclick="toggleVirtualKeyboard()">Cerrar ✖</button>
        </div>
    </div>
    <script>
        let personas = [
            {{ id: 1, nombre: "Persona 1", items: [], para_llevar: false, nota: "" }}
        ];
        let personaActualIdx = 0;
        const catalogData = REPLACE_CATALOGO_JSON;
        const taperMenuVal = REPLACE_TAPER_MENU_NUM;
        const taperEntradaVal = REPLACE_TAPER_ENTRADA_NUM;

        function renderBarraPersonas() {{
            const bar = document.getElementById('barPersonas');
            let html = "";
            personas.forEach((p, index) => {{
                const activeClass = (index === personaActualIdx) ? "active" : "";
                html += `<button type="button" class="btn-persona-tab ${{activeClass}}" onclick="cambiarPersona(${{index}})">👤 ${{p.nombre}}</button>`;
            }});
            html += `<button type="button" class="btn-add-persona" onclick="agregarPersona()">➕ Añadir otra persona</button>`;
            bar.innerHTML = html;
        }}
        function agregarPersona() {{
            const nextNum = personas.length + 1;
            personas.push({{
                id: nextNum,
                nombre: "Persona " + nextNum,
                items: [],
                para_llevar: false,
                nota: ""
            }});
            cambiarPersona(personas.length - 1);
        }}
        function cambiarPersona(index) {{
            personaActualIdx = index;
            renderBarraPersonas();
            const p = personas[personaActualIdx];
            document.getElementById('lblPersonaActual').innerText = p.nombre;
            document.getElementById('chkLlevarPersona').checked = p.para_llevar;
            document.getElementById('txtNotaPersona').value = p.nota;
            const cards = document.querySelectorAll('.item-card');
            cards.forEach(card => {{
                const pid = parseInt(card.getAttribute('data-id'));
                if (p.items.includes(pid)) {{
                    card.classList.add('selected');
                }} else {{
                    card.classList.remove('selected');
                }}
            }});
            renderResumenGlobal();
        }}
        function toggleCard(card) {{
            const pid = parseInt(card.getAttribute('data-id'));
            const p = personas[personaActualIdx];
            const idx = p.items.indexOf(pid);
            if (idx > -1) {{
                p.items.splice(idx, 1);
                card.classList.remove('selected');
            }} else {{
                p.items.push(pid);
                card.classList.add('selected');
            }}
            renderResumenGlobal();
        }}
        function toggleLlevarActual(checked) {{
            personas[personaActualIdx].para_llevar = checked;
            renderResumenGlobal();
        }}
        function actualizarNotaActual(val) {{
            personas[personaActualIdx].nota = val;
            renderResumenGlobal();
        }}
        function agregarNotaRapida(texto) {{
            const txt = document.getElementById('txtNotaPersona');
            if (txt.value.trim() === "") {{
                txt.value = texto;
            }} else {{
                txt.value += ", " + texto;
            }}
            actualizarNotaActual(txt.value);
            document.getElementById('popupNotasRapidas').style.display = 'none';
        }}
        function toggleNotasRapidasPopup() {{
            const pop = document.getElementById('popupNotasRapidas');
            pop.style.display = (pop.style.display === 'block') ? 'none' : 'block';
        }}
        function renderResumenGlobal() {{
            const cont = document.getElementById('contenedorResumenGlobal');
            let html = "";
            let hayItems = false;
            let totalGeneral = 0.0;
            personas.forEach((p) => {{
                if (p.items.length > 0 || p.nota.trim() !== "") {{
                    hayItems = true;
                    let itemsNombres = [];
                    let platosFondoCount = 0;
                    let listaPreciosItems = [];
                    p.items.forEach(pid => {{
                        if (catalogData[pid]) {{
                            let itemObj = catalogData[pid];
                            itemsNombres.push(itemObj.nombre);
                            listaPreciosItems.push({{ cat: itemObj.categoria, precio: itemObj.precio }});
                            if (itemObj.categoria === 'MENU') {{
                                platosFondoCount++;
                            }}
                        }}
                    }});
                    let subtotalPersona = 0.0;
                    let entradasGratisDisponibles = platosFondoCount;
                    listaPreciosItems.forEach(it => {{
                        let pItem = it.precio;
                        if (it.cat === 'ENTRADAS') {{
                            if (entradasGratisDisponibles > 0) {{
                                pItem = 0.0;
                                entradasGratisDisponibles--;
                            }}
                        }}
                        subtotalPersona += pItem;
                    }});
                    if (p.para_llevar) {{
                        let countMenuLlevar = listaPreciosItems.filter(it => it.cat === 'MENU').length;
                        let countEntradaLlevar = listaPreciosItems.filter(it => it.cat === 'ENTRADAS').length;
                        subtotalPersona += (countMenuLlevar * taperMenuVal) + (countEntradaLlevar * taperEntradaVal);
                    }}
                    totalGeneral += subtotalPersona;
                    let listaStr = itemsNombres.length > 0 ? itemsNombres.join(", ") : "Sin plato";
                    if (p.para_llevar) {{
                        listaStr += " 🛍️ [Para Llevar]";
                    }}
                    html += `<div class="persona-bloque-resumen">`;
                    html += `<div class="persona-titulo-resumen"><span>👤 ${{p.nombre}}: ${{listaStr}}</span><span style="color:#008833; font-weight:900;">S/ ${{subtotalPersona.toFixed(2)}}</span></div>`;
                    if (p.nota.trim() !== "") {{
                        html += `<div class="persona-nota-resumen">📌 Nota: ${{p.nota}}</div>`;
                    }}
                    html += `</div>`;
                }}
            }});
            if (!hayItems) {{
                html = `<p style="color:#888; font-style:italic; margin:0;">No se han seleccionado productos aún.</p>`;
            }} else {{
                html += `<div class="resumen-total-general">TOTAL PEDIDO: S/ ${{totalGeneral.toFixed(2)}}</div>`;
            }}
            cont.innerHTML = html;
        }}
        function openCategory(evt, catName) {{
            let views = document.getElementsByClassName("category-view");
            for (let i = 0; i < views.length; i++) {{
                views[i].classList.remove("active");
            }}
            let btns = document.getElementsByClassName("tab-btn");
            for (let i = 0; i < btns.length; i++) {{
                btns[i].classList.remove("active");
            }}
            document.getElementById(catName).classList.add("active");
            evt.currentTarget.classList.add("active");
        }}
        function toggleVirtualKeyboard() {{
            const kb = document.getElementById('virtualKeyboard');
            kb.style.display = (kb.style.display === 'block') ? 'none' : 'block';
        }}
        function vkPress(char) {{
            const txt = document.getElementById('txtNotaPersona');
            txt.value += char;
            actualizarNotaActual(txt.value);
            txt.focus();
        }}
        function vkBackspace() {{
            const txt = document.getElementById('txtNotaPersona');
            txt.value = txt.value.slice(0, -1);
            actualizarNotaActual(txt.value);
            txt.focus();
        }}
        function prepararEnvio(e) {{
            const personasValidas = personas.filter(p => p.items.length > 0);
            if (personasValidas.length === 0) {{
                alert("Por favor seleccione al menos un producto para enviar la comanda.");
                e.preventDefault();
                return false;
            }}
            document.getElementById('datos_personas_json').value = JSON.stringify(personasValidas);
            return true;
        }}
        renderBarraPersonas();
        renderResumenGlobal();
    </script>
</body>
</html>
"""

HTML_CIERRE_CAJA = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>Cierre de Caja - Mr. Cuy</title>
    <style>
        body {{ font-family: 'Courier New', Courier, monospace; width: 340px; margin: 0 auto; background: white; padding: 10px; color: #000; font-size: 16px; }}
        h2, h3, p {{ text-align: center; margin: 6px 0; font-size: 17px; }}
        .linea {{ border-bottom: 2px dashed #000; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 15px; }}
        th, td {{ padding: 6px 0; text-align: left; }}
        th {{ border-bottom: 2px solid #000; }}
        .total {{ font-size: 18px; font-weight: bold; text-align: right; margin-top: 12px; }}
        .no-print {{ text-align: center; margin-top: 28px; }}
        .btn-print {{ padding: 15px 22px; font-size: 18px; background: #000; color: #fff; cursor: pointer; text-decoration: none; border: none; border-radius: 8px; font-weight: bold; }}
    </style>
</head>
<body onload="setTimeout(function(){{ window.print(); }}, 500);">
    <h2>REPLACE_EMPRESA_NOMBRE</h2>
    <p>RUC: REPLACE_EMPRESA_RUC</p>
    <p>REPORTE DE CIERRE DE CAJA</p>
    <p>Cajero(a): REPLACE_CAJERO</p>
    <p>Fecha: REPLACE_FECHA</p>
    <div class="linea"></div>
    <p style="text-align:left;"><b>RESUMEN POR CATEGORÍAS:</b></p>
    REPLACE_BLOQUES_CATEGORIAS
    <div class="linea"></div>
    <p style="text-align:left;"><b>DETALLE DE PRODUCTOS:</b></p>
    <table>
        <tr>
            <th>Cant. / Prod.</th>
            <th style="text-align:right;">Subtotal</th>
        </tr>
        REPLACE_FILAS_CONTEO
    </table>
    <div class="linea"></div>
    <p style="text-align:left;">Total Cuentas: <b>REPLACE_CANTIDAD_PEDIDOS</b></p>
    <div class="total">
        TOTAL CAJA: S/ REPLACE_TOTAL_GENERAL
    </div>
    <div class="linea"></div>
    <p>¡Turno Finalizado!</p>
    <p style="color: green; font-size: 14px;">📂 Archivo Excel ('resumen de ventas.csv') generado en la carpeta del día.</p>
    <div class="no-print">
        <button class="btn-print" onclick="window.print();">🖨️ IMPRIMIR TICKET DE CIERRE</button><br><br>
        <a href="/menu_principal" style="color: blue; font-size: 16px; font-weight:bold;">⬅️ Volver al Menú Principal</a><br><br>
        <a href="/reiniciar_caja" style="color: red; font-size: 16px; font-weight: bold;" onclick="return confirm('¿Reiniciar caja y borrar pedidos?');">🧹 Reiniciar Caja</a>
    </div>
</body>
</html>
"""

HTML_CAMBIAR_MESA = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cambiar Mesa - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        body {{ background: linear-gradient(135deg, #fffdf0 0%, #fff5cc 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; padding: 25px; }}
        .card {{ background: #ffffff; padding: 45px; border-radius: 25px; box-shadow: 0 15px 40px rgba(0,0,0,0.15); width: 100%; max-width: 550px; border: 5px solid #3498db; text-align: center; color: #2c3e50; }}
        h2 {{ color: #3498db; margin-top: 0; font-weight: 900; font-size: 32px; }}
        label {{ font-weight: 900; display: block; margin-bottom: 12px; text-align: left; color: #2c3e50; font-size: 20px; }}
        select {{ width: 100%; padding: 18px; font-size: 20px; margin-bottom: 28px; border: 3px solid #ccc; border-radius: 12px; font-weight: bold; }}
        .btn-guardar {{ background: #3498db; color: white; width: 100%; padding: 20px; border: none; border-radius: 12px; font-size: 22px; font-weight: 900; cursor: pointer; transition: all 0.2s; box-shadow: 0 5px 15px rgba(52, 152, 219, 0.35); }}
        .btn-guardar:hover {{ transform: translateY(-2px); background: #2980b9; }}
        .btn-cancelar {{ display: inline-block; margin-top: 22px; color: #555; text-decoration: none; font-size: 20px; font-weight: 900; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🔄 Cambiar Mesa</h2>
        <p style="margin-bottom:25px; font-size:22px;">Pedido actual en: <b style="color:#d35400;">REPLACE_MESA_ACTUAL</b></p>
        <form action="/procesar_cambio_mesa" method="POST">
            <input type="hidden" name="id_pedido" value="REPLACE_ID">
            <label>Seleccione la nueva mesa:</label>
            <select name="nueva_mesa">
                REPLACE_OPCIONES_NUEVA_MESA
            </select>
            <button type="submit" class="btn-guardar">💾 Guardar Nuevo Destino</button>
        </form>
        <a href="/seleccion_piso" class="btn-cancelar">Cancelar</a>
    </div>
</body>
</html>
"""

HTML_ADMIN = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Administración - Mr. Cuy</title>
    {CSS_GLOBAL}
    <style>
        .main-container {{ max-width: 1300px; margin: 30px auto; padding: 0 20px; }}
        .form-box {{ background: white; padding: 30px; border-radius: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); margin-bottom: 35px; border-top: 8px solid #f1c40f; border: 3px solid #e8ecef; }}
        .form-box h2 {{ margin-top: 0; color: #2c3e50; font-size: 26px; font-weight: 900; }}
        input, select {{ width: 100%; padding: 16px 18px; font-size: 18px; margin-top: 8px; margin-bottom: 22px; border: 3px solid #ccc; border-radius: 10px; box-sizing: border-box; font-weight: bold; }}
        button {{ background: #00FF66; color: #004d1a; padding: 18px; font-size: 20px; border: 3px solid #00cc52; border-radius: 10px; cursor: pointer; font-weight: 900; width: 100%; transition: all 0.2s; box-shadow: 0 5px 15px rgba(0, 255, 102, 0.35); }}
        button:hover {{ transform: translateY(-2px); background: #33ff85; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; font-size: 18px; }}
        th, td {{ border: 2px solid #e8ecef; padding: 15px 18px; text-align: left; }}
        th {{ background-color: #2c3e50; color: white; font-weight: 900; text-transform: uppercase; font-size: 15px; }}
        .btn-eliminar {{ background: #e74c3c; padding: 10px 18px; color:white; text-decoration:none; border-radius: 8px; display: inline-block; font-size: 16px; font-weight: 900; }}
        .btn-guardar-sm {{ background: #00FF66; color: #004d1a; padding: 10px 18px; border: 2px solid #00cc52; border-radius: 8px; font-size: 16px; font-weight: 900; cursor: pointer; width: auto; }}
        .flex-row {{ display: flex; gap: 25px; flex-wrap: wrap; }}
        .flex-row > div {{ flex: 1; min-width: 250px; }}
        .btn-info-corner {{ background: #3498db; color: white; border: 3px solid #2980b9; padding: 12px 20px; border-radius: 10px; font-weight: 900; font-size: 18px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: all 0.2s; }}
        .btn-info-corner:hover {{ background: #2980b9; transform: translateY(-2px); }}
        .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; justify-content: center; align-items: center; }}
        .modal-content {{ background: white; padding: 40px; border-radius: 20px; max-width: 550px; width: 90%; border: 5px solid #3498db; box-shadow: 0 15px 35px rgba(0,0,0,0.2); text-align: center; }}
        .modal-content h3 {{ margin-top: 0; color: #2c3e50; font-size: 28px; font-weight: 900; }}
        .info-item {{ background: #fffdf0; border: 3px solid #f1c40f; border-radius: 12px; padding: 15px; margin: 15px 0; text-align: left; font-size: 18px; color: #2c3e50; font-weight: 700; }}
        .btn-cerrar-modal {{ background: #e74c3c; color: white; border: none; padding: 14px 25px; border-radius: 10px; font-size: 18px; font-weight: 900; cursor: pointer; margin-top: 20px; }}
    </style>
</head>
<body>
    <header>
        <div class="header-brand">
            <img src="/logo.png" alt="Logo" class="header-logo" onerror="this.style.display='none';">
            <h1>Panel de Administración - Mr. Cuy</h1>
        </div>
        <div style="display: flex; gap: 15px; align-items: center;">
            <button type="button" class="btn-info-corner" onclick="abrirInfoModal()">ℹ️ Info</button>
            <a href="/menu_principal" class="nav-btn nav-home">🏠 Menú Principal</a>
        </div>
    </header>
    <div class="main-container">
        <div class="form-box" style="border-top-color: #3498db;">
            <h2>🏛️ Configuración de Datos del Negocio & RUC</h2>
            <form action="/actualizar_empresa" method="POST">
                <div class="flex-row">
                    <div>
                        <label>Razón Social / Nombre Comercial:</label>
                        <input type="text" name="empresa_nombre" value="REPLACE_EMPRESA_NOMBRE" required>
                    </div>
                    <div>
                        <label>Número de RUC:</label>
                        <input type="text" name="empresa_ruc" value="REPLACE_EMPRESA_RUC" required maxlength="11">
                    </div>
                </div>
                <div class="flex-row">
                    <div>
                        <label>Dirección del Establecimiento:</label>
                        <input type="text" name="empresa_direccion" value="REPLACE_EMPRESA_DIRECCION">
                    </div>
                    <div>
                        <label>Teléfono / WhatsApp de Contacto:</label>
                        <input type="text" name="empresa_telefono" value="REPLACE_EMPRESA_TELEFONO">
                    </div>
                </div>
                <button type="submit" style="background: #3498db; color: white; border-color: #2980b9;">💾 Guardar Datos del Negocio</button>
            </form>
        </div>
        <div class="form-box" style="border-top-color: #f1c40f;">
            <h2>⚡ Configuración de Notas Rápidas para Pedidos</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Texto de la Nota</th>
                    <th>Acción</th>
                </tr>
                REPLACE_TABLA_NOTAS_RAPIDAS
            </table>
            <h3 style="font-size:20px; color:#2c3e50; font-weight:900;">Añadir Nueva Nota Rápida</h3>
            <form action="/agregar_nota_rapida" method="POST" style="display:flex; gap:15px; align-items:center;">
                <input type="text" name="texto_nota" required placeholder="Ej: Sin sal, Poco picante, Bien cocido..." style="margin:0;">
                <button type="submit" style="width:260px; margin:0;">➕ Agregar Nota</button>
            </form>
        </div>
        <div class="form-box" style="border-top-color: #00FF66;">
            <h2>🖨️ Configuración de Ticketeras (Cocina y Caja)</h2>
            <form action="/actualizar_impresoras" method="POST">
                <h4 style="margin: 5px 0 15px 0; color:#008833; font-weight:900; font-size:20px;">1. Ticketera de Pedidos / Cocina (Conexión Ethernet - Red):</h4>
                <div class="flex-row">
                    <div>
                        <label>Dirección IP de la Impresora de Cocina:</label>
                        <input type="text" name="impresora_cocina_ip" value="REPLACE_COCINA_IP" placeholder="Ej: 192.168.1.100">
                    </div>
                    <div>
                        <label>Puerto Socket (Por defecto 9100):</label>
                        <input type="text" name="impresora_cocina_puerto" value="REPLACE_COCINA_PUERTO" placeholder="9100">
                    </div>
                </div>
                <h4 style="margin: 20px 0 15px 0; color:#008833; font-weight:900; font-size:20px;">2. Ticketera de Caja / Comprobantes (Detectadas automáticamente en Windows):</h4>
                <div>
                    <label>Seleccionar Impresora USB / Sistema detectada:</label>
                    <select name="impresora_caja_nombre">
                        REPLACE_OPCIONES_IMPRESORAS_CAJA
                    </select>
                </div>
                <div style="margin-top:15px;">
                    <label>IP de la PC Principal / Caja (Para restringir cobros y cierre):</label>
                    <input type="text" name="pc_caja_ip" value="REPLACE_PC_CAJA_IP" placeholder="Ej: 192.168.1.100 o 127.0.0.1">
                </div>
                <button type="submit">💾 Guardar Configuración de Impresoras</button>
            </form>
        </div>
        <div class="form-box" style="border-top-color: #f1c40f;">
            <h2>🛍️ Configuración de Precios de Táperes (Para Llevar)</h2>
            <form action="/actualizar_taper" method="POST">
                <div class="flex-row">
                    <div>
                        <label>Precio Táper Menú / Fondo (S/):</label>
                        <input type="number" step="0.05" name="taper_menu" value="REPLACE_PRECIO_TAPER_MENU" required>
                    </div>
                    <div>
                        <label>Precio Táper Entrada (S/):</label>
                        <input type="number" step="0.05" name="taper_entrada" value="REPLACE_PRECIO_TAPER_ENTRADA" required>
                    </div>
                </div>
                <button type="submit">💾 Actualizar Precios de Táperes</button>
            </form>
        </div>
        <div class="form-box" style="border-top-color: #3498db;">
            <h2>📂 Gestión de Categorías del Menú</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nombre de la Categoría</th>
                    <th>Acción</th>
                </tr>
                REPLACE_TABLA_CATEGORIAS
            </table>
            <h3 style="font-size:20px; color:#2c3e50; font-weight:900;">Añadir Nueva Categoría</h3>
            <form action="/agregar_categoria" method="POST" style="display:flex; gap:15px; align-items:center;">
                <input type="text" name="nombre_categoria" required placeholder="Ej: CRIOLLOS, REGIONALES, MR. CUY, SOPAS..." style="margin:0; text-transform:uppercase;">
                <button type="submit" style="width:260px; margin:0; background: #3498db; color:white; border-color:#2980b9;">➕ Añadir Categoría</button>
            </form>
        </div>
        <div class="form-box">
            <h2>🏢 Configuración de Pisos y Cantidad de Mesas</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Nombre del Piso</th>
                    <th>Cantidad de Mesas</th>
                    <th>Acciones</th>
                </tr>
                REPLACE_TABLA_PISOS
            </table>
            <h3 style="font-size:20px; color:#2c3e50; font-weight:900;">Agregar Nuevo Piso</h3>
            <form action="/agregar_piso" method="POST" style="display:flex; gap:15px; align-items:center;">
                <input type="text" name="nombre_piso" required placeholder="Nombre (Ej: Piso 3 o Terraza)" style="margin:0;">
                <input type="number" name="cant_mesas" required placeholder="Cant. Mesas" min="1" max="50" style="margin:0; width:180px;">
                <button type="submit" style="width:240px; margin:0;">➕ Agregar Piso</button>
            </form>
        </div>
        <div class="form-box">
            <h2>👤 Registrar Cajero</h2>
            <form action="/agregar_cajero" method="POST">
                <label>Nombre del Cajero:</label>
                <input type="text" name="nombre_cajero" required placeholder="Ej: Carlos Pérez">
                <button type="submit">➕ Guardar Cajero</button>
            </form>
        </div>
        <h2 style="color: #2c3e50; font-weight:900; font-size:26px;">Cajeros Registrados</h2>
        <table>
            <tr><th>ID</th><th>Nombre</th><th>Acción</th></tr>
            REPLACE_TABLA_CAJEROS
        </table>
        <div class="form-box">
            <h2>👤 Registrar Mesero</h2>
            <form action="/agregar_mesero" method="POST">
                <label>Nombre:</label>
                <input type="text" name="nombre_mesero" required placeholder="Ej: Juan Pérez">
                <button type="submit">➕ Guardar Mesero</button>
            </form>
        </div>
        <h2 style="color: #2c3e50; font-weight:900; font-size:26px;">Meseros Registrados</h2>
        <table>
            <tr><th>ID</th><th>Nombre</th><th>Acción</th></tr>
            REPLACE_TABLA_MESEROS
        </table>
        <div class="form-box">
            <h2>Agregar Producto</h2>
            <form action="/agregar_producto" method="POST">
                <label>Categoría:</label>
                <select name="categoria">
                    REPLACE_OPCIONES_CATEGORIAS_SELECT
                </select>
                <label>Nombre del Producto:</label>
                <input type="text" name="nombre" required placeholder="Ej: Seco de Res o Ceviche de Entrada">
                <label>Precio (S/):</label>
                <input type="number" step="0.05" name="precio" required placeholder="0.00">
                <button type="submit">➕ Guardar en el Menú</button>
            </form>
        </div>
        <h2 style="color: #2c3e50; font-weight:900; margin-top: 40px; font-size:26px;">Menú Actual</h2>
        <table>
            <tr><th>ID</th><th>Categoría</th><th>Nombre</th><th>Precio Sola / Menú</th><th>Acción</th></tr>
            REPLACE_TABLA_MENU
        </table>
    </div>

    <!-- MODAL DE INFORMACIÓN DEL SISTEMA -->
    <div id="infoModal" class="modal-overlay">
        <div class="modal-content">
            <h3>ℹ️ Información del Sistema</h3>
            <div class="info-item">
                <b>📦 Versión del Sistema:</b> vREPLACE_VERSION Pro
            </div>
            <div class="info-item">
                <b>🛡️ Tipo de Licencia:</b> REPLACE_TIPO_LICENCIA_STR
            </div>
            <div class="info-item">
                <b>⏳ Tiempo Restante:<br></b> <span id="lblTiempoRestante" style="color:#d35400; font-size:20px; font-weight:900;">REPLACE_TIEMPO_RESTANTE</span>
            </div>
            <div class="info-item" style="background:#e8f8f5; border-color:#00FF66; text-align:center;">
                <b>👨‍💻 Desarrollado por:</b> <span style="color:#008833; font-size:22px;">Juli</span>
            </div>
            <button type="button" class="btn-cerrar-modal" onclick="cerrarInfoModal()">Cerrar ✖</button>
        </div>
    </div>

    <script>
        function abrirInfoModal() {{
            document.getElementById('infoModal').style.display = 'flex';
        }}
        function cerrarInfoModal() {{
            document.getElementById('infoModal').style.display = 'none';
        }}

        // Temporizador en tiempo real para la licencia de prueba
        const datosLicencia = REPLACE_DATOS_LICENCIA_JSON;
        if (datosLicencia.activo !== "ilimitado") {{
            const fechaInstalacion = new Date(datosLicencia.fecha_instalacion.replace(/-/g, '/'));
            const fechaLimite = new Date(fechaInstalacion.getTime() + (7 * 24 * 60 * 60 * 1000));

            function actualizarContador() {{
                const ahora = new Date();
                const diferencia = fechaLimite - ahora;
                const lbl = document.getElementById('lblTiempoRestante');
                if (diferencia <= 0) {{
                    lbl.innerText = "¡Periodo de prueba expirado!";
                    return;
                }}
                const dias = Math.floor(diferencia / (1000 * 60 * 60 * 24));
                const horas = Math.floor((diferencia % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutos = Math.floor((diferencia % (1000 * 60 * 60)) / (1000 * 60));
                const segundos = Math.floor((diferencia % (1000 * 60)) / 1000);
                lbl.innerText = `${{dias}} días, ${{horas}} horas, ${{minutos}} minutos, ${{segundos}} segundos`;
            }}
            setInterval(actualizarContador, 1000);
            actualizarContador();
        }}
    </script>
</body>
</html>
"""

HTML_PRECUENTA = """
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>Comprobante - Mr. Cuy</title>
    <style>
        body { font-family: 'Courier New', Courier, monospace; width: 340px; margin: 0 auto; background: white; padding: 10px; color: #000; font-size: 15px; }
        h2, h3, p { text-align: center; margin: 6px 0; font-size: 16px; }
        .linea { border-bottom: 2px dashed #000; margin: 10px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
        th, td { padding: 6px 0; text-align: left; }
        .total { font-size: 18px; font-weight: bold; text-align: right; margin-top: 14px; }
        .no-print { text-align: center; margin-top: 28px; }
        .btn-print { padding: 15px 22px; font-size: 18px; background: #000; color: #fff; cursor: pointer; text-decoration: none; border: none; border-radius: 8px; font-weight: bold; }
    </style>
</head>
<body onload="setTimeout(function(){{ window.print(); }}, 500);">
    <h2>REPLACE_EMPRESA_NOMBRE</h2>
    <p>RUC: REPLACE_EMPRESA_RUC</p>
    <p>REPLACE_EMPRESA_DIRECCION</p>
    <p>Telf: REPLACE_EMPRESA_TELEFONO</p>
    <div class="linea"></div>
    <p><b>REPLACE_TIPO_COMPROBANTE</b></p>
    <p><b>Mesa:</b> REPLACE_Mesa | <b>Mesero:</b> REPLACE_MESERO</p>
    <p><b>Cajero:</b> REPLACE_CAJERO</p>
    <p><b>Fecha:</b> REPLACE_FECHA</p>
    REPLACE_DATOS_CLIENTE_HTML
    <div class="linea"></div>
    <table>
        <tr><th>Descripción</th><th style="text-align:right;">Subtotal</th></tr>
        REPLACE_ITEMS_TICKET
    </table>
    <div class="linea"></div>
    <div class="total">
        TOTAL A PAGAR: S/ REPLACE_TOTAL
    </div>
    <div class="linea"></div>
    <p>¡Gracias por su preferencia!</p>
    <div class="no-print">
        <button class="btn-print" onclick="window.print();">🖨️ REIMPRIMIR TICKET</button><br><br>
        <a href="/seleccion_piso" style="color: blue; font-size: 16px; font-weight:bold;">⬅️ Volver a Mesas</a>
    </div>
</body>
</html>
"""

class ServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        conn = sqlite3.connect("restaurante.db")
        cursor = conn.cursor()
        path_clean = self.path.split('?')[0]
        cookies = parsear_cookies(self.headers)
        cajero_actual = cookies.get('cajero_mr_cuy', '')
        
        if path_clean in ['/logo.png', '/logo.jpg', '/logo.jpeg']:
            for fname in ['logo.png', 'logo.jpg', 'logo.jpeg']:
                if os.path.exists(fname):
                    self.send_response(200)
                    if fname.endswith('.png'):
                        self.send_header("Content-type", "image/png")
                    else:
                        self.send_header("Content-type", "image/jpeg")
                    self.end_headers()
                    with open(fname, 'rb') as f:
                        self.wfile.write(f.read())
                    conn.close()
                    return
            self.send_response(404)
            self.end_headers()
            conn.close()
            return
        
        if path_clean == '/':
            cursor.execute("SELECT id, nombre FROM cajeros")
            cajeros = cursor.fetchall()
            opciones = ""
            for cid, cnom in cajeros:
                opciones += f'<option value="{cnom}">{cnom}</option>'
            if not opciones:
                opciones = '<option value="Cajero General">Cajero General</option>'
            pagina = HTML_LOGIN_CAJERO.replace("REPLACE_OPCIONES_CAJEROS", opciones)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))
            conn.close()
            return

        if path_clean in ['/menu_principal', '/index', '/welcome']:
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            btn_cierre = '<a href="/cierre_caja" class="btn-menu btn-cierre">🔒 CIERRE DE CAJA DEL DÍA</a>' if es_pc_principal(self.client_address) else '<a href="#" class="btn-menu btn-cierre" style="opacity:0.5; cursor:not-allowed;" onclick="alert(\'Acceso Restringido: Esta opción solo está disponible en la PC Principal de Caja\'); return false;">🔒 CIERRE DE CAJA (RESTRINGIDO)</a>'
            pagina = HTML_WELCOME.replace("{REPLACE_BOTON_CIERRE}", btn_cierre)
            pagina = pagina.replace("REPLACE_CAJERO", cajero_actual)
            self.wfile.write(pagina.encode("utf-8"))
            
        elif path_clean == '/seleccion_piso':
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            cursor.execute("SELECT id, nombre, cant_mesas FROM pisos ORDER BY id")
            pisos = cursor.fetchall()
            botones_pisos = ""
            for pid, pnom, cant in pisos:
                botones_pisos += f'<a href="/mapa_piso?piso={pid}" class="btn-piso">📍 {pnom} ({cant} Mesas)</a>'
            pagina = HTML_SELECCION_PISO.replace("REPLACE_BOTONES_PISOS", botones_pisos)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))
            
        elif path_clean == '/mapa_piso':
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            piso_id = params.get('piso', ['1'])[0]
            cursor.execute("SELECT nombre, cant_mesas FROM pisos WHERE id = ?", (piso_id,))
            piso_data = cursor.fetchone()
            if not piso_data:
                self.send_response(303)
                self.send_header('Location', '/seleccion_piso')
                self.end_headers()
                conn.close()
                return
            piso_nombre, cant_mesas = piso_data
            cursor.execute("SELECT id, mesa, mesero, detalle, total FROM pedidos WHERE estado = 'Pendiente' AND piso_id = ? ORDER BY id DESC", (piso_id,))
            pedidos = cursor.fetchall()
            mesas_ocupadas = {p[1]: p for p in pedidos}
            mesas_grid = ""
            for i in range(1, cant_mesas + 1):
                m_nombre = f"Mesa {i}"
                if m_nombre in mesas_ocupadas:
                    mesas_grid += f'<a href="/ver_mesa?mesa=Mesa+{i}&piso={piso_id}" class="mesa-btn ocupada">🍽️ Mesa {i} <span class="subtext">OCUPADA</span></a>'
                else:
                    mesas_grid += f'<a href="/click_mesa?mesa=Mesa+{i}&piso={piso_id}" class="mesa-btn">Mesa {i} <span class="subtext">Libre</span></a>'
            filas_pedidos = ""
            style_cobrar = '' if es_pc_principal(self.client_address) else 'display:none;'
            for pid, mesa, mesero, detalle, total in pedidos:
                acciones = f"""
                <a href='/pantalla_cobrar?id={pid}&piso={piso_id}' class='btn-action btn-cobrar' style='{style_cobrar}'>💳 Cobrar</a>
                <a href='/precuenta?id={pid}' class='btn-action btn-precuenta' target='_blank'>🖨️ Ticket</a>
                <a href='/cambiar_mesa?id={pid}' class='btn-action btn-cambiar'>🔄 Cambiar</a>
                <a href='/anular_pedido?id={pid}&piso={piso_id}' class='btn-action btn-anular' onclick="return confirm('¿Seguro?');">❌ Anular</a>
                """
                filas_pedidos += f"<tr><td>{pid}</td><td><b>{mesa}</b></td><td>{mesero}</td><td>{detalle}</td><td><b style='color:#008833;'>S/ {total:.2f}</b></td><td>{acciones}</td></tr>"
            if not filas_pedidos:
                filas_pedidos = "<tr><td colspan='6' style='text-align: center; color: #777;'>No hay mesas ocupadas actualmente en este piso.</td></tr>"
            pagina = HTML_MAPA_MESAS.replace("REPLACE_TITULO_PISO", f"Mr. Cuy - {piso_nombre}")
            pagina = pagina.replace("REPLACE_SUBTITULO_MESAS", f"📍 Mesas en {piso_nombre}")
            pagina = pagina.replace("REPLACE_MESAS_GRID", mesas_grid)
            pagina = pagina.replace("REPLACE_TABLA_PEDIDOS", filas_pedidos)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))

        elif path_clean == '/click_mesa':
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            mesa_raw = params.get('mesa', ['Mesa 1'])[0]
            mesa = mesa_raw.replace('+', ' ')
            piso_id = params.get('piso', ['1'])[0]
            cursor.execute("SELECT id FROM pedidos WHERE mesa = ? AND piso_id = ? AND estado = 'Pendiente'", (mesa, piso_id))
            res = cursor.fetchone()
            if res:
                self.send_response(303)
                self.send_header('Location', f'/ver_mesa?mesa={urllib.parse.quote(mesa)}&piso={piso_id}')
                self.end_headers()
            else:
                self.send_response(303)
                self.send_header('Location', f'/seleccionar_mesero?mesa={urllib.parse.quote(mesa)}&piso={piso_id}')
                self.end_headers()

        elif path_clean == '/ver_mesa':
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            mesa_raw = params.get('mesa', ['Mesa 1'])[0]
            mesa = mesa_raw.replace('+', ' ')
            piso_id = params.get('piso', ['1'])[0]
            cursor.execute("SELECT id, mesero, detalle, total FROM pedidos WHERE mesa = ? AND piso_id = ? AND estado = 'Pendiente'", (mesa, piso_id))
            res = cursor.fetchone()
            if res:
                pid, mesero, detalle, total = res
                style_cobrar = '' if es_pc_principal(self.client_address) else 'display:none;'
                pagina = HTML_MESA_ATENDIDA.replace("REPLACE_MESA", mesa)
                pagina = pagina.replace("REPLACE_STYLE_COBRAR", style_cobrar)
                pagina = pagina.replace("REPLACE_MESERO", mesero)
                pagina = pagina.replace("REPLACE_DETALLE", detalle)
                pagina = pagina.replace("REPLACE_TOTAL", f"{total:.2f}")
                pagina = pagina.replace("REPLACE_ID", str(pid))
                pagina = pagina.replace("REPLACE_PISO", piso_id)
                pagina = pagina.replace("REPLACE_MESA_ENC", urllib.parse.quote(mesa))
                pagina = pagina.replace("REPLACE_MESERO_ENC", urllib.parse.quote(mesero))
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(pagina.encode("utf-8"))
            else:
                self.send_response(303)
                self.send_header('Location', f'/mapa_piso?piso={piso_id}')
                self.end_headers()

        elif path_clean == '/pantalla_cobrar':
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            piso_id = params.get('piso', ['1'])[0]
            if not es_pc_principal(self.client_address):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                msg = f"<!DOCTYPE html><html><head>{CSS_GLOBAL}</head><body style='background:#fffdf0; display:flex; justify-content:center; align-items:center; min-height:100vh; color:#2c3e50; text-align:center; padding:25px;'><div class='card' style='background:#ffffff; padding:45px; border-radius:20px; border:5px solid #e74c3c; max-width:550px;'><h2 style='color:#e74c3c; font-size:32px;'>⚠️ Acceso Restringido</h2><p style='font-size:20px;'>Esta opción solo está disponible en la PC Principal de Caja.</p><br><a href='/mapa_piso?piso={piso_id}' class='nav-btn nav-home' style='display:inline-block;'>⬅️ Volver al Mapa</a></div></body></html>"
                self.wfile.write(msg.encode("utf-8"))
                conn.close()
                return
            if 'id' in params:
                pid = params['id'][0]
                cursor.execute("SELECT mesa, mesero, detalle, total FROM pedidos WHERE id = ?", (pid,))
                res = cursor.fetchone()
                if res:
                    mesa, mesero, detalle, total = res
                    filas_consumo = f"<tr><td>{detalle}</td><td style='text-align:right;'>✔</td></tr>"
                    pagina = HTML_PANTALLA_COBRAR.replace("REPLACE_MESA", mesa)
                    pagina = pagina.replace("REPLACE_MESERO", mesero)
                    pagina = pagina.replace("REPLACE_FILAS_CONSUMO", filas_consumo)
                    pagina = pagina.replace("REPLACE_TOTAL", f"{total:.2f}")
                    pagina = pagina.replace("REPLACE_ID", str(pid))
                    pagina = pagina.replace("REPLACE_PISO", piso_id)
                    pagina = pagina.replace("REPLACE_MESA_ENC", urllib.parse.quote(mesa))
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(pagina.encode("utf-8"))
                    conn.close()
                    return
            self.send_response(303)
            self.send_header('Location', f'/mapa_piso?piso={piso_id}')
            self.end_headers()

        elif path_clean == '/historial_ventas':
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            hoy_str = datetime.date.today().strftime("%Y-%m-%d")
            fecha_sel = params.get('fecha', [hoy_str])[0]
            cursor.execute("SELECT id, mesa, mesero, cajero, detalle, total, tipo_comprobante, doc_cliente, razon_social FROM pedidos WHERE estado = 'Cobrado' AND fecha = ? ORDER BY id DESC", (fecha_sel,))
            ventas_dia = cursor.fetchall()
            total_dia = sum(v[5] for v in ventas_dia)
            cant_cuentas = len(ventas_dia)
            filas_historial = ""
            for vid, mesa, mesero, cajero, detalle, total, tipo_comp, doc, razon in ventas_dia:
                comp_str = tipo_comp if tipo_comp else "TICKET"
                if comp_str == "FACTURA" and doc:
                    comp_str += f"<br><small>{doc} - {razon}</small>"
                cajero_str = cajero if cajero else "N/D"
                filas_historial += f"<tr><td>{vid}</td><td><b>{mesa}</b></td><td>Mesero: <b>{mesero}</b><br>Cajero: <span style='color:#3498db; font-weight:bold;'>{cajero_str}</span></td><td><b>{comp_str}</b></td><td>{detalle}</td><td><b style='color:#008833;'>S/ {total:.2f}</b></td></tr>"
            if not filas_historial:
                filas_historial = "<tr><td colspan='6' style='text-align:center; color:#888;'>No hay ventas cobradas registradas en esta fecha.</td></tr>"
            pagina = HTML_HISTORIAL.replace("REPLACE_FECHA_VAL", fecha_sel)
            pagina = pagina.replace("REPLACE_FECHA_FMT", fecha_sel)
            pagina = pagina.replace("REPLACE_TOTAL_DIA", f"{total_dia:.2f}")
            pagina = pagina.replace("REPLACE_CANTIDAD_CUENTAS", str(cant_cuentas))
            pagina = pagina.replace("REPLACE_FILAS_HISTORIAL", filas_historial)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))

        elif path_clean == '/reiniciar_historial':
            cursor.execute("DELETE FROM pedidos WHERE estado = 'Cobrado'")
            conn.commit()
            self.send_response(303)
            self.send_header('Location', '/historial_ventas')
            self.end_headers()

        elif path_clean == '/historial_semana':
            hoy = datetime.date.today()
            fechas = [(hoy - datetime.timedelta(days=i)) for i in range(6, -1, -1)]
            total_semana = 0.0
            filas_semana = ""
            for f in fechas:
                f_str = f.strftime("%Y-%m-%d")
                f_fmt = f.strftime("%d/%m/%Y (%A)")
                cursor.execute("SELECT SUM(total) FROM pedidos WHERE estado = 'Cobrado' AND fecha = ?", (f_str,))
                res = cursor.fetchone()[0]
                monto_dia = res if res else 0.0
                total_semana += monto_dia
                filas_semana += f"<tr><td><b>{f_fmt}</b></td><td style='text-align:right;'><b style='color:#008833;'>S/ {monto_dia:.2f}</b></td></tr>"
            pagina = HTML_SEMANA.replace("REPLACE_TOTAL_SEMANA", f"{total_semana:.2f}")
            pagina = pagina.replace("REPLACE_FILAS_SEMANA", filas_semana)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))

        elif path_clean == '/seleccionar_mesero':
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            mesa_raw = params.get('mesa', ['Mesa 1'])[0]
            mesa = mesa_raw.replace('+', ' ')
            piso_id = params.get('piso', ['1'])[0]
            cursor.execute("SELECT id, nombre FROM meseros")
            meseros = cursor.fetchall()
            cuadros_meseros = ""
            for mid, mnom in meseros:
                cuadros_meseros += f"""
                <a href="/ordenar?mesa={urllib.parse.quote(mesa)}&mesero={urllib.parse.quote(mnom)}&piso={piso_id}" class="mesero-card">
                    👤 {mnom}
                </a>
                """
            if not cuadros_meseros:
                cuadros_meseros = f"""
                <a href="/ordenar?mesa={urllib.parse.quote(mesa)}&mesero=General&piso={piso_id}" class="mesero-card">
                    👤 General
                </a>
                """
            pagina = HTML_SELECCION_MESERO.replace("REPLACE_MESA", mesa)
            pagina = pagina.replace("REPLACE_CUADROS_MESEROS", cuadros_meseros)
            pagina = pagina.replace("REPLACE_CANCELAR_LINK", f"/mapa_piso?piso={piso_id}")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))

        elif path_clean == '/ordenar':
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            mesa_raw = params.get('mesa', ['Mesa 1'])[0]
            mesa = mesa_raw.replace('+', ' ')
            mesero_raw = params.get('mesero', ['General'])[0]
            mesero = mesero_raw.replace('+', ' ')
            piso_id = params.get('piso', ['1'])[0]
            
            cursor.execute("SELECT id, categoria, nombre, precio FROM productos")
            productos = cursor.fetchall()
            catalogo_dict = {}
            items_by_cat = {}
            for pid, cat, nom, prec in productos:
                catalogo_dict[pid] = {"nombre": nom, "precio": prec, "categoria": cat}
                items_by_cat.setdefault(cat, []).append((pid, nom, prec))

            cursor.execute("SELECT nombre FROM categorias ORDER BY id")
            categorias_db = [r[0] for r in cursor.fetchall()]
            if not categorias_db:
                categorias_db = list(items_by_cat.keys())

            cursor.execute("SELECT texto FROM notas_rapidas ORDER BY id")
            notas_rapidas_db = [r[0] for r in cursor.fetchall()]
            botones_notas_rapidas_html = ""
            for ntxt in notas_rapidas_db:
                botones_notas_rapidas_html += f'<button type="button" class="btn-chip-nota" onclick="agregarNotaRapida(\'{ntxt}\')">{ntxt}</button>'
            if not botones_notas_rapidas_html:
                botones_notas_rapidas_html = "<span style='font-size:15px; color:#888;'>No hay notas rápidas configuradas.</span>"

            tabs_cat_html = ""
            category_views_html = ""
            primer_tab = True
            for cat in categorias_db:
                active_tab_cls = " active" if primer_tab else ""
                tabs_cat_html += f'<button class="tab-btn{active_tab_cls}" onclick="openCategory(event, \'CAT_{cat}\')">🍽️ {cat}</button>'
                active_view_cls = " active" if primer_tab else ""
                items_cat = items_by_cat.get(cat, [])
                cards_html = generar_html_cards_interactivas(items_cat)
                category_views_html += f"""
                <div id="CAT_{cat}" class="category-view{active_view_cls}">
                    <div class="section-box">
                        <div class="section-title">📂 {cat}</div>
                        <div class="items-grid">
                            {cards_html}
                        </div>
                    </div>
                </div>
                """
                primer_tab = False
                
            cursor.execute("SELECT detalle FROM pedidos WHERE mesa = ? AND piso_id = ? AND estado = 'Pendiente'", (mesa, piso_id))
            res_existente = cursor.fetchone()
            if res_existente:
                pedidos_actuales_str = res_existente[0]
            else:
                pedidos_actuales_str = "<i style='color:#888;'>Mesa vacía / Sin consumos previos</i>"
            cfg = obtener_configuracion()
            taper_m = float(cfg.get('taper_menu', '1.00'))
            taper_e = float(cfg.get('taper_entrada', '0.50'))
            pagina = HTML_ORDEN.replace("REPLACE_MESA", mesa)
            pagina = pagina.replace("REPLACE_MESERO", mesero)
            pagina = pagina.replace("REPLACE_ORIGEN", piso_id)
            pagina = pagina.replace("REPLACE_VOLVER", f"/mapa_piso?piso={piso_id}")
            pagina = pagina.replace("REPLACE_PEDIDOS_ACTUALES", pedidos_actuales_str)
            pagina = pagina.replace("REPLACE_CATALOGO_JSON", json.dumps(catalogo_dict))
            pagina = pagina.replace("REPLACE_TAPER_MENU_NUM", f"{taper_m}")
            pagina = pagina.replace("REPLACE_TAPER_ENTRADA_NUM", f"{taper_e}")
            pagina = pagina.replace("REPLACE_TAPER_MENU", f"{taper_m:.2f}")
            pagina = pagina.replace("REPLACE_TAPER_ENTRADA", f"{taper_e:.2f}")
            pagina = pagina.replace("REPLACE_TABS_CAT", tabs_cat_html)
            pagina = pagina.replace("REPLACE_CATEGORY_VIEWS", category_views_html)
            pagina = pagina.replace("REPLACE_BOTONES_NOTAS_RAPIDAS", botones_notas_rapidas_html)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))

        elif path_clean == '/cierre_caja':
            if not cajero_actual:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                conn.close()
                return
            if not es_pc_principal(self.client_address):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                msg = f"<!DOCTYPE html><html><head>{CSS_GLOBAL}</head><body style='background:#fffdf0; display:flex; justify-content:center; align-items:center; min-height:100vh; color:#2c3e50; text-align:center; padding:25px;'><div class='card' style='background:#ffffff; padding:45px; border-radius:20px; border:5px solid #e74c3c; max-width:550px;'><h2 style='color:#e74c3c; font-size:32px;'>⚠️ Acceso Restringido</h2><p style='font-size:20px;'>Esta opción solo está disponible en la PC Principal de Caja.</p><br><a href='/menu_principal' class='nav-btn nav-home' style='display:inline-block;'>⬅️ Volver al Menú Principal</a></div></body></html>"
                self.wfile.write(msg.encode("utf-8"))
                conn.close()
                return
            
            generar_excel_cierre(cajero_actual)
            cursor.execute("SELECT detalle, total FROM pedidos")
            pedidos = cursor.fetchall()
            cursor.execute("SELECT nombre, categoria, precio FROM productos")
            prod_info = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            total_recaudado = sum(p[1] for p in pedidos)
            cantidad_pedidos = len(pedidos)
            conteo_productos = {}
            totales_categoria = {}
            for p in pedidos:
                texto_pedido = p[0]
                partes = texto_pedido.split(", ")
                for parte in partes:
                    item_limpio = parte.split(" (Nota:")[0].replace(" [PARA LLEVAR]", "").replace(" [Incluida]", "").split(" [Táper")[0]
                    if ": " in item_limpio:
                        item_limpio = item_limpio.split(": ", 1)[-1]
                    item_limpio = item_limpio.strip()
                    if item_limpio:
                        conteo_productos[item_limpio] = conteo_productos.get(item_limpio, 0) + 1
                        if item_limpio in prod_info:
                            cat, prec = prod_info[item_limpio]
                            totales_categoria[cat] = totales_categoria.get(cat, 0.0) + prec
            
            bloques_cat = ""
            for cat, monto in totales_categoria.items():
                bloques_cat += f"<p>{cat}: <b>S/ {monto:.2f}</b></p>"
            if not bloques_cat:
                bloques_cat = "<p>No hay ventas por categorías.</p>"
            filas_conteo = ""
            for prod, cant in conteo_productos.items():
                precio_unit = prod_info[prod][1] if prod in prod_info else 0.0
                subtotal = cant * precio_unit
                filas_conteo += f"<tr><td>{cant}x {prod}</td><td style='text-align:right;'>S/ {subtotal:.2f}</td></tr>"
            if not filas_conteo:
                filas_conteo = "<tr><td colspan='2' style='text-align:center;'>No hay productos registrados.</td></tr>"
                
            cfg = obtener_configuracion()
            fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
            texto_cierre_ticket = f"{cfg.get('empresa_nombre', 'MR. CUY')}\nRUC: {cfg.get('empresa_ruc','')}\nREPORTE DE CIERRE\nCajero: {cajero_actual}\nFecha: {fecha_hoy}\n--------------------------------\nTOTAL CAJA: S/ {total_recaudado:.2f}\n--------------------------------\n"
            imprimir_silencioso_caja(texto_cierre_ticket)

            pagina = HTML_CIERRE_CAJA.replace("REPLACE_EMPRESA_NOMBRE", str(cfg.get('empresa_nombre', 'MR. CUY RESTAURANTE')))
            pagina = pagina.replace("REPLACE_EMPRESA_RUC", str(cfg.get('empresa_ruc', '20123456789')))
            pagina = pagina.replace("REPLACE_FECHA", str(fecha_hoy))
            pagina = pagina.replace("REPLACE_CAJERO", str(cajero_actual))
            pagina = pagina.replace("REPLACE_TOTAL_GENERAL", f"{total_recaudado:.2f}")
            pagina = pagina.replace("REPLACE_CANTIDAD_PEDIDOS", str(cantidad_pedidos))
            pagina = pagina.replace("REPLACE_BLOQUES_CATEGORIAS", bloques_cat)
            pagina = pagina.replace("REPLACE_FILAS_CONTEO", filas_conteo)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(pagina.encode("utf-8"))
            
        elif path_clean == '/reiniciar_caja':
            cursor.execute("DELETE FROM pedidos")
            conn.commit()
            self.send_response(303)
            self.send_header('Location', '/menu_principal')
            self.end_headers()

        elif path_clean == '/cambiar_mesa':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                pedido_id = params['id'][0]
                cursor.execute("SELECT mesa, piso_id FROM pedidos WHERE id = ?", (pedido_id,))
                res = cursor.fetchone()
                if res:
                    mesa_actual, piso_act = res
                    cursor.execute("SELECT id, nombre, cant_mesas FROM pisos")
                    pisos = cursor.fetchall()
                    opciones_mesas = ""
                    for pid, pnom, cant in pisos:
                        opciones_mesas += f"<optgroup label='{pnom}'>"
                        for i in range(1, cant + 1):
                            opciones_mesas += f"<option value='{pid}|Mesa {i}'>{pnom} - Mesa {i}</option>"
                        opciones_mesas += "</optgroup>"
                    pagina = HTML_CAMBIAR_MESA.replace("REPLACE_MESA_ACTUAL", mesa_actual)
                    pagina = pagina.replace("REPLACE_ID", str(pedido_id))
                    pagina = pagina.replace("REPLACE_OPCIONES_NUEVA_MESA", opciones_mesas)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(pagina.encode("utf-8"))
                    conn.close()
                    return
            self.send_response(303)
            self.send_header('Location', '/seleccion_piso')
            self.end_headers()
            
        elif path_clean == '/anular_pedido':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            piso_id = params.get('piso', ['1'])[0]
            if 'id' in params:
                pedido_id = params['id'][0]
                cursor.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', f'/mapa_piso?piso={piso_id}')
            self.end_headers()
            
        elif path_clean == '/precuenta':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                pedido_id = params['id'][0]
                cursor.execute("SELECT mesa, mesero, cajero, detalle, total, tipo_comprobante, doc_cliente, razon_social, fecha FROM pedidos WHERE id = ?", (pedido_id,))
                res = cursor.fetchone()
                if res:
                    mesa, mesero, cajero, detalle, total, tipo_comp, doc, razon, fecha = res
                    cfg = obtener_configuracion()
                    tipo_str = tipo_comp if tipo_comp else "PRECUENTA / TICKET DE CONSUMO"
                    datos_cliente_html = ""
                    if tipo_comp == "FACTURA" and doc:
                        datos_cliente_html = f"<p><b>RUC Cliente:</b> {doc}</p><p><b>Razón Social:</b> {razon}</p>"
                    elif tipo_comp == "BOLETA":
                        datos_cliente_html = f"<p><b>Cliente:</b> PUBLICO GENERAL</p>"
                    items_ticket = f"<tr><td>{detalle}</td><td style='text-align:right;'>S/ {total:.2f}</td></tr>"
                    fecha_str = fecha if fecha else datetime.date.today().strftime("%Y-%m-%d")
                    cajero_str = cajero if cajero else "N/D"
                    
                    texto_raw_caja = f"{cfg.get('empresa_nombre', 'MR. CUY')}\nRUC: {cfg.get('empresa_ruc','')}\n{tipo_str}\nMesa: {mesa} | Mesero: {mesero}\nCajero: {cajero_str}\nFecha: {fecha_str}\n--------------------------------\n{detalle}\n--------------------------------\nTOTAL: S/ {total:.2f}\n¡Gracias por su preferencia!\n\n\n"
                    imprimir_silencioso_caja(texto_raw_caja)

                    pagina = HTML_PRECUENTA.replace("REPLACE_EMPRESA_NOMBRE", str(cfg.get('empresa_nombre', 'MR. CUY RESTAURANTE')))
                    pagina = pagina.replace("REPLACE_EMPRESA_RUC", str(cfg.get('empresa_ruc', '20123456789')))
                    pagina = pagina.replace("REPLACE_EMPRESA_DIRECCION", str(cfg.get('empresa_direccion', '')))
                    pagina = pagina.replace("REPLACE_EMPRESA_TELEFONO", str(cfg.get('empresa_telefono', '')))
                    pagina = pagina.replace("REPLACE_TIPO_COMPROBANTE", str(tipo_str))
                    pagina = pagina.replace("REPLACE_Mesa", str(mesa))
                    pagina = pagina.replace("REPLACE_MESERO", str(mesero))
                    pagina = pagina.replace("REPLACE_CAJERO", str(cajero_str))
                    pagina = pagina.replace("REPLACE_FECHA", str(fecha_str))
                    pagina = pagina.replace("REPLACE_DATOS_CLIENTE_HTML", str(datos_cliente_html))
                    pagina = pagina.replace("REPLACE_ITEMS_TICKET", str(items_ticket))
                    pagina = pagina.replace("REPLACE_TOTAL", f"{total:.2f}")
                    
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(pagina.encode("utf-8"))
                    conn.close()
                    return
            self.send_response(303)
            self.send_header('Location', '/seleccion_piso')
            self.end_headers()
            
        elif path_clean == '/admin':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            cfg = obtener_configuracion()
            
            lista_impresoras_win = obtener_impresoras_windows()
            caja_sel = cfg.get('impresora_caja_nombre', 'POS-80')
            opciones_impresoras_html = ""
            for imp in lista_impresoras_win:
                sel_attr = "selected" if imp == caja_sel else ""
                opciones_impresoras_html += f'<option value="{imp}" {sel_attr}>{imp}</option>'

            cursor.execute("SELECT id, texto FROM notas_rapidas ORDER BY id")
            notas_db = cursor.fetchall()
            tabla_notas_rapidas = ""
            for nid, ntxt in notas_db:
                tabla_notas_rapidas += f"""
                <tr>
                    <td><b>{nid}</b></td>
                    <td>{ntxt}</td>
                    <td><a href='/eliminar_nota_rapida?id={nid}' class='btn-eliminar' onclick="return confirm('¿Seguro?');">Eliminar</a></td>
                </tr>
                """
            if not tabla_notas_rapidas:
                tabla_notas_rapidas = "<tr><td colspan='3' style='text-align:center;'>No hay notas rápidas registradas.</td></tr>"

            cursor.execute("SELECT id, nombre FROM categorias ORDER BY id")
            categorias_db = cursor.fetchall()
            tabla_categorias = ""
            for cat_id, cat_nom in categorias_db:
                tabla_categorias += f"""
                <tr>
                    <td><b>{cat_id}</b></td>
                    <td>{cat_nom}</td>
                    <td><a href='/eliminar_categoria?id={cat_id}' class='btn-eliminar' onclick="return confirm('¿Seguro?');">Eliminar</a></td>
                </tr>
                """
            if not tabla_categorias:
                tabla_categorias = "<tr><td colspan='3' style='text-align:center;'>No hay categorías registradas.</td></tr>"

            opciones_cat_select = ""
            for _, cat_nom in categorias_db:
                opciones_cat_select += f'<option value="{cat_nom}">{cat_nom}</option>'

            cursor.execute("SELECT id, nombre, cant_mesas FROM pisos ORDER BY id")
            pisos = cursor.fetchall()
            tabla_pisos = ""
            for p in pisos:
                tabla_pisos += f"""
                <tr>
                    <form action='/editar_piso' method='POST'>
                        <input type='hidden' name='id' value='{p[0]}'>
                        <td><b>{p[0]}</b></td>
                        <td><input type='text' name='nombre' value='{p[1]}' required style='margin:0;'></td>
                        <td><input type='number' name='cant_mesas' value='{p[2]}' min='1' max='50' required style='margin:0; width:120px;'></td>
                        <td>
                            <button type='submit' class='btn-guardar-sm'>💾 Guardar</button>
                            <a href='/eliminar_piso?id={p[0]}' class='btn-eliminar' onclick="return confirm('¿Eliminar?');">Eliminar</a>
                        </td>
                    </form>
                </tr>
                """
            if not tabla_pisos:
                tabla_pisos = "<tr><td colspan='4' style='text-align:center;'>No hay pisos configurados.</td></tr>"
            
            cursor.execute("SELECT id, nombre FROM cajeros")
            cajeros = cursor.fetchall()
            tabla_cajeros = "".join([f"<tr><td>{c[0]}</td><td>{c[1]}</td><td><a href='/eliminar_cajero?id={c[0]}' class='btn-eliminar'>Eliminar</a></td></tr>" for c in cajeros])
            if not tabla_cajeros:
                tabla_cajeros = "<tr><td colspan='3' style='text-align:center;'>No hay cajeros registrados.</td></tr>"

            cursor.execute("SELECT id, nombre FROM meseros")
            meseros = cursor.fetchall()
            tabla_meseros = "".join([f"<tr><td>{m[0]}</td><td>{m[1]}</td><td><a href='/eliminar_mesero?id={m[0]}' class='btn-eliminar'>Eliminar</a></td></tr>" for m in meseros])
            
            cursor.execute("SELECT id, categoria, nombre, precio FROM productos ORDER BY categoria")
            productos = cursor.fetchall()
            tabla_menu = "".join([f"<tr><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td><td><b style='color:#008833;'>S/ {p[3]:.2f}</b></td><td><a href='/eliminar_producto?id={p[0]}' class='btn-eliminar'>Eliminar</a></td></tr>" for p in productos])
            
            datos_lic = {}
            if os.path.exists(ARCHIVO_LICENCIA):
                try:
                    with open(ARCHIVO_LICENCIA, "r", encoding="utf-8") as fl:
                        datos_lic = json.load(fl)
                except Exception:
                    pass
            tipo_lic_str = "Licencia Ilimitada (Activada)" if datos_lic.get("activo") == "ilimitado" else "Licencia de Prueba (7 Días)"
            
            pagina = HTML_ADMIN.replace("REPLACE_EMPRESA_NOMBRE", str(cfg.get('empresa_nombre', 'MR. CUY RESTAURANTE')))
            pagina = pagina.replace("REPLACE_EMPRESA_RUC", str(cfg.get('empresa_ruc', '20123456789')))
            pagina = pagina.replace("REPLACE_EMPRESA_DIRECCION", str(cfg.get('empresa_direccion', '')))
            pagina = pagina.replace("REPLACE_EMPRESA_TELEFONO", str(cfg.get('empresa_telefono', '')))
            pagina = pagina.replace("REPLACE_COCINA_IP", str(cfg.get('impresora_cocina_ip', '192.168.1.100')))
            pagina = pagina.replace("REPLACE_COCINA_PUERTO", str(cfg.get('impresora_cocina_puerto', '9100')))
            pagina = pagina.replace("REPLACE_PC_CAJA_IP", str(cfg.get('pc_caja_ip', '127.0.0.1')))
            pagina = pagina.replace("REPLACE_OPCIONES_IMPRESORAS_CAJA", opciones_impresoras_html)
            
            pagina = pagina.replace("REPLACE_PRECIO_TAPER_MENU", str(cfg.get('taper_menu', '1.00')))
            pagina = pagina.replace("REPLACE_PRECIO_TAPER_ENTRADA", str(cfg.get('taper_entrada', '0.50')))
            pagina = pagina.replace("REPLACE_TABLA_NOTAS_RAPIDAS", tabla_notas_rapidas)
            pagina = pagina.replace("REPLACE_TABLA_CATEGORIAS", tabla_categorias)
            pagina = pagina.replace("REPLACE_OPCIONES_CATEGORIAS_SELECT", opciones_cat_select)
            pagina = pagina.replace("REPLACE_TABLA_PISOS", tabla_pisos)
            pagina = pagina.replace("REPLACE_TABLA_CAJEROS", tabla_cajeros)
            pagina = pagina.replace("REPLACE_TABLA_MESEROS", tabla_meseros)
            pagina = pagina.replace("REPLACE_TABLA_MENU", tabla_menu)
            
            pagina = pagina.replace("REPLACE_VERSION", str(VERSION_ACTUAL))
            pagina = pagina.replace("REPLACE_TIPO_LICENCIA_STR", tipo_lic_str)
            pagina = pagina.replace("REPLACE_TIEMPO_RESTANTE", "Calculando..." if datos_lic.get("activo") != "ilimitado" else "Ilimitado")
            pagina = pagina.replace("REPLACE_DATOS_LICENCIA_JSON", json.dumps(datos_lic))
            
            self.wfile.write(pagina.encode("utf-8"))
            
        elif path_clean == '/eliminar_nota_rapida':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM notas_rapidas WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif path_clean == '/eliminar_piso':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM pisos WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        elif path_clean == '/eliminar_categoria':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM categorias WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif path_clean == '/eliminar_producto':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM productos WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        elif path_clean == '/eliminar_mesero':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM meseros WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif path_clean == '/eliminar_cajero':
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'id' in params:
                cursor.execute("DELETE FROM cajeros WHERE id = ?", (params['id'][0],))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        else:
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            
        conn.close()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        conn = sqlite3.connect("restaurante.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        if self.path == '/login_cajero':
            cajero_nombre = params.get('cajero', ['Cajero General'])[0]
            self.send_response(303)
            self.send_header('Set-Cookie', f'cajero_mr_cuy={urllib.parse.quote(cajero_nombre)}; Path=/')
            self.send_header('Location', '/menu_principal')
            self.end_headers()
            conn.close()
            return

        cookies = parsear_cookies(self.headers)
        cajero_actual = cookies.get('cajero_mr_cuy', 'Cajero General')

        if self.path == '/enviar':
            mesa = params.get('mesa', ['Mesa General'])[0]
            mesero = params.get('mesero', ['General'])[0]
            origen_piso = params.get('origen_piso', ['1'])[0]
            datos_json_str = params.get('datos_personas_json', ['[]'])[0]
            
            cfg = obtener_configuracion()
            taper_menu_val = float(cfg.get('taper_menu', '1.00'))
            taper_entrada_val = float(cfg.get('taper_entrada', '0.50'))
            try:
                lista_personas = json.loads(datos_json_str)
            except Exception:
                lista_personas = []
                
            if lista_personas:
                bloques_personas_str = []
                total_global = 0.0
                bloques_personas_cocina = []
                texto_comanda_cocina = f"=== COMANDA COCINA ===\nMESA: {mesa} | MESERO: {mesero}\n----------------------\n"
                hay_llevar_global = any(p.get('para_llevar', False) for p in lista_personas)
                if hay_llevar_global:
                    texto_comanda_cocina += "*** PEDIDO PARA LLEVAR ***\n----------------------\n"
                
                for p_data in lista_personas:
                    p_nombre = p_data.get('nombre', 'Persona')
                    p_items = p_data.get('items', [])
                    p_llevar = p_data.get('para_llevar', False)
                    p_nota = p_data.get('nota', '').strip()
                    if not p_items:
                        continue
                        
                    platos_fondo = []
                    entradas = []
                    otros_items = []
                    for pid in p_items:
                        cursor.execute("SELECT nombre, precio, categoria FROM productos WHERE id = ?", (pid,))
                        res = cursor.fetchone()
                        if res:
                            nom, prec, cat = res
                            if cat == 'MENU':
                                platos_fondo.append((nom, prec))
                            elif cat == 'ENTRADAS':
                                entradas.append((nom, prec))
                            else:
                                otros_items.append((nom, prec, cat))
                    
                    nombres_cocina = []
                    nombres = []
                    subtotal_persona = 0.0
                    cant_platos = len(platos_fondo)
                    for nom, prec in platos_fondo:
                        nom_final = nom
                        if p_llevar:
                            nom_final += f" [Táper Menú +S/ {taper_menu_val:.2f}]"
                            prec += taper_menu_val
                        nombres.append(nom_final)
                        nombres_cocina.append(nom_final)
                        subtotal_persona += prec
                        
                    entradas_gratis_disponibles = cant_platos
                    for nom, prec in entradas:
                        if entradas_gratis_disponibles > 0:
                            nom_final = f"{nom} [Incluida]"
                            prec_e = 0.0
                            entradas_gratis_disponibles -= 1
                        else:
                            nom_final = nom
                            prec_e = prec
                        if p_llevar:
                            nom_final += f" [Táper Entrada +S/ {taper_entrada_val:.2f}]"
                            prec_e += taper_entrada_val
                        nombres.append(nom_final)
                        nombres_cocina.append(nom_final)
                        subtotal_persona += prec_e
                            
                    for nom, prec, cat in otros_items:
                        nom_final = nom
                        if p_llevar:
                            nom_final += " [PARA LLEVAR]"
                        if cat not in ('GASEOSAS', 'CERVEZAS', 'BEBIDAS'):
                            nombres_cocina.append(nom_final)
                        nombres.append(nom_final)
                        subtotal_persona += prec
                    
                    det_p = f"{p_nombre}: " + ", ".join(nombres)
                    if p_nota:
                        det_p += f" (Nota: {p_nota})"
                    bloques_personas_str.append(det_p)
                    if nombres_cocina:
                        det_p_cocina = f"{p_nombre}: " + ", ".join(nombres_cocina)
                        if p_nota:
                            det_p_cocina += f" (Nota: {p_nota})"
                        bloques_personas_cocina.append((det_p_cocina, p_llevar))
                    total_global += subtotal_persona

                if bloques_personas_cocina:
                    for det_c, llev in bloques_personas_cocina:
                        linea_c = f"* {det_c}"
                        if llev:
                            linea_c += " --> [EMPACAR EN TÁPER / PARA LLEVAR]"
                        texto_comanda_cocina += f"{linea_c}\n"
                    imprimir_red_cocina(texto_comanda_cocina)

                if bloques_personas_str:
                    nuevos_detalles_str = ", ".join(bloques_personas_str)
                    fecha_actual = datetime.date.today().strftime("%Y-%m-%d")
                    cursor.execute("SELECT id, detalle, total FROM pedidos WHERE mesa = ? AND piso_id = ? AND estado = 'Pendiente'", (mesa, origen_piso))
                    existente = cursor.fetchone()
                    if existente:
                        nuevo_det = existente[1] + ", " + nuevos_detalles_str
                        nuevo_tot = existente[2] + total_global
                        cursor.execute("UPDATE pedidos SET detalle = ?, total = ? WHERE id = ?", (nuevo_det, nuevo_tot, existente[0]))
                    else:
                        cursor.execute("INSERT INTO pedidos (mesa, mesero, cajero, detalle, total, estado, fecha, piso_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (mesa, mesero, cajero_actual, nuevos_detalles_str, total_global, 'Pendiente', fecha_actual, origen_piso))
                    conn.commit()
                
            self.send_response(303)
            self.send_header('Location', f'/mapa_piso?piso={origen_piso}')
            self.end_headers()

        elif self.path == '/confirmar_cobro':
            if not es_pc_principal(self.client_address):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                msg = f"<!DOCTYPE html><html><head>{CSS_GLOBAL}</head><body style='background:#fffdf0; display:flex; justify-content:center; align-items:center; min-height:100vh; color:#2c3e50; text-align:center; padding:25px;'><div class='card' style='background:#ffffff; padding:45px; border-radius:20px; border:5px solid #e74c3c; max-width:550px;'><h2 style='color:#e74c3c; font-size:32px;'>⚠️ Acceso Restringido</h2><p style='font-size:20px;'>Esta opción solo está disponible en la PC Principal de Caja.</p><br><a href='/menu_principal' class='nav-btn nav-home' style='display:inline-block;'>⬅️ Volver al Menú Principal</a></div></body></html>"
                self.wfile.write(msg.encode("utf-8"))
                conn.close()
                return
            pid = params.get('id', [''])[0]
            piso_id = params.get('piso', ['1'])[0]
            tipo_comprobante = params.get('tipo_comprobante', ['TICKET'])[0]
            doc_cliente = params.get('doc_cliente', [''])[0].strip()
            razon_social = params.get('razon_social', [''])[0].strip()
            fecha_actual = datetime.date.today().strftime("%Y-%m-%d")
            if pid:
                cursor.execute("""
                    UPDATE pedidos 
                    SET estado = 'Cobrado', cajero = ?, fecha = ?, tipo_comprobante = ?, doc_cliente = ?, razon_social = ? 
                    WHERE id = ?
                """, (cajero_actual, fecha_actual, tipo_comprobante, doc_cliente, razon_social, pid))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', f'/precuenta?id={pid}')
            self.end_headers()

        elif self.path == '/actualizar_empresa':
            nombre = params.get('empresa_nombre', ['MR. CUY RESTAURANTE'])[0]
            ruc = params.get('empresa_ruc', ['20123456789'])[0]
            direccion = params.get('empresa_direccion', [''])[0]
            telefono = params.get('empresa_telefono', [''])[0]
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('empresa_nombre', ?)", (nombre,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('empresa_ruc', ?)", (ruc,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('empresa_direccion', ?)", (direccion,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('empresa_telefono', ?)", (telefono,))
            conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/actualizar_impresoras':
            cocina_ip = params.get('impresora_cocina_ip', ['192.168.1.100'])[0]
            cocina_puerto = params.get('impresora_cocina_puerto', ['9100'])[0]
            caja_nombre = params.get('impresora_caja_nombre', ['POS-80'])[0]
            pc_caja_ip = params.get('pc_caja_ip', ['127.0.0.1'])[0]
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('impresora_cocina_ip', ?)", (cocina_ip,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('impresora_cocina_puerto', ?)", (cocina_puerto,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('impresora_caja_nombre', ?)", (caja_nombre,))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('pc_caja_ip', ?)", (pc_caja_ip,))
            conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        elif self.path == '/actualizar_taper':
            try:
                t_menu = float(params.get('taper_menu', [1.00])[0])
                t_entrada = float(params.get('taper_entrada', [0.50])[0])
            except ValueError:
                t_menu = 1.00
                t_entrada = 0.50
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('taper_menu', ?)", (str(t_menu),))
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('taper_entrada', ?)", (str(t_entrada),))
            conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/agregar_nota_rapida':
            txt = params.get('texto_nota', [''])[0].strip()
            if txt:
                try:
                    cursor.execute("INSERT INTO notas_rapidas (texto) VALUES (?)", (txt,))
                    conn.commit()
                except sqlite3.IntegrityError:
                    pass
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/editar_piso':
            pid = params.get('id', [''])[0]
            pnom = params.get('nombre', [''])[0]
            try:
                cant = int(params.get('cant_mesas', [10])[0])
            except ValueError:
                cant = 10
            if pid and pnom:
                cursor.execute("UPDATE pisos SET nombre = ?, cant_mesas = ? WHERE id = ?", (pnom, cant, pid))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/agregar_piso':
            pnom = params.get('nombre_piso', [''])[0]
            try:
                cant = int(params.get('cant_mesas', [10])[0])
            except ValueError:
                cant = 10
            if pnom:
                cursor.execute("INSERT INTO pisos (nombre, cant_mesas) VALUES (?, ?)", (pnom, cant))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        elif self.path == '/agregar_categoria':
            cat_nom = params.get('nombre_categoria', [''])[0].strip().upper()
            if cat_nom:
                try:
                    cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (cat_nom,))
                    conn.commit()
                except sqlite3.IntegrityError:
                    pass
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/procesar_cambio_mesa':
            id_pedido = params.get('id_pedido', [''])[0]
            seleccion = params.get('nueva_mesa', ['1|Mesa 1'])[0]
            if id_pedido and '|' in seleccion:
                nuevo_piso_id, nueva_mesa = seleccion.split('|')
                cursor.execute("UPDATE pedidos SET mesa = ?, piso_id = ? WHERE id = ?", (nueva_mesa, nuevo_piso_id, id_pedido))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/seleccion_piso')
            self.end_headers()
            
        elif self.path == '/agregar_producto':
            cat = params.get('categoria', ['OTROS'])[0]
            nom = params.get('nombre', [''])[0]
            try:
                prec = float(params.get('precio', [0])[0])
            except ValueError:
                prec = 0.0
            if nom:
                cursor.execute("INSERT INTO productos (categoria, nombre, precio) VALUES (?, ?, ?)", (cat, nom, prec))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        elif self.path == '/agregar_mesero':
            nom_mesero = params.get('nombre_mesero', [''])[0]
            if nom_mesero:
                cursor.execute("INSERT INTO meseros (nombre) VALUES (?)", (nom_mesero,))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()

        elif self.path == '/agregar_cajero':
            nom_cajero = params.get('nombre_cajero', [''])[0]
            if nom_cajero:
                cursor.execute("INSERT INTO cajeros (nombre) VALUES (?)", (nom_cajero,))
                conn.commit()
            self.send_response(303)
            self.send_header('Location', '/admin')
            self.end_headers()
            
        conn.close()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run(server_class=ThreadingHTTPServer, handler_class=ServerHandler, port=8000):
    server_address = ('0.0.0.0', port)
    httpd = server_class(server_address, handler_class)
    print("--- SERVIDOR MR. CUY MULTIHILO ACTIVO (ACT. AUTOMÁTICA & LICENCIA PROTEGIDA) ---")
    print("Abre el navegador en http://localhost:8000")
    httpd.serve_forever()

if __name__ == '__main__':
    run()