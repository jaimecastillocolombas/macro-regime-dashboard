# macro-regime-dashboard

Self-updating macro dashboard (rates, bonds, inflation) and a regime-rotation strategy built on its signals.

> Work in progress: phase 1 (bonds and inflation). The full README comes with the first deploy.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # then add your FRED_API_KEY
pytest
```
