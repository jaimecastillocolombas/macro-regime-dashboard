# macro-regime-dashboard

Dashboard macroeconómico que se actualiza solo (tipos, bonos, inflación, mercados, noticias) y una estrategia de inversión que usa sus señales para rotar entre activos. Es un proyecto de portfolio para prácticas en finanzas, consultoría tecnológica y datos (riesgos, BCG X, IBM, PE), así que pesa más la calidad y la claridad que la cantidad de funcionalidades.

## Cómo trabajamos

- **Jaime tiene que poder defender cada línea en una entrevista.** Antes de escribir algo no trivial, explica el enfoque y por qué. Tras cada cambio, resume qué hace y qué alternativas descartaste.
- **Trabaja en pasos pequeños.** Haz un cambio lógico por commit, con mensajes en inglés siguiendo Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- **Pregunta antes** de añadir una dependencia nueva, cambiar la arquitectura o el modelo de datos, o tocar la lógica del backtest.
- **Ejecuta y comprueba siempre.** No des por hecho que una descarga o un gráfico funcionan: ejecútalo, mira el resultado y enséñalo.
- **La lógica de la estrategia (fase 3) la propones y la explicas, y Jaime la revisa línea a línea.** No la escribas entera de golpe.
- **Idioma:** la conversación es en español. El código, los comentarios, los docstrings, el README y los commits van en inglés.
- Si algo de este archivo deja de ser cierto, propón actualizarlo.

## Stack

- Python 3.11 o superior, pandas, requests
- SQLAlchemy con `DATABASE_URL`: SQLite en local por defecto y Postgres (Supabase) en producción
- Streamlit + Plotly para el dashboard, desplegado en Streamlit Community Cloud
- GitHub Actions (cron) para la ingesta programada
- pytest, ruff (lint y formato) y python-dotenv
- Dependencias en `requirements.txt`, con versiones fijadas

## Estructura

```
macro-regime-dashboard/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example            # nombres de las variables, nunca valores reales
├── pyproject.toml          # configuración de ruff y pytest
├── .github/workflows/
│   ├── ingest.yml          # ingesta programada
│   └── ci.yml              # ruff + pytest en cada push
├── src/
│   ├── config.py           # catálogo de series y variables de entorno
│   ├── db.py               # conexión, creación de tablas y upsert
│   ├── ingest/
│   │   ├── http.py         # sesión con timeout y reintentos, común a todas las fuentes
│   │   ├── availability.py # available_at: retrasos y calendarios de festivos por fuente
│   │   ├── fred.py
│   │   ├── ecb.py
│   │   ├── ine.py
│   │   └── run.py          # punto de entrada: `python -m src.ingest.run`
│   ├── transform/
│   │   ├── series.py       # funciones puras: spread, yoy, as_of
│   │   └── derived.py      # catálogo de series derivadas, calculadas al leer
│   └── strategy/           # fase 3
├── app/
│   └── streamlit_app.py
├── tests/
│   └── fixtures/           # respuestas de API guardadas
└── notebooks/              # solo exploración, nunca lógica de producción
```

## Modelo de datos

**`series`** guarda los metadatos de cada serie: `series_id`, `source`, `name`, `unit`, `frequency`, `country` y `publication_lag_days`.

**`observations`** guarda los datos:

- `series_id`
- `date`: fecha de referencia del dato (el mes o día al que corresponde)
- `value`
- `available_at`: fecha en que el dato se conoció públicamente
- `retrieved_at`: fecha en que lo descargamos

La clave es (`series_id`, `date`) y la escritura se hace con upsert.

**`date` y `available_at` no se mezclan nunca.** Cualquier señal o backtest filtra por `available_at` para evitar el look-ahead bias:

