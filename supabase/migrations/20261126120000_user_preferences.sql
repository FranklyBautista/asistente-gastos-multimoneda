-- Fase 13: las preferencias de la cuenta se cambian también desde la app (Perfil).
-- Igual que el resto de las escrituras de la web y la app (ADR 0012), pasan por una función:
-- la tabla users sigue sin política de update para authenticated.
--
-- Cada parámetro en null deja el valor como estaba, así la app cambia una preferencia a la vez.
-- Los valores válidos son los mismos que ofrece el bot en /start (chat/keyboards.py).

create function update_preferences(
  p_default_currency text default null,
  p_ves_rate_source text default null,
  p_timezone text default null,
  p_context_replies boolean default null
) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := (select public.app_user_id());
begin
  if v_user is null then
    raise exception 'not_linked' using errcode = '28000';
  end if;
  if p_default_currency is not null
     and p_default_currency not in ('VES', 'COP', 'USD', 'USDT') then
    raise exception 'invalid_currency' using errcode = '22023';
  end if;
  if p_ves_rate_source is not null
     and p_ves_rate_source not in ('bcv', 'parallel', 'p2p') then
    raise exception 'invalid_rate_source' using errcode = '22023';
  end if;
  -- Solo las zonas que ofrece el bot: el bot las abre con ZoneInfo y muestra su nombre.
  if p_timezone is not null and p_timezone not in (
    'America/Caracas', 'America/Bogota', 'Europe/Madrid', 'America/New_York'
  ) then
    raise exception 'invalid_timezone' using errcode = '22023';
  end if;

  update public.users set
    default_currency = coalesce(p_default_currency, default_currency),
    ves_rate_source = coalesce(p_ves_rate_source, ves_rate_source),
    timezone = coalesce(p_timezone, timezone),
    context_replies = coalesce(p_context_replies, context_replies)
  where id = v_user;
end;
$$;
revoke execute on function update_preferences(text, text, text, boolean) from public, anon;
grant execute on function update_preferences(text, text, text, boolean) to authenticated;
