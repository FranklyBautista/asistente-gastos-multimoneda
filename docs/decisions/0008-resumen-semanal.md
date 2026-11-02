# 0008. Resumen semanal

- **Estado:** aceptada
- **Fecha:** 2026-11-01

## Contexto

La Fase 7 manda cada semana un mensaje que explica en lenguaje natural cómo te fue, con un dato propio de quien vive en Venezuela: cuánto poder adquisitivo perdieron (o ganaron) tus bolívares. Un texto redactado se lee mejor que una tabla, pero un LLM puede inventar o cambiar cifras, y aquí son datos financieros. Además, el envío debe respetar la zona horaria de cada usuario y no repetirse si el bot se reinicia.

## Decisión

- **Métricas en código.** `domain/metrics.py` calcula, con datos de la BD, los gastos e ingresos por moneda original, su suma en USD (snapshots), la variación contra la semana pasada, la categoría con más gasto y el poder adquisitivo del bolívar. El LLM no hace ninguna cuenta.
- **Semana a la misma altura.** La semana va del lunes a las 00:00 (hora local) hasta ahora y se compara con la semana pasada hasta hace exactamente 7 días. Así el resumen del domingo no compara seis días y medio con siete, y `/resumen` un miércoles compara tres días con tres. La comparación es en USD con la tasa de cada movimiento, porque sumar Bs con COP no tiene sentido.
- **Poder adquisitivo del bolívar.** Variación de `usd_per_unit` del Bs con tu fuente (BCV, paralelo o P2P) entre la tasa vigente al empezar la semana y la de ahora, aplicada a tu saldo actual en Bs: "tus 10.000 Bs valían 25 USD el lunes y hoy 20 USD". Si el historial de tasas empieza a mitad de semana, se usa la primera tasa guardada y el texto dice "desde el 28/10".
- **Frases con cifras ya formateadas.** Las métricas se convierten en frases (`facts`) con los números escritos como los ve el usuario (`1.200,50 Bs`, `12,5 %`). Esas frases son, a la vez, la plantilla de respaldo y lo único que recibe el LLM (en JSON, sin ids ni filas).
- **Redacción con LLM y verificación de cifras.** El LLM (prompt `resumen-v1`) devuelve de 3 a 7 líneas. Se piden como lista porque, pedido como un solo texto, Gemini escribía un párrafo aunque se le pidieran líneas. Cada número del texto debe valer lo mismo que alguno de las frases o del encabezado (`domain/numbers.py`): se compara por valor para aceptar "1.200" donde la frase decía "1.200,00", pero no "1.250". Si sobra un número, si el texto es demasiado largo o si el LLM no responde, se envía la plantilla. El resumen nunca falla ni muestra una cifra inventada.
- **Lo que queda fuera del LLM.** El encabezado con las fechas y el aviso de tasa vieja se arman en código. Una semana sin movimientos no llama al LLM.
- **Envío por zona horaria, sin duplicados.** Un trabajo de APScheduler corre cada 15 minutos y le envía el resumen a cada usuario con onboarding cuando en su zona horaria es domingo desde las 18:00 (`WEEKLY_SUMMARY_HOUR`). Antes de enviar inserta la fila `(user_id, week_start)` en `weekly_summaries`, cuya clave primaria impide un segundo envío aunque el bot se reinicie o corra dos veces. Si el envío falla, la fila se borra y se reintenta en la siguiente corrida. `/resumen` da el de la semana en curso cuando lo pidas y no cuenta como envío.

## Consecuencias

- La verificación solo ve cifras escritas con dígitos. Un número escrito con letras ("dos categorías") o una dirección invertida ("subió" en vez de "bajó") no se detectan; el prompt prohíbe lo primero y las frases ya dicen la dirección con palabras.
- Si el bot está apagado todo el domingo desde las 18:00, ese resumen no se envía: el lunes ya es otra semana. Se puede pedir con `/resumen`, pero un lunes muestra la semana nueva.
- Cada resumen cuesta una llamada al LLM por usuario y semana; con el plan gratuito de Gemini es despreciable.
- El texto de las frases vive en `services/weekly_summary.py` y no en `chat/`, porque es también la entrada del LLM. Por eso el formato de montos pasó de `chat/formatting.py` a `domain/money.py`.
- La sección "Deudas pendientes" de la Fase 11 se agrega como una frase más.
