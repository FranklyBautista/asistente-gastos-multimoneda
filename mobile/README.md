# App móvil (Expo)

El panel web en el bolsillo: saldos y consolidado en USD, movimientos, cambios entre monedas y deudas. Es otro cliente de Supabase, igual que la web: lee las vistas y funciones con la llave publicable bajo la RLS de tu sesión, así que no tiene backend propio ni hace cálculos de dinero ([ADR 0018](../docs/decisions/0018-app-movil.md)).

## Estado (MVP de la Fase 13)

| Hecho                                                                | Pendiente                                   |
| -------------------------------------------------------------------- | ------------------------------------------- |
| Login, registro y vinculación con el código de `/vincular`           | Edición de movimientos (hoy solo en la web) |
| Sesión en el llavero del teléfono (`expo-secure-store`, en trozos)   | Gráficas (Victory Native)                   |
| Inicio: consolidado en USD, mes en curso y saldos por cuenta         |                                             |
| Movimientos paginados con filtros de moneda, tipo, categoría y fecha | Bloqueo con biometría                       |
| Historial de cambios y deudas (liquidadas tachadas)                  | Fuente Plus Jakarta Sans y pulido visual    |
| Colchón en días y topes del mes en Inicio (Fase 12)                  |                                             |
| Pruebas con Jest y CI `mobile.yml`                                   | Maestro (E2E) y build del APK con EAS       |

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

`eas.json` tiene los perfiles `development` (dev client), `preview` (APK interno con enlace) y `production`. Requiere una cuenta de Expo:

```powershell
cd mobile
npx eas-cli@latest login
npx eas-cli@latest build --profile preview --platform android
```

Las variables `EXPO_PUBLIC_*` se fijan al compilar: cárgalas en EAS (`eas env:create`) antes del build.
