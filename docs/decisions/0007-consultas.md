# 0007. Consultas conversacionales

- **Estado:** aceptada
- **Fecha:** 2026-11-01

## Contexto

La Fase 6 responde preguntas como "¿cuánto gasté esta semana?" con datos reales. Hay tres riesgos: que el LLM escriba SQL erróneo o inseguro, que se equivoque con las fechas ("esta semana" depende de la zona horaria) y que invente una cifra al redactar. Además, el plan gratuito de Gemini ya dio errores 429 con una sola llamada por mensaje.

## Decisión

- **Herramientas con parámetros tipados, en la misma llamada de extracción.** La extracción que ya clasifica la intención devuelve, con `intent: query`, un `ParsedQuery`: la herramienta (`spending_by_category`, `totals`, `account_balances` o `list_transactions`) y sus parámetros, validados por Pydantic. Es el equivalente a function calling, pero sin una segunda llamada al LLM.
- **SQL fijo.** Cada herramienta es una consulta de `db/repositories/reports.py`; los filtros opcionales se componen con `psycopg.sql` y parámetros. El LLM nunca escribe SQL. Todo filtra por `user_id` y excluye lo borrado.
- **Fechas en código.** El LLM elige un periodo de una lista cerrada (`today`, `this_week`, `last_month`, `month` con su número…) y `domain.periods.resolve_range` calcula el rango exacto `[inicio, fin)` en la zona horaria del usuario. La semana empieza el lunes. "Octubre" sin año es el último octubre que ya empezó. Sin periodo se usa este mes, o "desde siempre" para listar movimientos.
- **Categorías sin adivinar.** Una categoría que no existe no se ignora (eso daría el total de todas): el bot dice que no la tiene y lista las disponibles. El prompt (`extraccion-v4`) pide pasarla tal como se dijo: en una prueba en Telegram, un modelo respondió con el total de todos los gastos a "¿cuánto gasté en mascotas?", probablemente porque cambió la categoría por otra o la dejó vacía.
- **Siempre por moneda original.** Ningún total suma Bs con USD. El consolidado en USD solo aparece si se pide. Para gastos e ingresos es la suma de los snapshots (lo que valía cada movimiento al registrarse) y la respuesta lo dice. Para saldos usa las tasas vigentes (con tu fuente de Bs), avisa si alguna está vieja y deja fuera del total, con aviso, las monedas sin tasa.
- **Respuestas con plantillas, no redactadas por el LLM.** El plan proponía que el LLM redactara con lo que devolvieran las herramientas. Se cambió por plantillas fijas en `chat/answers.py`: ninguna cifra puede salir inventada, no hace falta verificar el texto y se ahorra una llamada por pregunta. Sin datos, la respuesta lo dice ("No tengo gastos registrados esta semana") en vez de mostrar ceros. La redacción con LLM y verificación de cifras queda para el resumen semanal (Fase 7), donde un texto natural sí aporta.

## Consecuencias

- Las preguntas fuera de las cuatro herramientas reciben un mensaje con lo que el bot sí puede responder. Ampliar es agregar una herramienta: un valor en `ParsedQuery.tool`, una consulta y una plantilla.
- Las respuestas son más rígidas que un texto redactado, pero exactas y verificables por prueba.
- La herramienta `list_debts` de la Fase 11 se agrega aquí mismo.
