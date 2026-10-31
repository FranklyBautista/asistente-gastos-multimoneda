# 0004. Fuentes de tasas, refresco y respaldo

- **Estado:** aceptada
- **Fecha:** 2026-10-27

## Contexto

El bot necesita una tasa a USD por moneda (ADR 0002) y, para el bolívar, tres: BCV, paralelo y P2P. Las APIs gratuitas tienen límites, pueden caerse y cambian de formato sin aviso. El plan inicial proponía Cotizave para el bolívar, pero no se encontró documentación ni un plan vigente.

## Decisión

| Tasa | Fuente | `source` | Notas |
|---|---|---|---|
| Bs BCV y paralelo | [DolarApi](https://ve.dolarapi.com/v1/dolares) | `bcv`, `parallel` | Sin llave. Publica el promedio en Bs por USD |
| Bs P2P | Binance P2P (`bapi/c2c/v2/friendly/c2c/adv/search`) | `p2p` | Sin llave, **no documentado**. Mediana de los 10 primeros anuncios de compra y de venta de USDT y punto medio entre ambas |
| COP | [ExchangeRate-API, acceso abierto](https://www.exchangerate-api.com/docs/free) | `fx` | Sin llave. Se actualiza a diario; pide atribución con enlace y como mucho una consulta por hora |
| USDT | [CoinGecko](https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd) | `coingecko` | Sin llave; límite de pocas consultas por minuto |

- El P2P cotiza Bs por **USDT**, no por USD. Se cruza con la tasa del USDT: `usd_per_unit(VES) = usd_per_unit(USDT) / Bs por USDT`. Si CoinGecko falla, se usa el último USDT guardado; si nunca hubo uno, el P2P se omite en esa vuelta.
- Las fuentes publican "unidades por USD"; `domain.conversion.usd_per_unit_from` invierte una sola vez y redondea a la escala de la columna (`numeric(20,10)`). Los JSON se leen con `Decimal`, nunca con `float`.
- Un trabajo de APScheduler refresca todas las fuentes al arrancar y cada `RATES_REFRESH_MINUTES` (60 por defecto). Cada fuente se consulta por separado: una caída se registra en el log y no frena a las demás.
- Cada refresco agrega filas a `exchange_rates`, que sirve también de historial. El bot nunca consulta una API al responder: lee la última tasa guardada.
- **Respaldo:** si una fuente deja de responder se sigue usando su última tasa, marcada como vieja cuando supera `RATES_MAX_AGE_HOURS` (6 por defecto). Si nunca hubo una tasa, se lanza `RateUnavailable` y el bot lo dice en vez de inventarla.
- `/tasas` muestra las cinco tasas, la fuente de Bs del usuario y el aviso de las viejas, con la atribución que pide ExchangeRate-API.

## Consecuencias

- Unas 120 filas por día en `exchange_rates`. Si crece demasiado, se puede compactar el historial a una fila por hora o por día.
- El endpoint de Binance puede cambiar o bloquearse; el respaldo y la tasa marcada como vieja lo absorben, y el cliente está aislado en `rates/ves.py`.
- La web (Fase 10) también debe mostrar la atribución de ExchangeRate-API donde muestre COP.
- Con `numeric(20,10)`, una tasa de 1.000 Bs por USD conserva 8 cifras significativas. Si el bolívar se devalúa varios órdenes de magnitud habrá que ampliar la escala con una migración.
