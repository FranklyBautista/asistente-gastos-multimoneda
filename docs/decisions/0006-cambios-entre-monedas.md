# 0006. Cambios entre monedas

- **Estado:** aceptada
- **Fecha:** 2026-10-31

## Contexto

"Cambié 50 USDT a Bs" no es gasto ni ingreso: mueve dinero entre dos cuentas de monedas distintas. Registrarlo como gasto falsea los totales. Además, la gente casi nunca dice los tres datos (cuánto entregó, cuánto recibió y a qué tasa) y dice la tasa siempre igual, sin importar la dirección: quien vende USDT "a 985" y quien compra USDT "a 985" dicen el mismo número.

## Decisión

- **Convención:** una tasa de cambio son las unidades de la moneda recibida por 1 de la entregada (`effective_rate = to_amount / from_amount`). `reference_rate` se guarda en la misma dirección, así que se comparan directamente.
- **El LLM no hace cuentas:** devuelve solo lo que dice el mensaje (`ParsedExchange`), con la tasa tal como se dijo. El dato que falta lo calcula `domain.exchange.complete_amounts`. Si están los tres, mandan los montos, porque la tasa dicha suele estar redondeada.
- **Dirección de la tasa:** se elige la orientación (la tasa o su inversa) más cercana a la tasa de referencia del momento. Sin referencia, se toma tal cual. Los montos se calculan con el número tal como se dijo, sin invertirlo ni redondearlo antes, para que 20 USDT "a 990" den 19.800 Bs exactos.
- **Tasa de referencia:** se arma con las tasas guardadas (Fase 3), con USD como pivote: `usd_per_unit(origen) / usd_per_unit(destino)`. Para el bolívar se usa la fuente que eligió el usuario. Si alguna tasa no existe todavía, el cambio se guarda sin referencia y la confirmación lo dice. Si alguna está vieja, se avisa.
- **Diferencia:** `(efectiva / referencia − 1) × 100`. Positivo significa que se recibió más que con la referencia.
- **Lo que falta se pregunta:** una sola pregunta corta, armada en código según lo que falte (moneda de origen, de destino o los montos). La próxima respuesta del usuario, si llega en menos de 10 minutos, se manda al LLM junto con el mensaje anterior y la pregunta. Si no tiene que ver, se interpreta sola. Esto vale también para las preguntas de monto de la Fase 4. La pregunta pendiente vive en memoria, como los pendientes de moneda (ADR 0005).
- **Misma moneda:** es una transferencia entre cuentas y queda fuera de esta fase; el bot lo dice y no guarda nada.
- **Presentación:** la tasa se muestra como se cotiza en la calle, la moneda débil por 1 de la fuerte ("990,00 Bs por USDT"), con la referencia en la misma orientación.
- **Deshacer:** borrado lógico del cambio (`deleted_at`), con su propio botón (`undox:<id>`).

## Consecuencias

- `account_balances` ya restaba del origen y sumaba al destino; una prueba de integración lo verifica con un cambio de USDT a Bs y con su deshacer.
- Un cambio no lleva snapshot en USD propio: su valor se deduce de las tasas guardadas o de `reference_rate`.
- Para elegir mal la orientación, la tasa dicha tendría que parecerse más a la inversa de la referencia (0,001 frente a 999), algo que no pasa por error. El único caso borroso es entre monedas cuya tasa ronda 1 (USD ↔ USDT), y ahí las dos orientaciones dan casi el mismo resultado. Si algo sale raro, la diferencia en % de la confirmación lo hace visible y el botón Deshacer lo corrige.