- **FRED, series mensuales:** `value` es la vintage actual y `available_at` es la fecha de la primera publicación (`realtime_start` con `output_type=4` de ALFRED). Para fechas anteriores a las vintages se usa `publication_lag_days`. El look-ahead residual está medido: el IPC sin desestacionalizar casi no se revisa (subyacente: 3,4 % de los valores, máximo 0,2 puntos del índice).
- **FRED, series diarias** (tipos, 5y5y): tienen miles de vintages y no se revisan, así que `available_at` = fecha + `publication_lag_days` días hábiles.
- **BCE e INE:** no guardan historial de publicaciones, así que `available_at = min(fecha + publication_lag_days, día de descarga)`. El histórico recibe el retraso conservador (documentado en `config.py` con su fuente) y, desde la primera ingesta programada, los datos nuevos reciben el día en que se vieron. Las series diarias del BCE usan días hábiles del calendario TARGET2.
- **Series derivadas** (interanuales del IPC de EE. UU., pendiente del euro, prima ES-DE): se calculan al leer, no se guardan. Su `available_at` es el máximo del de sus componentes, así que filtrar la derivada por `available_at <= t` equivale a calcularla con las componentes filtradas en t. Los spreads 10Y-2Y y 10Y-3M de EE. UU. no se derivan: se usan `T10Y2Y` y `T10Y3M` de FRED.

## Fuentes de datos (fase 1)

Verifica cada identificador de serie contra la fuente antes de darlo por bueno.

**FRED** (`https://api.stlouisfed.org/fred/`). Requiere `FRED_API_KEY`, que es gratuita.
- Tipos y curva: `DGS3MO`, `DGS2`, `DGS10`, `T10Y2Y`, `T10Y3M`
- Inflación: `CPIAUCNS` (general) y `CPILFENS` (subyacente), **sin desestacionalizar**. La tasa interanual no lo necesita y es la cifra oficial de la BLS. Las versiones desestacionalizadas (`CPIAUCSL`, `CPILFESL`) se descartaron porque el 88–91 % de su histórico se ha revisado. Son índices, así que la tasa interanual se calcula en `transform/`.
- Expectativas de inflación: `T5YIFR` (5y5y forward)

**BCE Data Portal** (`https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata`). No requiere clave.
- Curva AAA de la zona euro: dataset `YC`, por ejemplo `YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`, con plazos de 3M a 30Y. Se publica cada día hábil hacia las 12:00 CET.
- IPCA de la zona euro: `HICP/M.U2.N.000000.4D0.ANR` (general) y `HICP/M.U2.N.XEF000.4D0.ANR` (subyacente)
- IPCA de España: `HICP/M.ES.N.000000.4D0.ANR`
- El dataset antiguo `ICP` está congelado desde diciembre de 2025; el IPCA se publica ahora en `HICP` con proveedor `4D0`.
- El cortafuegos del portal bloquea ráfagas de peticiones y consultas con comodines (página HTML con código 400): se pide una serie cada vez, con pausa entre peticiones.
- Facilidad de depósito: `FM/D.U2.EUR.4F.KR.DFR.LEV`
- Prima de riesgo España-Alemania (mensual): tipos a largo plazo del dataset `IRS` para ES y DE

**INE** (API JSON en `servicios.ine.es/wstempus/js/ES/`). IPC de España en tasa anual, base 2025:
- General: `IPC290750`; subyacente (sin alimentos no elaborados ni productos energéticos): `IPC292510`.
- Los códigos de la base 2021 (`IPC251856`...) están congelados desde diciembre de 2025.
- El periodo se construye con `Anyo` y `FK_Periodo`: `Fecha` es un epoch en hora de Madrid y falta antes de 1970.
- El último mes suele ser el dato adelantado (`FK_TipoDato` 3). Si el definitivo difiere, el upsert lo trata como revisión.
- Un código inexistente devuelve HTTP 200 con el cuerpo vacío, y se trata como error.

## Reglas de ingeniería

- **Ingesta idempotente:** ejecutarla dos veces no duplica nada.
- **Robustez:** cada petición lleva timeout y reintentos con backoff. Si una fuente falla, las demás siguen, y `run.py` termina con un resumen (series actualizadas, filas nuevas, errores).
- **Secretos:** ninguna clave en el código ni en el historial de git. En local van en `.env` (incluido en `.gitignore`), en CI como GitHub Secrets y en la app como Streamlit secrets.
- **Tests:** usan las respuestas guardadas en `tests/fixtures/` y nunca llaman a APIs reales en CI. Prioriza tests de parsing, de transformaciones y de no duplicación en el upsert.
- **Unidades:** los tipos de interés y la inflación se guardan en porcentaje. La unidad de cada serie queda registrada en la tabla `series`.
- Escribe funciones pequeñas y puras para las transformaciones, con type hints en todo `src/`.

