import { Suspense } from "react";

import { Card, Empty, LinkBanner, Loading } from "@/components/panel";
import { type ExchangeRow, getExchanges, getSession } from "@/lib/data";
import {
  CURRENCY_LABELS,
  type Currency,
  formatAmount,
  formatDateTime,
  formatPercent,
  formatRate,
} from "@/lib/format";

export const metadata = { title: "Cambios · Asistente de gastos" };

export default function ExchangesPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Cambios entre monedas</h1>
      <Suspense fallback={<Loading />}>
        <Exchanges />
      </Suspense>
    </>
  );
}

/**
 * La tasa como se suele decir: unidades de la moneda débil por 1 de la fuerte.
 * `rate` está en "destino por 1 de origen" (effective_rate y reference_rate).
 */
function describeRate(rate: number, from: Currency, to: Currency): string {
  if (rate >= 1) return `${formatRate(rate)} ${CURRENCY_LABELS[to]} por ${CURRENCY_LABELS[from]}`;
  return `${formatRate(1 / rate)} ${CURRENCY_LABELS[from]} por ${CURRENCY_LABELS[to]}`;
}

async function Exchanges() {
  const { user } = await getSession();
  if (!user) return <LinkBanner />;
  const exchanges = await getExchanges();
  const compared = exchanges.filter((e) => e.differencePct !== null);
  const average = compared.length
    ? compared.reduce((sum, e) => sum + (e.differencePct ?? 0), 0) / compared.length
    : null;

  return (
    <>
      {average !== null ? (
        <Card>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Diferencia promedio contra la tasa de referencia ({compared.length}{" "}
            {compared.length === 1 ? "cambio" : "cambios"})
          </p>
          <p className="font-mono text-2xl font-semibold tabular-nums">
            {formatPercent(Number(average.toFixed(2)))}
          </p>
          <p className="text-xs text-zinc-500">
            Positivo: recibiste más que con la tasa de referencia del momento. Negativo: menos.
          </p>
        </Card>
      ) : null}
      <Card>
        {exchanges.length === 0 ? (
          <Empty>
            Todavía no registraste cambios. En Telegram, escribe por ejemplo «cambié 50 usdt a bs a
            985».
          </Empty>
        ) : (
          <ul className="-mx-4 divide-y divide-zinc-200 dark:divide-zinc-800" aria-label="Cambios">
            {exchanges.map((e) => (
              <ExchangeItem key={e.id} exchange={e} timeZone={user.timezone} />
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

function ExchangeItem({ exchange: e, timeZone }: { exchange: ExchangeRow; timeZone: string }) {
  const diff = e.differencePct;
  return (
    <li className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex flex-col">
        <span className="font-mono tabular-nums">
          {formatAmount(e.fromAmount, e.fromCurrency)} {CURRENCY_LABELS[e.fromCurrency]} →{" "}
          {formatAmount(e.toAmount, e.toCurrency)} {CURRENCY_LABELS[e.toCurrency]}
        </span>
        <span className="text-xs text-zinc-500">
          {formatDateTime(e.occurredAt, timeZone)} · {e.fromAccount} → {e.toAccount}
        </span>
      </div>
      <div className="flex flex-col text-sm sm:items-end">
        <span>
          Tasa:{" "}
          <span className="font-mono">
            {describeRate(e.effectiveRate, e.fromCurrency, e.toCurrency)}
          </span>
        </span>
        {e.referenceRate !== null ? (
          <span className="text-xs text-zinc-500">
            Referencia: {describeRate(e.referenceRate, e.fromCurrency, e.toCurrency)}
          </span>
        ) : (
          <span className="text-xs text-zinc-500">Sin tasa de referencia</span>
        )}
        {diff !== null ? (
          <span
            className={
              "font-mono text-sm tabular-nums " +
              (diff > 0
                ? "text-emerald-700 dark:text-emerald-400"
                : diff < 0
                  ? "text-red-700 dark:text-red-400"
                  : "")
            }
          >
            {formatPercent(diff)} {diff > 0 ? "a tu favor" : diff < 0 ? "en contra" : ""}
          </span>
        ) : null}
      </div>
    </li>
  );
}
