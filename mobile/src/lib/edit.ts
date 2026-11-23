import type { Kind } from "./format";
import type { Category } from "./queries";

/** Categorías globales de la liquidación de deudas (migración debt_categories, ADR 0016). */
export const DEBT_CATEGORIES = ["pago de deudas", "cobro de deudas"];

/**
 * Categorías que se ofrecen al editar, como en la web: las del tipo elegido, sin las de deudas
 * (solo las usa el bot al liquidar), salvo la que el movimiento ya tiene.
 */
export function categoryOptions(
  categories: Category[],
  kind: Kind,
  currentId: string | null,
): Category[] {
  return categories.filter(
    (c) => c.kind === kind && (!DEBT_CATEGORIES.includes(c.name) || c.id === currentId),
  );
}

/** La categoría elegida si sigue siendo válida; si no (cambió el tipo), la primera. */
export function pickCategory(options: Category[], chosen: string | null): string | undefined {
  return options.some((c) => c.id === chosen) ? (chosen ?? undefined) : options[0]?.id;
}

/** Monto escrito en el teclado ("12,50" o "12.50"); null si no es un número mayor que cero. */
export function parseAmount(text: string): number | null {
  const value = Number(text.trim().replace(",", "."));
  return text.trim() !== "" && Number.isFinite(value) && value > 0 ? value : null;
}
