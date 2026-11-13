"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useActionState, useLayoutEffect, useRef, useState } from "react";

import { type FormState, redeemCode, signIn, signUp } from "@/app/actions";
import { KeyIcon, LockIcon, MailIcon } from "@/components/icons";

/** Campo en píldora: ícono, etiqueta solo para lectores y el input. */
const pill =
  "flex h-[52px] items-center gap-2.5 rounded-full border border-line bg-field pr-1.5 pl-4 " +
  "text-muted focus-within:border-lime";
const input =
  "h-full min-w-0 flex-1 bg-transparent text-[15px] font-medium text-foreground outline-none " +
  "placeholder:text-faint focus-visible:outline-none";
const button =
  "btn-lime mt-2 h-[52px] w-full rounded-full text-[15px] font-bold disabled:opacity-60";
const card =
  "flex flex-col gap-3 rounded-[26px] border border-line p-[18px] " +
  "bg-[linear-gradient(180deg,rgba(30,56,35,.7),rgba(12,24,14,.85))] " +
  "shadow-[inset_0_1px_0_rgba(255,255,255,.06),0_24px_60px_-20px_rgba(0,0,0,.7)]";

function Feedback({ state }: { state: FormState }) {
  if (state.error) {
    return (
      <p role="alert" className="px-2 text-sm font-semibold text-danger">
        {state.error}
      </p>
    );
  }
  if (state.notice) {
    return (
      <p role="status" className="px-2 text-sm font-semibold text-lime-soft">
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

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-[18px]"
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {open ? null : <path d="M4 4l16 16" />}
    </svg>
  );
}

function AuthFormFields({ mode }: { mode: "login" | "registro" }) {
  const isLogin = mode === "login";
  const [state, action, pending] = useActionState(isLogin ? signIn : signUp, {});
  const [visible, setVisible] = useState(false);
  const password = useRef<HTMLInputElement>(null);
  // Al ocultarse la página (o al ir atrás y adelante), la contraseña no queda en el DOM.
  useLayoutEffect(() => {
    const field = password.current;
    return () => {
      if (field) field.value = "";
    };
  }, []);
  return (
    <>
      <form action={action} className={card}>
        <label className={pill}>
          <MailIcon className="size-[18px] flex-none" strokeWidth={1.8} />
          <span className="sr-only">Correo</span>
          <input
            className={input}
            name="email"
            type="email"
            autoComplete="email"
            placeholder="tu@correo.com"
            required
            inputMode="email"
          />
        </label>
        <div className={pill}>
          <LockIcon className="size-[18px] flex-none" strokeWidth={1.8} />
          <label htmlFor={`clave-${mode}`} className="sr-only">
            Contraseña
          </label>
          <input
            id={`clave-${mode}`}
            ref={password}
            className={input}
            name="password"
            type={visible ? "text" : "password"}
            placeholder={isLogin ? "Contraseña" : "Contraseña (8 o más caracteres)"}
            autoComplete={isLogin ? "current-password" : "new-password"}
            minLength={isLogin ? undefined : 8}
            required
          />
          <button
            type="button"
            aria-label="Ver lo escrito"
            aria-pressed={visible}
            onClick={() => setVisible((v) => !v)}
            className="grid size-11 flex-none place-items-center rounded-full text-muted hover:text-foreground"
          >
            <EyeIcon open={visible} />
          </button>
        </div>
        <Feedback state={state} />
        <button className={button} disabled={pending}>
          {pending ? "Un momento…" : isLogin ? "Entrar" : "Crear cuenta"}
        </button>
      </form>
      <p className="mt-auto flex items-center justify-between gap-4 text-[13px] text-muted">
        {isLogin ? (
          <>
            ¿No tienes cuenta?
            <Link className="flex min-h-11 items-center font-bold text-lime" href="/registro">
              Créala aquí
            </Link>
          </>
        ) : (
          <>
            ¿Ya tienes cuenta?
            <Link className="flex min-h-11 items-center font-bold text-lime" href="/login">
              Inicia sesión
            </Link>
          </>
        )}
      </p>
    </>
  );
}

function LinkFormFields() {
  const [state, action, pending] = useActionState(redeemCode, {});
  return (
    <form action={action} className={card}>
      <label className={pill}>
        <KeyIcon className="size-[18px] flex-none" strokeWidth={1.8} />
        <span className="sr-only">Código de /vincular</span>
        <input
          className={`${input} font-bold tracking-[0.3em] uppercase`}
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
