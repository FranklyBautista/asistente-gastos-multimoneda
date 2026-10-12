# 0001. Stack del proyecto

- **Estado:** aceptada
- **Fecha:** 2026-10-12

## Contexto

El proyecto es un bot de Telegram que registra gastos en lenguaje natural en cuatro monedas (VES, COP, USD y USDT), más una app web para verlo todo centralizado. Se desarrolla en solitario, con planes gratuitos, y sirve como pieza de portfolio.

## Decisión

- **Bot:** Python 3.12, uv, aiogram 3, FastAPI (solo webhook y `/health`), Pydantic v2 y pydantic-settings.
- **Datos:** Postgres en Supabase, con psycopg 3 async y SQL explícito; migraciones con la Supabase CLI y pruebas con pgTAP.
- **LLM:** Gemini Flash como principal y Groq como alternativa, detrás de una interfaz `LLMClient` propia.
- **Tareas programadas:** APScheduler 3.x dentro del proceso del bot.
- **Calidad:** ruff, pyright, pytest e import-linter; CI en GitHub Actions; gitleaks en pre-commit.
- **Web (Fase 9):** Next.js, Tailwind, Recharts y `@supabase/ssr`, desplegada en Vercel.

Detalle completo y alternativas descartadas en `docs/STACK_Y_ARQUITECTURA.md`.

## Consecuencias

- Las transacciones de varias tablas (un cambio de moneda toca dos cuentas) son triviales con psycopg; a cambio, el SQL se escribe y se prueba a mano.
- El bot usa credenciales de servicio que se saltan la RLS: cada repositorio filtra por `user_id` sin excepción.
- APScheduler dentro del proceso obliga a mantener una sola instancia del bot.
- Cambiar de proveedor de LLM solo requiere un adaptador nuevo en `llm/`.
