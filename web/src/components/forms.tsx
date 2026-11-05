"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useActionState, useLayoutEffect, useRef } from "react";

import { type FormState, redeemCode, signIn, signUp } from "@/app/actions";

const input =
  "w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2.5 text-base outline-none " +
  "focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/30 dark:border-zinc-700";
const button =
  "w-full rounded-lg bg-emerald-700 px-4 py-2.5 font-medium text-white hover:bg-emerald-800 " +
  "disabled:opacity-60";

function Feedback({ state }: { state: FormState }) {
  if (state.error) {
    return (
      <p role="alert" className="text-sm text-red-700 dark:text-red-400">
        {state.error}
      </p>
    );
  }
  if (state.notice) {
    return (
      <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
        {state.notice}
      </p>
    );
  }
  return null;
}

/**
 * Con Cache Components, Next.js oculta la página anterior en vez de desmontarla (Activity).
 * `key={bfcacheId}` reinicia el formulario y sus errores en cada navegación nueva.
 */
export function AuthForm({ mode }: { mode: "login" | "registro" }) {
  const { bfcacheId } = useRouter();
  return <AuthFormFields key={bfcacheId} mode={mode} />;
}

export function LinkForm() {
  const { bfcacheId } = useRouter();
  return <LinkFormFields key={bfcacheId} />;
}

function AuthFormFields({ mode }: { mode: "login" | "registro" }) {
  const isLogin = mode === "login";
  const [state, action, pending] = useActionState(isLogin ? signIn : signUp, {});
  const password = useRef<HTMLInputElement>(null);
  // Al ocultarse la página (o al ir atrás y adelante), la contraseña no queda en el DOM.
  useLayoutEffect(() => {
    const field = password.current;
    return () => {
      if (field) field.value = "";
    };
  }, []);
  return (
    <form action={action} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        Correo
        <input
          className={input}
          name="email"
          type="email"
          autoComplete="email"
          required
          inputMode="email"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Contraseña
        <input
          ref={password}
          className={input}
          name="password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          minLength={isLogin ? undefined : 8}
          required
        />
      </label>
      <Feedback state={state} />
      <button className={button} disabled={pending}>
        {pending ? "Un momento…" : isLogin ? "Entrar" : "Crear cuenta"}
      </button>
      <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
        {isLogin ? (
          <>
            ¿No tienes cuenta?{" "}
            <Link className="underline" href="/registro">
              Créala aquí
            </Link>
          </>
        ) : (
          <>
            ¿Ya tienes cuenta?{" "}
            <Link className="underline" href="/login">
              Inicia sesión
            </Link>
          </>
        )}
      </p>
    </form>
  );
}

function LinkFormFields() {
  const [state, action, pending] = useActionState(redeemCode, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm">
        Código de /vincular
        <input
          className={`${input} font-mono tracking-[0.3em] uppercase`}
          name="code"
          autoComplete="one-time-code"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={12}
          placeholder="K7MP4XQ2"
          required
        />
      </label>
      <Feedback state={state} />
      <button className={button} disabled={pending}>
        {pending ? "Vinculando…" : "Vincular"}
      </button>
    </form>
  );
}
