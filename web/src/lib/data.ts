import "server-only";

import { redirect } from "next/navigation";
import { connection } from "next/server";
import { cache } from "react";

import { type Currency, isCurrency, isKind, type Kind } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

/**
 * Capa de acceso a datos: la única puerta de la web a Supabase. Cada consulta pasa por la
 * RLS de la sesión, así que solo devuelve datos de quien inició sesión (ADR 0012). Nada de
 * esto se cachea entre peticiones: son datos financieros personales.
 */

export type LinkedUser = { displayName: string | null; timezone: string; vesRateSource: string };
export type Session = { email: string; user: LinkedUser | null };

/** Sesión y usuario del bot vinculado; una sola lectura por petición. */
export const getSession = cache(async (): Promise<Session> => {
  // Siempre en la petición: el cliente de Supabase usa la hora actual para validar la sesión,
  // y Next.js no permite eso durante un prerender.
  await connection();
  const supabase = await createClient();
  const { data: claims } = await supabase.auth.getClaims();
  if (!claims?.claims) redirect("/login");
  const email = String(claims.claims.email ?? "");

  const { data: user, error } = await supabase
    .from("users")
    .select("display_name, timezone, ves_rate_source")
    .maybeSingle();
  if (error) throw new Error(`No se pudo leer el usuario: ${error.message}`);
  return {
    email,
    user: user
      ? {
          displayName: user.display_name,
          timezone: user.timezone,
          vesRateSource: user.ves_rate_source,
        }
      : null,
  };
});

function currency(value: unknown): Currency {
  if (!isCurrency(value)) throw new Error(`Moneda desconocida: ${String(value)}`);
  return value;
}

function kind(value: unknown): Kind {
  if (!isKind(value)) throw new Error(`Tipo de movimiento desconocido: ${String(value)}`);
  return value;
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
  usdPerUnit: number | null;
  rateFetchedAt: string | null;
  rateStale: boolean;
};

export async function getBalances(): Promise<Balance[]> {
  const supabase = await createClient();
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
      usdPerUnit: row.usd_per_unit === null ? null : Number(row.usd_per_unit),
      rateFetchedAt: row.rate_fetched_at,
      rateStale: Boolean(row.rate_stale),
    };
  });
}

// ---- Movimientos ----

export type TransactionFilters = {
  currency?: Currency;
  kind?: Kind;
  categoryId?: string;
  from?: string;
  to?: string;
};

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

export async function listTransactions(
  filters: TransactionFilters,
  page: number,
): Promise<{ rows: TransactionRow[]; total: number }> {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("list_transactions", {
    p_currency: filters.currency,
    p_kind: filters.kind,
    p_category_id: filters.categoryId,
    p_from: filters.from,
    p_to: filters.to,
    p_limit: PAGE_SIZE,
    p_offset: (page - 1) * PAGE_SIZE,
  });
  if (error) throw new Error(`No se pudieron leer los movimientos: ${error.message}`);
  return {
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

export type EditableTransaction = {
  id: string;
  kind: Kind;
  amount: number;
  currency: Currency;
  accountId: string;
  categoryId: string | null;
  description: string | null;
  occurredAt: string;
  rawText: string | null;
};

export async function getTransaction(id: string): Promise<EditableTransaction | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("transactions")
    .select(
      "id, kind, amount, currency, account_id, category_id, description, occurred_at, raw_text",
    )
    .eq("id", id)
    .is("deleted_at", null)
    .maybeSingle();
  if (error) throw new Error(`No se pudo leer el movimiento: ${error.message}`);
  if (!data) return null;
  return {
    id: data.id,
    kind: kind(data.kind),
    amount: Number(data.amount),
    currency: currency(data.currency),
    accountId: data.account_id,
    categoryId: data.category_id,
    description: data.description,
    occurredAt: data.occurred_at,
    rawText: data.raw_text,
  };
}

export type Account = { id: string; name: string; currency: Currency };
export type Category = { id: string; name: string; kind: Kind };

export async function getAccounts(): Promise<Account[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("accounts")
    .select("id, name, currency")
    .eq("archived", false)
    .order("currency")
    .order("name");
  if (error) throw new Error(`No se pudieron leer las cuentas: ${error.message}`);
  return data.map((a) => ({ id: a.id, name: a.name, currency: currency(a.currency) }));
}

export async function getCategories(): Promise<Category[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("categories")
    .select("id, name, kind")
    .order("kind")
    .order("name");
  if (error) throw new Error(`No se pudieron leer las categorías: ${error.message}`);
  return data.map((c) => ({ id: c.id, name: c.name, kind: kind(c.kind) }));
}

// ---- Gráficas ----

export type CategorySpending = { category: string; totalUsd: number; movements: number };
export type WeekSpending = { weekStart: string; expensesUsd: number; incomeUsd: number };
export type BolivarRate = { day: string; source: string; usdPerUnit: number };

export async function getSpendingByCategory(from: string, to: string): Promise<CategorySpending[]> {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("spending_by_category", { p_from: from, p_to: to });
  if (error) throw new Error(`No se pudo leer el gasto por categoría: ${error.message}`);
  return data.map((r) => ({
    category: r.category,
    totalUsd: Number(r.total_usd),
    movements: Number(r.movements),
  }));
}

export async function getSpendingByWeek(weeks: number): Promise<WeekSpending[]> {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("spending_by_week", { p_weeks: weeks });
  if (error) throw new Error(`No se pudo leer el gasto por semana: ${error.message}`);
  return data.map((r) => ({
    weekStart: r.week_start,
    expensesUsd: Number(r.expenses_usd),
    incomeUsd: Number(r.income_usd),
  }));
}

export async function getBolivarRates(days: number): Promise<BolivarRate[]> {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("bolivar_rates", { p_days: days });
  if (error) throw new Error(`No se pudo leer la tasa del bolívar: ${error.message}`);
  return data.map((r) => ({ day: r.day, source: r.source, usdPerUnit: Number(r.usd_per_unit) }));
}

// ---- Cambios entre monedas ----

export type ExchangeRow = {
  id: string;
  occurredAt: string;
  fromAmount: number;
  fromCurrency: Currency;
  fromAccount: string;
  toAmount: number;
  toCurrency: Currency;
  toAccount: string;
  effectiveRate: number;
  referenceRate: number | null;
  differencePct: number | null;
};

export async function getExchanges(): Promise<ExchangeRow[]> {
  const supabase = await createClient();
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
    fromAccount: String(r.from_account),
    toAmount: Number(r.to_amount),
    toCurrency: currency(r.to_currency),
    toAccount: String(r.to_account),
    effectiveRate: Number(r.effective_rate),
    referenceRate: r.reference_rate === null ? null : Number(r.reference_rate),
    differencePct: r.difference_pct === null ? null : Number(r.difference_pct),
  }));
}
