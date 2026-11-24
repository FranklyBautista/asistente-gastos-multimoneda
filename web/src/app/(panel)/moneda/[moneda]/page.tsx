import { notFound } from "next/navigation";
import { Suspense } from "react";

import { CurrencyDetail } from "@/components/currency-detail";
import { LinkBanner, Loading } from "@/components/panel";
import { getBalances, getSession, listTransactions } from "@/lib/data";
import { isCurrency } from "@/lib/format";

export const metadata = { title: "Moneda · Asistente de gastos" };

/** Detalle de una moneda: su saldo (todas sus cuentas) y sus movimientos. */
export default function CurrencyPage({ params }: PageProps<"/moneda/[moneda]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Detail params={params} />
    </Suspense>
  );
}

async function Detail({ params }: { params: PageProps<"/moneda/[moneda]">["params"] }) {
  const { moneda } = await params;
  const currency = moneda.toUpperCase();
  if (!isCurrency(currency)) notFound();

  const { user } = await getSession();
  if (!user) return <LinkBanner />;

  const [balances, movements] = await Promise.all([
    getBalances(),
    listTransactions({ currency }, 1),
  ]);
  return (
    <CurrencyDetail
      currency={currency}
      balances={balances}
      movements={movements}
      timeZone={user.timezone}
    />
  );
}
