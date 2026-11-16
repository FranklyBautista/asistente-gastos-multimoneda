# 0016. Seguimiento de deudas

- **Estado:** aceptada
- **Fecha:** 2026-11-15

## Contexto

La Fase 11 permite anotar lo que debes y lo que te deben escribiendo en el chat («le debo 20 dólares a miguel», «luisa me debe 50 mil»), y tacharlo cuando se paga. El riesgo principal es contar el mismo dinero dos veces o mezclar deudas con gastos y falsear los saldos.

## Decisión

### 1. Las deudas son un libro aparte

- Tablas `debts` y `debt_payments` (migración `20261111120000_debts`) y la vista `debt_balances`, que calcula `remaining` y `status` (`open`, `partial`, `settled`). Como los saldos, el pendiente nunca se guarda.
- Anotar o liquidar una deuda **no mueve saldos**. Una deuda se queda en su moneda original («20 dólares» son 20 USD aunque el dólar se mueva) y guarda el snapshot de la tasa al registrarla, como los movimientos (ADR 0002).
- Una deuda pagada no se borra: pasa a `settled` y se muestra tachada (`<s>` en Telegram, `line-through` en la web). `cancelled_at` es solo para anular una deuda anotada por error (Deshacer). Una deuda con pagos vigentes no se anula: primero se deshacen sus pagos.

### 2. El gasto original no se cuenta dos veces

«Le debo 20 a Miguel del almuerzo» **no** crea un gasto en comida. El dinero sale una sola vez: cuando se paga. Al liquidar con dinero, el bot crea un gasto en «pago de deudas» (o un ingreso en «cobro de deudas» si te pagaron), enlazado por `debt_payments.transaction_id`, en la misma transacción SQL que el pago. Si se elige «Sin movimiento» (se pagó por otra vía), no se crea nada y los saldos no cambian.

Se descartó anotar el gasto al registrar la deuda y una transferencia al pagarla: un préstamo que te hacen no es un gasto, y la deuda puede no pagarse nunca. La consecuencia es que «¿cuánto gasté en comida?» no incluye lo que comiste a crédito hasta que lo pagues, y entonces cuenta en «pago de deudas». La categoría de la deuda («comida») queda como dato informativo.

Las dos categorías globales (`20261115120000_debt_categories`) no se le ofrecen al LLM: solo las usa la liquidación.

### 3. La base garantiza las reglas, no solo el bot

- La FK compuesta `(debt_id, user_id, currency)` impide pagar en otra moneda o la deuda de otra persona. Pagar en otra moneda queda fuera de la v1.
- El trigger `debt_payments_check` bloquea la deuda y rechaza un pago que supere lo pendiente o caiga en una deuda anulada. Así dos pagos simultáneos no pasan la validación a la vez. El bot traduce ese error a `DebtChanged` («esa deuda cambió mientras elegías») y no deja nada guardado.
- `counterparty_key` es una columna generada (minúsculas, sin tildes, un solo espacio), para que el bot y la web no puedan normalizar distinto. `gastos.domain.debt.counterparty_key` repite la regla para buscar en memoria.
- RLS de solo lectura por dueño y `debt_balances` con `security_invoker`, igual que el resto del panel (ADR 0012).

### 4. Flujo en el chat

- Dos intenciones nuevas en la misma llamada de extracción (prompt `extraccion-v6`): `log_debt` (`ParsedDebt`) y `settle_debt` (`ParsedDebtPayment`). El prompt insiste en la dirección («le debo» frente a «me debe»; «prestar» la invierte), que es el error más caro.
- Moneda dudosa: botones, como en la Fase 4. Contraparte: tal como se escribió, con mayúscula inicial.
- Al pagar se buscan las deudas pendientes con la misma dirección, persona (por palabras: «miguel» encuentra «Miguel Ángel», pero «migue» no) y moneda si se dijo. Con un monto, se descartan las deudas donde no cabe. Una coincidencia → se paga; varias → botones; ninguna → se muestran las pendientes. Un monto mayor que lo pendiente se pregunta, y la respuesta se junta con el mensaje anterior como cualquier otra pregunta del bot.
- La cuenta se deduce solo si el mensaje la nombra y coincide de verdad («por banesco»). Si no, se pregunta con las cuentas de esa moneda y «Sin movimiento».
- Los pendientes de los botones viven en memoria con un token de un solo uso y 30 minutos de vida, como los de la Fase 4. Los callbacks llevan un índice y no ids, por el límite de 64 bytes de Telegram.
- Una deuda o un pago reciente cuenta como la última acción: «eso fue transporte» no corrige un gasto anterior. El gasto que nace de un pago tampoco se corrige por mensaje, porque desajustaría el pago. Se deshace con su botón (completa la ADR 0015).

### 5. Consultas y resumen

- `list_debts(direction, counterparty, include_settled)` es una herramienta más de `ParsedQuery`. A diferencia de lo que anticipaba la ADR 0007, la responde `DebtService` y no `QueryService`, porque comparte la búsqueda por persona con la liquidación. Los totales van por moneda original, como todas las consultas. También está el comando `/deudas`.
- El resumen semanal agrega la sección «📒 Deudas pendientes» como **plantilla fija fuera del texto del LLM**, en vez de «una frase más» como anticipaba la ADR 0008. Así estas cifras no pasan por el modelo y no hace falta verificarlas.

## Consecuencias

- Evaluación: 20 frases nuevas en `bot/eval/dataset.jsonl` (`deu-`, `pag-` y `dq-`, incluidas «miguel me pagó» y dos que no son deudas). Con Gemini real, 20 de 20 correctas y la dirección 15 de 15.
- Si el bot se reinicia entre la pregunta y el botón, el botón avisa que expiró y basta con reescribir el mensaje.
- Editar en la web el gasto que nació de un pago (ADR 0014) puede desajustarlo frente al pago. Se acepta en la v1: la edición web es para corregir errores y el pago sigue siendo la fuente de lo pendiente.
- Las monedas de una deuda y de su pago siempre coinciden. Pagar 20 USD de deuda con Bs exige anotar antes el cambio de moneda.
