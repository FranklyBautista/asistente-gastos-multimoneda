import Link from "next/link";

import { CurrencyIcon } from "@/components/currency";
import { ArrowInIcon, ArrowOutIcon } from "@/components/icons";
import { CategoryBadge } from "@/components/panel";
import type { TransactionRow } from "@/lib/data";
import {
  CURRENCY_LABELS,
  formatAmount,
  formatDateTime,
  formatMovementDate,
  formatUsd,
} from "@/lib/format";

/** Una fila de movimiento: toda la tarjeta lleva a corregirlo. */
export function TransactionItem({
  t,
  timeZone,
  showAccount = true,
}: {
  t: TransactionRow;
  timeZone: string;
  showAccount?: boolean;
}) {
  const title = t.description || t.categoryName || "Sin descripción";
  const income = t.kind === "income";
  return (
    <li>
      <Link
        href={`/movimientos/editar?id=${t.id}`}
        className="glass flex items-center gap-3 rounded-[18px] px-3.5 py-3 transition-colors hover:border-lime/35"
      >
        <CategoryBadge name={t.categoryName} income={income} />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex min-w-0 items-center gap-1.5 text-sm font-semibold">
            <span className="sr-only">Editar </span>
            <span className="truncate">{title}</span>
            {t.edited ? (
              <span className="flex-none rounded-full bg-lime/[0.12] px-2 py-px text-xs font-bold text-lime-soft">
                corregido
              </span>
            ) : null}
          </span>
          <span className="truncate text-xs text-muted">
            {t.categoryName ?? "sin categoría"}
            {showAccount ? ` · ${t.accountName}` : ""}
          </span>
          <span className="truncate text-xs text-faint">
            {formatDateTime(t.occurredAt, timeZone)}
          </span>
        </span>
        <span className="flex flex-none flex-col items-end gap-0.5">
          <span
            className={
              "flex items-center gap-1.5 text-sm font-bold " +
              (income ? "text-lime" : "text-danger")
            }
          >
            <CurrencyIcon currency={t.currency} className="size-4" />
            <span>
              {income ? "+" : "−"}
              {formatAmount(t.amount, t.currency)} {CURRENCY_LABELS[t.currency]}
            </span>
          </span>
          {t.currency !== "USD" ? (
            <span className="text-xs text-faint">≈ {formatUsd(t.amountUsd)}</span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}

/**
 * Fila compacta para el detalle de una moneda: flecha de entrada o salida, qué fue, cuándo y
 * el monto con signo. Toda la fila lleva a corregirlo.
 */
export function MovementRow({ t, timeZone }: { t: TransactionRow; timeZone: string }) {
  const income = t.kind === "income";
  const title = t.description || t.categoryName || (income ? "Ingreso" : "Gasto");
  return (
    <li>
      <Link
        href={`/movimientos/editar?id=${t.id}`}
        className="flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-white/[0.03]"
      >
        <span
          className={
            "grid size-11 flex-none place-items-center rounded-2xl bg-chip " +
            (income ? "text-lime" : "text-danger")
          }
        >
          {income ? (
            <ArrowInIcon className="size-5" strokeWidth={2.2} />
          ) : (
            <ArrowOutIcon className="size-5" strokeWidth={2.2} />
          )}
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex min-w-0 items-center gap-1.5 text-[15px] font-semibold">
            <span className="sr-only">Editar </span>
            <span className="truncate">{title}</span>
            {t.edited ? (
              <span className="flex-none rounded-full bg-lime/[0.12] px-2 py-px text-xs font-bold text-lime-soft">
                corregido
              </span>
            ) : null}
          </span>
          <span className="truncate text-xs text-muted">
            {formatMovementDate(t.occurredAt, timeZone)} · {t.accountName}
          </span>
        </span>
        <span className="flex flex-none flex-col items-end gap-0.5">
          <span className={"text-[15px] font-bold " + (income ? "text-lime" : "text-foreground")}>
            {income ? "+" : "−"}
            {formatAmount(t.amount, t.currency)} {CURRENCY_LABELS[t.currency]}
          </span>
          {t.currency !== "USD" ? (
            <span className="text-xs text-faint">≈ {formatUsd(t.amountUsd)}</span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}
