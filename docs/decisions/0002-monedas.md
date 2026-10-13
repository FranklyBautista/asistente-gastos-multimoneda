# 0002. Modelo de monedas y tasas

- **Estado:** aceptada
- **Fecha:** 2026-10-12

## Contexto

El usuario maneja bolívares, pesos colombianos, dólares y USDT a la vez. El bolívar tiene varias tasas de referencia (BCV, paralelo y P2P) y el mercado se mueve a diario. Mezclar la dirección de una tasa (Bs por USD frente a USD por Bs) es el error clásico que produce totales absurdos.

## Decisión

- Códigos internos: `VES`, `COP`, `USD` y `USDT`. El mapeo de `VED` (nombre que usan algunas APIs) vive solo en `rates/ves.py`.
- USD es el pivote. Toda tasa se guarda como `usd_per_unit` (USD por una unidad de la moneda); para USD vale 1.
- USDT es una moneda propia, con cuentas y tasa propias; no se trata como USD.
- Cada movimiento se guarda en su moneda original con un snapshot de la tasa (`usd_per_unit`, `amount_usd`) del momento en que se registró.
- La fuente de tasa del bolívar es una preferencia por usuario (`ves_rate_source`).
- Los saldos se calculan a partir de los movimientos; nunca se guardan.
- Montos con `Decimal` en el código y `numeric` en la base de datos; nunca `float`.
- Si el mensaje no deja clara la moneda (confianza menor a 0.8), se pregunta; no se adivina.

## Consecuencias

- El historial no cambia cuando el mercado se mueve, y siempre se puede reconstruir el total en USD de un periodo.
- Corregir un movimiento obliga a recalcular su snapshot.
- Sumar montos de monedas distintas sin pasar por `to_usd()` es un error que deben atrapar las pruebas del dominio.
