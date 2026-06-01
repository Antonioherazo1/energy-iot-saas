# Energy IoT SaaS Backend

Backend inicial para una plataforma SaaS industrial de monitoreo electrico IoT.

## Objetivo de esta base

- FastAPI modular.
- PostgreSQL con SQLAlchemy.
- JWT access + refresh tokens.
- Organizaciones, usuarios, dispositivos y telemetria.
- MQTT ingestion preparado para Mosquitto.
- WebSockets para tiempo real.
- Bajo consumo de RAM para EC2 pequena.

## Comandos locales

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## Comandos Docker

```powershell
docker compose up -d --build
```

API local:

- http://localhost:8000/docs
- http://localhost:8000/api/v1/health

