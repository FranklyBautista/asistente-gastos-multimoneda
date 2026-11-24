import Link from "next/link";

import { CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import { ArrowRightIcon, ChevronLeftIcon } from "@/components/icons";
import { Empty } from "@/components/panel";
import { MovementRow } from "@/components/transactions";
import type { Balance, TransactionRow } from "@/lib/data";
import { CURRENCY_LABELS, type Currency, formatAmount, formatUsd } from "@/lib/format";

const CURRENCY_NAMES: Record<Currency, string> = {
  VES: "Bolívar venezolano",
  COP: "Peso colombiano",
  USD: "Dólar estadounidense",
  USDT: "Tether",
};

/**
 * Detalle de una moneda: encabezado con su color, el saldo de todas sus cuentas y su
 * equivalente, y la lista de sus movimientos.
 */
export function CurrencyDetail({
  currency,
  balances,
  movements,
  timeZone,
}: {
  currency: Currency;
  balances: Balance[];
  movements: { rows: TransactionRow[]; total: number };
  timeZone: string;
}) {
  const accounts = balances.filter((b) => b.currency === currency);
  const totalUsd = balances.reduce((s, b) => s + (b.balanceUsd ?? 0), 0);
  const balance = accounts.reduce((s, b) => s + b.balance, 0);
  const priced = accounts.filter((b) => b.balanceUsd !== null);
  const balanceUsd = priced.length ? priced.reduce((s, b) => s + (b.balanceUsd ?? 0), 0) : null;
  const share =
    totalUsd > 0 && balanceUsd !== null && balanceUsd > 0 ? (balanceUsd / totalUsd) * 100 : null;
  const label = CURRENCY_LABELS[currency];
  const accent = CURRENCY_ACCENT[currency];

  return (
    <>
      <section
        aria-labelledby="moneda"
        className="relative flex flex-col items-center gap-1 overflow-hidden rounded-3xl border px-5 pt-5 pb-6 text-center"
        style={{
          borderColor: `${accent}40`,
          background: `radial-gradient(120% 90% at 50% 0%, ${accent}38 0%, #0c1a0f 62%, #081209 100%)`,
        }}
      >
        <Link
          href="/"
          className="glass absolute top-4 left-4 grid size-11 place-items-center rounded-full text-foreground hover:text-lime"
        >
          <ChevronLeftIcon className="size-5" strokeWidth={2.2} />
          <span className="sr-only">Volver al inicio</span>
        </Link>

        <CurrencyIcon currency={currency} className="mt-2 size-16 shadow-lg" />
        <h1 id="moneda" className="mt-1 text-base font-bold">
          {currency === "VES" ? "VES / Bs" : label}
          <span className="block text-xs font-medium text-muted">{CURRENCY_NAMES[currency]}</span>
        </h1>

        <p
          className="mt-3 text-[clamp(30px,9vw,42px)] leading-tight font-extrabold tracking-tight break-all"
          data-testid="currency-balance"
        >
          {formatAmount(balance, currency)}{" "}
          <span className="text-[0.6em]" style={{ color: accent }}>
            {label}
          </span>
        </p>
        <p className="text-sm text-muted">
          {currency === "USD"
            ? "Moneda base"
            : balanceUsd !== null
              ? `≈ ${formatUsd(balanceUsd)} USD`
              : "Sin tasa todavía: no suma al total"}
          {share !== null ? ` · ${Math.round(share)}% de tu saldo total` : ""}
        </p>

        {accounts.length > 0 ? (
          <ul
            aria-label={`Cuentas en ${label}`}
            className="mt-4 flex flex-wrap justify-center gap-2"
          >
            {accounts.map((a) => (
              <li
                key={a.accountId}
                className="rounded-full border border-white/10 bg-white/[0.06] px-3.5 py-2 text-[13px]"
              >
                <span className="text-muted">{a.name}</span>{" "}
                <span className="font-bold">{formatAmount(a.balance, currency)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section aria-labelledby="movimientos" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 id="movimientos" className="text-[20px] font-bold">
            Movimientos
          </h2>
          {movements.total > movements.rows.length ? (
            <Link
              href={`/movimientos?moneda=${currency}`}
              className="flex min-h-11 items-center gap-1.5 text-[13px] font-semibold text-lime hover:text-lime-soft"
            >
              Ver los {movements.total}
              <ArrowRightIcon className="size-4" />
            </Link>
          ) : null}
        </div>
        {movements.rows.length === 0 ? (
          <Empty>
            Todavía no hay movimientos en {label}. Anótalos escribiéndole al bot en Telegram.
          </Empty>
        ) : (
          <ul
            aria-label={`Movimientos en ${label}`}
            className="glass flex flex-col divide-y divide-white/[0.07] overflow-hidden rounded-3xl"
          >
            {movements.rows.map((t) => (
              <MovementRow key={t.id} t={t} timeZone={timeZone} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
