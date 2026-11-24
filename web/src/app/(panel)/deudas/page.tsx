import { Suspense } from "react";

import { SendIcon } from "@/components/icons";
import { Chip, Empty, LinkBanner, Loading } from "@/components/panel";
import { type DebtDirection, type DebtRow, getDebts, getSession } from "@/lib/data";
import {
  CURRENCIES,
  CURRENCY_LABELS,
  type Currency,
  formatAmount,
  formatDateTime,
  isCurrency,
} from "@/lib/format";

export const metadata = { title: "Deudas · Asistente de gastos" };

type Search = Record<string, string | string[] | undefined>;
type Filters = { direction?: DebtDirection; currency?: Currency; person?: string };

function one(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v?.trim() || undefined;
}

/** Los filtros vienen de la URL: lo que no es válido se ignora. */
function parseFilters(search: Search): Filters {
  const direction = one(search.tipo);
  const currency = one(search.moneda);
  return {
    direction: direction === "i_owe" || direction === "owed_to_me" ? direction : undefined,
    currency: isCurrency(currency) ? currency : undefined,
    person: one(search.persona),
  };
}

function hrefFor(filters: Filters): string {
  const params = new URLSearchParams();
  if (filters.direction) params.set("tipo", filters.direction);
  if (filters.currency) params.set("moneda", filters.currency);
  if (filters.person) params.set("persona", filters.person);
  const query = params.toString();
  return query ? `/deudas?${query}` : "/deudas";
}

const DIRECTION_CHIPS = [
  { value: undefined, label: "Todas" },
  { value: "i_owe", label: "Debo" },
  { value: "owed_to_me", label: "Me deben" },
] as const;

export default function DebtsPage({ searchParams }: PageProps<"/deudas">) {
  return (
    <>
      <h1 className="text-[26px] font-extrabold tracking-tight">Deudas</h1>
      <Suspense fallback={<Loading />}>
        <Debts searchParams={searchParams} />
      </Suspense>
    </>
  );
}

/** Lo pendiente sumado por moneda original: nunca se mezclan monedas en un total. */
function pendingByCurrency(debts: DebtRow[]): [Currency, number][] {
  const totals = new Map<Currency, number>();
  for (const d of debts) {
    if (d.status !== "settled") totals.set(d.currency, (totals.get(d.currency) ?? 0) + d.remaining);
  }
  return CURRENCIES.filter((c) => totals.has(c)).map((c) => [c, totals.get(c) ?? 0]);
}

