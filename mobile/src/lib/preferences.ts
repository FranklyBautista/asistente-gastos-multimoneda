import type { Currency } from "./format";

/**
 * Opciones de las preferencias de la cuenta, las mismas que ofrece el bot en /start
 * (bot/src/gastos/chat/keyboards.py) y que acepta update_preferences
 * (migración 20261126120000_user_preferences).
 */
export const CURRENCY_OPTIONS: { value: Currency; label: string }[] = [
  { value: "USD", label: "USD" },
  { value: "USDT", label: "USDT" },
  { value: "VES", label: "Bs" },
  { value: "COP", label: "COP" },
];

export const RATE_SOURCE_OPTIONS: { value: string; label: string }[] = [
  { value: "bcv", label: "BCV (oficial)" },
  { value: "parallel", label: "Paralelo" },
  { value: "p2p", label: "Binance P2P" },
];

export const TIMEZONE_OPTIONS: { value: string; label: string }[] = [
  { value: "America/Caracas", label: "Caracas" },
  { value: "America/Bogota", label: "Bogotá" },
  { value: "Europe/Madrid", label: "Madrid" },
  { value: "America/New_York", label: "Nueva York" },
];

export type PreferencesPatch = {
  defaultCurrency?: Currency;
  vesRateSource?: string;
  timezone?: string;
  contextReplies?: boolean;
};

/** El nombre de la zona para mostrar; si no es una de las del bot, el nombre IANA legible. */
export function timezoneLabel(timezone: string): string {
  return TIMEZONE_OPTIONS.find((o) => o.value === timezone)?.label ?? timezone.replaceAll("_", " ");
}

const PREFERENCE_ERRORS: Record<string, string> = {
  not_linked: "Vincula tu cuenta con Telegram antes de cambiar tus preferencias.",
  invalid_currency: "Esa moneda no está disponible.",
  invalid_rate_source: "Esa fuente de tasa no está disponible.",
  invalid_timezone: "Esa zona horaria no está disponible.",
};

/** El mensaje de un error de update_preferences (el código va dentro del texto), o uno genérico. */
export function preferenceErrorMessage(message: string | undefined): string {
  const known = Object.keys(PREFERENCE_ERRORS).find((code) => message?.includes(code));
  return known ? PREFERENCE_ERRORS[known] : "No se pudo guardar. Inténtalo de nuevo.";
}
