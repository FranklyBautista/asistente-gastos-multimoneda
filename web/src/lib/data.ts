import "server-only";

import { redirect } from "next/navigation";
import { connection } from "next/server";

import { createClient } from "@/lib/supabase/server";

export type Balance = {
  accountId: string;
  name: string;
  currency: "VES" | "COP" | "USD" | "USDT";
  balance: number;
};

export type Profile = {
  email: string;
  /** null mientras la cuenta web no esté vinculada con Telegram. */
  linked: { displayName: string | null; balances: Balance[] } | null;
};

/**
 * Capa de acceso a datos: la única puerta de la web a Supabase. Cada consulta pasa por la
 * RLS de la sesión, así que solo devuelve datos de quien inició sesión (ADR 0012). Nada de
 * esto se cachea: son datos financieros personales.
 */
export async function getProfile(): Promise<Profile> {
  // Siempre en la petición: el cliente de Supabase usa la hora actual para validar la sesión,
  // y Next.js no permite eso durante un prerender.
  await connection();
  const supabase = await createClient();
  const { data: claims } = await supabase.auth.getClaims();
  if (!claims?.claims) redirect("/login");
  const email = String(claims.claims.email ?? "");

  const { data: user, error } = await supabase.from("users").select("display_name").maybeSingle();
  if (error) throw new Error(`No se pudo leer el usuario: ${error.message}`);
  if (!user) return { email, linked: null };

  const { data: rows, error: balancesError } = await supabase
    .from("account_balances")
    .select("account_id, name, currency, balance")
    .order("currency");
  if (balancesError) throw new Error(`No se pudieron leer los saldos: ${balancesError.message}`);

  return {
    email,
    linked: { displayName: user.display_name, balances: (rows ?? []).map(toBalance) },
  };
}

const CURRENCIES: readonly Balance["currency"][] = ["VES", "COP", "USD", "USDT"];

/** Las columnas de una vista llegan como anulables en los tipos generados; se validan aquí. */
function toBalance(row: {
  account_id: string | null;
  name: string | null;
  currency: string | null;
  balance: number | null;
}): Balance {
  const currency = CURRENCIES.find((c) => c === row.currency);
  if (!row.account_id || !row.name || !currency) {
    throw new Error(`Saldo con datos incompletos: ${JSON.stringify(row)}`);
  }
  return {
    accountId: row.account_id,
    name: row.name,
    currency,
    balance: Number(row.balance ?? 0),
  };
}
