# 0018. App móvil con Expo como otro cliente de Supabase

- **Estado:** aceptada (MVP; el resto de la Fase 13 sigue pendiente)
- **Fecha:** 2026-11-21

## Contexto

La web (ADR 0012 y 0014) se usa sobre todo desde el teléfono, y lo que más se consulta ahí son los saldos y el último movimiento. La Fase 13 lleva el panel a una app Android que se pueda instalar con un enlace, sin backend nuevo ni migraciones.

## Decisión

### 1. Expo (React Native) en `mobile/`, no una PWA

- **Por qué Expo y no una PWA:** una PWA reutilizaría la web, pero en Android no puede guardar la sesión en el Keystore. Además, la biometría al abrir queda limitada y la instalación depende del navegador. Expo da acceso nativo (`expo-secure-store` y, más adelante, `expo-local-authentication`) y un APK con EAS. Sirve también para un portafolio móvil.
- **Por qué no Flutter ni Kotlin:** el resto del proyecto es TypeScript. Con Expo, la app comparte el formato, los mensajes y los tipos de la base con la web.
- **Proyecto aparte:** con su propio `package.json`, su CI `mobile.yml` con filtro de rutas y sus tareas `mobile-*` en `tasks.ps1`. Así la web y el bot no dependen de React Native, ni sus CI se rompen por la app.

### 2. Mismo modelo de seguridad que la web

- Solo la llave publicable en `EXPO_PUBLIC_*`. Las lecturas pasan por la RLS de la sesión y las escrituras por funciones `security definer` (por ahora solo `redeem_link_code`).
- La sesión se guarda en el llavero (`expo-secure-store`), partida en trozos de 1.800 caracteres porque algunos iOS rechazan valores de más de 2 KB. El contador de trozos se escribe al final: una escritura a medias cuenta como sesión ausente.
- El token se refresca solo con la app en primer plano (`startAutoRefresh` y `stopAutoRefresh` según `AppState`).
- TanStack Query guarda los datos solo en memoria y los borra al cerrar sesión. No se persisten en disco hasta decidir cómo cifrarlos.

### 3. Cero cálculos de dinero en el cliente

- **Origen de los datos:** saldos, equivalentes en USD, diferencias de cambio y pendientes de deudas vienen de `account_balances_usd`, `list_transactions`, `spending_by_category`, `exchange_history` y `debt_balances`.
- **Lo que suma la app:** como la web, solo suma lo ya convertido (el consolidado y el mes en curso) y promedia las diferencias de cambio.
- **Copias de la web:** `format.ts`, `link-errors.ts` y `database.types.ts` son copias exactas de `web/src/lib/`, vigiladas por `parity-test.ts`. Se eligieron copias y no un paquete compartido para no meter un workspace de npm en un repo que hoy tiene dos proyectos de Node independientes.

### 4. Alcance del MVP

- **Incluido:** login, registro y vinculación con el código de `/vincular`; pestañas Inicio, Movimientos (filtro por moneda y scroll infinito), Cambios y Deudas.
- **Navegación:** Expo Router con `Tabs` de JavaScript.
- **Estilos:** `StyleSheet` con los colores de `globals.css`.
- **Se pospone:**
  - Edición de movimientos.
  - Gráficas (Victory Native).
  - Topes y colchón.
  - Biometría.
  - NativeWind y la fuente Plus Jakarta Sans.
  - E2E con Maestro.
  - Build del APK.
- **Registro:** no se configuró un enlace profundo (`asistentegastos://`). El correo de confirmación abre la web y luego se entra en la app con correo y contraseña.

## Consecuencias

- **Builds y CI:** la app corre en Expo Go mientras no haya librerías nativas fuera de él. El CI compila el bundle de Android con `expo export`, pero no prueba en un dispositivo.
- **Copias de la web:** si cambia una migración, hay que regenerar los tipos de la web y copiarlos a `mobile/`. El CI de la app corre también con cambios en `web/src/lib/`, así que lo avisa.
- **Variables al compilar:** las `EXPO_PUBLIC_*` se fijan al compilar, como las `NEXT_PUBLIC_*` de Vercel (ADR 0013). Un build de EAS necesita las variables cargadas en EAS antes de compilar.
