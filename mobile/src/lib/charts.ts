/**
 * Cuentas de presentación de las gráficas, las mismas que /graficas en la web. Los totales en
 * USD y las tasas vienen de la base (spending_by_category, spending_by_week, bolivar_rates).
 */

export const CHART_PERIODS = [7, 30, 90] as const;
export const WEEKS = 12;
export const BOLIVAR_DAYS = 90;

export type BolivarPoint = { day: string; bsPerUsd: number };

/** De USD por bolívar (como se guarda) a bolívares por dólar (como se lee en la calle). */
export function bolivarSeries(rates: { day: string; usdPerUnit: number }[]): BolivarPoint[] {
  return rates.map((r) => ({ day: r.day, bsPerUsd: 1 / r.usdPerUnit }));
}

/**
 * Variación en % de lo que compra un bolívar entre el primer y el último día, con 2 decimales.
 * Negativa = cada bolívar compra menos dólares (como el bot y la web).
 */
export function bolivarChange(firstUsdPerUnit: number, lastUsdPerUnit: number): number {
  return Number(((lastUsdPerUnit / firstUsdPerUnit - 1) * 100).toFixed(2));
}

export function bolivarVerdict(change: number): string {
  if (change < 0) return "Tus bolívares compran menos dólares que al inicio del periodo.";
  if (change > 0) return "Tus bolívares compran más dólares que al inicio del periodo.";
  return "El bolívar no cambió frente al dólar en este periodo.";
}

/** "3 nov." para un día `YYYY-MM-DD`, sin que la zona horaria mueva la fecha. */
export function shortDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("es-VE", { day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)))
    .replace(/\.$/, "");
}

/**
 * Cifras cortas para los ejes ("$80", "$1,3 mil"). Se arma a mano porque Hermes (Android) no
 * soporta currencyDisplay "narrowSymbol" y mostraría "USD 200,0".
 */
export function compactUsd(value: number): string {
  const number = (n: number, digits: number) =>
    new Intl.NumberFormat("es-VE", { maximumFractionDigits: digits }).format(n);
  return Math.abs(value) >= 1000 ? `$${number(value / 1000, 1)} mil` : `$${number(value, 0)}`;
}
