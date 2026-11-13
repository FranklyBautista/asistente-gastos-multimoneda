import Link from "next/link";

import { CategoryBadge } from "@/components/panel";
import type { TransactionRow } from "@/lib/data";
import { CURRENCY_LABELS, formatAmount, formatDateTime, formatUsd } from "@/lib/format";

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
              <span className="flex-none rounded-full bg-lime/[0.12] px-2 py-px text-[10px] font-bold text-lime-soft">
                corregido
              </span>
            ) : null}
          </span>
          <span className="truncate text-[11px] text-muted">
            {t.categoryName ?? "sin categoría"}
            {showAccount ? ` · ${t.accountName}` : ""}
          </span>
          <span className="truncate text-[11px] text-faint">
            {formatDateTime(t.occurredAt, timeZone)}
          </span>
        </span>
        <span className="flex flex-none flex-col items-end gap-0.5">
          <span className={"text-sm font-bold " + (income ? "text-lime" : "text-danger")}>
            {income ? "+" : "−"}
            {formatAmount(t.amount, t.currency)} {CURRENCY_LABELS[t.currency]}
          </span>
          {t.currency !== "USD" ? (
            <span className="text-[11px] text-faint">≈ {formatUsd(t.amountUsd)}</span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}
