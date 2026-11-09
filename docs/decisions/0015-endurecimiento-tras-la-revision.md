# 0015. Endurecimiento tras la revisión del ciclo de vida

- **Estado:** aceptada
- **Fecha:** 2026-11-10

## Contexto

El 2026-11-09 se revisó el proyecto completo, desde que llega un mensaje hasta el despliegue. Cinco hallazgos tenían la mejor relación valor/esfuerzo: dos podían modificar datos sin que el usuario lo notara, dos bloqueaban o corrompían el registro en Bs y el último dejaba la base sin respaldos ni alertas.

## Decisión

### 1. Una corrección solo toca lo último que se anotó

- `CorrectionRepository.last_batch` devuelve un `LastBatch`, que dice qué fue lo último que anotó el usuario:
  - el último mensaje con movimientos, **incluidos los deshechos**;
  - el último cambio de moneda, para lo cual `exchanges` gana la columna `created_at`. `occurred_at` no sirve porque puede estar en el pasado.
- Si lo último se deshizo o fue un cambio, no hay nada que corregir y el bot explica por qué. Antes caía en el mensaje anterior: «almuerzo» → «taxi» → Deshacer → «eso fue transporte» recategorizaba el almuerzo.
- Solo se corrige por mensaje lo anotado en las últimas 24 horas (`MAX_AGE`). Lo más viejo se edita en la web (ADR 0014).
- Índices `(user_id, created_at desc)` en `transactions` y `exchanges`.

### 2. Los updates de cada persona se atienden de a uno

- `PerUserOrderMiddleware` toma un `asyncio.Lock` por persona antes de cualquier consulta a la base de datos. Así un «eso fue comida» que llega dos segundos después de «almuerzo 15 bs» espera a que este termine.
- Las personas distintas siguen en paralelo. El lock se borra cuando nadie espera. Vive en memoria, igual que el límite de mensajes: alcanza con una sola instancia del bot.

### 3. `/corregir` solo corrige, y los ejemplos no llevan montos

- Si el LLM interpreta `/corregir <texto>` como otra intención, por ejemplo un gasto nuevo, el bot pregunta qué corregir en vez de anotar un duplicado.
- Solo `category`, `currency` y `kind` vuelven al prompt como ejemplos. Un monto o una cuenta corregidos dependen de ese caso: «almuerzo 15» corregido a 18 enseñaba a anotar 18. Las correcciones se siguen guardando completas; esto completa la ADR 0009.

### 4. Tasas: respaldo para el Bs y filtro de saltos

- Si la fuente del Bs del usuario no tiene una tasa fresca, porque nunca se pudo obtener o lleva más de 6 horas sin responder, se usa la primera fresca de `parallel → bcv → p2p`. La confirmación lo avisa y `rate_source` del movimiento guarda la fuente real. Si ninguna está fresca, se usa la suya aunque esté vieja, como antes.
- Una tasa nueva que se mueve más de ±25 % frente a la última guardada se descarta y se registra `rate_jump_rejected`. Si el salto se repite 3 refrescos seguidos (unas 3 horas), se acepta como real (`rate_jump_accepted`). Un decimal corrido en la fuente ya no deja snapshots ×10 para siempre.

### 5. Respaldos nocturnos y latido externo

- `backup.yml` hace cada noche un `pg_dump` del esquema `public`, lo cifra con AES-256 (`BACKUP_PASSPHRASE`) y lo guarda 30 días como artefacto. Va cifrado porque el repo es público.
- La restauración, `scripts/restaurar-respaldo.sh`, carga solo datos sobre una base ya migrada. Usa `session_replication_role = replica` para que los triggers y las FK no estorben, y quita los vínculos con cuentas web inexistentes. Se probó contra Supabase local.
- `HEALTHCHECK_URL` (healthchecks.io): el refresco de tasas avisa cada hora si funcionó o no (`/fail`). Si el aviso deja de llegar, se manda un correo. Un aviso que falla nunca frena el refresco.

## Consecuencias

- Pruebas nuevas:
  - Unitarias: motivos para no corregir, `/corregir` que no es corrección, orden por persona, respaldo del Bs, saltos de tasa y latido.
  - De integración: deshacer y luego corregir, un cambio como última acción, y ejemplos sin monto.
- Los cambios de moneda anteriores a esta migración tienen `created_at = occurred_at`.
- Falta configurar en GitHub y Railway los secretos `SUPABASE_DB_URL`, `BACKUP_PASSPHRASE` y `HEALTHCHECK_URL` (`docs/DESPLIEGUE.md`, secciones 6 y 7). Sin ellos, el respaldo falla con un error claro y el latido no se envía.
- Quedan pendientes los hallazgos menores de la revisión: presupuesto de tiempo del LLM, errores 404 y de red de Gemini, filtro de chat privado, resumen semanal ante SIGTERM y versiones fijas en el CI.
