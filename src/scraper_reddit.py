import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class ScraperReddit:
    """Extrae publicaciones (posts) y comentarios de Reddit sobre un tema
    usando la API oficial de Reddit (OAuth "client_credentials", sin
    necesidad de usuario ni login manual). Requiere REDDIT_CLIENT_ID y
    REDDIT_CLIENT_SECRET en .env (se crean gratis en
    https://www.reddit.com/prefs/apps, tipo "script")."""

    URL_TOKEN = "https://www.reddit.com/api/v1/access_token"
    URL_BASE = "https://oauth.reddit.com"

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        max_publicaciones=25,
        max_comentarios_por_publicacion=300,
        archivo_salida="datos/reddit_publicaciones.json",
    ):
        self.busqueda = busqueda
        self.max_publicaciones = max_publicaciones
        self.max_comentarios_por_publicacion = max_comentarios_por_publicacion
        self.archivo_salida = archivo_salida
        self.client_id = os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        self.user_agent = os.getenv(
            "REDDIT_USER_AGENT",
            "computacion-paralela-museo-ecuador/1.0",
        )
        self.token = None
        self.gestor = None
        self.publicaciones = []

    def _checkpoint(self):
        """Si un scraper de Selenium está iniciando sesión en otro hilo, se
        bloquea aquí hasta que termine (ver GestorLogin)."""
        if self.gestor is not None:
            self.gestor.esperar()

    # ------------------------------------------------------------------
    # Autenticación (application-only OAuth, sin cuenta de usuario)
    # ------------------------------------------------------------------
    def autenticar(self):
        respuesta = requests.post(
            self.URL_TOKEN,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"User-Agent": self.user_agent},
            timeout=30,
        )
        respuesta.raise_for_status()
        self.token = respuesta.json()["access_token"]

    def _headers(self):
        return {
            "Authorization": f"bearer {self.token}",
            "User-Agent": self.user_agent,
        }

    # ------------------------------------------------------------------
    # Publicaciones (posts)
    # ------------------------------------------------------------------
    def buscar_publicaciones(self):
        params = {
            "q": self.busqueda,
            "limit": min(self.max_publicaciones, 100),
            "sort": "relevance",
            "type": "link",
        }
        respuesta = requests.get(
            f"{self.URL_BASE}/search",
            params=params,
            headers=self._headers(),
            timeout=30,
        )
        respuesta.raise_for_status()

        for hijo in respuesta.json().get("data", {}).get("children", []):
            d = hijo["data"]
            texto = (d.get("title") or "") + "\n" + (d.get("selftext") or "")
            self.publicaciones.append({
                "fuente": "Reddit",
                "consulta": self.busqueda,
                "autor": d.get("author", "desconocido"),
                "texto": texto.strip(),
                "fecha": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(d.get("created_utc", 0))
                ),
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "post_id": d.get("id"),
                "subreddit": d.get("subreddit"),
                "vistas": d.get("ups", 0),
            })
        print(f"Publicaciones encontradas en Reddit: {len(self.publicaciones)}")

    # ------------------------------------------------------------------
    # Comentarios
    # ------------------------------------------------------------------
    def extraer_comentarios(self, post_id):
        """Descarga los comentarios (aplanados, con nivel según profundidad)
        de una publicación. Devuelve [{autor, texto, likes, nivel}, ...]."""
        comentarios = []
        respuesta = requests.get(
            f"{self.URL_BASE}/comments/{post_id}",
            params={"limit": self.max_comentarios_por_publicacion, "depth": 5},
            headers=self._headers(),
            timeout=30,
        )
        if respuesta.status_code != 200:
            return comentarios

        arbol_comentarios = respuesta.json()[1]["data"]["children"]

        def recorrer(nodos, nivel=1):
            for nodo in nodos:
                if nodo.get("kind") != "t1":  # solo comentarios, no "more"
                    continue
                d = nodo["data"]
                texto = d.get("body", "")
                if texto and texto != "[deleted]" and texto != "[removed]":
                    comentarios.append({
                        "autor": d.get("author", "desconocido"),
                        "texto": texto,
                        "likes": d.get("ups", 0),
                        "nivel": nivel,
                    })
                respuestas = d.get("replies")
                if isinstance(respuestas, dict):
                    recorrer(respuestas.get("data", {}).get("children", []), nivel + 1)

        recorrer(arbol_comentarios)
        return comentarios[: self.max_comentarios_por_publicacion]

    def extraer_comentarios_de_publicaciones(self):
        for n, pub in enumerate(self.publicaciones, start=1):
            self._checkpoint()
            pub["comentarios"] = self.extraer_comentarios(pub["post_id"])
            print(f"[{n}/{len(self.publicaciones)}] r/{pub['subreddit']} "
                  f"({pub['autor']}): {len(pub['comentarios'])} comentarios")

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------
    def guardar(self):
        os.makedirs(os.path.dirname(self.archivo_salida) or ".", exist_ok=True)
        with open(self.archivo_salida, "w", encoding="utf-8") as f:
            json.dump(self.publicaciones, f, ensure_ascii=False, indent=2)
        print(f"\nGuardadas {len(self.publicaciones)} publicaciones en {self.archivo_salida}")

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------
    def ejecutar(self, gestor=None):
        self.gestor = gestor
        if not self.client_id or not self.client_secret:
            print("Define REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET en .env")
            return
        self._checkpoint()
        self.autenticar()
        self.buscar_publicaciones()
        self.extraer_comentarios_de_publicaciones()
        self.guardar()
