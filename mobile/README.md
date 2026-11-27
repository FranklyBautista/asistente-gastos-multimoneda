# App móvil (Expo)

El panel web en el bolsillo: saldos y consolidado en USD, movimientos, cambios entre monedas y deudas. Es otro cliente de Supabase, igual que la web: lee las vistas y funciones con la llave publicable bajo la RLS de tu sesión, así que no tiene backend propio ni hace cálculos de dinero ([ADR 0018](../docs/decisions/0018-app-movil.md)).

**Descarga:** [APK para Android](https://github.com/FranklyBautista/asistente-gastos-multimoneda/releases/download/mobile-v1.0.0/asistente-gastos.apk) (arm64; en el teléfono hay que permitir instalar apps de fuentes desconocidas). Entra con la misma cuenta que la web, vinculada con `/vincular` en el bot.

## Estado (Fase 13)

| Hecho                                                                                                  | Pendiente                                |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| Login, registro (el correo de confirmación abre la app) y vinculación con el código de `/vincular`     |                                          |
| Sesión en el llavero del teléfono (`expo-secure-store`, en trozos)                                     |                                          |
| Inicio: consolidado en USD, mes en curso y saldos por cuenta                                           |                                          |
| Movimientos paginados con filtros de moneda, tipo, categoría y fecha · edición (no los pagos de deuda) |                                          |
| Historial de cambios y deudas (liquidadas tachadas)                                                    | Fuente Plus Jakarta Sans y pulido visual |
| Gráficas: categoría, semanas y bolívar (Victory Native 42 + Skia)                                      |
| Bloqueo con huella, rostro o PIN al abrir y tras 30 s en segundo plano (Ajustes)                       |
| Colchón en días y topes del mes en Inicio (Fase 12)                                                    |                                          |
| Pruebas con Jest y CI `mobile.yml` · APK con EAS                                                       | Maestro (E2E)                            |

## Desarrollo

```powershell
.\tasks.ps1 mobile-setup        # npm install
copy mobile\.env.example mobile\.env.local   # y pon la URL y la llave publicable
.\tasks.ps1 mobile              # npx expo start: escanea el QR con Expo Go en Android
.\tasks.ps1 mobile-check        # lint, formato, tipos y pruebas
```

- Contra Supabase local (`.\tasks.ps1 db-up`), el teléfono no ve `127.0.0.1`: usa la IP de tu PC en la red (`http://192.168.x.x:55321`) o el emulador de Android Studio (`http://10.0.2.2:55321`).
- Contra la nube, usa la URL y la llave publicable del proyecto (Project Settings → API). Nunca la llave secreta.
- Todas las librerías nativas de la app vienen en Expo Go, así que todavía no hace falta un dev build.

## Copias de la web

`src/lib/format.ts`, `src/lib/link-errors.ts` y `src/lib/database.types.ts` son copias exactas de los archivos de `web/src/lib/`. La prueba `parity-test.ts` falla si se separan. Cuando cambie el original (por ejemplo, al regenerar los tipos tras una migración), cópialo:

```powershell
copy web\src\lib\format.ts mobile\src\lib\format.ts
copy web\src\lib\link-errors.ts mobile\src\lib\link-errors.ts
copy web\src\lib\supabase\database.types.ts mobile\src\lib\database.types.ts
```

## APK con EAS

`eas.json` tiene los perfiles `development` (dev client), `preview` (APK interno) y `production`. El proyecto es `@franklyb/asistente-gastos` y las variables `EXPO_PUBLIC_*` viven en los entornos `preview` y `production` de EAS (`eas env:list --environment preview`), porque se fijan al compilar.

```powershell
cd mobile
npx eas-cli@latest build --profile preview --platform android
```

- El perfil `preview` compila solo para `arm64-v8a`: con las 4 arquitecturas, el daemon de Gradle se quedaba sin memoria en el worker gratuito al compilar Reanimated, Skia y Worklets. Cubre prácticamente todos los teléfonos actuales; el emulador x86_64 de Android Studio sigue usándose con Expo Go.
- EAS sube los archivos tal como están en disco, no el último commit. Para publicar un APK, compílalo desde un worktree limpio (`git worktree add --detach <carpeta> <commit>`).
- Publica el APK como asset `asistente-gastos.apk` de un release de GitHub (`mobile-vX.Y.Z`), que es lo que enlaza este README: los builds de Expo del plan gratuito caducan.
- El correo de confirmación vuelve a `asistentegastos://auth/callback`, que tiene que estar en Redirect URLs de Auth en Supabase (en local ya está en `supabase/config.toml`).
