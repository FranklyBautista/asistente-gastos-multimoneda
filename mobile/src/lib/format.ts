export const CURRENCIES = ["VES", "COP", "USD", "USDT"] as const;
export type Currency = (typeof CURRENCIES)[number];

export function isCurrency(value: unknown): value is Currency {
  return CURRENCIES.some((c) => c === value);
}

// Decimales por moneda, igual que el bot (domain/money.py).
const DECIMALS: Record<Currency, number> = { VES: 2, COP: 0, USD: 2, USDT: 2 };

export const CURRENCY_LABELS: Record<Currency, string> = {
  VES: "Bs",
  COP: "COP",
  USD: "USD",
  USDT: "USDT",
};

export const RATE_SOURCE_LABELS: Record<string, string> = {
  bcv: "BCV",
  parallel: "paralelo",
  p2p: "Binance P2P",
  fx: "ExchangeRate-API",
  coingecko: "CoinGecko",
  pivot: "pivote",
};

export const KIND_LABELS = { expense: "Gasto", income: "Ingreso" } as const;
export type Kind = keyof typeof KIND_LABELS;

export function isKind(value: unknown): value is Kind {
  return value === "expense" || value === "income";
}

export function formatAmount(amount: number, currency: Currency): string {
  const digits = DECIMALS[currency];
  return new Intl.NumberFormat("es-VE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}

/** "$1.234,50" y "−$5,66": el signo va antes del símbolo. */
export function formatUsd(amount: number): string {
  const text = `$${formatAmount(Math.abs(amount), "USD")}`;
  return amount < 0 && text !== "$0,00" ? `−${text}` : text;
}

/** Una tasa legible: 0,0016 USD por Bs se muestra como 625,00 Bs por USD. */
export function formatRate(value: number, digits = 2): string {
  return new Intl.NumberFormat("es-VE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${new Intl.NumberFormat("es-VE", { maximumFractionDigits: 2 }).format(value)} %`;
}

/** Fecha y hora en la zona horaria del usuario (la misma que usa el bot). */
export function formatDateTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("es-VE", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(iso));
}

/** Un día `YYYY-MM-DD` (ya local) sin desplazarlo de zona. */
export function formatDay(day: string, style: "short" | "medium" = "short"): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("es-VE", {
    day: "numeric",
    month: "short",
    ...(style === "medium" ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

/** Hoy en la zona del usuario, como `YYYY-MM-DD`. */
export function localToday(timeZone: string, offsetDays = 0): string {
  const now = new Date(Date.now() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(now);
}
