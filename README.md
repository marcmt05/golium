# Golium

Pipeline local de predicción deportiva con export JSON estático para frontend (GitHub + Cloudflare).

## Objetivo operativo

1. Ejecutas el motor Python en local.
2. Se generan JSON finales en `public-data/`.
3. El frontend solo renderiza esos JSON (sin cálculo probabilístico crítico).
4. Opcionalmente se guarda snapshot histórico por ejecución.
5. Publicas el repo y Cloudflare muestra los datos.

## Arquitectura actual

- `engine/`: modelado, mercados, picks, métricas.
- `run_pipeline.py`: ejecuta pipeline completo y exporta `public-data/*.json`.
- `history/snapshots/<snapshot_id>/`: copia versionada de cada corrida (`data.json`, `picks.json`, `metrics.json`, `model-info.json`, `ledger.json`).
- `settle_picks.py`: liquida picks históricos contra resultados finales disponibles en snapshots.
- `js/`: frontend de render.

## Distinción de picks

### Sin cuotas reales
- Se generan picks con `pick_type = "model_pick"`.
- `offered_odds = null`, `offered_odds_is_real = false`.
- No se etiqueta como value bet.

### Con cuotas reales
- Se generan `pick_type = "value_bet"`.
- Incluye `edge`, `ev`, `stake_fraction`.
- `offered_odds_is_real = true`.

## Taxonomía única de mercados

Usada en engine + JSON + frontend + settlement:

- `1`
- `X`
- `2`
- `O2.5`
- `U2.5`
- `O3.5`
- `U3.5`
- `BTTS_Y`
- `BTTS_N`
- `AH_HOME_-0.5`
- `AH_AWAY_-0.5`

## Requisitos

- Python 3.10+

Instalación:

```bash
pip install -r requirements.txt
```

## Ejecución local

### 1) Generar/actualizar dataset base

```bash
python scraper.py laliga
# o
python scraper.py all
```

### 2) Ejecutar pipeline principal

```bash
python run_pipeline.py --config engine_config.json
```

Salida:

- `public-data/data.json`
- `public-data/picks.json`
- `public-data/metrics.json`
- `public-data/model-info.json`
- `history/snapshots/<snapshot_id>/...`

### 3) Liquidar picks históricos

```bash
python settle_picks.py
```

Opcional: sincronizar último snapshot a `public-data/`:

```bash
python settle_picks.py --sync-public
```

### 4) Recalcular métricas rápidas desde `public-data/picks.json`

```bash
python backtest_runner.py
```

### 5) Levantar frontend local

```bash
python server.py
```

Abrir: `http://localhost:8000/`

## Qué hace `settle_picks.py`

- Recorre `history/snapshots/*`.
- Marca picks `open -> settled` cuando el fixture ya está finalizado.
- Soporta settlement para:
  - `1`, `X`, `2`
  - `O2.5`, `U2.5`
  - `O3.5`, `U3.5`
  - `BTTS_Y`, `BTTS_N`
  - `AH_HOME_-0.5`, `AH_AWAY_-0.5`
- Recalcula `profit_units` y reescribe:
  - `picks.json`
  - `ledger.json`
  - `metrics.json`

## Métricas incluidas

`metrics.json` incorpora:

- total picks
- settled picks
- yield / ROI
- hit rate
- average edge
- average EV
- average profit
- Brier score
- log loss

Agrupaciones:

- por mercado
- por liga
- por bucket de cuotas (`1.00-1.49`, `1.50-1.99`, `2.00-2.49`, `2.50+`, `N/A`)
- por bucket de edge (`0-1.99%`, `2-3.99%`, `4-5.99%`, `6%+`, `N/A`)
- por `pick_type`

## Notas de reproducibilidad

- El frontend no ejecuta Poisson/Dixon-Coles ni Kelly real.
- El motor Python es la única fuente de verdad para probabilidades/mercados.
- Si faltan cuotas reales, se etiqueta explícitamente como `model_pick`.
