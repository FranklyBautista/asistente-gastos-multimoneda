"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { CODE_PATTERN, linkErrorMessage, normalizeCode } from "@/lib/link-errors";
import { createClient } from "@/lib/supabase/server";

export type FormState = { error?: string; notice?: string };

function credentials(formData: FormData) {
  return {
    email: String(formData.get("email") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
  };
}

export async function signIn(_prev: FormState, formData: FormData): Promise<FormState> {
  const { email, password } = credentials(formData);
  if (!email || !password) return { error: "Escribe tu correo y tu contraseña." };
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    return error.code === "email_not_confirmed"
      ? { error: "Confirma tu correo antes de entrar: revisa tu bandeja de entrada." }
      : { error: "Correo o contraseña incorrectos." };
  }
  redirect("/");
}

export async function signUp(_prev: FormState, formData: FormData): Promise<FormState> {
  const { email, password } = credentials(formData);
  if (!email) return { error: "Escribe tu correo." };
  if (password.length < 8) return { error: "La contraseña debe tener al menos 8 caracteres." };
  const origin = (await headers()).get("origin") ?? "";
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { emailRedirectTo: `${origin}/auth/callback` },
  });
  if (error) {
    return error.code === "weak_password"
      ? { error: "Esa contraseña es muy débil; prueba con una más larga." }
      : { error: "No se pudo crear la cuenta. Revisa el correo e inténtalo de nuevo." };
  }
  // Con la confirmación de correo activa (Supabase nube) no hay sesión hasta confirmar.
  if (!data.session) {
    return {
      notice: "Te enviamos un correo para confirmar la cuenta. Ábrelo y luego inicia sesión.",
    };
  }
  redirect("/");
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

export async function redeemCode(_prev: FormState, formData: FormData): Promise<FormState> {
  const code = normalizeCode(String(formData.get("code") ?? ""));
  if (!CODE_PATTERN.test(code)) {
    return { error: "El código tiene 8 letras y números, como K7MP4XQ2." };
  }
  const supabase = await createClient();
  const { error } = await supabase.rpc("redeem_link_code", { p_code: code });
  if (error) return { error: linkErrorMessage(error.message) };
  redirect("/");
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Errores de edit_transaction (supabase/migrations/20261109120000_web_panel.sql).
const EDIT_ERRORS: Record<string, string> = {
  not_linked: "Vincula tu cuenta con Telegram antes de editar.",
  transaction_not_found: "Ese movimiento ya no existe o se deshizo.",
  account_not_found: "Esa cuenta no existe.",
  category_mismatch: "Elige una categoría que corresponda al tipo de movimiento.",
  invalid_amount: "El monto debe ser mayor que cero.",
  invalid_kind: "Elige si es un gasto o un ingreso.",
  rate_unavailable: "Todavía no hay tasa guardada para esa moneda; inténtalo más tarde.",
};

/**
 * Edita un movimiento con la RPC `edit_transaction`, que valida que sea de la sesión,
 * recalcula el snapshot en USD y deja cada cambio en `corrections` (ADR 0014).
 */
export async function editTransaction(
  id: string,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  if (!UUID.test(id)) return { error: EDIT_ERRORS.transaction_not_found };
  const kind = String(formData.get("kind") ?? "");
  const amount = Number(String(formData.get("amount") ?? "").replace(",", "."));
  const account = String(formData.get("account") ?? "");
  const category = String(formData.get("category") ?? "");
  if (!Number.isFinite(amount) || amount <= 0) return { error: EDIT_ERRORS.invalid_amount };
  if (!UUID.test(account)) return { error: EDIT_ERRORS.account_not_found };
  if (!UUID.test(category)) return { error: EDIT_ERRORS.category_mismatch };

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("edit_transaction", {
    p_id: id,
    p_kind: kind,
    p_amount: amount,
    p_account_id: account,
    p_category_id: category,
  });
  if (error) {
    const known = Object.keys(EDIT_ERRORS).find((code) => error.message.includes(code));
    return { error: known ? EDIT_ERRORS[known] : "No se pudo guardar. Inténtalo de nuevo." };
  }
  redirect(`/movimientos?editado=${data}`);
}
