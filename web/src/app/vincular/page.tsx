import Link from "next/link";

import { LinkForm } from "@/components/forms";

export const metadata = { title: "Vincular Telegram · Asistente de gastos" };

export default function LinkPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Vincular con Telegram</h1>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
          <li>
            En Telegram, escríbele <span className="font-mono">/vincular</span> al bot.
          </li>
          <li>Copia aquí el código que te responde. Vence en 10 minutos.</li>
        </ol>
      </header>
      <LinkForm />
      <Link className="text-center text-sm underline" href="/">
        Volver al inicio
      </Link>
    </section>
  );
}
