import { signOut } from "@/app/actions";
import { LogoutIcon, WalletIcon } from "@/components/icons";
import { PanelNav } from "@/components/nav";

/** Panel: barra de arriba con la marca y la sesión, contenido al centro y menú flotante abajo. */
export default function PanelLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-5 pt-6 sm:px-6">
        <span className="flex items-center gap-2.5 text-sm font-bold whitespace-nowrap">
          <span className="grid size-9 place-items-center rounded-xl border border-lime/40 bg-chip text-lime-soft shadow-[0_0_24px_rgba(141,251,134,.25)]">
            <WalletIcon className="size-[18px]" />
          </span>
          Asistente de gastos
        </span>
        <form action={signOut}>
          <button
            title="Cerrar sesión"
            className="glass flex h-11 min-w-11 items-center justify-center gap-2 rounded-full text-[13px] font-semibold whitespace-nowrap text-muted hover:text-foreground sm:px-4"
          >
            <LogoutIcon className="size-4" />
            <span className="max-sm:sr-only">Cerrar sesión</span>
          </button>
        </form>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-5 pt-6 pb-32 sm:px-6">
        {children}
      </main>
      <PanelNav />
    </>
  );
}
