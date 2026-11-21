/** Mensajes de Supabase Auth traducidos, sin detalles internos (como la web). */
export function authErrorMessage(code: string | undefined, mode: "signIn" | "signUp"): string {
  if (code === "email_not_confirmed") {
    return "Confirma tu correo antes de entrar: revisa tu bandeja de entrada.";
  }
  if (code === "weak_password") return "Esa contraseña es muy débil; prueba con una más larga.";
  return mode === "signIn"
    ? "Correo o contraseña incorrectos."
    : "No se pudo crear la cuenta. Revisa el correo e inténtalo de nuevo.";
}
