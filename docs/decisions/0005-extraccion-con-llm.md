# 0005. Extracción de movimientos con Gemini

- **Estado:** aceptada
- **Fecha:** 2026-10-31

## Contexto

La Fase 4 convierte mensajes escritos como se habla ("taxi 20 mil y café 3 dólares") en movimientos guardados. El ADR 0001 eligió Gemini Flash como proveedor principal detrás de una interfaz propia. Hacía falta decidir qué modelo usar, qué hacer cuando el proveedor falla, dónde guardar los mensajes que esperan una aclaración y cómo deshacer un registro.

## Decisión

- **Proveedor:** API de Gemini (Google AI Studio) en su plan gratuito. La suscripción Google AI Pro es un producto aparte y no da acceso a la API. La llave va en `GEMINI_API_KEY`.
- **Modelos:** `GEMINI_MODELS` es una lista en orden de preferencia: hoy `gemini-3.5-flash`, `gemini-3.5-flash-lite` y `gemini-3.8-flash`. El 3.8 es el más nuevo, pero el 2026-10-31 falló en 10 de 10 mensajes (503, 429 o tiempo agotado), mientras que los 3.5 respondieron todos; por eso va último. Las 10 frases de prueba se interpretaron bien. Se descartaron los alias `*-latest` (cambian de modelo sin aviso y en la prueba uno tardó 166 s) y los modelos *preview* (límites más bajos).
- **Fallos del proveedor:** cada llamada tiene un tiempo límite (`LLM_TIMEOUT_SECONDS`, 20 s; las respuestas sanas tardan entre 4 y 15 s). Con 429, 5xx o tiempo agotado se pasa al siguiente modelo. Si la salida no valida contra el esquema Pydantic, se reintenta una vez con el mismo modelo. Si nada funciona, se lanza `LLMUnavailable` y el bot avisa que no anotó nada. Los errores 400, 401 y 403 no se esconden: son de configuración.
- **Salida estructurada:** el esquema `Extraction` se pasa como `response_schema` y se vuelve a validar con Pydantic al recibirlo. Los montos llegan como `float` y se pasan a `Decimal` por `str`. Las categorías que no estén en la lista del usuario se descartan y se usa la de respaldo ("otros" u "otros ingresos").
- **Prompt versionado:** `extraction/prompt.py` con `PROMPT_VERSION`, las reglas del léxico de monedas (ADR 0002) y 15 ejemplos. Un test comprueba que todos los ejemplos cumplen el esquema.
- **Moneda dudosa:** con `currency` null o confianza menor a 0.8, el mensaje queda pendiente y se pregunta con botones (la moneda por defecto del usuario va primero). La moneda elegida se aplica solo a los movimientos dudosos del mensaje.
- **Pendientes en memoria:** se guardan en un diccionario con un token de un solo uso que vence a los 30 minutos (máximo 500). Si el bot se reinicia antes de que el usuario responda, el botón avisa que expiró y basta con reenviar el mensaje. No justifica una tabla mientras el bot corra en una sola instancia.
- **Deshacer:** todos los movimientos de un mensaje se insertan en una sola transacción SQL, así que comparten `created_at` (`now()`). El botón Deshacer lleva el id de uno de ellos y borra lógicamente los del mismo usuario con ese `created_at` y ese `raw_text`. Funciona tras un reinicio y no requiere columnas nuevas.

## Consecuencias

- En el plan gratuito Google puede usar los mensajes para mejorar sus productos. Si eso deja de ser aceptable, se activa la facturación del proyecto o se usa Groq; el cambio queda aislado en `llm/`.
- Groq sigue en la configuración, pero todavía no tiene adaptador: con `LLM_PROVIDER=groq` el bot no arranca y lo dice.
- La precisión del extractor se mide con el set de evaluación de la Fase 8; hasta entonces el prompt se ajusta con el uso real.
- Si el bot pasa a varias instancias, los pendientes deben ir a la base de datos o a Redis.
