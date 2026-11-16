import Link from "next/link";
import { Suspense } from "react";

import { ChevronLeftIcon, ChevronRightIcon, FilterIcon } from "@/components/icons";
import { Chip, Empty, LinkBanner, Loading } from "@/components/panel";
import { TransactionItem } from "@/components/transactions";
import {
  getCategories,
  getSession,
  listTransactions,
  PAGE_SIZE,
  type TransactionFilters,
} from "@/lib/data";
import { CURRENCIES, CURRENCY_LABELS, isCurrency, isKind, KIND_LABELS } from "@/lib/format";

export const metadata = { title: "Movimientos · Asistente de gastos" };

type Search = Record<string, string | string[] | undefined>;

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function one(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v?.trim() || undefined;
}

/** Los filtros vienen de la URL: lo que no es válido se ignora. */
function parseFilters(search: Search): { filters: TransactionFilters; page: number } {
  const currency = one(search.moneda);
  const kind = one(search.tipo);
  const categoryId = one(search.categoria);
  const from = one(search.desde);
  const to = one(search.hasta);
  const page = Number.parseInt(one(search.pagina) ?? "1", 10);
  return {
    filters: {
      currency: isCurrency(currency) ? currency : undefined,
      kind: isKind(kind) ? kind : undefined,
      categoryId: categoryId && UUID.test(categoryId) ? categoryId : undefined,
      from: from && DAY.test(from) ? from : undefined,
      to: to && DAY.test(to) ? to : undefined,
    },
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function hrefFor(filters: TransactionFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.currency) params.set("moneda", filters.currency);
  if (filters.kind) params.set("tipo", filters.kind);
  if (filters.categoryId) params.set("categoria", filters.categoryId);
  if (filters.from) params.set("desde", filters.from);
  if (filters.to) params.set("hasta", filters.to);
  if (page > 1) params.set("pagina", String(page));
  const query = params.toString();
  return query ? `/movimientos?${query}` : "/movimientos";
}

export default function TransactionsPage({ searchParams }: PageProps<"/movimientos">) {
  return (
    <>
      <h1 className="text-[26px] font-extrabold tracking-tight">Movimientos</h1>
      <Suspense fallback={<Loading />}>
        <Transactions searchParams={searchParams} />
      </Suspense>
    </>
  );
}

const field =
  "h-11 w-full rounded-full border border-line bg-field px-4 text-sm text-foreground outline-none " +
  "focus:border-lime";

const KIND_CHIPS = [
  { value: undefined, label: "Todos" },
  { value: "expense", label: "Gastos" },
  { value: "income", label: "Ingresos" },
] as const;

async function Transactions({ searchParams }: Pick<PageProps<"/movimientos">, "searchParams">) {
  const { user } = await getSession();
  if (!user) return <LinkBanner />;
  const search = await searchParams;
  const { filters, page } = parseFilters(search);
  const edited = Number.parseInt(one(search.editado) ?? "", 10);
  const [{ rows, total }, categories] = await Promise.all([
    listTransactions(filters, page),
    getCategories(),
  ]);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const extra = [filters.categoryId, filters.from, filters.to].filter(Boolean).length;
  const anyFilter = extra > 0 || Boolean(filters.currency || filters.kind);

  return (
    <>
      {Number.isFinite(edited) ? (
        <p
          role="status"
          className="rounded-2xl border border-lime/25 bg-lime/10 px-4 py-3 text-sm font-semibold text-lime-soft"
        >
          {edited === 0
            ? "No había nada que cambiar."
            : "Movimiento corregido. El bot aprenderá de esta corrección."}
        </p>
      ) : null}

      <nav
        aria-label="Tipo"
        className="grid grid-cols-3 rounded-full border border-line bg-field p-1 sm:max-w-sm"
      >
        {KIND_CHIPS.map(({ value, label }) => (
          <Chip
            key={label}
            solid
            href={hrefFor({ ...filters, kind: value }, 1)}
            active={filters.kind === value}
          >
            {label}
          </Chip>
        ))}
      </nav>

      <nav
        aria-label="Moneda"
        className="scrollbar-none -mx-5 -my-1 flex gap-2 overflow-x-auto px-5 py-1 sm:mx-0 sm:px-0"
      >
        <Chip href={hrefFor({ ...filters, currency: undefined }, 1)} active={!filters.currency}>
          Todas
        </Chip>
        {CURRENCIES.map((c) => (
          <Chip
            key={c}
            href={hrefFor({ ...filters, currency: c }, 1)}
            active={filters.currency === c}
          >
            {CURRENCY_LABELS[c]}
          </Chip>
        ))}
      </nav>

      {/* Formulario GET: los filtros quedan en la URL y se pueden compartir o recargar. */}
      <details className="glass group rounded-3xl" open={extra > 0}>
        <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 px-5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          <FilterIcon className="size-[18px] text-muted" />
          Más filtros
          {extra > 0 ? (
            <span className="grid size-5 place-items-center rounded-full bg-lime text-[11px] font-extrabold text-on-lime">
              {extra}
            </span>
          ) : null}
          <span className="ml-auto text-xs font-normal text-muted">Categoría y fechas</span>
        </summary>
        <form
          action="/movimientos"
          className="grid gap-3 px-5 pb-5 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end"
        >
          {filters.currency ? <input type="hidden" name="moneda" value={filters.currency} /> : null}
          {filters.kind ? <input type="hidden" name="tipo" value={filters.kind} /> : null}
          <label className="flex flex-col gap-1.5 text-xs text-muted">
            Categoría
            <select name="categoria" defaultValue={filters.categoryId ?? ""} className={field}>
              <option value="">Todas</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({KIND_LABELS[c.kind].toLowerCase()})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs text-muted">
            Desde
            <input type="date" name="desde" defaultValue={filters.from ?? ""} className={field} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs text-muted">
            Hasta
            <input type="date" name="hasta" defaultValue={filters.to ?? ""} className={field} />
          </label>
          <button className="btn-lime h-11 rounded-full px-6 text-sm font-bold">Filtrar</button>
        </form>
      </details>

      <p className="text-xs text-muted">
        {total === 1 ? "1 movimiento" : `${total} movimientos`}
        {pages > 1 ? ` · página ${page} de ${pages}` : ""}
        {anyFilter ? (
          <>
            {" · "}
            <Link href="/movimientos" className="font-semibold text-lime hover:text-lime-soft">
              Limpiar filtros
            </Link>
          </>
        ) : null}
      </p>

      {rows.length === 0 ? (
        <Empty>No hay movimientos con esos filtros.</Empty>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Movimientos">
          {rows.map((t) => (
            <TransactionItem key={t.id} t={t} timeZone={user.timezone} />
          ))}
        </ul>
      )}

      {pages > 1 ? (
        <nav aria-label="Páginas" className="flex justify-between gap-3 text-sm font-semibold">
          {page > 1 ? (
            <Link
              href={hrefFor(filters, page - 1)}
              className="glass flex h-11 items-center gap-1 rounded-full pr-4 pl-3"
            >
              <ChevronLeftIcon className="size-4" />
              Anterior
            </Link>
          ) : (
            <span />
          )}
          {page < pages ? (
            <Link
              href={hrefFor(filters, page + 1)}
              className="glass flex h-11 items-center gap-1 rounded-full pr-3 pl-4"
            >
              Siguiente
              <ChevronRightIcon className="size-4" />
            </Link>
          ) : null}
        </nav>
      ) : null}
    </>
  );
}
