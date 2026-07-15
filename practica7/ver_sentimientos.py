#!/usr/bin/env python3
"""
Servidor y Lanzador del Dashboard de Sentimientos — Práctica 07.

Inicia un servidor HTTP local ligero para explorar visualmente las opiniones
clasificadas por los LLMs y abre automáticamente el navegador web.

Uso:
    python3 ver_sentimientos.py                # Abre el último dataset guardado
    python3 ver_sentimientos.py --puerto 8085  # Usar un puerto personalizado
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

# Rutas de datos
_DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
_DIR_INTERFAZ = os.path.join(_DIR_ACTUAL, "interfaz")
_DIR_DATOS_P7 = os.path.join(_DIR_ACTUAL, "datos")
_DIR_DATOS_RAIZ = os.path.join(_DIR_ACTUAL, "..", "datos")


def listar_archivos_sentimientos():
    """Busca y ordena todos los archivos de sentimientos disponibles en el proyecto."""
    archivos = {}
    directorios = [d for d in [_DIR_DATOS_RAIZ, _DIR_DATOS_P7] if os.path.isdir(d)]

    for d in directorios:
        for f in os.listdir(d):
            if f.startswith("sentimientos_") and f.endswith(".json"):
                ruta = os.path.join(d, f)
                # Conservamos solo la versión de modificación más reciente
                if f not in archivos or os.path.getmtime(ruta) > os.path.getmtime(archivos[f]):
                    archivos[f] = ruta

    if not archivos:
        return [], None

    # Ordenar por fecha de modificación (más reciente primero)
    ordenados = sorted(archivos.items(), key=lambda item: os.path.getmtime(item[1]), reverse=True)
    lista_info = []
    for nombre, ruta in ordenados:
        from datetime import datetime
        t = os.path.getmtime(ruta)
        lista_info.append({
            "nombre": nombre,
            "ruta": ruta,
            "fecha": datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
        })

    return lista_info, lista_info[0]["nombre"]


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Servir archivos estáticos directamente desde practica7/interfaz
        super().__init__(*args, directory=_DIR_INTERFAZ, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        # Endpoint: lista de datasets
        if parsed.path == "/api/datasets":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            
            datasets, latest = listar_archivos_sentimientos()
            self.wfile.write(json.dumps({"datasets": datasets, "latest": latest}).encode("utf-8"))
            return

        # Endpoint: cargar dataset específico
        if parsed.path == "/api/dataset":
            query = urllib.parse.parse_qs(parsed.query)
            filename = query.get("file", [""])[0]
            datasets, _ = listar_archivos_sentimientos()
            
            ruta_objetivo = None
            for d in datasets:
                if d["nombre"] == filename:
                    ruta_objetivo = d["ruta"]
                    break
            
            if not ruta_objetivo and datasets:
                ruta_objetivo = datasets[0]["ruta"]

            if ruta_objetivo and os.path.exists(ruta_objetivo):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                with open(ruta_objetivo, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Dataset no encontrado"}')
            return

        # Comportamiento por defecto: servir estáticos de interfaz
        return super().do_GET()

    def log_message(self, format, *args):
        # Silenciar logs del servidor local en consola para mantenerla limpia
        pass


def main():
    parser = argparse.ArgumentParser(description="Lanzador del Dashboard de Sentimientos (Práctica 07).")
    parser.add_argument("--puerto", type=int, default=8080, help="Puerto local para el servidor web (por defecto: 8080).")
    parser.add_argument("--no-abrir", action="store_true", help="No abrir el navegador automáticamente.")
    args = parser.parse_args()

    datasets, latest = listar_archivos_sentimientos()
    if not datasets:
        print("⚠️ No se encontraron archivos 'sentimientos_*.json' en datos/ ni en practica7/datos/.")
        print("💡 Consejo: Corre primero 'python3 practica7/main.py --proveedor openai' para generar uno.")

    # Intentar puertos si el 8080 está en uso
    puerto = args.puerto
    httpd = None
    for p in range(puerto, puerto + 10):
        try:
            httpd = socketserver.TCPServer(("", p), DashboardHandler)
            puerto = p
            break
        except OSError:
            continue

    if not httpd:
        print("❌ No se pudo iniciar el servidor. Puertos ocupados.")
        sys.exit(1)

    url = f"http://localhost:{puerto}"
    print("\n" + "=" * 70)
    print("  🚀 DASHBOARD DE ANÁLISIS DE SENTIMIENTOS ACTIVO")
    print("  Práctica de Laboratorio 07 — Computación Paralela")
    print("=" * 70)
    print(f"🔗 Interfaz visual disponible en: {url}")
    if latest:
        print(f"📊 Dataset cargado por defecto : {latest}")
    print("💡 Presiona Ctrl+C en esta consola para detener el servidor.\n")

    if not args.no_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido correctamente.")
        httpd.server_close()


if __name__ == "__main__":
    main()
