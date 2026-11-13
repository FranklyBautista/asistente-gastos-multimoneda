import { AuthForm } from "@/components/forms";

export const metadata = { title: "Crear cuenta · Asistente de gastos" };

export default function SignUpPage() {
  return (
    <section className="flex flex-1 flex-col gap-6">
      <header className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-[28px] font-extrabold tracking-tight">Crear cuenta</h1>
        <p className="max-w-72 text-sm text-muted">
          Después la vinculas con tu cuenta de Telegram usando /vincular.
        </p>
      </header>
      <AuthForm mode="registro" />
    </section>
  );
}
