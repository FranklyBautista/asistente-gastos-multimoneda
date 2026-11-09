# 0014. Panel web: lecturas agregadas en SQL y edición por RPC

- **Estado:** aceptada
- **Fecha:** 2026-11-09

## Contexto

La Fase 10 convierte la web en un panel con cuatro secciones: saldos con un consolidado en USD, movimientos con filtros y edición, gráficas (gasto por categoría, por semana y poder adquisitivo del bolívar) e historial de cambios entre monedas. La web solo tiene la llave publicable y lee bajo RLS (ADR 0012). Además, las reglas de dinero viven en el bot (`domain/`), y la web no debe reimplementarlas con `float` ni dar resultados distintos.

## Decisión

### Las cuentas se hacen en Postgres, no en TypeScript

Migración `20261109120000_web_panel.sql`:

- **`latest_rates`**: la última tasa de cada par moneda–fuente, con una subconsulta `lateral ... limit 1` por par para usar el índice `(currency, source, fetched_at desc)`.
- **`account_balances_usd`**: cada saldo con su equivalente en USD a la tasa vigente de la fuente del usuario. Para el bolívar se usa su preferencia, igual que `rate_source_for`. USD es el pivote. `rate_stale` usa las mismas 6 horas que el bot. Las cuentas archivadas no aparecen, igual que en `/saldos`.
- **`exchange_history`**: cada cambio con `difference_pct = (efectiva / referencia − 1) × 100`, la misma fórmula de `domain.exchange.difference_pct`.
- **`list_transactions(...)`**: filtros por moneda, tipo, categoría y rango de días, con `total` (`count(*) over ()`) para paginar. El límite se acota a 100.
- **`spending_by_category`**, **`spending_by_week`** y **`bolivar_rates`**: los agregados de las gráficas. Las sumas usan el snapshot `amount_usd` de cada movimiento, que es lo único comparable entre monedas (ADR 0002). Las semanas van de lunes a domingo.
- Los días que elige la web son días **locales del usuario**. `local_day_start(día)` los convierte a UTC con `users.timezone`, como `domain.periods` en el bot.
- Todas estas vistas y funciones son `security invoker`, así que la RLS de cada tabla sigue siendo la única barrera. Las funciones revocan `EXECUTE` a `public` y `anon` y lo conceden solo a `authenticated`.

### Editar un movimiento es una función `security definer`

- `edit_transaction(id, kind, amount, account_id, category_id)` hace cuatro cosas:
  - Comprueba que el movimiento, la cuenta (no archivada) y la categoría sean de la sesión, con `app_user_id()`.
  - Exige que la categoría corresponda al tipo.
  - Recalcula el snapshot como `CorrectionService`: en la misma moneda conserva la tasa del registro con el monto nuevo; en otra moneda usa la tasa del usuario vigente cuando se anotó (o la primera posterior); en USD usa el pivote.
  - Guarda un registro en `corrections` por campo cambiado, con los valores del esquema de extracción (`expense`, `COP`, `20000`). Así las ediciones web también llegan al prompt del bot como ejemplos (ADR 0009).
- Devuelve cuántos campos cambiaron. Errores: `not_linked`, `transaction_not_found`, `account_not_found`, `category_mismatch`, `invalid_amount`, `invalid_kind` y `rate_unavailable`.
- No se puede editar la descripción ni la fecha: `corrections.field` no las contempla y no sirven como ejemplos para el prompt. Borrar sigue siendo el botón Deshacer del bot.

### Presentación

- Rutas agrupadas: `(panel)` para `/`, `/movimientos`, `/movimientos/editar?id=`, `/graficas` y `/cambios`, con menú; `(cuenta)` para login, registro y vinculación.
- La edición usa `?id=` en vez de `/movimientos/[id]`. Con Cache Components, una ruta dinámica pide `generateStaticParams` con al menos un valor, y un id de movimiento no se puede prerenderizar.
- Los filtros son un formulario GET: quedan en la URL y se pueden recargar o compartir.
- Recharts para las tres gráficas. Cada una tiene una sola serie y un solo color, validado para modo claro y oscuro (`--chart-mark` en `globals.css`). El texto usa tonos neutros, y debajo hay una tabla «Ver datos» con los mismos números como alternativa accesible. La gráfica en sí lleva `aria-hidden`.
- La tasa del bolívar se muestra como Bs por USD. El porcentaje de poder adquisitivo es la variación de `usd_per_unit`: negativo significa que cada bolívar compra menos dólares, igual que en el resumen semanal.

## Consecuencias

- La prueba pgTAP `060_web_panel` (37 casos) cubre:
  - los cálculos, zonas horarias y paginación;
  - el snapshot de la edición y las correcciones registradas;
  - el aislamiento entre usuarios y que `anon` no tenga acceso.
- La prueba E2E `panel.spec.ts` recorre inicio → filtros → edición → gráficas → cambios.
- La regla del snapshot ahora está en dos sitios: `CorrectionService` (Python) y `edit_transaction` (SQL). Si cambia una, hay que cambiar la otra. Los comentarios de ambas se refieren mutuamente.
- El consolidado se calcula con `numeric` en Postgres. La web solo convierte a `number` para mostrar el resultado.
- La migración se aplica a la nube con `supabase db push` **antes** de mergear, porque Vercel despliega el panel con el merge (`docs/DESPLIEGUE.md`).
