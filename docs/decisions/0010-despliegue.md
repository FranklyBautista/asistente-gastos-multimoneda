# 0010. Despliegue del bot en Railway con webhook

- **Estado:** aceptada
- **Fecha:** 2026-11-03

## Contexto

Hasta la Fase 8 el bot solo corría en la laptop, en modo polling. Para usarlo a diario y mostrarlo tiene que correr siempre, con la base de datos en Supabase (nube) y sin gastar más cuota del LLM de la que da el plan gratuito.

## Decisión

### Plataforma: Railway con un Dockerfile

- **Railway** (plan Hobby) corre el bot como un servicio siempre encendido. Render en su plan gratis duerme el servicio tras 15 minutos sin tráfico, y con eso se pierden el refresco de tasas y el resumen del domingo, que corren dentro del proceso (APScheduler, ADR 0008). Fly.io pide tarjeta y más configuración para lo mismo.
- **Imagen propia (`bot/Dockerfile`)** en vez del builder automático: la misma imagen se construye en el CI (job `image`) y en local (`.\tasks.ps1 image`), con `uv sync --locked`, dependencias de desarrollo fuera y usuario sin privilegios.
- **Sin `railway.toml`.** El "config as code" de Railway está obsoleto y deja de leerse el 2026-12-01. Su reemplazo (`.railway/railway.ts`) todavía no cubre Dockerfiles ni el tiempo de drenado. Los pocos ajustes del servicio (directorio raíz, healthcheck, variables) quedan documentados en `docs/DESPLIEGUE.md`.

### Webhook en producción, polling en local

- Con `WEBHOOK_URL` el bot registra el webhook en Telegram y sirve HTTP con FastAPI y uvicorn. Sin ella, usa polling como hasta ahora. Un solo `main.py` y la misma configuración (`Settings`).
- **Secreto obligatorio.** `WEBHOOK_SECRET` (16 a 256 caracteres) viaja en la cabecera `X-Telegram-Bot-Api-Secret-Token` y se compara en tiempo constante. Sin él, cualquiera que conozca la URL podría mandar updates falsos con el `telegram_id` de la lista blanca. `Settings` no arranca con webhook sin secreto ni con una URL que no sea `https://`.
- **Respuesta inmediata.** Un mensaje tarda 5 a 15 s por el LLM y Telegram reintenta si no recibe respuesta a tiempo, lo que duplicaría movimientos. El update se procesa en una tarea aparte y se responde 200 al instante.
- **Apagado ordenado.** Cada redespliegue manda SIGTERM. El servidor deja de aceptar updates y espera hasta 20 s a los que están en curso (`DRAIN_SECONDS`); luego `main()` cierra el scheduler, la sesión del bot y el pool. uvicorn vuelve a lanzar la señal al salir, lo que mataría el proceso antes de ese cierre, así que `WebhookServer` no lo hace. Railway debe dar al menos ese tiempo antes del SIGKILL: `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=25`.
- **El webhook no se borra al apagar:** en un redespliegue la instancia nueva ya lo está usando. Por lo mismo, el modo polling no lo borra: si el token tiene un webhook activo, el bot local se niega a arrancar y pide usar otro bot de desarrollo.
- `/health` responde 200 si la base de datos contesta (`select 1`) y 503 si no. Railway lo usa para no mandar tráfico a una versión que no arrancó bien. No hay `/docs` ni `/openapi.json`.

### Límite de mensajes

- 20 mensajes por minuto y por persona (`RATE_LIMIT_PER_MINUTE`), con una ventana deslizante en memoria. Cada mensaje de texto puede costar una llamada a Gemini, y el plan gratuito tiene un límite por minuto y por día. Los botones no cuentan: no llaman al LLM.
- Al pasarse, el bot avisa una vez por ventana («no anoté ese mensaje») y luego ignora en silencio, para no gastar llamadas a Telegram.

### Base de datos en la nube

- Las migraciones se aplican con `supabase db push`; el seed de desarrollo no se carga en la nube.
- El bot se conecta por el **pooler de sesión** de Supabase (IPv4, puerto 5432). La conexión directa solo tiene IPv6 en el plan gratuito. El pool ya desactiva los prepared statements, así que también funcionaría con el pooler en modo transacción.
- Todas las tablas tienen RLS activo sin políticas: la anon key no lee nada. El bot entra como dueño de las tablas y se la salta; las políticas por dueño llegan con la web (Fase 9).

## Consecuencias

- **Una sola instancia.** El límite de mensajes, las aclaraciones pendientes (30 min) y el scheduler viven en memoria. Con dos réplicas el límite sería por réplica y una respuesta a un botón podría caer en la réplica que no tiene la aclaración. Un redespliegue borra las aclaraciones en curso: el usuario tendría que volver a escribir el mensaje.
- Durante el solapamiento de un redespliegue corren dos instancias unos segundos. El resumen semanal no se duplica porque se reserva en `weekly_summaries` antes de enviarse (ADR 0008); un refresco de tasas de más no hace daño.
- Si Telegram reenvía un update (por ejemplo, si el servidor se cayó justo después de recibirlo), puede anotarse dos veces. Sigue pendiente la idempotencia por `message_id` (guía de arquitectura, sección 4).
- Railway cobra por uso: el bot entra en los 5 USD mensuales del plan Hobby.
- Desarrollo y producción necesitan bots distintos (dos tokens de @BotFather).
