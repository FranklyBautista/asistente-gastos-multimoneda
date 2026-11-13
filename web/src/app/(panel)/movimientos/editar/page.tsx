import Link from "next/link";
import { Suspense } from "react";

import { EditTransactionForm } from "@/components/edit-transaction";
import { ChevronLeftIcon } from "@/components/icons";
import { Empty, LinkBanner, Loading } from "@/components/panel";
import { getAccounts, getCategories, getSession, getTransaction } from "@/lib/data";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Editar movimiento · Asistente de gastos" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function EditPage({ searchParams }: PageProps<"/movimientos/editar">) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4">
      <header className="grid grid-cols-[44px_1fr_44px] items-center">
        <Link
          href="/movimientos"
          aria-label="Volver a movimientos"
          className="grid size-11 place-items-center rounded-full bg-white/[0.08] hover:bg-white/[0.14]"
        >
          <ChevronLeftIcon />
        </Link>
        <h1 className="text-center text-[17px] font-bold">Editar movimiento</h1>
      </header>
      <Suspense fallback={<Loading />}>
        <Editor searchParams={searchParams} />
      </Suspense>
    </div>
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
    <>
      {transaction.description ? (
        <p className="-mt-1 text-center text-sm text-muted">{transaction.description}</p>
      ) : null}
      <EditTransactionForm
        transaction={transaction}
        accounts={accounts}
        categories={categories}
        dateLabel={formatDateTime(transaction.occurredAt, user.timezone)}
      />
      <p className="text-center text-xs text-faint">
        Si cambias la moneda, el equivalente en USD se recalcula con la tasa de cuando lo anotaste.
        Cada cambio queda como corrección y el bot lo usa como ejemplo.
      </p>
    </>
  );
}
