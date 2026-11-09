import Link from "next/link";
import { Suspense } from "react";

import { BolivarChart, CategoryChart, WeeklyChart } from "@/components/charts";
import { Card, Empty, LinkBanner, Loading } from "@/components/panel";
import {
  getBalances,
  getBolivarRates,
  getSession,
  getSpendingByCategory,
  getSpendingByWeek,
} from "@/lib/data";
import {
  formatAmount,
  formatDay,
  formatPercent,
  formatRate,
  formatUsd,
  localToday,
  RATE_SOURCE_LABELS,
} from "@/lib/format";

export const metadata = { title: "Gráficas · Asistente de gastos" };

const PERIODS = [7, 30, 90] as const;
const WEEKS = 12;
const BOLIVAR_DAYS = 90;

export default function ChartsPage({ searchParams }: PageProps<"/graficas">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Gráficas</h1>
      <Suspense fallback={<Loading />}>
        <Charts searchParams={searchParams} />
      </Suspense>
    </>
  );
}

/** Tabla con los mismos datos de la gráfica: la alternativa textual (y para lectores). */
function DataTable({ headers, rows }: { headers: [string, string]; rows: [string, string][] }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-zinc-600 dark:text-zinc-400">Ver datos</summary>
      <table className="mt-2 w-full text-left">
        <thead className="text-xs text-zinc-500">
          <tr>
            <th className="py-1 font-normal">{headers[0]}</th>
            <th className="py-1 text-right font-normal">{headers[1]}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {rows.map(([a, b]) => (
            <tr key={a}>
              <td className="py-1">{a}</td>
              <td className="py-1 text-right font-mono tabular-nums">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

async function Charts({ searchParams }: Pick<PageProps<"/graficas">, "searchParams">) {
  const { user } = await getSession();
  if (!user) return <LinkBanner />;
  const raw = (await searchParams).dias;
  const days = PERIODS.find((p) => String(p) === (Array.isArray(raw) ? raw[0] : raw)) ?? 30;
  const to = localToday(user.timezone);
  const from = localToday(user.timezone, -(days - 1));

  const [categories, weeks, bolivar, balances] = await Promise.all([
    getSpendingByCategory(from, to),
    getSpendingByWeek(WEEKS),
    getBolivarRates(BOLIVAR_DAYS),
    getBalances(),
  ]);
  const categoryTotal = categories.reduce((sum, c) => sum + c.totalUsd, 0);
  const bolivarSeries = bolivar.map((r) => ({ day: r.day, bsPerUsd: 1 / r.usdPerUnit }));
  const first = bolivar.at(0);
  const last = bolivar.at(-1);
  const vesBalance = balances
    .filter((b) => b.currency === "VES")
    .reduce((sum, b) => sum + b.balance, 0);

  return (
    <>
      <Card title="Gasto por categoría">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Últimos {days} días, en USD al momento de cada gasto · total{" "}
            <span className="font-mono tabular-nums">{formatUsd(categoryTotal)}</span>
          </p>
          <nav aria-label="Periodo" className="flex gap-1 text-sm">
            {PERIODS.map((p) => (
              <Link
                key={p}
                href={`/graficas?dias=${p}`}
                aria-current={p === days ? "true" : undefined}
                className={
                  "rounded-md px-2 py-1 " +
                  (p === days
                    ? "bg-zinc-200 font-medium dark:bg-zinc-800"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900")
                }
              >
                {p} días
              </Link>
            ))}
          </nav>
        </div>
        {categories.length === 0 ? (
          <Empty>No hay gastos en este periodo.</Empty>
        ) : (
          <>
            <CategoryChart data={categories} />
            <DataTable
              headers={["Categoría", "Gasto (USD)"]}
              rows={categories.map((c) => [c.category, formatUsd(c.totalUsd)])}
            />
          </>
        )}
      </Card>

      <Card title="Gasto por semana">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Últimas {WEEKS} semanas (de lunes a domingo), en USD.
        </p>
        <WeeklyChart data={weeks} />
        <DataTable
          headers={["Semana del", "Gasto (USD)"]}
          rows={weeks.map((w) => [formatDay(w.weekStart, "medium"), formatUsd(w.expensesUsd)])}
        />
      </Card>

      <Card title="Poder adquisitivo del bolívar">
        {first && last ? (
          <>
            <BolivarSummary
              source={RATE_SOURCE_LABELS[last.source] ?? last.source}
              firstDay={first.day}
              firstRate={first.usdPerUnit}
              lastRate={last.usdPerUnit}
              vesBalance={vesBalance}
            />
            <BolivarChart data={bolivarSeries} />
            <DataTable
              headers={["Día", "Bs por 1 USD"]}
              rows={bolivarSeries.map((r) => [formatDay(r.day, "medium"), formatRate(r.bsPerUsd)])}
            />
          </>
        ) : (
          <Empty>Todavía no hay tasas del bolívar guardadas con tu fuente.</Empty>
        )}
      </Card>
    </>
  );
}

function BolivarSummary({
  source,
  firstDay,
  firstRate,
  lastRate,
  vesBalance,
}: {
  source: string;
  firstDay: string;
  firstRate: number;
  lastRate: number;
  vesBalance: number;
}) {
  // Variación de usd_per_unit: negativa = cada bolívar compra menos dólares (como el bot).
  const change = (lastRate / firstRate - 1) * 100;
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Bs por cada USD con la tasa {source}, desde el {formatDay(firstDay, "medium")}. Si la línea
        sube, cada bolívar compra menos dólares.
      </p>
      <p className="font-mono text-2xl font-semibold tabular-nums" data-testid="bolivar-change">
        {formatPercent(Number(change.toFixed(2)))}
      </p>
      <p className="text-sm">
        {change < 0
          ? "Tus bolívares compran menos dólares que al inicio del periodo."
          : change > 0
            ? "Tus bolívares compran más dólares que al inicio del periodo."
            : "El bolívar no cambió frente al dólar en este periodo."}
        {vesBalance > 0 ? (
          <>
            {" "}
            Tu saldo de {formatAmount(vesBalance, "VES")} Bs valía{" "}
            {formatUsd(vesBalance * firstRate)} y hoy vale {formatUsd(vesBalance * lastRate)}.
          </>
        ) : null}
      </p>
    </div>
  );
}
