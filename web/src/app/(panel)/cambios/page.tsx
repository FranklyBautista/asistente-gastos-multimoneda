import { Suspense } from "react";

import { ArrowRightIcon, SendIcon } from "@/components/icons";
import { Empty, LinkBanner, Loading } from "@/components/panel";
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
      <h1 className="text-[26px] font-extrabold tracking-tight">Cambios entre monedas</h1>
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
        <section
          aria-label="Diferencia promedio"
          className="hero-lime flex flex-col gap-2 rounded-[26px] p-5"
        >
          <p className="text-[13px] font-semibold opacity-80">
            Diferencia promedio contra la tasa de referencia
          </p>
          <p className="flex flex-wrap items-baseline gap-x-2.5">
            <span className="text-[40px] leading-tight font-extrabold tracking-tight">
              {formatPercent(Number(average.toFixed(2)))}
            </span>
            <span className="text-[13px] font-semibold opacity-75">
              en {compared.length} {compared.length === 1 ? "cambio" : "cambios"}
            </span>
          </p>
          <p className="text-xs font-medium opacity-80">
            Positivo: recibiste más que con la tasa de referencia del momento. Negativo: menos.
          </p>
        </section>
      ) : null}

      <h2 className="text-[17px] font-bold">Historial</h2>
      {exchanges.length === 0 ? (
        <Empty>
          Todavía no registraste cambios. En Telegram, escribe por ejemplo «cambié 50 usdt a bs a
          985».
        </Empty>
      ) : (
        <ul className="flex flex-col gap-2.5" aria-label="Cambios">
          {exchanges.map((e) => (
            <ExchangeItem key={e.id} exchange={e} timeZone={user.timezone} />
          ))}
        </ul>
      )}
      <p className="flex items-start gap-2 text-xs text-muted">
        <SendIcon className="mt-px size-4 flex-none" strokeWidth={1.8} />
        Para anotar un cambio, escríbele al bot por ejemplo «cambié 50 usdt a bs a 985».
      </p>
    </>
  );
}

function ExchangeItem({ exchange: e, timeZone }: { exchange: ExchangeRow; timeZone: string }) {
  const diff = e.differencePct;
  return (
    <li className="glass flex flex-col gap-2.5 rounded-[20px] px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-x-2 text-[15px] font-bold">
          <span>
            {formatAmount(e.fromAmount, e.fromCurrency)} {CURRENCY_LABELS[e.fromCurrency]}
          </span>{" "}
          <span className="sr-only">→</span>{" "}
          <ArrowRightIcon className="size-4 text-lime" strokeWidth={2} />{" "}
          <span>
            {formatAmount(e.toAmount, e.toCurrency)} {CURRENCY_LABELS[e.toCurrency]}
          </span>
        </span>
        {diff !== null ? (
          <span
            className={
              "rounded-full px-2.5 py-1 text-xs font-bold " +
              (diff > 0
                ? "bg-lime/15 text-lime-soft"
                : diff < 0
                  ? "bg-danger/15 text-[#ff9c95]"
                  : "bg-white/10 text-muted")
            }
          >
            {formatPercent(diff)} {diff > 0 ? "a tu favor" : diff < 0 ? "en contra" : ""}
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-0.5 text-xs text-muted sm:flex-row sm:justify-between sm:gap-4">
        <span>
          Tasa:{" "}
          <span className="font-semibold text-foreground">
            {describeRate(e.effectiveRate, e.fromCurrency, e.toCurrency)}
          </span>
          {e.referenceRate !== null
            ? ` · referencia: ${describeRate(e.referenceRate, e.fromCurrency, e.toCurrency)}`
            : " · sin tasa de referencia"}
        </span>
        <span className="text-faint">
          {formatDateTime(e.occurredAt, timeZone)} · {e.fromAccount} → {e.toAccount}
        </span>
      </div>
    </li>
  );
}
