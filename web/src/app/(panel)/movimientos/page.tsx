import Link from "next/link";
import { Suspense } from "react";

import { Card, Empty, LinkBanner, Loading } from "@/components/panel";
import {
  getCategories,
  getSession,
  listTransactions,
  PAGE_SIZE,
  type TransactionFilters,
} from "@/lib/data";
import {
  CURRENCIES,
  CURRENCY_LABELS,
  formatAmount,
  formatDateTime,
  formatUsd,
  isCurrency,
  isKind,
  KIND_LABELS,
} from "@/lib/format";

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
      <h1 className="text-2xl font-semibold">Movimientos</h1>
      <Suspense fallback={<Loading />}>
        <Transactions searchParams={searchParams} />
      </Suspense>
    </>
  );
}

const field =
  "rounded-lg border border-zinc-300 bg-transparent px-2 py-1.5 text-sm dark:border-zinc-700";

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

  return (
    <>
      {Number.isFinite(edited) ? (
        <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
          {edited === 0
            ? "No había nada que cambiar."
            : "Movimiento corregido. El bot aprenderá de esta corrección."}
        </p>
      ) : null}

      {/* Formulario GET: los filtros quedan en la URL y se pueden compartir o recargar. */}
      <form
        action="/movimientos"
        className="grid grid-cols-2 gap-3 rounded-lg border border-zinc-200 p-4 sm:grid-cols-3 lg:grid-cols-6 dark:border-zinc-800"
      >
        <label className="flex flex-col gap-1 text-xs">
          Moneda
          <select name="moneda" defaultValue={filters.currency ?? ""} className={field}>
            <option value="">Todas</option>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {CURRENCY_LABELS[c]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          Tipo
          <select name="tipo" defaultValue={filters.kind ?? ""} className={field}>
            <option value="">Todos</option>
            <option value="expense">Gastos</option>
            <option value="income">Ingresos</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
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
        <label className="flex flex-col gap-1 text-xs">
          Desde
          <input type="date" name="desde" defaultValue={filters.from ?? ""} className={field} />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          Hasta
          <input type="date" name="hasta" defaultValue={filters.to ?? ""} className={field} />
        </label>
        <div className="flex items-end gap-2">
          <button className="rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
            Filtrar
          </button>
          <Link href="/movimientos" className="py-1.5 text-sm underline">
            Limpiar
          </Link>
        </div>
      </form>

      <Card>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {total === 1 ? "1 movimiento" : `${total} movimientos`}
          {pages > 1 ? ` · página ${page} de ${pages}` : ""}
        </p>
        {rows.length === 0 ? (
          <Empty>No hay movimientos con esos filtros.</Empty>
        ) : (
          <ul
            className="-mx-4 divide-y divide-zinc-200 dark:divide-zinc-800"
            aria-label="Movimientos"
          >
            {rows.map((t) => (
              <li key={t.id} className="flex items-start justify-between gap-4 px-4 py-3">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate">
                    {t.description || t.categoryName || "Sin descripción"}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {formatDateTime(t.occurredAt, user.timezone)} ·{" "}
                    {t.categoryName ?? "sin categoría"} · {t.accountName}
                    {t.edited ? " · corregido" : ""}
                  </span>
                </div>
                <div className="flex shrink-0 flex-col items-end">
                  <span
                    className={
                      "font-mono tabular-nums " +
                      (t.kind === "income" ? "text-emerald-700 dark:text-emerald-400" : "")
                    }
                  >
                    {t.kind === "income" ? "+" : "−"}
                    {formatAmount(t.amount, t.currency)}{" "}
                    <span className="text-xs text-zinc-500">{CURRENCY_LABELS[t.currency]}</span>
                  </span>
                  {t.currency !== "USD" ? (
                    <span className="font-mono text-xs text-zinc-500 tabular-nums">
                      ≈ {formatUsd(t.amountUsd)}
                    </span>
                  ) : null}
                  <Link
                    href={`/movimientos/editar?id=${t.id}`}
                    className="text-xs underline"
                    aria-label={`Editar ${t.description || "movimiento"}`}
                  >
                    Editar
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
        {pages > 1 ? (
          <nav aria-label="Páginas" className="flex justify-between text-sm">
            {page > 1 ? (
              <Link href={hrefFor(filters, page - 1)} className="underline">
                ← Anterior
              </Link>
            ) : (
              <span />
            )}
            {page < pages ? (
              <Link href={hrefFor(filters, page + 1)} className="underline">
                Siguiente →
              </Link>
            ) : null}
          </nav>
        ) : null}
      </Card>
    </>
  );
}
