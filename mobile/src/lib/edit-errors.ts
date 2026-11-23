/**
 * Errores de edit_transaction (migraciones 20261109120000_web_panel y
 * 20261123120000_edit_debt_linked, ADR 0014) traducidos para la persona. La app móvil usa una
 * copia exacta de este archivo (mobile/src/lib/edit-errors.ts, vigilada por parity-test.ts).
 */
export const EDIT_ERRORS: Record<string, string> = {
  not_linked: "Vincula tu cuenta con Telegram antes de editar.",
  transaction_not_found: "Ese movimiento ya no existe o se deshizo.",
  account_not_found: "Esa cuenta no existe.",
  category_mismatch: "Elige una categoría que corresponda al tipo de movimiento.",
  invalid_amount: "El monto debe ser mayor que cero.",
  invalid_kind: "Elige si es un gasto o un ingreso.",
  rate_unavailable: "Todavía no hay tasa guardada para esa moneda; inténtalo más tarde.",
  debt_linked:
    "Es el pago de una deuda: si lo cambias aquí, la deuda quedaría descuadrada. Si es lo último que anotaste, deshazlo en el bot y anótalo de nuevo.",
};

export const DEBT_LINKED_MESSAGE = EDIT_ERRORS.debt_linked;

/** El mensaje de un error de la base (el código va dentro del texto), o uno genérico. */
export function editErrorMessage(message: string | undefined): string {
  const known = Object.keys(EDIT_ERRORS).find((code) => message?.includes(code));
  return known ? EDIT_ERRORS[known] : "No se pudo guardar. Inténtalo de nuevo.";
}
