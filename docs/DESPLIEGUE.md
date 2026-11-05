# Despliegue del bot

El bot corre en **Railway** (imagen de `bot/Dockerfile`, modo webhook) y la base de datos en **Supabase** (nube). Las decisiones están en el [ADR 0010](decisions/0010-despliegue.md).

```mermaid
flowchart LR
  T["Telegram"] -- "POST /telegram/webhook<br/>(cabecera con el secreto)" --> R["Railway: bot<br/>FastAPI + aiogram + APScheduler"]
  R -- "pooler de sesión :5432" --> S[("Supabase Postgres")]
  R --> G["Gemini"]
  R --> A["APIs de tasas"]
  RW["Healthcheck de Railway"] -- "GET /health" --> R
```

Pasos en orden: bot de desarrollo → base de datos → Railway → verificación. Se hacen una sola vez; después, cada merge a `main` redespliega solo.

## 1. Un bot para desarrollo

Con el webhook activo, un token ya no puede usarse en polling. `@frankly_gastos_bot` pasa a ser el de producción y para la laptop se crea otro:

1. En Telegram, con [@BotFather](https://t.me/BotFather): `/newbot`, por ejemplo `frankly_gastos_dev_bot`.
2. Pon su token en `TELEGRAM_BOT_TOKEN` de `bot\.env` (local). El token de producción solo va en Railway.

Si un día corres `.\tasks.ps1 run` con el token de producción, el bot se niega a arrancar en vez de quitarle el webhook a Railway.

## 2. Base de datos en Supabase

1. Crea un proyecto en [supabase.com](https://supabase.com/dashboard) (plan gratuito). Elige la región **East US (North Virginia)**, la misma que el servicio de Railway, y guarda la contraseña de la base de datos.
2. Aplica las migraciones desde la raíz del repositorio:

   ```powershell
   supabase login
   supabase link --project-ref <ref-del-proyecto>   # el ref está en la URL del panel
   supabase db push                                 # aplica supabase/migrations; el seed no se carga
   supabase migration list                          # local y remoto deben coincidir
   ```

3. Copia la cadena de conexión en **Connect → Connection string → Session pooler**. Tiene esta forma:

   ```text
   postgresql://postgres.<ref>:<contraseña>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```

   Usa el **pooler de sesión**, no la conexión directa (`db.<ref>.supabase.co`): en el plan gratuito la directa solo tiene IPv6. Si la contraseña tiene caracteres como `@`, `:` o `/`, escríbelos codificados (`%40`, `%3A`, `%2F`).

Todas las tablas tienen RLS activo sin políticas, así que la anon key no puede leer nada. El bot entra como dueño de las tablas.

## 3. Servicio en Railway

1. En [railway.com](https://railway.com): **New Project → Deploy from GitHub repo** y elige `asistente-gastos-multimoneda`. El primer intento fallará porque faltan las variables; es normal.
2. En el servicio, **Settings**:

   | Ajuste | Valor |
   |---|---|
   | Source → Root Directory | `/bot` (Railway encuentra el `Dockerfile` solo) |
   | Source → Branch | `main` |
   | Build → Watch Paths | `/bot/**` (los cambios en `docs/` o `supabase/` no redespliegan) |
   | Networking → Generate Domain | puerto `8080` |
   | Deploy → Healthcheck Path | `/health` |
   | Deploy → Region | US East (cerca de Supabase) |
   | Deploy → Replicas | `1` (el scheduler y el límite de mensajes viven en memoria) |

3. En **Variables → Raw Editor** pega esto y rellena los valores:

   ```env
   ENV=prod
   TELEGRAM_BOT_TOKEN=<token de @frankly_gastos_bot>
   ALLOWED_TELEGRAM_IDS=[<tu id de Telegram>]
   DATABASE_URL=<cadena del pooler de sesión>
   GEMINI_API_KEY=<llave de AI Studio>
   WEBHOOK_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}
   WEBHOOK_SECRET=<ver abajo>
   PORT=8080
   RAILWAY_DEPLOYMENT_DRAINING_SECONDS=25
   ```

   - `WEBHOOK_SECRET`: genera uno con `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"` (desde `bot\`). No hace falta guardarlo en ningún otro lado.
   - `WEBHOOK_URL`: Railway reemplaza `${{RAILWAY_PUBLIC_DOMAIN}}` por el dominio generado en el paso 2. Si no lo resuelve, pega el dominio a mano (`https://<servicio>.up.railway.app`, sin barra final).
   - `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=25`: en cada redespliegue el bot espera hasta 20 s a los mensajes que está procesando; sin esto Railway lo mataría antes.
   - Opcionales, con su valor por defecto: `RATE_LIMIT_PER_MINUTE=20`, `WEEKLY_SUMMARY_HOUR=18`, `RATES_REFRESH_MINUTES=60`, `GEMINI_MODELS`.

4. **Deploy.** Railway construye la imagen, arranca el bot y espera a que `/health` responda 200 antes de mandarle tráfico.

## 4. Verificación

1. En **Deployments → View logs** deben aparecer `bot_started` con `"mode": "webhook"` y, segundos después, `rates_refreshed`.
2. Comprueba que Telegram llega al webhook (en PowerShell, con el token de producción):

   ```powershell
   $token = Read-Host "Token de producción"
   Invoke-RestMethod "https://api.telegram.org/bot$token/getWebhookInfo" | Select-Object -ExpandProperty result
   ```

   `url` debe terminar en `/telegram/webhook`, `pending_update_count` en 0 y sin `last_error_message`.
3. `https://<dominio>/health` en el navegador debe responder `{"status":"ok"}`.
4. En Telegram, con `@frankly_gastos_bot`: `/start` (la base de datos de la nube está vacía, así que el onboarding empieza de nuevo), `/tasas`, «gasté 70 bs en pasaje», «eso fue comida» y `/resumen`.

## Operación

- **Redespliegue:** cada push a `main` que toque `bot/` construye y despliega una versión nueva. La anterior sigue atendiendo hasta que la nueva pasa el healthcheck.
- **Volver a una versión anterior:** en Deployments, el menú de un despliegue viejo → **Redeploy**.
- **Migraciones nuevas:** `supabase db push` *antes* de mergear el código que las necesita.
- **Probar la imagen en local:** `.\tasks.ps1 image` y luego `docker run --rm --env-file bot\.env -e WEBHOOK_URL= -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:55322/postgres gastos-bot:local` (polling con el bot de desarrollo).
- **Apagar el bot de producción:** detén el servicio en Railway y borra el webhook con `Invoke-RestMethod "https://api.telegram.org/bot$token/deleteWebhook"`; si no, Telegram sigue intentando entregar los mensajes.
- **Costo:** el plan Hobby de Railway cuesta 5 USD al mes con ese mismo monto de uso incluido; un bot con una sola réplica entra ahí. Supabase y Gemini quedan en sus planes gratuitos.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| El despliegue falla en el healthcheck | `DATABASE_URL` mal escrita o con la conexión directa (IPv6); revisa los logs (`ValidationError` o `connection failed`) |
| `ValidationError` al arrancar | Falta una variable obligatoria, `WEBHOOK_URL` no empieza con `https://` o `WEBHOOK_SECRET` tiene menos de 16 caracteres |
| `getWebhookInfo` muestra `last_error_message: 401` | El secreto registrado no coincide con `WEBHOOK_SECRET` (por ejemplo, la cambiaste y otra instancia volvió a registrar el webhook); redespliega |
| El bot no responde y los logs dicen `update_ignored` con `not_allowed` | Tu id no está en `ALLOWED_TELEGRAM_IDS` (debe ir en JSON: `[123]`) |
| En local: «Este bot tiene un webhook activo» | Estás usando el token de producción en `bot\.env`; usa el del bot de desarrollo |
| «Vas muy rápido» | Más de `RATE_LIMIT_PER_MINUTE` mensajes en un minuto; espera o sube el límite |
