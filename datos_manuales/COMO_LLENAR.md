# Cómo llenar los datos manuales

Facebook, X (Twitter) y TikTok bloquean el scraping automático gratuito, por lo
que las opiniones reales sobre el diseño **"Ecos del Sol"** del Museo Nacional
del Ecuador se recolectan **manualmente** en estos tres archivos:

- `facebook.csv`  → publicaciones/comentarios de Facebook
- `x_twitter.csv` → tweets de X
- `tiktok.csv`    → descripciones/comentarios de TikTok

El sistema lee los tres **en paralelo**, los limpia, normaliza y guarda el
dataset en `datos/`.

## Columnas

Solo **`texto`** es obligatorio. El resto es opcional pero suma trazabilidad.

| Columna | Obligatorio | Qué poner |
|---------|:-----------:|-----------|
| `texto` | ✅ | El contenido de la opinión (comentario, tweet, descripción) |
| `consulta` | | Hashtag/keyword/página con la que lo encontraste (ej. `#EcosDelSol`, `pagina:ecuavisa`) |
| `autor` | | Usuario que lo publicó (puedes anonimizar) |
| `fecha` | | Fecha de publicación (ej. `2026-07-10`) |
| `url` | | Enlace a la publicación |
| `likes` | | Nº de me gusta / reacciones |
| `comentarios` | | Nº de comentarios |
| `compartidos` | | Nº de veces compartido |
| `vistas` | | Nº de reproducciones/vistas (útil en TikTok) |

## Recomendación: usa una hoja de cálculo

Abre el `.csv` con **LibreOffice Calc / Excel / Google Sheets**, llena las filas
y **exporta como CSV (UTF-8)**. Así los textos con comas, comillas o saltos de
línea se escapan solos y no rompes el formato.

Si editas a mano en un editor de texto: encierra entre comillas dobles cualquier
texto que tenga comas, y duplica las comillas internas (`"` → `""`).

## Ejemplo de una fila (formato)

```csv
texto,consulta,autor,fecha,url,likes,comentarios,compartidos,vistas
"El diseño no representa nuestra identidad, parece un centro comercial",#EcosDelSol,@usuario1,2026-07-10,https://x.com/...,120,8,15,0
```

> Consejo: recolecta un mix de opiniones **a favor y en contra** para que el
> análisis de sentimientos del proyecto final sea representativo.
