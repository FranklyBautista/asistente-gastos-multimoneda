-- Prueba de humo: confirma que pgTAP corre.
begin;
create extension if not exists pgtap with schema extensions;
select plan(1);
select ok(true, 'pgTAP está disponible');
select * from finish();
rollback;
