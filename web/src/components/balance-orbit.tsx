import Link from "next/link";

import { CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import type { Balance } from "@/lib/data";
import { CURRENCIES, CURRENCY_LABELS, type Currency, formatUsd } from "@/lib/format";

/** Saldo de todas las cuentas de una moneda y su parte del consolidado. */
export type CurrencyGroup = {
  currency: Currency;
  balance: number;
  /** null si ninguna cuenta de la moneda tiene tasa todavía. */
  balanceUsd: number | null;
  /** Porcentaje del consolidado (0–100), o null si no suma. */
  share: number | null;
};

export function groupByCurrency(balances: Balance[], totalUsd: number): CurrencyGroup[] {
  return CURRENCIES.flatMap((currency) => {
    const accounts = balances.filter((b) => b.currency === currency);
    if (accounts.length === 0) return [];
    const priced = accounts.filter((b) => b.balanceUsd !== null);
    const balanceUsd = priced.length ? priced.reduce((s, b) => s + (b.balanceUsd ?? 0), 0) : null;
    return [
      {
        currency,
        balance: accounts.reduce((s, b) => s + b.balance, 0),
        balanceUsd,
        share:
          totalUsd > 0 && balanceUsd !== null && balanceUsd > 0
            ? Math.min(100, (balanceUsd / totalUsd) * 100)
            : null,
      },
    ];
  });
}

/** Ángulos (grados, 0 = derecha, sentido horario) de cada burbuja alrededor del centro. */
function angles(n: number): number[] {
  // Con 4 monedas: Bs arriba a la izquierda, COP arriba a la derecha, USD y USDT abajo.
  if (n === 4) return [-135, -45, 135, 45];
  return Array.from({ length: n }, (_, i) => -90 + (i * 360) / n);
}

const ORBIT_RADIUS = 39; // % del lado del contenedor

/**
 * El consolidado en una burbuja central con cada moneda orbitando alrededor. Cada moneda es
 * un enlace a su detalle (`/moneda/VES`): su saldo y sus movimientos.
 */
export function BalanceOrbit({ groups, totalUsd }: { groups: CurrencyGroup[]; totalUsd: number }) {
  const positions = angles(groups.length);

  return (
    <nav
      aria-label="Saldo por moneda"
      className="@container relative mx-auto aspect-square w-full max-w-[420px]"
    >
      {/* Órbita punteada. */}
      <span
        aria-hidden="true"
        className="absolute rounded-full border border-dashed border-white/15"
        style={{ inset: `${50 - ORBIT_RADIUS}%` }}
      />

      {/* Centro: el consolidado. */}
      <div className="orbit-core absolute inset-[21%] flex flex-col items-center justify-center rounded-full px-[6%] text-center">
        <span className="text-[clamp(11px,3.4cqw,14px)] font-semibold text-muted">Saldo total</span>
        <span
          className="text-[clamp(22px,8.6cqw,38px)] leading-tight font-extrabold tracking-tight"
          data-testid="total-usd"
        >
          {formatUsd(totalUsd)}
        </span>
        <span className="text-[clamp(10px,3.1cqw,13px)] text-faint">consolidado en USD</span>
      </div>

      {/* Una burbuja por moneda. */}
      {groups.map((g, i) => {
        const rad = (positions[i] * Math.PI) / 180;
        return (
          <Link
            key={g.currency}
            href={`/moneda/${g.currency}`}
            className="orbit-bubble absolute flex size-[27%] -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center gap-[3%] rounded-full transition-transform duration-200 hover:scale-105 active:scale-95"
            style={
              {
                "--acc": CURRENCY_ACCENT[g.currency],
                left: `${50 + ORBIT_RADIUS * Math.cos(rad)}%`,
                top: `${50 + ORBIT_RADIUS * Math.sin(rad)}%`,
              } as React.CSSProperties
            }
          >
            <CurrencyIcon currency={g.currency} className="size-[38%]" />
            <span className="text-[clamp(11px,3.4cqw,14px)] leading-none font-bold">
              {g.currency === "VES" ? "VES / Bs" : CURRENCY_LABELS[g.currency]}
              <span className="sr-only">: ver saldo y movimientos</span>
            </span>
            {g.share !== null ? (
              <span className="text-[clamp(9px,2.7cqw,11px)] leading-none font-semibold text-muted">
                {Math.round(g.share)}%
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
