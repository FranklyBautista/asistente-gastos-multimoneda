# Guion del video de demo (2–3 minutos)

El objetivo es que quien lo vea entienda en menos de 3 minutos qué problema resuelve el proyecto y cómo funciona por dentro. Grábalo con el bot de producción y la web en <https://asistente-gastos-multimoneda.vercel.app>: el teléfono (o Telegram Desktop) a un lado y el navegador al otro.

## Antes de grabar

- Pide `/tasas` para confirmar que hay tasas recientes.
- Ten una cuenta web vinculada con unos cuantos movimientos de días anteriores, para que las gráficas tengan forma.
- Borra lo que no quieras mostrar con el botón Deshacer.
- Oculta las notificaciones del sistema y usa el modo oscuro o el claro en las dos pantallas, no uno distinto en cada una.

## Escenas

| Tiempo | Pantalla | Qué haces | Qué dices |
|---|---|---|---|
| 0:00–0:15 | Web, inicio | Muestra el consolidado en USD. | «Vivo con bolívares, pesos, dólares y USDT a la vez. Este asistente lleva mis cuentas en las cuatro monedas.» |
| 0:15–0:45 | Telegram | Escribe `gasté 15 en el almuerzo`. El bot pregunta la moneda con botones; elige USD. Luego escribe `pagué 70 bs de pasaje y 20 mil de taxi`. | «Le escribo como hablo. Si la moneda es ambigua, pregunta en vez de adivinar. Puede anotar varios movimientos de un mismo mensaje, cada uno con la tasa del momento.» |
| 0:45–1:05 | Telegram | `cambié 50 usdt a bs a 985` | «Los cambios entre monedas se comparan contra la tasa de referencia: aquí ves cuánto gané o perdí.» |
| 1:05–1:20 | Telegram | `eso fue transporte` y luego `¿cuánto gasté esta semana?` | «Si se equivoca, lo corrijo escribiendo y lo tiene en cuenta en los mensajes siguientes. Las respuestas salen de la base de datos: el modelo nunca inventa una cifra.» |
| 1:20–1:35 | Telegram | `/vincular` y copia el código. En la web: Vincular y pega el código. *(Si ya está vinculada, salta esta escena.)* | «La web se une a mi cuenta de Telegram con un código de un solo uso.» |
| 1:35–2:05 | Web, Movimientos | Recarga y muestra los movimientos recién anotados. Filtra por Bs. Edita uno: cambia la categoría y guarda. | «Todo lo del chat aparece aquí. Puedo filtrar y corregir; al editar se recalcula el valor en USD, y el bot también aprende de esa corrección.» |
| 2:05–2:30 | Web, Gráficas | Gasto por categoría, por semana y poder adquisitivo del bolívar. Abre «Ver datos». | «Aquí veo en qué gasto y cuánto valor perdieron mis bolívares frente al dólar. Cada gráfica tiene su tabla.» |
| 2:30–2:45 | Web, Cambios | El historial con la diferencia en %. | «Y aquí reviso si cambié bien a lo largo del tiempo.» |
| 2:45–3:00 | README del repo | Diagrama de arquitectura y métricas. | «Bot en Python con capas verificadas en el CI, Postgres con RLS por dueño y una web en Next.js. La extracción acierta el 95,8 % del set de evaluación.» |

## Después

- Súbelo a YouTube (no listado) o a Loom.
- Enlázalo en la sección «Demo» del [`README.md`](../README.md).
