import type { Balance } from "@/lib/data";
import { CURRENCY_LABELS, type Currency, formatAmount, formatUsd } from "@/lib/format";

/**
 * Color de acento por moneda (pasa 4.5:1 como texto sobre las superficies oscuras).
 * Sirve para el borde, el brillo y la barra de cada tarjeta.
 */
export const CURRENCY_ACCENT: Record<Currency, string> = {
  VES: "#ffcf4d",
  COP: "#7cc4ff",
  USD: "#8dfb86",
  USDT: "#4fd8b0",
};

/**
 * Ícono redondo de la moneda: la bandera del país, o el símbolo de Tether para USDT.
 * Decorativo: siempre va junto al código de la moneda escrito.
 */
export function CurrencyIcon({
  currency,
  className = "size-9",
}: {
  currency: Currency;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={
        "inline-grid flex-none place-items-center overflow-hidden rounded-full ring-1 ring-white/15 " +
        className
      }
    >
      <svg viewBox="0 0 24 24" className="size-full" aria-hidden="true">
        {GLYPHS[currency]}
      </svg>
    </span>
  );
}

const GLYPHS: Record<Currency, React.ReactNode> = {
  // Venezuela: franjas amarilla, azul y roja con el arco de estrellas.
  VES: (
    <>
      <rect width="24" height="8" fill="#ffcc00" />
      <rect y="8" width="24" height="8" fill="#00247d" />
      <rect y="16" width="24" height="8" fill="#cf142b" />
      {[
        [7, 13.6],
        [8.6, 11.4],
        [10.7, 10.1],
        [13.3, 10.1],
        [15.4, 11.4],
        [17, 13.6],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="0.75" fill="#fff" />
      ))}
    </>
  ),
  // Colombia: amarillo (mitad), azul y rojo.
  COP: (
    <>
      <rect width="24" height="12" fill="#fcd116" />
      <rect y="12" width="24" height="6" fill="#003893" />
      <rect y="18" width="24" height="6" fill="#ce1126" />
    </>
  ),
  // Estados Unidos: franjas rojas y blancas con el cantón azul.
  USD: (
    <>
      <rect width="24" height="24" fill="#fff" />
      {[0, 2, 4, 6, 8, 10, 12].map((i) => (
        <rect key={i} y={i * (24 / 13)} width="24" height={24 / 13} fill="#b22234" />
      ))}
      <rect width="11" height={(24 / 13) * 7} fill="#3c3b6e" />
      {[
        [2.5, 2.5],
        [5.5, 2.5],
        [8.5, 2.5],
        [4, 5.5],
        [7, 5.5],
        [2.5, 8.5],
        [5.5, 8.5],
        [8.5, 8.5],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="0.7" fill="#fff" />
      ))}
    </>
  ),
  // Tether: círculo verde azulado con la ₮.
  USDT: (
    <>
      <rect width="24" height="24" fill="#26a17b" />
      <g fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round">
        <path d="M7 7.5h10M12 7.5v10" />
        <ellipse cx="12" cy="11.6" rx="5.2" ry="1.7" strokeWidth="1.4" />
      </g>
    </>
  ),
};

/** Tarjeta de una cuenta: ícono y color de su moneda, saldo y su peso en el consolidado. */
export function AccountCard({ b, totalUsd }: { b: Balance; totalUsd: number }) {
  const accent = CURRENCY_ACCENT[b.currency];
  const share =
    totalUsd > 0 && b.balanceUsd !== null && b.balanceUsd > 0
      ? Math.min(100, (b.balanceUsd / totalUsd) * 100)
      : null;
  return (
    <li
      className="glass relative flex min-w-44 flex-none flex-col gap-3 overflow-hidden rounded-[18px] p-3.5"
      style={{ borderColor: `${accent}40` }}
    >
      {/* Brillo de la moneda en la esquina. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -top-10 -right-10 size-28 rounded-full opacity-20 blur-2xl"
        style={{ background: accent }}
      />
      <div className="relative flex items-center gap-2.5">
        <CurrencyIcon currency={b.currency} />
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[13px] font-semibold">{b.name}</span>
          <span className="text-[11px] font-bold tracking-wide" style={{ color: accent }}>
            {CURRENCY_LABELS[b.currency]}
          </span>
        </span>
      </div>
      <div className="relative flex flex-col gap-0.5">
        <span className={"text-lg font-extrabold " + (b.balance < 0 ? "text-danger" : "")}>
          {formatAmount(b.balance, b.currency)}
        </span>
        <span className="text-xs text-faint">
          {b.currency === "USD"
            ? "Moneda base"
            : b.balanceUsd !== null
              ? `≈ ${formatUsd(b.balanceUsd)}`
              : "Sin tasa"}
        </span>
      </div>
      {share !== null ? (
        <div className="relative flex items-center gap-2">
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.max(share, 2)}%`, background: accent }}
            />
          </span>
          <span className="text-[11px] font-semibold text-muted">
            {Math.round(share)}% del total
          </span>
        </div>
      ) : null}
    </li>
  );
}
