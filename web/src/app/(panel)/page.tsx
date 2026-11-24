import Link from "next/link";
import { Suspense } from "react";

import { BalanceOrbit, groupByCurrency } from "@/components/balance-orbit";
import { AccountCard, CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import { AlertIcon, ArrowInIcon, ArrowOutIcon, ArrowRightIcon, SendIcon } from "@/components/icons";
import { BudgetsCard, RunwayCard } from "@/components/habits";
import { Card, Empty, LinkBanner, Loading } from "@/components/panel";
import { TransactionItem } from "@/components/transactions";
import {
  type Balance,
  getBalances,
  getBudgets,
  getPeriodTotals,
  getSession,
  getSpendingPace,
  listTransactions,
} from "@/lib/data";
import {
  CURRENCY_LABELS,
  type Currency,
  formatDateTime,
  formatMonth,
  formatRate,
  formatUsd,
  localToday,
  RATE_SOURCE_LABELS,
} from "@/lib/format";
import { daysLeftInMonth, runway } from "@/lib/habits";

export const metadata = { title: "Inicio · Asistente de gastos" };

const RECENT = 4;

export default function HomePage() {
  return (
    // La sesión se lee en cada petición: con Cache Components va detrás de Suspense.
    <Suspense
      fallback={
        <>
          <h1 className="text-[26px] font-extrabold tracking-tight">Tus finanzas</h1>
          <Loading />
        </>
      }
    >
      <Overview />
    </Suspense>
  );
}

/** Saludo según la hora local del usuario. */
function greeting(timeZone: string): string {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone }).format(
      new Date(),
    ),
  );
  if (hour < 12) return "Buenos días";
  if (hour < 19) return "Buenas tardes";
  return "Buenas noches";
}

