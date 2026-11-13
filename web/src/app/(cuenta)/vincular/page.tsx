import Link from "next/link";

import { LinkForm } from "@/components/forms";

export const metadata = { title: "Vincular Telegram · Asistente de gastos" };

export default function LinkPage() {
  return (
    <section className="flex flex-1 flex-col gap-6">
      <header className="flex flex-col items-center gap-3 text-center">
        <h1 className="text-[28px] font-extrabold tracking-tight">Vincular con Telegram</h1>
        <ol className="glass flex list-inside list-decimal flex-col gap-1.5 rounded-3xl px-5 py-4 text-left text-sm text-muted marker:font-bold marker:text-lime">
          <li>
            En Telegram, escríbele <span className="font-bold text-foreground">/vincular</span> al
            bot.
          </li>
          <li>Copia aquí el código que te responde. Vence en 10 minutos.</li>
        </ol>
      </header>
      <LinkForm />
      <Link
        className="mt-auto flex min-h-11 items-center justify-center text-sm font-bold text-lime"
        href="/"
      >
        Volver al inicio
      </Link>
    </section>
  );
}
