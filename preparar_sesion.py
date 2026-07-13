#!/usr/bin/env python3
"""
Ayudante de inicio de sesión para los scrapers de Selenium.

Abre el navegador con el perfil persistente de una red y espera a que inicies
sesión MANUALMENTE. Al terminar, la sesión queda guardada en el perfil y los
scrapers la reutilizan sin volver a pedir login.

Uso:
    python3 preparar_sesion.py x          # X (Twitter)
    python3 preparar_sesion.py facebook
    python3 preparar_sesion.py tiktok
"""

from __future__ import annotations

import sys

from src.navegador import crear_driver

LOGIN_URLS = {
    "x": "https://x.com/login",
    "facebook": "https://www.facebook.com/login",
    "tiktok": "https://www.tiktok.com/login",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in LOGIN_URLS:
        print(f"Uso: python3 preparar_sesion.py [{'/'.join(LOGIN_URLS)}]")
        sys.exit(1)

    red = sys.argv[1]
    print(f"Abriendo navegador para iniciar sesión en '{red}'...")
    # Nunca headless: necesitas ver la ventana para iniciar sesión.
    driver = crear_driver(red, headless=False)
    try:
        driver.get(LOGIN_URLS[red])
        print("\n" + "=" * 60)
        print(f"  Inicia sesión en la ventana de Chrome para '{red}'.")
        print("  Cuando ya estés DENTRO de tu cuenta, vuelve aquí y")
        input("  presiona ENTER para guardar la sesión y cerrar... ")
        print("=" * 60)
        print(f"Sesión de '{red}' guardada en el perfil. Ya puedes ejecutar main.py")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
