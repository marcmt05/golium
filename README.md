# Golium

Web de análisis de partidos y detección de **value bets** para fútbol, basada en datos scrapeados y modelo Poisson/Dixon-Coles ya existente.

## Características

- Análisis de fixtures con mercados:
  - 1X2
  - Over/Under 2.5
  - Over/Under 3.5
  - BTTS
  - Handicap asiático visualizado en líneas: **Local -0.5 / Local +0.5 / Visita -0.5 / Visita +0.5**
- Ranking y forma de equipos.
- Módulo de combinada sugerida con filtro de EV y control de margen.
- Interfaz limpia enfocada a analítica/apuestas informativas.

> Este proyecto **no** incluye autenticación ni base de datos.

---

## Requisitos

- Python 3.10+

No se requieren dependencias externas (solo librería estándar).

---

## Arranque local

1. Generar datos:

```bash
python scraper.py laliga
# o: python scraper.py all
```

2. Ejecutar motor local (predicciones + picks + métricas):

```bash
python run_pipeline.py --config engine_config.json
```

Esto genera:
- `public-data/data.json`
- `public-data/picks.json`
- `public-data/metrics.json`
- `public-data/model-info.json`

3. Arrancar servidor:

```bash
python server.py
```

4. Abrir en navegador:

- `http://localhost:8000/`
- Healthcheck: `http://localhost:8000/health`

---

## Variables de entorno

- `PORT` (por defecto `8000`)
- `HOST` (por defecto `0.0.0.0`)

Ejemplo:

```bash
PORT=9000 HOST=0.0.0.0 python server.py
```

---

## Despliegue

### Render

Este repo incluye `render.yaml` y `Procfile`.

Pasos rápidos:

1. Crear servicio Web en Render apuntando al repo.
2. Render detecta `render.yaml`.
3. Comando de arranque: `python server.py`.

### Railway

1. Crear proyecto desde el repo.
2. Configurar variable `PORT` si la plataforma no la inyecta automáticamente.
3. Start command: `python server.py`.

### Docker

Construir imagen:

```bash
docker build -t golium .
```

Ejecutar:

```bash
docker run --rm -p 8000:8000 golium
```

---

## Estructura principal

- `app.html`: UI y lógica de visualización/mercados.
- `scraper.py`: ingesta/generación de `data.json`.
- `server.py`: servidor estático + endpoint de healthcheck.
- `data.json`: dataset de fixtures generado por scraper.
- `engine/`: motor local Python (features, modelos, betting, validación).
- `public-data/`: JSON finales para la web estática.


## Cambios recientes
- Añadido `worldcup` (`fifa.world`) para mostrar el **Mundial 2026**.
- Añadidos `AH Visita -0.5` y `AH Local +0.5`.
- Corregido `AH Visita +0.5` para que use la condición correcta (**visita o empate**).
- Eliminados los mercados `AH Local -1.5`, `AH Visita +1.5` y tarjetas.
- Añadido `Over/Under 3.5 goles`.


## Refactor fase 1 aplicado

Cambios ya aplicados en este zip:

- `app.html` deja de llevar el motor inline y pasa a cargar scripts externos.
- `app.js` se mantiene como bundle de compatibilidad, pero la fuente real queda separada en `js/`.
- Nueva separación por responsabilidades:
  - `js/state.js`
  - `js/utils.js`
  - `js/data.js`
  - `js/model.js`
  - `js/render.js`
  - `js/combinada.js`
  - `js/main.js`
- Eliminado el fallback aleatorio de forma (`Math.random`) para que el modelo sea reproducible.
- Añadido `storage.py` + `save_snapshot.py` para empezar a persistir snapshots en SQLite (`golium.db`).
- Añadido endpoint `GET /api/snapshots` para inspeccionar los últimos snapshots guardados.

### Guardar un snapshot en SQLite

```bash
python save_snapshot.py
```

### Ver snapshots

```bash
http://localhost:8000/api/snapshots
```


## Scraper integrado

El scraper principal (`scraper.py`) ahora integra el enfoque combinado ESPN + Understat + FBref del archivo aportado por el usuario. fileciteturn0file0

- `scraper.py`: scraper principal actual, compatible con la estructura de `data.json` que espera la app.
- `combined_scraper.py`: copia del scraper aportado, guardada como referencia.
- `scraper_legacy.py`: antiguo scraper del proyecto, conservado como fallback y para `quiniela`.

### Uso

```bash
python scraper.py laliga
python scraper.py all
python scraper_legacy.py quiniela
```

### Nota

La integración mantiene el shape del frontend actual, pero el enriquecimiento xG depende de la disponibilidad real de Understat y FBref para cada equipo/competición.
