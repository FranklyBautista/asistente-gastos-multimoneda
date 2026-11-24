/** Traduce los errores de redeem_link_code (ADR 0012) a mensajes para la persona. */
const MESSAGES: Record<string, string> = {
  invalid_code:
    "Ese código no es válido o ya venció. Pide uno nuevo con /vincular en Telegram (dura 10 minutos).",
  telegram_already_linked: "Esa cuenta de Telegram ya está vinculada con otra cuenta web.",
  web_already_linked: "Tu cuenta web ya está vinculada con una cuenta de Telegram.",
  not_authenticated: "Tu sesión venció. Vuelve a iniciar sesión.",
};

const FALLBACK = "No se pudo vincular la cuenta. Inténtalo de nuevo en un momento.";

export function linkErrorMessage(message: string | undefined): string {
  return (message && MESSAGES[message]) || FALLBACK;
}

/** Formato del código: 8 caracteres sin I, O, 0 ni 1 (igual que en la base de datos). */
export const CODE_PATTERN = /^[A-HJ-NP-Z2-9]{8}$/;

export function normalizeCode(raw: string): string {
  return raw.replace(/[\s-]/g, "").toUpperCase();
}
