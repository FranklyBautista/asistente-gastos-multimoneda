import { Card } from "@/components/panel";
import type { BudgetRow } from "@/lib/data";
import { formatAmount, formatUsd } from "@/lib/format";
import { budgetState, type BudgetState, daysText, type Runway, usedPct } from "@/lib/habits";

/** El colchón en días, con los mismos textos que /colchon en el bot y la app móvil. */
export function RunwayCard({ result }: { result: Runway }) {
  if (!result.known) {
    const text = {
      no_history: "Cuando lleves dos semanas anotando, verás para cuántos días te alcanza.",
      short_history: `Llevas ${daysText(result.historyDays)} anotando. Con dos semanas de gastos verás para cuántos días te alcanza.`,
      no_expenses: `No anotaste gastos en ${daysText(result.historyDays)}, así que todavía no se puede calcular.`,
    }[result.reason];
    return (
      <Card title="Colchón">
        <p className="text-sm text-muted">{text}</p>
      </Card>
    );
  }

  const window =
    result.windowDays >= 90
      ? "tu promedio de los últimos 90 días"
      : `tu promedio desde que empezaste a anotar hace ${daysText(result.windowDays)}`;
  return (
    <Card title="Colchón">
      <p
        className="text-[28px] leading-none font-extrabold tracking-tight"
        aria-label={`Cubres unos ${daysText(result.days)} de tus gastos`}
      >
        {result.days === 0 ? "Menos de 1 día" : `≈ ${daysText(result.days)}`}
      </p>
      <p className="text-sm text-muted">
        Gastas {formatUsd(result.dailySpendUsd)} al día, {window}.
        {result.nextStep !== null ? ` Siguiente escalón: ${daysText(result.nextStep)}.` : ""}
      </p>
      <p className="text-xs text-faint">Lo que te deben no cuenta hasta que te lo paguen.</p>
    </Card>
  );
}

const BAR_COLORS: Record<BudgetState, string> = {
  ok: "bg-lime",
  near: "bg-warn",
  over: "bg-danger",
};

/** Topes del mes en USD: barra de avance y lo que queda, sin regaños (como el bot). */
export function BudgetsCard({ rows, daysLeft }: { rows: BudgetRow[]; daysLeft: number }) {
  return (
    <Card
      title="Topes del mes"
      action={<span className="text-xs text-faint">Quedan {daysText(daysLeft)}</span>}
    >
      {rows.length === 0 ? (
        <p className="text-sm text-muted">
          Todavía no tienes topes. Pídeselo al bot, por ejemplo: «no quiero gastar más de 100
          dólares al mes en comida».
        </p>
      ) : (
        <ul aria-label="Topes del mes" className="flex flex-col gap-4">
          {rows.map((b) => (
            <BudgetLine key={b.id} row={b} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function BudgetLine({ row }: { row: BudgetRow }) {
  const state = budgetState(row.spentUsd, row.limitUsd);
  const pct = usedPct(row.spentUsd, row.limitUsd);
  const detail =
    state === "over"
      ? `${formatUsd(row.spentUsd - row.limitUsd)} por encima del tope`
      : `te quedan ${formatUsd(row.limitUsd - row.spentUsd)}`;
  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate capitalize">{row.category}</span>
        <span className="font-bold whitespace-nowrap">
          {formatAmount(row.spentUsd, "USD")} / {formatUsd(row.limitUsd)}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`Tope de ${row.category}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(pct, 100)}
        aria-valuetext={`${pct} %`}
        className="h-2 overflow-hidden rounded-full bg-chip"
      >
        <div
          className={`h-2 rounded-full ${BAR_COLORS[state]}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <p className={"text-xs " + (state === "over" ? "text-danger" : "text-faint")}>
        {pct} % · {detail}
      </p>
    </li>
  );
}
