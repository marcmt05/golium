# Golium

Web privada de análisis futbolístico para uso personal.

## Flujo objetivo (local -> estático)
1. Ejecutas scraping y motor local en Python.
2. El motor genera JSON finales en `public-data/`.
3. El frontend **solo renderiza** esos JSON (no recalcula modelo).
4. Subes al repo y Cloudflare publica la web estática.

## Stack actual (sin reescritura)
- Frontend: HTML + JavaScript vanilla.
- Motor local: Python 3.11.
- Persistencia: JSON (`public-data/` + `history/snapshots/`).
- Publicación: GitHub + Cloudflare.

---

## Ejecución local

### 1) Generar dataset base
```bash
python scraper.py all
```

### 2) Ejecutar pipeline local (modelo + picks + métricas + snapshot)
```bash
python run_pipeline.py --config engine_config.json
```

Esto genera:
- `public-data/data.json`
- `public-data/picks.json`
- `public-data/metrics.json`
- `public-data/model-info.json`
- `history/snapshots/<snapshot_id>/{data.json,picks.json,metrics.json,model-info.json,ledger.json}`

### 3) (Opcional) liquidar picks históricos cuando haya resultados finales
```bash
python settle_picks.py --history-dir history/snapshots --results public-data/data.json
```

### 4) (Opcional) recalcular backtest sobre último snapshot
```bash
python backtest_runner.py --history-dir history/snapshots
```

### 5) Levantar web local
```bash
python server.py
```
Abre `http://localhost:8000/app.html`.

---

## Convenciones importantes

### Tipos de pick
- `model_pick`: no hay cuotas reales integradas (`offered_odds = null`).
- `value_bet`: sí hay cuota real (`offered_odds_is_real = true`) y se calcula edge/EV real.

### Taxonomía de mercados (única)
- `1`, `X`, `2`
- `O2.5`, `U2.5`
- `O3.5`, `U3.5`
- `BTTS_Y`, `BTTS_N`
- `AH_HOME_-0.5`, `AH_AWAY_-0.5`

---

## Scripts principales
- `run_pipeline.py`: ejecuta todo y guarda snapshot histórico.
- `export_public_data.py`: atajo para exportar data pública + snapshot.
- `settle_picks.py`: settlement real de picks históricos.
- `backtest_runner.py`: métricas de backtest sobre picks.

---

## Nota de compatibilidad
- No se rehízo UI ni se cambió framework frontend.
- Se mantiene flujo GitHub + Cloudflare.
- El frontend no ejecuta Poisson/Dixon-Coles/lambdas/EV/Kelly del modelo.
- `scraper_legacy.py` se mantiene como fallback legado.
