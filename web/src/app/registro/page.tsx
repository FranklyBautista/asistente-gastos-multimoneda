import { AuthForm } from "@/components/forms";

export const metadata = { title: "Crear cuenta · Asistente de gastos" };

export default function SignUpPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Crear cuenta</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Después la vinculas con tu cuenta de Telegram usando /vincular.
        </p>
      </header>
      <AuthForm mode="registro" />
    </section>
  );
}