async function Overview() {
  const { email, user } = await getSession();
  if (!user) {
    return (
      <>
        <h1 className="text-[26px] font-extrabold tracking-tight">Tus finanzas</h1>
        <LinkBanner />
        <p className="text-sm text-muted">{email}</p>
      </>
    );
  }
  const today = localToday(user.timezone);
  const [balances, month, recent, budgets, pace] = await Promise.all([
    getBalances(),
    getPeriodTotals(`${today.slice(0, 8)}01`, today),
    listTransactions({}, 1),
    getBudgets(),
    getSpendingPace(),
  ]);
  const priced = balances.filter((b) => b.balanceUsd !== null);
  const totalUsd = priced.reduce((sum, b) => sum + (b.balanceUsd ?? 0), 0);
  const unpriced = balances.filter((b) => b.balanceUsd === null && b.balance !== 0);
  const rates = uniqueRates(balances);
  const stale = rates.filter((r) => r.rateStale);
  const vesSource = RATE_SOURCE_LABELS[user.vesRateSource] ?? user.vesRateSource;
  const groups = groupByCurrency(balances, totalUsd);

  return (
    <>
      <header className="flex flex-col gap-1">
        <span className="text-[13px] text-muted">
          {greeting(user.timezone)}
          {user.displayName ? `, ${user.displayName}` : ""}
        </span>
        <h1 className="text-[26px] font-extrabold tracking-tight">Tus finanzas</h1>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-lime/25 bg-lime/10 px-2.5 py-1 font-semibold text-lime-soft">
            <SendIcon className="size-3.5" strokeWidth={2} />
            Cuenta vinculada con Telegram{user.displayName ? ` (${user.displayName})` : ""}
          </span>
          <span className="truncate">{email}</span>
        </p>
      </header>

      <section aria-label="Saldo consolidado" className="flex flex-col gap-4">
        <BalanceOrbit groups={groups} totalUsd={totalUsd} />
        <p className="text-center text-xs text-muted">
          Toca una moneda para ver su saldo y sus movimientos. {balances.length}{" "}
          {balances.length === 1 ? "cuenta" : "cuentas"}, cada una con la tasa vigente de su fuente
          (los Bs con la tuya: {vesSource}).
        </p>
        {unpriced.length > 0 ? (
          <p role="status" className="flex items-start gap-1.5 text-[13px] font-semibold text-warn">
            <AlertIcon className="mt-px size-4 flex-none" />
            Sin tasa todavía para {unpriced.map((b) => b.name).join(", ")}: no suma al total.
          </p>
        ) : null}
        {stale.length > 0 ? (
          <p role="status" className="flex items-start gap-1.5 text-[13px] font-semibold text-warn">
            <AlertIcon className="mt-px size-4 flex-none" />
            Tasa vieja (más de 6 horas sin actualizar):{" "}
            {stale.map((r) => RATE_SOURCE_LABELS[r.rateSource ?? ""] ?? r.rateSource).join(", ")}.
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-2.5">
          <MonthStat
            label={`Ingresos de ${formatMonth(today)}`}
            value={formatUsd(month.incomeUsd)}
            income
          />
          <MonthStat
            label={`Gastos de ${formatMonth(today)}`}
            value={formatUsd(month.expensesUsd)}
          />
        </div>
      </section>

      <div className="grid gap-5 sm:grid-cols-2">
        <RunwayCard result={runway(totalUsd, pace.expensesUsd, pace.windowDays)} />
        <BudgetsCard rows={budgets} daysLeft={daysLeftInMonth(today)} />
      </div>

      <section aria-labelledby="cuentas" className="flex flex-col gap-3">
        <h2 id="cuentas" className="text-[17px] font-bold">
          Tus cuentas
        </h2>
        <ul
          aria-label="Saldos por cuenta"
          className="scrollbar-none -mx-5 flex gap-2.5 overflow-x-auto px-5 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible md:grid-cols-4 sm:px-0"
        >
          {balances.map((b) => (
            <AccountCard key={b.accountId} b={b} totalUsd={totalUsd} />
          ))}
        </ul>
      </section>

      <section aria-labelledby="recientes" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 id="recientes" className="text-[17px] font-bold">
            Movimientos recientes
          </h2>
          <Link
            href="/movimientos"
            className="flex min-h-11 items-center gap-1.5 text-[13px] font-semibold text-lime hover:text-lime-soft"
          >
            Ver todos
            <ArrowRightIcon className="size-4" />
          </Link>
        </div>
        {recent.rows.length === 0 ? (
          <Empty>Todavía no hay movimientos. Anótalos escribiéndole al bot en Telegram.</Empty>
        ) : (
          <ul aria-label="Movimientos recientes" className="flex flex-col gap-2">
            {recent.rows.slice(0, RECENT).map((t) => (
              <TransactionItem key={t.id} t={t} timeZone={user.timezone} showAccount={false} />
            ))}
          </ul>
        )}
      </section>

      {rates.length > 0 ? (
        <Card title="Tasas usadas">
          <ul className="flex flex-col gap-2.5 text-sm">
            {rates.map((r) => (
              <li
                key={r.currency}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-0.5"
              >
                <span className="flex items-center gap-2 text-muted">
                  <CurrencyIcon currency={r.currency} className="size-6" />
                  <span>
                    <span className="font-semibold" style={{ color: CURRENCY_ACCENT[r.currency] }}>
                      {CURRENCY_LABELS[r.currency]}
                    </span>{" "}
                    · {RATE_SOURCE_LABELS[r.rateSource ?? ""] ?? r.rateSource}
                  </span>
                </span>
                <span className="font-semibold">
                  {describeRate(r.currency, r.usdPerUnit ?? 0)}
                  {r.rateFetchedAt ? (
                    <span
                      className={
                        "ml-2 text-xs font-normal " + (r.rateStale ? "text-warn" : "text-faint")
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

function MonthStat({
  label,
  value,
  income = false,
}: {
  label: string;
  value: string;
  income?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-[#0b1a0e] px-3 py-2.5 text-foreground">
      <span
        className={
          "grid size-8 flex-none place-items-center rounded-full " +
          (income ? "bg-lime/15 text-lime" : "bg-danger/15 text-danger")
        }
      >
        {income ? (
          <ArrowInIcon className="size-4" strokeWidth={2.2} />
        ) : (
          <ArrowOutIcon className="size-4" strokeWidth={2.2} />
        )}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-xs text-muted">{label}</span>
        <span className="truncate text-sm font-bold">{value}</span>
      </span>
    </div>
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