async function Debts({ searchParams }: Pick<PageProps<"/deudas">, "searchParams">) {
  const { user } = await getSession();
  if (!user) return <LinkBanner />;
  const filters = parseFilters(await searchParams);
  const all = await getDebts();
  const people = [...new Map(all.map((d) => [d.counterpartyKey, d.counterparty])).entries()].sort(
    (a, b) => a[0].localeCompare(b[0]),
  );
  const debts = all.filter(
    (d) =>
      (!filters.direction || d.direction === filters.direction) &&
      (!filters.currency || d.currency === filters.currency) &&
      (!filters.person || d.counterpartyKey === filters.person),
  );
  const pending = debts.filter((d) => d.status !== "settled");
  const settled = debts.filter((d) => d.status === "settled");
  const owe = pendingByCurrency(pending.filter((d) => d.direction === "i_owe"));
  const owed = pendingByCurrency(pending.filter((d) => d.direction === "owed_to_me"));

  return (
    <>
      <section aria-label="Total pendiente" className="grid grid-cols-2 gap-2.5">
        <TotalCard title="Debes" totals={owe} empty="No le debes nada a nadie." />
        <TotalCard title="Te deben" totals={owed} empty="Nadie te debe nada." />
      </section>

      <nav
        aria-label="Tipo de deuda"
        className="grid grid-cols-3 rounded-full border border-line bg-field p-1 sm:max-w-sm"
      >
        {DIRECTION_CHIPS.map(({ value, label }) => (
          <Chip
            key={label}
            solid
            href={hrefFor({ ...filters, direction: value })}
            active={filters.direction === value}
          >
            {label}
          </Chip>
        ))}
      </nav>

      <nav
        aria-label="Moneda"
        className="scrollbar-none -mx-5 -my-1 flex gap-2 overflow-x-auto px-5 py-1 sm:mx-0 sm:px-0"
      >
        <Chip href={hrefFor({ ...filters, currency: undefined })} active={!filters.currency}>
          Todas
        </Chip>
        {CURRENCIES.map((c) => (
          <Chip key={c} href={hrefFor({ ...filters, currency: c })} active={filters.currency === c}>
            {CURRENCY_LABELS[c]}
          </Chip>
        ))}
      </nav>

      {people.length > 1 ? (
        <nav
          aria-label="Persona"
          className="scrollbar-none -mx-5 -my-1 flex gap-2 overflow-x-auto px-5 py-1 sm:mx-0 sm:px-0"
        >
          <Chip href={hrefFor({ ...filters, person: undefined })} active={!filters.person}>
            Todas las personas
          </Chip>
          {people.map(([key, name]) => (
            <Chip
              key={key}
              href={hrefFor({ ...filters, person: key })}
              active={filters.person === key}
            >
              {name}
            </Chip>
          ))}
        </nav>
      ) : null}

      <h2 className="text-[17px] font-bold">Pendientes</h2>
      {pending.length === 0 ? (
        <Empty>
          {all.length === 0
            ? "Todavía no anotaste deudas. En Telegram, escribe por ejemplo «le debo 20 dólares a miguel»."
            : "No hay deudas pendientes con esos filtros."}
        </Empty>
      ) : (
        <ul className="flex flex-col gap-2.5" aria-label="Deudas pendientes">
          {pending.map((d) => (
            <DebtItem key={d.id} debt={d} timeZone={user.timezone} />
          ))}
        </ul>
      )}

      {settled.length > 0 ? (
        <>
          <h2 className="text-[17px] font-bold">Liquidadas</h2>
          <ul className="flex flex-col gap-2.5" aria-label="Deudas liquidadas">
            {settled.map((d) => (
              <DebtItem key={d.id} debt={d} timeZone={user.timezone} />
            ))}
          </ul>
        </>
      ) : null}

      <p className="flex items-start gap-2 text-xs text-muted">
        <SendIcon className="mt-px size-4 flex-none" strokeWidth={1.8} />
        Para anotar o pagar una deuda, escríbele al bot: «le debo 20 dólares a miguel» o «le pagué a
        miguel».
      </p>
    </>
  );
}

function TotalCard({
  title,
  totals,
  empty,
}: {
  title: string;
  totals: [Currency, number][];
  empty: string;
}) {
  return (
    <div className="glass flex min-w-0 flex-col gap-1.5 rounded-3xl px-4 py-4 sm:px-5">
      <p className="text-[13px] font-semibold text-muted">{title}</p>
      {totals.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="flex flex-col">
          {totals.map(([c, amount]) => (
            <li
              key={c}
              className="text-lg leading-tight font-extrabold tracking-tight sm:text-[22px]"
            >
              {formatAmount(amount, c)}{" "}
              <span className="text-sm font-bold text-muted">{CURRENCY_LABELS[c]}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DebtItem({ debt: d, timeZone }: { debt: DebtRow; timeZone: string }) {
  const done = d.status === "settled";
  const money = `${formatAmount(d.amount, d.currency)} ${CURRENCY_LABELS[d.currency]}`;
  const who = d.direction === "i_owe" ? `Le debes ${money} a ${d.counterparty}` : null;
  return (
    <li className={"glass flex flex-col gap-1.5 rounded-[18px] px-4 py-3.5"}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={"text-[15px] font-bold " + (done ? "text-muted line-through" : "")}>
          {who ?? `${d.counterparty} te debe ${money}`}
        </span>
        <span
          className={
            "rounded-full px-2.5 py-1 text-xs font-bold " +
            (done
              ? "bg-white/10 text-muted"
              : d.direction === "i_owe"
                ? "bg-danger/15 text-[#ff9c95]"
                : "bg-lime/15 text-lime-soft")
          }
        >
          {done
            ? "Liquidada"
            : d.status === "partial"
              ? `Pendiente ${formatAmount(d.remaining, d.currency)} ${CURRENCY_LABELS[d.currency]}`
              : "Pendiente"}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 text-xs text-muted sm:flex-row sm:justify-between sm:gap-4">
        <span className={done ? "line-through" : ""}>{d.description ?? "Sin descripción"}</span>
        <span className="text-faint">
          {formatDateTime(d.incurredAt, timeZone)}
          {done && d.lastPaidAt ? ` · pagada el ${formatDateTime(d.lastPaidAt, timeZone)}` : ""}
        </span>
      </div>
    </li>
  );
}
