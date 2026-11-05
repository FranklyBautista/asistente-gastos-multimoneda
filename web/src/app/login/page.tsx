import { AuthForm } from "@/components/forms";

export const metadata = { title: "Iniciar sesión · Asistente de gastos" };

export default function LoginPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Iniciar sesión</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Mira en un solo lugar lo que anotas en Telegram.
        </p>
      </header>
      <AuthForm mode="login" />
    </section>
  );
}
