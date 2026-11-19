# 0017. Hábitos: contexto al anotar, colchón en días y topes por categoría

- **Estado:** aceptada (la parte web queda pendiente, ver Consecuencias)
- **Fecha:** 2026-11-19

## Contexto

La investigación sobre hábitos financieros (`reports/Hábitos financieros y funciones app.md`) concluyó que pocas funciones cambian resultados y que conviene esperar efectos modestos. Las tres con mejor relación entre respaldo y esfuerzo para este bot son:

1. Mirar los propios números a menudo, en el momento.
2. Tener un colchón, medido en el tiempo que cubre (un mes de gastos es el umbral que más separa a quien pasa apuros de quien no).
3. Ponerse un tope por categoría antes de gastar.

La misma investigación pide cuidar el tono, porque los mensajes de regaño hacen que la gente deje de mirar, y no mandar mensajes de más. La Fase 12 añade esas tres funciones. La app móvil pasa a una fase posterior.

## Decisión

### 1. Topes en dólares, por mes calendario local

- Tabla `budgets` (migración `20261119120000_budgets`) con `limit_usd`. Un tope vigente por categoría, garantizado con un índice único parcial. Los reemplazados, quitados o deshechos quedan con `archived_at`.
- Solo categorías de gasto, globales o propias. Lo garantiza el trigger `budgets_check_category` además del bot. Las categorías de deudas no se ofrecen.
- Lo gastado contra un tope es la suma de los snapshots `amount_usd` (ADR 0002). Así un tope no se queda viejo con cada subida del dólar. Si el tope se dice en otra moneda, se convierte una sola vez con la tasa vigente del usuario y se confirma el valor guardado. Sin moneda se entiende USD, que es la unidad de los topes.
- Estado `ok`, `near` desde el 80 % y `over`. El 80 % no sale de la investigación: es el umbral habitual de las apps.
- Sin monto («quiero un tope en comida»), el bot pregunta y sugiere el promedio de los últimos tres meses en que ya anotaba, redondeado hacia arriba a 5 USD. La respuesta se junta con la pregunta como cualquier otra aclaración.
- Fijar un tope tiene botón Deshacer. `replaces_id` permite restaurar el tope que había antes.
- Intención nueva `set_budget` (`ParsedBudget`) y herramienta de consulta `budget_status`, en el prompt `extraccion-v7`. Comando `/topes`.

### 2. Colchón en días, sin tablas nuevas

- colchón = saldo total en USD a las tasas vigentes / gasto diario promedio. El promedio usa los últimos 90 días, o los días desde el primer movimiento si son menos (`gastos.domain.runway`).
- Con menos de 14 días de historial, o sin gastos, no se calcula: se explica por qué.
- Lo que te deben no cuenta hasta que te lo paguen.
- Escalones 14, 30, 60 y 90 días: el bot dice cuál es el siguiente.
- Herramienta de consulta `runway` («¿cuánto me dura la plata?») y comando `/colchon`.
- El resumen semanal suma la sección «🛟 Colchón» como plantilla fija fuera del texto del LLM, igual que las deudas (ADR 0016). Se descartó compararlo con la semana anterior: exigiría reconstruir los saldos y las tasas de hace siete días.
- La web calculará lo mismo con la función SQL `spending_pace` (días de la ventana y gasto en USD) y la misma división. La prueba pgTAP fija la ventana.

### 3. Una línea de contexto al anotar

- Cada gasto confirmado puede llevar hasta dos líneas: una por categoría del mensaje, primero las que tienen tope.
- Con tope: «comida: llevas 62,00 de 100,00 USD este mes; te quedan 38,00 USD para 12 días».
- Sin tope: la semana en curso frente a la semana pasada a la misma altura, solo si el usuario ya anotaba entonces.
- Ingresos y pagos de deudas no llevan línea.
- Tono descriptivo: «12,00 USD por encima del tope», nunca «te pasaste». No hay avisos por dejar de anotar ni mensajes aparte: el contexto viaja en la confirmación que ya se envía.
- `users.context_replies` (por defecto encendido) y el comando `/contexto` para apagarlo.
- `ContextService` nunca rompe una confirmación: si falla, la registra en el log y el gasto sale sin contexto.

## Consecuencias

- Evaluación: 15 frases nuevas en `bot/eval/dataset.jsonl` (`top-`, `tq-` y `col-`), incluida una con la palabra «tope» que es un gasto y no un tope.
- El contexto suma tres o cuatro consultas por mensaje anotado, sin llamadas al LLM.
- Un tope no es un movimiento: «eso fue transporte» después de fijar un tope corrige el último gasto, no el tope. Para cambiar un tope basta con escribir el nuevo monto o tocar Deshacer.
- **Web pendiente:** las tarjetas de colchón y de topes en Inicio (`budget_progress`, `spending_pace`) se hacen cuando la auditoría de interfaz que está sin commit en `web/` llegue a `main`. La base ya está lista y probada.
