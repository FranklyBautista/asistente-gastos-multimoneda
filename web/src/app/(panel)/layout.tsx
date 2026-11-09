import { signOut } from "@/app/actions";
import { PanelNav } from "@/components/nav";

/** Panel: menú arriba y contenido ancho. Los datos se leen en cada página (con Suspense). */
export default function PanelLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="border-b border-zinc-200 dark:border-zinc-800">
        <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <span className="font-semibold">Asistente de gastos</span>
          <form action={signOut}>
            <button className="text-sm text-zinc-600 underline dark:text-zinc-400">
              Cerrar sesión
            </button>
          </form>
          <PanelNav />
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
        {children}
      </main>
    </>
  );
}
