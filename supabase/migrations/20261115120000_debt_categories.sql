-- Categorías de los movimientos que nacen al liquidar una deuda con dinero (Fase 11, ADR 0016):
-- un gasto en «pago de deudas» si pagaste tú y un ingreso en «cobro de deudas» si te pagaron.
-- El bot no se las ofrece al LLM: solo las usa la liquidación.
insert into categories (user_id, name, kind) values
  (null, 'pago de deudas', 'expense'),
  (null, 'cobro de deudas', 'income');
