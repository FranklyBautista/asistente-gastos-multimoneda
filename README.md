# Gastos multimoneda

Bot de Telegram que registra gastos e ingresos escritos en lenguaje natural ("gasté 15 en el almuerzo") en su moneda original: bolívares, pesos colombianos, dólares o USDT.
Guarda cada movimiento con la tasa del momento, responde preguntas sobre tus finanzas y envía un resumen semanal.
Una app web (en desarrollo) muestra todo centralizado.

> Estado: **Fase 0**, esqueleto del proyecto y CI. Ver [`docs/STACK_Y_ARQUITECTURA.md`](docs/STACK_Y_ARQUITECTURA.md).

## Arquitectura

```mermaid
flowchart LR
  U["Usuario en Telegram"] --> H["chat: handlers"]
  H --> S["services"]
  S --> E["extraction + llm"]
  S --> D["db: repositorios"]
  S --> DOM["domain: reglas puras"]
  J["jobs: scheduler"] --> S
  R["rates: APIs externas"] --> S
  D --> PG[("Postgres en Supabase")]
  W["web (Fase 9)"] --> PG
```

Cada capa solo importa de las que están por debajo; `import-linter` lo verifica en el CI.

## Desarrollo

Requisitos: Git, Docker Desktop, [uv](https://docs.astral.sh/uv/) y [Supabase CLI](https://supabase.com/docs/guides/cli). Las tareas comunes están en `tasks.ps1` (PowerShell, Windows).

```powershell
Copy-Item bot\.env.example bot\.env   # rellena los valores
.\tasks.ps1 setup                     # instala dependencias del bot
.\tasks.ps1 hooks                     # instala pre-commit (ruff + gitleaks)
.\tasks.ps1 db-up                     # levanta Supabase local (requiere Docker)
.\tasks.ps1 check                     # lint, tipos, capas, pruebas y pgTAP
```

Supabase local usa los puertos 553xx (base de datos en `127.0.0.1:55322`) para convivir con otros proyectos que usen los puertos por defecto.

## Estructura

| Carpeta | Contenido |
|---|---|
| `bot/` | Bot en Python (aiogram, FastAPI, psycopg) |
| `supabase/` | Migraciones, seed y pruebas pgTAP; fuente de verdad del esquema |
| `docs/` | Guía de arquitectura y decisiones (ADR) |
| `web/` | App web en Next.js (Fase 9) |

## Licencia

MIT
