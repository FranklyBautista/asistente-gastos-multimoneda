import Link from "next/link";
import { Suspense } from "react";

import { signOut } from "@/app/actions";
import { type Balance, getProfile } from "@/lib/data";

// Decimales por moneda, igual que el bot (domain/money.py).
const DECIMALS: Record<Balance["currency"], number> = { VES: 2, COP: 0, USD: 2, USDT: 2 };

function formatAmount(balance: Balance) {
  const digits = DECIMALS[balance.currency];
  return new Intl.NumberFormat("es-VE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(balance.balance);
}

export default function HomePage() {
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Tus finanzas</h1>
      {/* La sesión se lee en cada petición: con Cache Components va detrás de Suspense. */}
      <Suspense fallback={<p className="text-sm text-zinc-500">Cargando…</p>}>
        <Overview />
      </Suspense>
    </section>
  );
}

async function Overview() {
  const profile = await getProfile();
  return (
    <>
      {profile.linked ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Cuenta vinculada con Telegram
            {profile.linked.displayName ? ` (${profile.linked.displayName})` : ""}.
          </p>
          <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
            {profile.linked.balances.map((b) => (
              <li key={b.accountId} className="flex items-baseline justify-between px-4 py-3">
                <span>{b.name}</span>
                <span className="font-mono tabular-nums">
                  {formatAmount(b)} <span className="text-xs text-zinc-500">{b.currency}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-zinc-500">
            Pronto: consolidado en USD, movimientos y gráficas.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950/40">
          <p>Tu cuenta web todavía no está unida a tu cuenta de Telegram.</p>
          <Link
            href="/vincular"
            className="self-start rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800"
          >
            Vincular con Telegram
          </Link>
        </div>
      )}
      <form action={signOut} className="flex items-center justify-between text-sm">
        <span className="text-zinc-500">{profile.email}</span>
        <button className="underline">Cerrar sesión</button>
      </form>
    </>
  );
}
