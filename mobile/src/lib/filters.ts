import { type Currency, type Kind, localToday } from "./format";

/** Filtros de Movimientos: los mismos que la web (moneda, tipo, categoría y fechas). */
export type TxFilters = {
  currency?: Currency;
  kind?: Kind;
  categoryId?: string;
  /** Últimos N días contando hoy; sin valor, todo el historial. */
  days?: number;
};

export const PERIODS = [7, 30, 90] as const;

export type TxQuery = {
  currency?: Currency;
  kind?: Kind;
  categoryId?: string;
  from?: string;
  to?: string;
};

/** Traduce los filtros a los parámetros de `list_transactions`, con días locales del usuario. */
export function toQuery(filters: TxFilters, timeZone: string): TxQuery {
  const { days, ...rest } = filters;
  if (!days) return rest;
  return { ...rest, from: localToday(timeZone, -(days - 1)), to: localToday(timeZone) };
}

/** Cuántos filtros de la hoja están activos (la moneda va aparte, en los chips). */
export function sheetFilterCount(filters: TxFilters): number {
  return [filters.kind, filters.categoryId, filters.days].filter(Boolean).length;
}

/** Al cambiar el tipo, la categoría elegida se descarta si es del otro tipo. */
export function withKind(
  filters: TxFilters,
  kind: Kind | undefined,
  categoryKind: (id: string) => Kind | undefined,
): TxFilters {
  const keep = !kind || !filters.categoryId || categoryKind(filters.categoryId) === kind;
  return { ...filters, kind, categoryId: keep ? filters.categoryId : undefined };
}
