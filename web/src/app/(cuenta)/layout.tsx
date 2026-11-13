import { PieIcon, SwapIcon, WalletIcon } from "@/components/icons";

/** Login, registro y vinculación: una columna angosta con la marca arriba, sin el menú del panel. */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-7 px-6 pt-16 pb-8">
      <div aria-hidden="true" className="flex h-26 items-center justify-center gap-7">
        <span className="grid size-14 -rotate-[14deg] place-items-center rounded-[18px] border border-line bg-[linear-gradient(160deg,#1b3620,#0b160d)] text-lime-soft shadow-[0_10px_24px_rgba(0,0,0,.45)]">
          <PieIcon className="size-6" strokeWidth={1.8} />
        </span>
        <span className="grid size-22 place-items-center rounded-[26px] border border-lime/45 bg-[linear-gradient(160deg,#234a29,#0e1c11)] text-[#d9ffd5] shadow-[0_0_40px_rgba(141,251,134,.35),inset_0_1px_0_rgba(255,255,255,.12)]">
          <WalletIcon className="size-9" strokeWidth={1.7} />
        </span>
        <span className="grid size-14 rotate-[14deg] place-items-center rounded-[18px] border border-line bg-[linear-gradient(160deg,#1b3620,#0b160d)] text-lime-soft shadow-[0_10px_24px_rgba(0,0,0,.45)]">
          <SwapIcon className="size-6" strokeWidth={1.8} />
        </span>
      </div>
      <p className="-mb-4 text-center text-sm font-bold tracking-wide text-lime-soft">
        Asistente de gastos
      </p>
      {children}
    </main>
  );
}
