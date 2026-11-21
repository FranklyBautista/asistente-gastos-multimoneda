import { type Currency, isCurrency, isKind, type Kind } from "./format";
import { supabase } from "./supabase";

/**
 * Las mismas lecturas que la web (web/src/lib/data.ts), con el cliente de la app. Todo pasa
 * por la RLS de la sesión: solo devuelve datos de quien inició sesión. La app no calcula
 * dinero: saldos, equivalentes en USD y diferencias vienen de las vistas y funciones.
 */

function currency(value: unknown): Currency {
  if (!isCurrency(value)) throw new Error(`Moneda desconocida: ${String(value)}`);
  return value;
}

function kind(value: unknown): Kind {
  if (!isKind(value)) throw new Error(`Tipo de movimiento desconocido: ${String(value)}`);
  return value;
}

// ---- Usuario del bot vinculado ----

export type LinkedUser = { displayName: string | null; timezone: string; vesRateSource: string };

/** null si la cuenta web todavía no está vinculada con Telegram (/vincular). */
export async function getLinkedUser(): Promise<LinkedUser | null> {
  const { data, error } = await supabase
    .from("users")
    .select("display_name, timezone, ves_rate_source")
    .maybeSingle();
  if (error) throw new Error(`No se pudo leer el usuario: ${error.message}`);
  return data
    ? {
        displayName: data.display_name,
        timezone: data.timezone,
        vesRateSource: data.ves_rate_source,
      }
    : null;
}

// ---- Saldos ----

export type Balance = {
  accountId: string;
  name: string;
  currency: Currency;
  balance: number;
  /** null si la moneda todavía no tiene tasa guardada. */
  balanceUsd: number | null;
  rateSource: string | null;
  rateStale: boolean;
};

export async function getBalances(): Promise<Balance[]> {
  const { data, error } = await supabase
    .from("account_balances_usd")
    .select("*")
    .order("currency")
    .order("name");
  if (error) throw new Error(`No se pudieron leer los saldos: ${error.message}`);
  return data.map((row) => {
    if (!row.account_id || !row.name) {
      throw new Error(`Saldo con datos incompletos: ${JSON.stringify(row)}`);
    }
    return {
      accountId: row.account_id,
      name: row.name,
      currency: currency(row.currency),
      balance: Number(row.balance ?? 0),
      balanceUsd: row.balance_usd === null ? null : Number(row.balance_usd),
      rateSource: row.rate_source,
      rateStale: Boolean(row.rate_stale),
    };
  });
}

/** Gastos e ingresos en USD entre dos días locales (incluidos), como la web. */
export async function getPeriodTotals(
  from: string,
  to: string,
): Promise<{ incomeUsd: number; expensesUsd: number }> {
  const { data: spending, error } = await supabase.rpc("spending_by_category", {
    p_from: from,
    p_to: to,
  });
  if (error) throw new Error(`No se pudo leer el gasto del mes: ${error.message}`);
  let incomeUsd = 0;
  for (let offset = 0; offset < 2_000; offset += 100) {
    const { data, error: incomeError } = await supabase.rpc("list_transactions", {
      p_kind: "income",
      p_from: from,
      p_to: to,
      p_limit: 100,
      p_offset: offset,
    });
    if (incomeError) throw new Error(`No se pudieron leer los ingresos: ${incomeError.message}`);
    incomeUsd += data.reduce((sum, r) => sum + Number(r.amount_usd), 0);
    if (data.length < 100 || offset + data.length >= Number(data[0].total)) break;
  }
  return {
    incomeUsd,
    expensesUsd: spending.reduce((sum, c) => sum + Number(c.total_usd), 0),
  };
}

// ---- Movimientos ----

export type TransactionRow = {
  id: string;
  occurredAt: string;
  kind: Kind;
  amount: number;
  currency: Currency;
  accountName: string;
  categoryName: string | null;
  description: string | null;
  amountUsd: number;
  edited: boolean;
};

export const PAGE_SIZE = 25;

export type TransactionPage = { rows: TransactionRow[]; total: number; page: number };

export async function listTransactions(
  filters: { currency?: Currency; kind?: Kind },
  page: number,
): Promise<TransactionPage> {
  const { data, error } = await supabase.rpc("list_transactions", {
    p_currency: filters.currency,
    p_kind: filters.kind,
    p_limit: PAGE_SIZE,
    p_offset: (page - 1) * PAGE_SIZE,
  });
  if (error) throw new Error(`No se pudieron leer los movimientos: ${error.message}`);
  return {
    page,
    total: data.length ? Number(data[0].total) : 0,
    rows: data.map((r) => ({
      id: r.id,
      occurredAt: r.occurred_at,
      kind: kind(r.kind),
      amount: Number(r.amount),
      currency: currency(r.currency),
      accountName: r.account_name,
      // Sin categoría llega null aunque los tipos generados digan string.
      categoryName: (r.category_name as string | null) ?? null,
      description: (r.description as string | null) ?? null,
      amountUsd: Number(r.amount_usd),
      edited: r.edited,
    })),
  };
}

// ---- Cambios entre monedas ----

export type ExchangeRow = {
  id: string;
  occurredAt: string;
  fromAmount: number;
  fromCurrency: Currency;
  toAmount: number;
  toCurrency: Currency;
  effectiveRate: number;
  referenceRate: number | null;
  differencePct: number | null;
};

export async function getExchanges(): Promise<ExchangeRow[]> {
  const { data, error } = await supabase
    .from("exchange_history")
    .select("*")
    .order("occurred_at", { ascending: false })
    .limit(200);
  if (error) throw new Error(`No se pudieron leer los cambios: ${error.message}`);
  return data.map((r) => ({
    id: String(r.id),
    occurredAt: String(r.occurred_at),
    fromAmount: Number(r.from_amount),
    fromCurrency: currency(r.from_currency),
    toAmount: Number(r.to_amount),
    toCurrency: currency(r.to_currency),
    effectiveRate: Number(r.effective_rate),
    referenceRate: r.reference_rate === null ? null : Number(r.reference_rate),
    differencePct: r.difference_pct === null ? null : Number(r.difference_pct),
  }));
}

// ---- Deudas ----

export type DebtRow = {
  id: string;
  direction: "i_owe" | "owed_to_me";
  counterparty: string;
  currency: Currency;
  amount: number;
  remaining: number;
  status: "open" | "partial" | "settled";
  description: string | null;
  incurredAt: string;
};

/** Deudas vigentes (sin las anuladas) desde `debt_balances`. */
export async function getDebts(): Promise<DebtRow[]> {
  const { data, error } = await supabase
    .from("debt_balances")
    .select("*")
    .order("incurred_at", { ascending: false })
    .limit(500);
  if (error) throw new Error(`No se pudieron leer las deudas: ${error.message}`);
  return data.map((r) => ({
    id: String(r.debt_id),
    direction: r.direction === "owed_to_me" ? "owed_to_me" : "i_owe",
    counterparty: String(r.counterparty),
    currency: currency(r.currency),
    amount: Number(r.amount),
    remaining: Number(r.remaining),
    status: r.status === "settled" || r.status === "partial" ? r.status : "open",
    description: r.description,
    incurredAt: String(r.incurred_at),
  }));
}

// ---- Vinculación ----

/** Canjea el código de /vincular; lanza el código de error de la base (ver link-errors). */
export async function redeemLinkCode(code: string): Promise<void> {
  const { error } = await supabase.rpc("redeem_link_code", { p_code: code });
  if (error) throw new Error(error.message);
}
