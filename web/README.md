# Web del asistente de gastos

Next.js 16 (App Router, Cache Components) con Tailwind, Recharts y Supabase Auth. La persona crea su cuenta con correo y contraseña y la vincula con Telegram usando el código de `/vincular`. Después tiene un panel con cuatro secciones:

| Ruta                      | Qué muestra                                                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `/`                       | Saldo de cada cuenta, consolidado en USD y tasas usadas (con aviso si están viejas)                                    |
| `/movimientos`            | Lista paginada con filtros por moneda, tipo, categoría y fechas (formulario GET)                                       |
| `/movimientos/editar?id=` | Edición de tipo, monto, cuenta y categoría mediante la RPC `edit_transaction`                                          |
| `/graficas`               | Gasto por categoría (7, 30 o 90 días), gasto por semana y poder adquisitivo del Bs, cada gráfica con su tabla de datos |
| `/cambios`                | Historial de cambios con tasa efectiva, tasa de referencia y diferencia en %                                           |

`login`, `registro` y `vincular` están en el grupo de rutas `(cuenta)`; el panel, en `(panel)`.

## Desarrollo

```powershell
.\tasks.ps1 db-up                                  # Supabase local
.\tasks.ps1 web-setup                              # npm install
Copy-Item web\.env.example web\.env.local          # pega PUBLISHABLE_KEY de `supabase status`
.\tasks.ps1 web                                    # http://localhost:3000
```

Para probar la vinculación en local, el bot debe apuntar a la misma base de datos (`.\tasks.ps1 run`). Con `WEB_URL=http://localhost:3000` en `bot\.env`, `/vincular` muestra el enlace.

## Producción

Publicada en <https://asistente-gastos-multimoneda.vercel.app>. El paso a paso está en [`docs/DESPLIEGUE.md`](../docs/DESPLIEGUE.md#5-web-en-vercel).

## Calidad

- `.\tasks.ps1 web-check`: ESLint, Prettier, tipos y build.
- `.\tasks.ps1 e2e`: Playwright contra Supabase local. Cubre dos flujos:
  - `vincular.spec.ts`: registro → vinculación → saldos.
  - `panel.spec.ts`: saldos → filtros → edición → gráficas → cambios.
  - La primera vez hay que correr `npx playwright install chromium` dentro de `web\`.
- Tipos de la base: después de cada migración, `supabase gen types typescript --local --schema public > web\src\lib\supabase\database.types.ts`.

## Seguridad (ADR 0012 y 0014)

- **Llave:** la web solo tiene la llave publicable. Lo que lee pasa por la RLS de la sesión: cada persona ve únicamente sus datos.
- **Lecturas del panel:** son vistas y funciones `security invoker` (`account_balances_usd`, `list_transactions`, `spending_by_*`, `bolivar_rates`, `exchange_history`). Los cálculos con dinero se hacen en Postgres con `numeric`.
- **Escrituras:** la web no escribe tablas.
  - Vincular es `redeem_link_code`.
  - Editar es `edit_transaction`, que valida al dueño, recalcula el snapshot en USD y guarda la corrección.
- **Sesión:** se valida con `getClaims()` en el servidor, nunca con `getSession()`. `src/proxy.ts` refresca la sesión y redirige; la autorización real la hace la base de datos.
- **Caché:** nada con datos personales se cachea (`use cache`). Las lecturas llaman a `connection()` y corren en cada petición.
