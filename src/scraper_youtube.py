import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


class ScraperYouTube:
    """Extrae videos y comentarios de YouTube sobre un tema usando la
    YouTube Data API v3 (oficial y gratuita, sin navegador ni login).
    Requiere YOUTUBE_API_KEY en .env."""

    URL_BUSQUEDA = "https://www.googleapis.com/youtube/v3/search"
    URL_COMENTARIOS = "https://www.googleapis.com/youtube/v3/commentThreads"

    def __init__(
        self,
        busqueda="museo nacional del ecuador",
        max_videos=25,
        max_comentarios_por_video=300,
        archivo_salida="datos/youtube_publicaciones.json",
    ):
        self.busqueda = busqueda
        self.max_videos = max_videos
        self.max_comentarios_por_video = max_comentarios_por_video
        self.archivo_salida = archivo_salida
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        self.publicaciones = []

    # ------------------------------------------------------------------
    # Videos
    # ------------------------------------------------------------------
    def buscar_videos(self):
        """Busca videos del tema (una búsqueda cuesta 100 unidades de cuota)."""
        params = {
            "key": self.api_key,
            "part": "snippet",
            "q": self.busqueda,
            "type": "video",
            "maxResults": min(self.max_videos, 50),
            "relevanceLanguage": "es",
        }
        respuesta = requests.get(self.URL_BUSQUEDA, params=params, timeout=30)
        respuesta.raise_for_status()

        for item in respuesta.json().get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]
            self.publicaciones.append({
                "fuente": "YouTube",
                "consulta": self.busqueda,
                "autor": snippet["channelTitle"],
                "texto": snippet["title"] + "\n" + snippet["description"],
                "fecha": snippet["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
            })
        print(f"Videos encontrados: {len(self.publicaciones)}")

    # ------------------------------------------------------------------
    # Comentarios
    # ------------------------------------------------------------------
    def extraer_comentarios(self, video_id):
        """Descarga los hilos de comentarios del video, con paginación.
        Devuelve [{autor, texto, likes, nivel}, ...]."""
        comentarios = []
        params = {
            "key": self.api_key,
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": 100,
            "textFormat": "plainText",
        }
        while len(comentarios) < self.max_comentarios_por_video:
            respuesta = requests.get(self.URL_COMENTARIOS, params=params, timeout=30)
            if respuesta.status_code == 403:
                break  # comentarios deshabilitados en este video
            respuesta.raise_for_status()
            datos = respuesta.json()

            for hilo in datos.get("items", []):
                principal = hilo["snippet"]["topLevelComment"]["snippet"]
                comentarios.append({
                    "autor": principal["authorDisplayName"],
                    "texto": principal["textOriginal"],
                    "likes": principal["likeCount"],
                    "nivel": 1,
                })
                for respuesta_hilo in hilo.get("replies", {}).get("comments", []):
                    s = respuesta_hilo["snippet"]
                    comentarios.append({
                        "autor": s["authorDisplayName"],
                        "texto": s["textOriginal"],
                        "likes": s["likeCount"],
                        "nivel": 2,
                    })

            if "nextPageToken" not in datos:
                break
            params["pageToken"] = datos["nextPageToken"]

        return comentarios[: self.max_comentarios_por_video]

    def extraer_comentarios_de_videos(self):
        for n, video in enumerate(self.publicaciones, start=1):
            video["comentarios"] = self.extraer_comentarios(video["video_id"])
            print(f"[{n}/{len(self.publicaciones)}] {video['autor']}: "
                  f"{len(video['comentarios'])} comentarios")

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
    def ejecutar(self):
        if not self.api_key:
            print("Define YOUTUBE_API_KEY en .env")
            return
        self.buscar_videos()
        self.extraer_comentarios_de_videos()
        self.guardar()
