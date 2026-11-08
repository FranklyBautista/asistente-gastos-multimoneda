# 0013. La web en Vercel y el bot en Railway

- **Estado:** aceptada
- **Fecha:** 2026-11-08

## Contexto

La web (Next.js en `web/`) necesitaba un despliegue público para probar en producción el registro, la vinculación con `/vincular` y los saldos. Al importar el repositorio, Vercel detectó `bot/` y `web/` y propuso desplegar ambos como servicios de un mismo proyecto. El formulario no dejó continuar sin una configuración de servicios.

## Decisión

### Solo la web va a Vercel

- `vercel.json`, en la raíz del repositorio, declara un único servicio (`web`), público en `/`, sin bindings. El Root Directory del proyecto queda en la raíz, porque `root` se resuelve desde ese archivo.
- La web y el bot no se llaman entre sí: se comunican por Supabase. `WEB_URL` es solo un enlace de texto en el mensaje de `/vincular`.

### El bot se queda en Railway

- Al arrancar, el bot registra su webhook en Telegram (`bot/src/gastos/main.py`). Otra instancia con el mismo token se llevaría los mensajes de la que está en Railway.
- APScheduler (tasas, resumen semanal, purga), el límite de mensajes y las aclaraciones pendientes viven en un proceso siempre encendido (ADR 0010). Los servicios de Vercel están pensados para atender peticiones.

### Variables de la web

- Solo `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. La llave es publicable y la autorización real la hace la RLS (ADR 0012). La web no recibe `DATABASE_URL` ni llaves de servicio.

## Consecuencias

- Las variables `NEXT_PUBLIC_*` se fijan al compilar. Sin ellas, `proxy.ts` falla y todas las rutas responden 500; agregarlas después exige volver a desplegar.
- Si Vercel vuelve a proponer `bot` como servicio, no hay que aceptarlo.
- El repositorio no usa workspaces, así que Vercel no puede saltarse por sí solo los builds de cambios ajenos a `web/`. Un cambio en `bot/` puede generar un build de la web sin efecto.
- La URL de Vercel se configura en dos sitios más: Supabase Auth (Site URL y Redirect URLs) y `WEB_URL` en Railway. Si cambia el dominio, hay que actualizar ambos.
