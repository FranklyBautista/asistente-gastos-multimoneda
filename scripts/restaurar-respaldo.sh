#!/bin/sh
# Restaura un volcado de .github/workflows/backup.yml en una base YA migrada
# (`supabase db push`), reemplazando todos los datos del esquema public.
#
# Corre dentro del contenedor postgres:17-alpine (ver docs/DESPLIEGUE.md#respaldos):
#   U  = cadena de conexión de destino (Session pooler, con contraseña)
#   /out/gastos.dump = el volcado ya descifrado
#
# - session_replication_role = replica apaga triggers y FK mientras se cargan los datos:
#   así el trigger de cuentas por defecto no duplica cuentas y el orden de carga no importa.
# - Las cuentas web (auth.users) no van en el volcado: los vínculos que apunten a usuarios
#   inexistentes se ponen en null y cada persona vuelve a vincular con /vincular.
set -eu
{
  echo "set session_replication_role = replica;"
  echo "do \$\$ declare r record; begin for r in select tablename from pg_tables where schemaname = 'public' loop execute format('truncate table public.%I cascade', r.tablename); end loop; end \$\$;"
  pg_restore --data-only --no-owner --no-privileges -f - /out/gastos.dump
  echo "update public.users set auth_user_id = null where auth_user_id is not null and auth_user_id not in (select id from auth.users);"
} | psql "$U" -v ON_ERROR_STOP=1 -q
psql "$U" -tAc "select 'usuarios: ' || count(*) from public.users union all select 'movimientos: ' || count(*) from public.transactions union all select 'cambios: ' || count(*) from public.exchanges"
