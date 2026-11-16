import Link from "next/link";

import { ArrowInIcon, CategoryIcon, SendIcon } from "@/components/icons";

/** Lo que ve una cuenta web que todavía no está unida a Telegram. */
export function LinkBanner() {
  return (
    <div className="glass flex flex-col gap-4 rounded-3xl p-5 text-sm">
      <span className="grid size-11 place-items-center rounded-2xl border border-lime/30 bg-chip text-lime-soft">
        <SendIcon />
      </span>
      <p className="text-base">Tu cuenta web todavía no está unida a tu cuenta de Telegram.</p>
      <Link
        href="/vincular"
        className="btn-lime grid h-12 place-items-center rounded-full px-6 font-bold sm:self-start"
      >
        Vincular con Telegram
      </Link>
    </div>
  );
}

export function Loading() {
  return (
    <p className="text-sm text-muted" role="status">
      Cargando…
    </p>
  );
}

export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass flex flex-col gap-3 rounded-3xl p-5 ${className}`}>
      {title || action ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {title ? <h2 className="text-base font-bold">{title}</h2> : null}
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

/** Cuadro del ícono de una categoría, como en las filas de movimientos. */
export function CategoryBadge({ name, income = false }: { name: string | null; income?: boolean }) {
  return (
    <span className="grid size-10 flex-none place-items-center rounded-xl border border-lime/20 bg-lime/[0.08] text-lime-soft">
      {income && !name ? (
        <ArrowInIcon className="size-[18px]" strokeWidth={1.8} />
      ) : (
        <CategoryIcon name={name} className="size-[18px]" strokeWidth={1.8} />
      )}
    </span>
  );
}

/** Píldora de filtro: enlace (GET) con estado activo. */
export function Chip({
  href,
  active,
  children,
  solid = false,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
  /** Activo en lima sólido (segmentos) en vez de borde lima (monedas). */
  solid?: boolean;
}) {
  const on = solid
    ? "bg-lime font-bold text-on-lime shadow-[0_6px_18px_-6px_rgba(110,240,120,.6)]"
    : "border border-lime bg-lime/15 font-bold text-lime-soft";
  return (
    <Link
      href={href}
      aria-current={active ? "true" : undefined}
      className={
        "grid h-10 flex-none place-items-center rounded-full px-4 text-[13px] whitespace-nowrap " +
        (active
          ? on
          : solid
            ? "font-semibold text-muted hover:text-foreground"
            : "glass font-semibold")
      }
    >
      {children}
    </Link>
  );
}
