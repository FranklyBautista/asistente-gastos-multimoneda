import Link from "next/link";

/** Lo que ve una cuenta web que todavía no está unida a Telegram. */
export function LinkBanner() {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950/40">
      <p>Tu cuenta web todavía no está unida a tu cuenta de Telegram.</p>
      <Link
        href="/vincular"
        className="self-start rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800"
      >
        Vincular con Telegram
      </Link>
    </div>
  );
}

export function Loading() {
  return <p className="text-sm text-zinc-500">Cargando…</p>;
}

export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800 ${className}`}
    >
      {title ? <h2 className="text-base font-semibold">{title}</h2> : null}
      {children}
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-zinc-500">{children}</p>;
}
