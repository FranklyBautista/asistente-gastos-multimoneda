"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Inicio" },
  { href: "/movimientos", label: "Movimientos" },
  { href: "/graficas", label: "Gráficas" },
  { href: "/cambios", label: "Cambios" },
] as const;

export function PanelNav() {
  const path = usePathname();
  return (
    <nav aria-label="Secciones" className="-mx-1 flex w-full gap-1 overflow-x-auto text-sm">
      {LINKS.map(({ href, label }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={
              "rounded-md px-3 py-1.5 whitespace-nowrap " +
              (active
                ? "bg-emerald-700 text-white"
                : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800")
            }
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
