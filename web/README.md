# Web del asistente de gastos

Next.js 16 (App Router, Cache Components) con Tailwind y Supabase Auth. La persona crea su cuenta con correo y contraseña, la vincula con su cuenta de Telegram usando el código de `/vincular` y ve sus saldos. El panel completo llega en la Fase 10.

## Desarrollo

```powershell
.\tasks.ps1 db-up                                  # Supabase local
.\tasks.ps1 web-setup                              # npm install
Copy-Item web\.env.example web\.env.local          # pega PUBLISHABLE_KEY de `supabase status`
.\tasks.ps1 web                                    # http://localhost:3000
```

Para probar la vinculación en local, el bot debe apuntar a la misma base de datos (`.\tasks.ps1 run`); con `WEB_URL=http://localhost:3000` en `bot\.env`, `/vincular` muestra el enlace.

## Calidad

- `.\tasks.ps1 web-check`: ESLint, Prettier, tipos y build.
- `.\tasks.ps1 e2e`: Playwright contra Supabase local (registro → vincular → saldos). La primera vez: `npx playwright install chromium` dentro de `web\`.
- Tipos de la base: `supabase gen types typescript --local --schema public > web\src\lib\supabase\database.types.ts` después de cada migración.

## Seguridad (ADR 0012)

- La web solo tiene la llave publicable. Lo que lee pasa por la RLS de la sesión: cada persona ve únicamente sus datos.
- No escribe tablas: vincular es la función `redeem_link_code`. La sesión se valida con `getClaims()` en el servidor, nunca con `getSession()`.
- `src/proxy.ts` refresca la sesión y redirige; la autorización real la hace la base de datos.
- Nada con datos personales se cachea (`use cache`): las lecturas llaman a `connection()` y corren en cada petición.
