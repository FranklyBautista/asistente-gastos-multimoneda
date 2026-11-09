import { Suspense } from "react";

import { Card, LinkBanner, Loading } from "@/components/panel";
import { type Balance, getBalances, getSession } from "@/lib/data";
import {
  CURRENCY_LABELS,
  type Currency,
  formatAmount,
  formatDateTime,
  formatRate,
  formatUsd,
  RATE_SOURCE_LABELS,
} from "@/lib/format";

export const metadata = { title: "Inicio · Asistente de gastos" };

export default function HomePage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Tus finanzas</h1>
      {/* La sesión se lee en cada petición: con Cache Components va detrás de Suspense. */}
      <Suspense fallback={<Loading />}>
        <Overview />
      </Suspense>
    </>
  );
}

async function Overview() {
  const { email, user } = await getSession();
  if (!user) {
    return (
      <>
        <LinkBanner />
        <p className="text-sm text-zinc-500">{email}</p>
      </>
    );
  }
  const balances = await getBalances();
  const priced = balances.filter((b) => b.balanceUsd !== null);
  const totalUsd = priced.reduce((sum, b) => sum + (b.balanceUsd ?? 0), 0);
  const unpriced = balances.filter((b) => b.balanceUsd === null && b.balance !== 0);
  const rates = uniqueRates(balances);
  const stale = rates.filter((r) => r.rateStale);

  return (
    <>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Cuenta vinculada con Telegram{user.displayName ? ` (${user.displayName})` : ""} · {email}
      </p>

      <Card>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Consolidado en USD</p>
        <p className="font-mono text-3xl font-semibold tabular-nums" data-testid="total-usd">
          {formatUsd(totalUsd)}
        </p>
        <p className="text-xs text-zinc-500">
          Cada saldo convertido con la tasa vigente de su fuente (los Bs con la tuya:{" "}
          {RATE_SOURCE_LABELS[user.vesRateSource] ?? user.vesRateSource}).
        </p>
        {unpriced.length > 0 ? (
          <p role="status" className="text-sm text-amber-700 dark:text-amber-400">
            Sin tasa todavía para {unpriced.map((b) => b.name).join(", ")}: no suma al total.
          </p>
        ) : null}
        {stale.length > 0 ? (
          <p role="status" className="text-sm text-amber-700 dark:text-amber-400">
            Tasa vieja (más de 6 horas sin actualizar):{" "}
            {stale.map((r) => RATE_SOURCE_LABELS[r.rateSource ?? ""] ?? r.rateSource).join(", ")}.
          </p>
        ) : null}
      </Card>

      <Card title="Saldos por cuenta">
        <ul className="-mx-4 divide-y divide-zinc-200 dark:divide-zinc-800">
          {balances.map((b) => (
            <li key={b.accountId} className="flex items-baseline justify-between gap-4 px-4 py-3">
              <span>{b.name}</span>
              <span className="flex flex-col items-end">
                <span className="font-mono tabular-nums">
                  {formatAmount(b.balance, b.currency)}{" "}
                  <span className="text-xs text-zinc-500">{CURRENCY_LABELS[b.currency]}</span>
                </span>
                {b.currency !== "USD" && b.balanceUsd !== null ? (
                  <span className="font-mono text-xs text-zinc-500 tabular-nums">
                    ≈ {formatUsd(b.balanceUsd)}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      {rates.length > 0 ? (
        <Card title="Tasas usadas">
          <ul className="flex flex-col gap-2 text-sm">
            {rates.map((r) => (
              <li key={r.currency} className="flex flex-wrap justify-between gap-x-4">
                <span>
                  {CURRENCY_LABELS[r.currency]} ·{" "}
                  {RATE_SOURCE_LABELS[r.rateSource ?? ""] ?? r.rateSource}
                </span>
                <span className="font-mono tabular-nums">
                  {describeRate(r.currency, r.usdPerUnit ?? 0)}
                  {r.rateFetchedAt ? (
                    <span
                      className={
                        "ml-2 text-xs " +
                        (r.rateStale ? "text-amber-700 dark:text-amber-400" : "text-zinc-500")
                      }
                    >
                      {formatDateTime(r.rateFetchedAt, user.timezone)}
                      {r.rateStale ? " (vieja)" : ""}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </>
  );
}

/** Una tasa por moneda (todas las cuentas de una moneda usan la misma). */
function uniqueRates(balances: Balance[]): Balance[] {
  const seen = new Map<Currency, Balance>();
  for (const b of balances) {
    if (b.currency !== "USD" && b.usdPerUnit !== null && !seen.has(b.currency)) {
      seen.set(b.currency, b);
    }
  }
  return [...seen.values()];
}

/** Monedas débiles como "unidades por 1 USD"; USDT como "USD por 1 USDT". */
function describeRate(currency: Currency, usdPerUnit: number): string {
  if (usdPerUnit >= 0.5) return `1 ${CURRENCY_LABELS[currency]} = ${formatRate(usdPerUnit, 4)} USD`;
  return `1 USD = ${formatRate(1 / usdPerUnit)} ${CURRENCY_LABELS[currency]}`;
}
