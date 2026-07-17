import os
import sys

# Asegura que la raíz del proyecto esté en el path para poder importar 'src.*'
# aunque este archivo se ejecute directamente (p. ej. desde dentro de src/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.controlador import ejecutar_paralelo


def main():
    ejecutar_paralelo()


if __name__ == "__main__":
    main()
