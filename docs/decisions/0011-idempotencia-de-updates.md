# 0011. Idempotencia de los updates de Telegram

- **Estado:** aceptada
- **Fecha:** 2026-11-05

## Contexto

Telegram puede entregar dos veces el mismo update. En producción (webhook, ADR 0010) pasa si la respuesta 200 del bot se pierde en la red; en local (polling), si el bot se reinicia después de procesar un mensaje pero antes de confirmar el offset. En ambos casos un gasto quedaría anotado dos veces, y un duplicado así pasa inadvertido en los saldos. La guía de arquitectura dejaba la decisión pendiente desde la Fase 4.

## Decisión

- **Se deduplica el update, no el movimiento.** Cada update se reserva por `(bot_id, update_id)` en la tabla `processed_updates` antes de procesarlo (`insert ... on conflict do nothing`); si ya existía, se descarta y se registra `update_ignored` con `reason=duplicate`. Cubre todo lo que llega por Telegram (mensajes, botones y correcciones) sin tocar `transactions`, `exchanges` ni `corrections`.
- Se descartó guardar el `message_id` en cada movimiento con un índice único: un mensaje puede crear varios movimientos, un cambio entre monedas o una corrección, y la respuesta a una aclaración se junta con el mensaje anterior. Habría que repetir la regla en cada tabla.
- **`bot_id` en la clave:** `update_id` es único por bot, no global. La base local puede recibir updates de bots distintos (el de desarrollo y, antes, el de producción).
- **Orden de los middlewares:** contexto de logs → lista blanca → repetidos → usuario. Los updates de quien no está en la lista blanca siguen sin tocar la base de datos.
- **Retención de 2 días.** Telegram guarda los updates sin entregar 24 horas; el programador borra cada día a las 08:00 UTC las filas de más de 2 días.

## Consecuencias

- Se prefiere perder un update a duplicarlo: si el bot se cae a mitad de uno ya reservado, una nueva entrega se descarta. La persona no recibe confirmación y puede volver a escribirlo; un gasto duplicado, en cambio, no se nota.
- Cada update cuesta un `insert` más en la base de datos, un costo despreciable al lado de la llamada al LLM.
- Si el mismo texto se escribe dos veces a propósito, son dos updates distintos y se anotan los dos, como debe ser.
