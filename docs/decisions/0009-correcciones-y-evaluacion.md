# 0009. Correcciones y set de evaluación

- **Estado:** aceptada
- **Fecha:** 2026-11-02

## Contexto

La extracción con LLM se equivoca a veces de categoría, de moneda o de monto. Hasta la Fase 7, la única salida era tocar Deshacer y escribir de nuevo, y el bot repetía el mismo error la próxima vez. Además, sin una medición no hay forma de saber si un cambio de prompt mejora o empeora la extracción.

## Decisión

### Correcciones

- **Se corrige el último mensaje anotado.** "Eso fue transporte", "eran 20 mil pesos", "era un ingreso" o `/corregir <texto>` llegan como `intent: correction` con un `ParsedCorrection` que solo trae lo que cambia (prompt `extraccion-v5`). `/corregir` sin texto muestra qué se corregiría.
- **Si el mensaje anotó varios movimientos**, la pista del usuario elige uno ("el café era en bs" → `target_hint: café`, comparado con la descripción o la categoría). Sin pista, o si coincide con más de uno, el bot pregunta cuál en vez de adivinar.
- **Se modifica el movimiento, no se crea otro.** Es un `update` sobre `transactions` en la misma transacción SQL que los registros de `corrections` (uno por campo cambiado). Deshacer sigue funcionando sobre el movimiento corregido.
- **Snapshot de tasa.** Si cambia la moneda, se usa la tasa del usuario vigente cuando se anotó el movimiento (`created_at`), no la de ahora: la corrección arregla un error de lectura, no cambia cuándo pasó. Si solo cambia el monto, se conserva el `usd_per_unit` y se recalcula `amount_usd`.
- **Sin adivinar.** Una categoría que no existe se responde con la lista de las que hay. En la misma moneda, la cuenta solo cambia si la pista coincide con una cuenta. Si se pasa de gasto a ingreso (o al revés) sin decir la categoría, se usa la de respaldo del nuevo tipo.

### Correcciones como ejemplos

- Las últimas 10 correcciones del usuario (la más reciente de cada mensaje y campo) se agregan al final del prompt de extracción como `«mensaje original» -> campo: valor correcto`. Los valores se guardan con los nombres del esquema (`COP`, `income`, `transporte`) justamente para eso.
- El mensaje original sale de `transactions.raw_text` (por la FK `corrections.transaction_id`); `corrections.raw_text` guarda el texto de la corrección.
- Cuesta una consulta corta a la BD por mensaje y unas líneas más de prompt.

### Set de evaluación

- `bot/eval/dataset.jsonl` tiene 73 frases con su resultado esperado: 14 con moneda dudosa, cambios, consultas, correcciones y aclaraciones. El puntuador (`gastos/extraction/evaluation.py`) es código puro con pruebas; `bot/eval/run_eval.py` llama a Gemini real con una pausa entre frases y guarda el resultado en `bot/eval/results/<versión del prompt>.json`.
- **La moneda se mide como la usa el bot.** Si viene null o con confianza menor a 0.8, el bot pregunta. Así se mide por separado "moneda clara anotada" y "moneda dudosa preguntada": adivinar una moneda dudosa es peor que preguntar.
- Solo se comparan los campos que cada caso indica (una categoría discutible, como "spotify" en ocio o servicios, no se puntúa).
- No corre en el CI: consume cuota del LLM y su resultado no es determinista. Se corre a mano cuando cambia el prompt.

### Resultado inicial (`extraccion-v5`, 2026-11-02)

72 de 73 frases evaluadas (una sin respuesta del LLM por el límite del plan gratuito): 95,8 % de casos exactos. Intención, categoría, consultas y correcciones salieron al 100 %, igual que la moneda clara anotada (35/35) y la moneda dudosa preguntada (14/14). Hubo tres fallos. En «pagué 200 con pago móvil» y «me pagaron 100» no vino ningún movimiento, así que el bot preguntaría el monto en vez de solo la moneda. En «vendí 30 usdt en binance p2p a 1.010» la moneda de destino vino null: el prompt pide no deducirla de la tasa (ADR 0006), así que el bot pregunta. Detalle en `bot/eval/results/extraccion-v5.json`.

## Consecuencias

- Las correcciones solo alcanzan al último mensaje. Corregir movimientos viejos queda para la lista con edición de la web (Fase 10).
- Los cambios entre monedas no se corrigen con texto: siguen con Deshacer.
- Un usuario con muchas correcciones parecidas puede sesgar al modelo ("todo lo que tenga «mil» es COP"). Para ese usuario es lo deseado; el set de evaluación se corre sin correcciones para medir el prompt base.
- Las frases del set son de ejemplo; conviene sumarle frases reales a medida que aparezcan errores en el uso.