## Reglas para la estrategia (fases 3 y 4)

- Las señales usan solo datos con `available_at <= t`. La señal se calcula al cierre de t y se ejecuta en t+1.
- Se incluyen costes de transacción y se reporta la rotación de la cartera.
- La validación es walk-forward: nunca se optimizan parámetros sobre el periodo completo.
- El benchmark es una cartera 60/40 y buy & hold de renta variable.
- Las métricas son CAGR, volatilidad, Sharpe, drawdown máximo y turnover.
- Si el Sharpe sale por encima de 1,5, sospecha y busca el error antes de celebrarlo.

## Hoja de ruta

### Fase 1: bonos e inflación, desplegado (EN CURSO)

- [x] Esqueleto del repo: `requirements.txt`, `.gitignore`, `.env.example`, ruff, pytest y `ci.yml`
- [x] `db.py`: tablas `series` y `observations` con upsert
- [x] Ingesta FRED con tests
- [x] Ingesta BCE con tests
- [x] Ingesta INE con tests
- [x] `run.py` con el resumen final
- [x] Transformaciones: tasas interanuales, spreads 10Y-2Y y 10Y-3M de EE. UU., pendiente de la curva euro y prima de riesgo ES-DE
- [ ] Página *Rates & Bonds* del dashboard:
  - curva actual frente a hace 1 mes y 1 año (EE. UU. y euro)
  - histórico del spread con los periodos de inversión sombreados
  - prima de riesgo
- [ ] Página *Inflation* del dashboard:
  - general frente a subyacente para España, zona euro y EE. UU., con línea del 2 %
  - expectativas 5y5y
- [ ] Cabecera con la fecha de la última actualización de cada fuente
- [ ] `ingest.yml`: cron diario en UTC, posterior a la publicación del BCE, más `workflow_dispatch` para lanzarlo a mano
- [ ] Postgres en Supabase y despliegue en Streamlit Community Cloud
- [ ] README v1: el problema, una captura, el enlace a la demo, un diagrama de arquitectura en Mermaid, las fuentes y cómo ejecutarlo en local

La fase 1 está terminada cuando hay una demo pública que se actualiza sola cada día y un README que se entiende en 30 segundos.

### Fase 2: mercados y noticias

- Índices, divisas, materias primas y VIX desde Finnhub (plan gratuito, uso personal, unas 60 llamadas por minuto)
- Feed de noticias filtrado, con el sentimiento calculado por nosotros con FinBERT (`ProsusAI/finbert`), porque el sentimiento de Finnhub es de pago
- Indicador agregado de sentimiento diario en el dashboard

### Fase 3: backtest de la estrategia de rotación por régimen

- Se definen regímenes a partir de las señales de la fase 1 (curva, inflación y su tendencia) y del momentum
- La estrategia asigna pesos entre renta variable, bonos, oro y liquidez mediante ETFs
- La fuente de precios históricos está por decidir: el plan gratuito de Finnhub no incluye velas históricas

### Fase 4: paper trading

- La estrategia se ejecuta en la cuenta de paper trading de Alpaca (gratuita y abierta fuera de EE. UU.)
- El dashboard muestra la cartera y el P&L en vivo frente al benchmark

## Comandos

```bash
pip install -r requirements.txt
python -m src.ingest.run              # ejecutar la ingesta
streamlit run app/streamlit_app.py    # arrancar el dashboard en local
pytest                                # tests
ruff check . && ruff format .         # lint y formato
```

## Cosas a vigilar

- GitHub desactiva los workflows programados de los repos públicos tras 60 días sin actividad. Hay que hacer algún commit de vez en cuando.
- Comprueba que el plan gratuito de Supabase no pause el proyecto por inactividad.
- La app de Streamlit Community Cloud se duerme tras un tiempo sin visitas. Por eso el README lleva capturas, por si un reclutador la encuentra dormida.
