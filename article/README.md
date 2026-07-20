# Artículo académico (Proyecto Final)

Artículo en inglés, plantilla oficial de Springer **LNCS** (`llncs.cls` /
`splncs04.bst`, obtenida de CTAN, licencia CC BY 4.0), documentando la
aplicación web de extracción y análisis paralelo de redes sociales.

## Compilar

Requiere una distribución LaTeX (TeX Live) con `pdflatex` y `bibtex`.

```bash
cd article
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Genera `main.pdf` (11 páginas). Los archivos auxiliares (`.aux`, `.bbl`,
`.log`, etc.) no se versionan.

## Contenido

- `main.tex` — artículo completo (título, abstract, introducción, trabajos
  relacionados, metodología con diagrama de arquitectura en TikZ,
  resultados, conclusiones y recomendaciones).
- `references.bib` — 18 referencias verificadas (6 trabajos relacionados
  ≤3 años + 12 referencias de apoyo/fundamentales).
- `llncs.cls`, `splncs04.bst` — plantilla oficial Springer LNCS (CTAN).

Los resultados reportados (corpus de 508 opiniones, tiempos de ejecución,
benchmark secuencial vs. paralelo, acuerdo entre modelos LLM) provienen de
corridas reales del sistema, documentadas en `practica7/informe.md` y en
los datasets de `datos/` y `practica7/datos/`.
