# Despliegue

El bot corre en **Railway** (imagen de `bot/Dockerfile`, modo webhook), la web en **Vercel** y la base de datos en **Supabase** (nube). Las decisiones están en el [ADR 0010](decisions/0010-despliegue.md) y el [ADR 0013](decisions/0013-despliegue-de-la-web.md).

```mermaid
flowchart LR
  T["Telegram"] -- "POST /telegram/webhook<br/>(cabecera con el secreto)" --> R["Railway: bot<br/>FastAPI + aiogram + APScheduler"]
  R -- "pooler de sesión :5432" --> S[("Supabase Postgres")]
  R --> G["Gemini"]
  R --> A["APIs de tasas"]
  RW["Healthcheck de Railway"] -- "GET /health" --> R
  N["Navegador"] --> V["Vercel: web<br/>Next.js + Supabase Auth"]
  V -- "llave publicable y RLS" --> S
```

Pasos en orden: bot de desarrollo → base de datos → Railway → verificación → web. Se hacen una sola vez; después, cada merge a `main` despliega solo lo que cambió (ver [Operación](#operación)).

## 1. Un bot para desarrollo

Con el webhook activo, un token ya no puede usarse en polling. `@frankly_gastos_bot` pasa a ser el de producción y para la laptop se crea otro:

1. En Telegram, con [@BotFather](https://t.me/BotFather): `/newbot`, por ejemplo `frankly_gastos_dev_bot`.
2. Pon su token en `TELEGRAM_BOT_TOKEN` de `bot\.env` (local). El token de producción solo va en Railway.

Si un día corres `.\tasks.ps1 run` con el token de producción, el bot se niega a arrancar en vez de quitarle el webhook a Railway.

## 2. Base de datos en Supabase

1. Crea un proyecto en [supabase.com](https://supabase.com/dashboard) (plan gratuito). Elige una región del este de EE. UU., cerca del servicio de Railway (US East, en Virginia), y guarda la contraseña de la base de datos en un gestor de contraseñas. El proyecto actual (`asistente-gastos-multimoneda`) está en **East US (Ohio)**, `us-east-2`: entre Ohio y Virginia la latencia es mínima.
2. Aplica las migraciones desde la raíz del repositorio:

   ```powershell
   supabase login
   supabase link --project-ref <ref-del-proyecto>   # el ref está en la URL del panel
   supabase db push                                 # aplica supabase/migrations; el seed no se carga
   supabase migration list                          # local y remoto deben coincidir
   ```

   Si `db push` se queda en «Initialising login role...», tu red está bloqueando el puerto 5432 (pasa en algunas redes domésticas: la conexión TCP abre pero Postgres nunca contesta). La CLI siempre usa ese puerto con el proyecto enlazado, así que pásale la cadena del pooler en modo transacción (puerto 6543), con la contraseña en una variable de entorno para que no quede en el historial:

   ```powershell
   $env:PGPASSWORD = Read-Host "Contraseña de la base de datos"
   $url = "postgresql://postgres.<ref>@aws-0-us-east-2.pooler.supabase.com:6543/postgres"
   supabase db push --db-url $url
   supabase migration list --db-url $url
   Remove-Item Env:PGPASSWORD
   ```

   Railway no tiene ese bloqueo: el bot usa el pooler de sesión (5432) como dice el paso 3.

3. Copia la cadena de conexión en **Connect → Connection string → Session pooler**. Tiene esta forma:

   ```text
   postgresql://postgres.<ref>:<contraseña>@aws-<n>-us-east-2.pooler.supabase.com:5432/postgres
   ```

   Copia el host tal cual aparece en el panel: los proyectos nuevos pueden estar en `aws-1-...` en vez de `aws-0-...`, y con el host equivocado la conexión se queda colgada en vez de fallar.

   Usa el **pooler de sesión**, no la conexión directa (`db.<ref>.supabase.co`): en el plan gratuito la directa solo tiene IPv6. Si la contraseña tiene caracteres como `@`, `:` o `/`, escríbelos codificados (`%40`, `%3A`, `%2F`).

Todas las tablas tienen RLS activo: `anon` no tiene acceso a nada y `authenticated` solo lee lo suyo ([ADR 0012](decisions/0012-acceso-web-y-vinculacion.md)). El bot entra como dueño de las tablas.

## 3. Servicio en Railway

1. Instala la [Railway App](https://github.com/apps/railway-app) en tu cuenta de GitHub, con acceso a `asistente-gastos-multimoneda`. Que Railway aparezca en **Authorized GitHub Apps** no basta: la instalación se ve en **Installed GitHub Apps**.
2. En [railway.com](https://railway.com): **New Project → Deploy from GitHub repo** y elige `asistente-gastos-multimoneda`. El primer intento fallará porque faltan las variables; es normal.
3. En el servicio (no en los ajustes del proyecto), **Settings**:

   | Ajuste | Valor |
   |---|---|
   | Source → Root Directory | `/bot` (Railway encuentra el `Dockerfile` solo) |
   | Source → Branch | `main` |
   | Source → Auto deploy | Pulsa **Enable** si dice «Auto deploy is disabled» |
   | Source → Wait for CI | Activado, si aparece (espera a GitHub Actions antes de desplegar) |
   | Build → Watch Paths | `/bot/**` (los cambios en `docs/` o `supabase/` no redespliegan) |
   | Networking → Generate Domain | puerto `8080` |
   | Deploy → Healthcheck Path | `/health` |
   | Deploy → Region | US East (Virginia, la más cercana a Supabase en Ohio) |
   | Deploy → Replicas | `1` (el scheduler y el límite de mensajes viven en memoria) |

4. En **Variables → Raw Editor** pega esto y rellena los valores:

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
   - `WEBHOOK_URL`: Railway reemplaza `${{RAILWAY_PUBLIC_DOMAIN}}` por el dominio generado en el paso 3. Si no lo resuelve, pega el dominio a mano (`https://<servicio>.up.railway.app`, sin barra final).
   - `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=25`: en cada redespliegue el bot espera hasta 20 s a los mensajes que está procesando; sin esto Railway lo mataría antes.
   - Opcionales, con su valor por defecto: `RATE_LIMIT_PER_MINUTE=20`, `WEEKLY_SUMMARY_HOUR=18`, `RATES_REFRESH_MINUTES=60`, `GEMINI_MODELS`, `WEB_URL` (URL pública de la web; con ella `/vincular` muestra el enlace) y `HEALTHCHECK_URL` (alerta si el bot deja de funcionar, sección 7).

5. **Deploy.** Railway construye la imagen, arranca el bot y espera a que `/health` responda 200 antes de mandarle tráfico.

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

## 5. Web en Vercel

`vercel.json`, en la raíz del repositorio, declara solo el servicio `web`. El bot **no** va a Vercel: si el formulario propone agregar `bot`, no lo aceptes ([ADR 0013](decisions/0013-despliegue-de-la-web.md)).

1. En [vercel.com/new](https://vercel.com/new), importa `asistente-gastos-multimoneda` y deja **Root Directory** en la raíz (`./`), no en `web`.
2. Agrega las variables de entorno (los valores salen de **Project Settings → API** en Supabase):

   ```env
   NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<llave publicable, sb_publishable_...>
   ```

3. **Deploy** y copia el dominio de producción. Estas variables se fijan al compilar: si las agregas o cambias después, hay que volver a desplegar.
4. En Supabase, **Authentication → URL Configuration**:

   | Campo | Valor |
   |---|---|
   | Site URL | `https://<dominio-de-vercel>` |
   | Redirect URLs | `https://<dominio-de-vercel>/auth/callback` (conserva las de `localhost`) |

5. En Railway, pon `WEB_URL=https://<dominio-de-vercel>`, sin barra final. Esto redespliega el bot y `/vincular` empieza a mostrar el enlace.
6. Comprueba el flujo completo: regístrate en `/registro`, abre el enlace del correo de confirmación, escribe `/vincular` en `@frankly_gastos_bot`, canjea el código en la web y revisa que aparezcan los saldos.

En la nube la confirmación de correo está activa. Supabase la envía con su servidor de correo incluido, pensado para pruebas y con un límite bajo por hora; si no llega nada, revisa ese límite o configura un SMTP propio.

## 6. Respaldos

El plan gratuito de Supabase no guarda respaldos descargables. El workflow [`backup.yml`](../.github/workflows/backup.yml) hace uno cada noche (03:30 en Caracas):

- Vuelca el esquema `public`, que tiene todo lo del bot.
- Lo cifra con AES-256 y una frase de paso tuya. Esto es obligatorio porque el repo es público y cualquiera podría bajar un artefacto sin cifrar.
- Lo guarda como artefacto del workflow durante 30 días.

Las cuentas web (`auth.users`) no se respaldan: si hubiera que restaurar, cada persona vuelve a registrarse y a usar `/vincular`.

**Configuración (una vez):**

1. En GitHub, **Settings → Secrets and variables → Actions → New repository secret**:
   - `SUPABASE_DB_URL`: la cadena del **Session pooler** con la contraseña (la misma forma que `DATABASE_URL` en Railway).
   - `BACKUP_PASSPHRASE`: una frase larga. Guárdala en tu gestor de contraseñas; sin ella, los respaldos no se pueden abrir.
2. **Actions → backup → Run workflow** para probarlo. Al terminar debe aparecer un artefacto `backup-<número>` con un archivo `gastos-AAAA-MM-DD.dump.gpg`.

GitHub pausa los workflows programados de un repo público después de 60 días sin commits. Si eso pasa, **Actions → backup → Enable workflow**.

**Restaurar** (en un proyecto de Supabase nuevo o en el mismo):

1. Si el proyecto es nuevo, aplícale las migraciones (`supabase db push`, sección 2).
2. Baja el artefacto, descomprime el `.zip` y descifra el volcado en una carpeta vacía:

   ```powershell
   gpg --output gastos.dump --decrypt gastos-AAAA-MM-DD.dump.gpg
   ```

3. Restaura. [`scripts/restaurar-respaldo.sh`](../scripts/restaurar-respaldo.sh) vacía las tablas de `public`, carga los datos sin disparar triggers y quita los vínculos web que ya no existen:

   ```powershell
   $env:U = Read-Host "Cadena del Session pooler (con contraseña)"
   docker run --rm -e U -v "${PWD}:/out" -v "C:\dev\gastos-multimoneda\scripts:/scripts" postgres:17-alpine sh /scripts/restaurar-respaldo.sh
   Remove-Item Env:U
   ```

   Al terminar muestra cuántos usuarios, movimientos y cambios quedaron. Reemplaza **todos** los datos del proyecto de destino.

## 7. Alerta si el bot deja de funcionar

El bot avisa a [healthchecks.io](https://healthchecks.io) (plan gratuito) cada vez que refresca las tasas, una vez por hora:

- Si refrescó alguna tasa, el aviso es «bien».
- Si ninguna fuente respondió, avisa a la URL `/fail`.
- Si el aviso deja de llegar (el bot se cayó o el programador se trabó), healthchecks.io te manda un correo.

1. Crea una cuenta y un chequeo con **Period** de 1 hora y **Grace** de 30 minutos.
2. Copia su URL de ping (`https://hc-ping.com/<uuid>`) en la variable `HEALTHCHECK_URL` de Railway. El bot se redespliega solo.
3. En una hora, el chequeo debe pasar a **up**.

## Operación

- **Redespliegue del bot:** con **Auto deploy** activo, cada push a `main` que toque `bot/` construye y despliega una versión nueva. La anterior sigue atendiendo hasta que la nueva pasa el healthcheck.
- **Redespliegue de la web:** Vercel despliega los push a `main`. Volver a una versión anterior se hace desde **Deployments** en Vercel.
- **Volver a una versión anterior:** en Deployments, el menú de un despliegue viejo → **Redeploy**.
- **Migraciones nuevas:** `supabase db push` *antes* de mergear el código que las necesita. Si no, el bot (Railway) o el panel (Vercel) se despliegan con el merge y fallan contra un esquema viejo; por ejemplo, el panel de la Fase 10 necesita `20261109120000_web_panel.sql`.
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
| Un merge a `main` no despliega el bot | **Auto deploy** está desactivado (Settings → Source del servicio) o el cambio no toca `/bot/**` |
| Todas las rutas de la web dan 500 («Internal Server Error») | Faltan las variables `NEXT_PUBLIC_*` en ese build; agrégalas y vuelve a desplegar |
| El enlace del correo no vuelve a la web | Falta el dominio en **Site URL** o **Redirect URLs** de Supabase |
