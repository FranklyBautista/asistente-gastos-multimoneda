import Link from "next/link";
import { Suspense } from "react";

import { EditTransactionForm } from "@/components/edit-transaction";
import { Empty, LinkBanner, Loading } from "@/components/panel";
import { getAccounts, getCategories, getSession, getTransaction } from "@/lib/data";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Editar movimiento · Asistente de gastos" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function EditPage({ searchParams }: PageProps<"/movimientos/editar">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Editar movimiento</h1>
      <Suspense fallback={<Loading />}>
        <Editor searchParams={searchParams} />
      </Suspense>
      <Link href="/movimientos" className="text-sm underline">
        ← Volver a movimientos
      </Link>
    </>
  );
}

async function Editor({ searchParams }: Pick<PageProps<"/movimientos/editar">, "searchParams">) {
  const { user } = await getSession();
  if (!user) return <LinkBanner />;
  const raw = (await searchParams).id;
  const id = Array.isArray(raw) ? raw[0] : raw;
  const transaction = id && UUID.test(id) ? await getTransaction(id) : null;
  if (!transaction) return <Empty>Ese movimiento no existe o ya se deshizo.</Empty>;
  const [accounts, categories] = await Promise.all([getAccounts(), getCategories()]);

  return (
    <div className="flex max-w-md flex-col gap-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-zinc-500">Fecha</dt>
        <dd>{formatDateTime(transaction.occurredAt, user.timezone)}</dd>
        <dt className="text-zinc-500">Descripción</dt>
        <dd>{transaction.description || "—"}</dd>
        {transaction.rawText ? (
          <>
            <dt className="text-zinc-500">Mensaje</dt>
            <dd className="italic">«{transaction.rawText}»</dd>
          </>
        ) : null}
      </dl>
      <EditTransactionForm transaction={transaction} accounts={accounts} categories={categories} />
      <p className="text-xs text-zinc-500">
        Si cambias la moneda, el equivalente en USD se recalcula con la tasa de cuando lo anotaste.
        Cada cambio queda como corrección y el bot lo usa como ejemplo.
      </p>
    </div>
  );
}
