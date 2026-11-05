# 0012. Acceso de la web y vinculación con Telegram

- **Estado:** aceptada
- **Fecha:** 2026-11-06

## Contexto

La web (Fases 9 y 10) muestra las mismas finanzas que el bot. El bot identifica a la persona por su `telegram_id`; la web, por la sesión de Supabase Auth. Hay que unir las dos identidades sin pedir datos sensibles, y la web solo debe ver los datos de quien inició sesión. Hasta ahora todas las tablas tenían RLS activo sin políticas, pero Supabase concede por defecto todos los permisos a `anon` y `authenticated`, así que la RLS era la única barrera.

## Decisión

### Vinculación por código de un solo uso

- `/vincular` en el bot genera un código de 8 caracteres de un alfabeto sin `I`, `O`, `0` ni `1` (32^8 ≈ 10^12 combinaciones), válido 10 minutos. Pedir otro anula los anteriores sin usar. Si la cuenta ya está vinculada, el bot lo dice y no emite código.
- La web, con la sesión iniciada, lo canjea con la función `redeem_link_code(code)` (`security definer`). Esa función bloquea la fila del código, valida vencimiento y uso, rechaza si el usuario del bot ya está vinculado a otra cuenta web o si la cuenta web ya tiene otro usuario del bot, y guarda `users.auth_user_id`. Errores: `invalid_code`, `telegram_already_linked`, `web_already_linked` y `not_authenticated`.
- Se descartó vincular por el correo o por el `telegram_id` escrito en la web: cualquiera podría escribir el id de otra persona. El código prueba que quien lo canjea controla la cuenta de Telegram, que ya está en la lista blanca.

### Permisos: lectura por dueño, escrituras por funciones

- Se revocan todos los permisos de `anon` y `authenticated` sobre tablas, secuencias y funciones del esquema `public`, también para los objetos futuros (default privileges). `anon` no tiene acceso a nada.
- `authenticated` solo tiene `select` sobre lo que muestra la web: `users`, `accounts`, `categories`, `transactions`, `exchanges`, `exchange_rates`, `corrections` y la vista `account_balances` (ya creada con `security_invoker = true`). `link_codes`, `weekly_summaries` y `processed_updates` son internas del bot.
- Políticas de lectura por dueño con `app_user_id()`, una función `security definer` que devuelve el `users.id` de la sesión. Así las políticas no dependen de la RLS de `users`. Las categorías globales (`user_id is null`) y las tasas, que son datos de mercado, las lee cualquier sesión.
- La web no escribe tablas: cada escritura futura (por ejemplo, editar un movimiento en la Fase 10) será una función con su propio `grant`.
- PostgreSQL concede `EXECUTE` a `PUBLIC` en toda función nueva por un default global. Por eso cada función expuesta revoca `public` y `anon` y concede solo a `authenticated`. Una prueba pgTAP lo verifica.

### El bot no cambia

- Sigue entrando como dueño de las tablas (`postgres`), que se salta la RLS, y filtra siempre por `user_id`.
- `WEB_URL` es opcional: si está, `/vincular` muestra el enlace a `<WEB_URL>/vincular`.

## Consecuencias

- Las pruebas pgTAP (`050_web_access`) cubren accesos cruzados entre usuarios, `anon` sin acceso, escrituras rechazadas y cada error del canje.
- Una tabla nueva queda sin acceso desde la web hasta que se le concedan permisos y políticas de forma explícita.
- Desvincular una cuenta no tiene comando todavía; se hace a mano (`update users set auth_user_id = null`).
- Si se borra la cuenta web en Supabase Auth, `auth_user_id` queda en `null` (`on delete set null`) y la cuenta de Telegram puede volver a vincularse.
