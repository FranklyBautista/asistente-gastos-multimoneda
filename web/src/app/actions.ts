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
