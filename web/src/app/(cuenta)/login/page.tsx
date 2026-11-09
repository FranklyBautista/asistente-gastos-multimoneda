import { Suspense } from "react";

import { AuthForm } from "@/components/forms";

export const metadata = { title: "Iniciar sesión · Asistente de gastos" };

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Iniciar sesión</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Mira en un solo lugar lo que anotas en Telegram.
        </p>
      </header>
      <Suspense fallback={null}>
        <CallbackError searchParams={searchParams} />
      </Suspense>
      <AuthForm mode="login" />
    </section>
  );
}

/** /auth/callback manda aquí con ?error=confirmacion si el enlace del correo no sirvió. */
async function CallbackError({ searchParams }: Pick<PageProps<"/login">, "searchParams">) {
  const { error } = await searchParams;
  if (error !== "confirmacion") return null;
  return (
    <p role="alert" className="text-sm text-red-700 dark:text-red-400">
      No se pudo confirmar el correo: el enlace venció o se abrió en otro navegador. Inicia sesión;
      si te lo pide, vuelve a registrarte para recibir un correo nuevo.
    </p>
  );
}
