"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { HomeIcon, ListIcon, PieIcon, PlusIcon, SwapIcon } from "@/components/icons";

const LINKS = [
  { href: "/", label: "Inicio", Icon: HomeIcon },
  { href: "/movimientos", label: "Movimientos", Icon: ListIcon },
  { href: "/graficas", label: "Gráficas", Icon: PieIcon },
  { href: "/cambios", label: "Cambios", Icon: SwapIcon },
] as const;

/** Usuario del bot (sin @) para el botón de anotar; sin él, el botón no aparece. */
const BOT = process.env.NEXT_PUBLIC_TELEGRAM_BOT?.replace(/^@/, "");

/** Barra flotante de abajo: las cuatro secciones y el atajo para anotar en Telegram. */
export function PanelNav() {
  const path = usePathname();
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 flex justify-center px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
      <div className="pointer-events-auto flex w-full max-w-md items-center gap-2.5">
        <nav
          aria-label="Secciones"
          className="flex h-16 flex-1 items-center justify-between rounded-full border border-line bg-[#08100a]/85 px-2 shadow-[0_10px_30px_rgba(0,0,0,.5)] backdrop-blur-lg"
        >
          {LINKS.map(({ href, label, Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={
                  "flex h-12 min-w-12 items-center justify-center gap-2 rounded-full px-3 text-xs font-semibold " +
                  (active
                    ? "bg-chip text-lime shadow-[inset_0_0_0_1px_rgba(141,251,134,.35)]"
                    : "text-muted hover:text-foreground")
                }
              >
                <Icon />
                <span className={active ? "max-sm:sr-only" : "sr-only"}>{label}</span>
              </Link>
            );
          })}
        </nav>
        {BOT ? (
          <a
            href={`https://t.me/${BOT}`}
            target="_blank"
            rel="noreferrer"
            aria-label="Anotar en Telegram"
            title="Anotar en Telegram"
            className="grid size-16 flex-none place-items-center rounded-full bg-[linear-gradient(140deg,#c2ffae,#6eea78)] text-on-lime shadow-[0_10px_30px_-6px_rgba(110,240,120,.6)]"
          >
            <PlusIcon className="size-6" strokeWidth={2.2} />
          </a>
        ) : null}
      </div>
    </div>
  );
}
