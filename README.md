# Golium

Web de análisis de partidos y detección de **value bets** para fútbol, basada en datos scrapeados y modelo Poisson/Dixon-Coles ya existente.

## Qué cambia en esta versión

- **SofaScore ya no depende de Scrapling** ni de abrir navegador.
- El scraper usa la **API pública JSON** de SofaScore para sacar:
  - temporadas
  - clasificación total / local / visitante
  - jornadas
  - partidos por ronda
  - estadísticas de partido
  - alineaciones
  - incidentes
- Se añade modo **hybrid**: ESPN como base + enriquecimiento de SofaScore.
- Se añaden **teamMetrics** para algoritmos de apuestas:
  - goles a favor / en contra
  - xG / xGA medios
  - tiros y tiros a puerta
  - corners
  - tarjetas
  - BTTS rate
  - Over 2.5 rate

## Modos de scraper

```bash
python scraper.py laliga hybrid
python scraper.py laliga espn
python scraper.py laliga sofascore
python scraper.py all hybrid
```

Si no indicas modo, usa `hybrid` por defecto.

## Requisitos

- Python 3.10+

No se requieren dependencias externas.

## Arranque local

1. Generar datos:

```bash
python scraper.py laliga hybrid
# o:
python scraper.py all hybrid
```

2. Arrancar servidor:

```bash
python server.py
```

3. Abrir en navegador:

- `http://localhost:8000/`
- Healthcheck: `http://localhost:8000/health`

## Variables de entorno

- `PORT` (por defecto `8000`)
- `HOST` (por defecto `0.0.0.0`)

Ejemplo:

```bash
PORT=9000 HOST=0.0.0.0 python server.py
```

## Estructura principal

- `app.html`: UI y lógica de visualización/mercados.
- `scraper.py`: ingesta/generación de `data.json`.
- `engine/data_sources/espn_scraper.py`: fuente base ESPN.
- `engine/data_sources/sofascore_scraper.py`: scraper directo de SofaScore por API JSON.
- `engine/data_sources/hybrid_scraper.py`: mezcla ESPN + SofaScore.
- `server.py`: servidor estático + endpoint de healthcheck.
- `data.json`: dataset generado por scraper.
