"use client";

import { useActionState, useState } from "react";

import { editTransaction, type FormState } from "@/app/actions";
import { ArrowInIcon, ArrowOutIcon, SendIcon } from "@/components/icons";
import type { Account, Category, EditableTransaction } from "@/lib/data";
import { CURRENCY_LABELS, type Kind, KIND_LABELS } from "@/lib/format";

const field =
  "rounded-[18px] border border-line bg-[linear-gradient(180deg,rgba(22,40,26,.8),rgba(9,18,11,.9))]";

export function EditTransactionForm({
  transaction,
  accounts,
  categories,
  dateLabel,
}: {
  transaction: EditableTransaction;
  accounts: Account[];
  categories: Category[];
  /** Fecha y hora ya formateadas en la zona del usuario. */
  dateLabel: string;
}) {
  const [state, action, pending] = useActionState<FormState, FormData>(
    editTransaction.bind(null, transaction.id),
    {},
  );
  const [kind, setKind] = useState<Kind>(transaction.kind);
  const [accountId, setAccountId] = useState(transaction.accountId);
  const currency = accounts.find((a) => a.id === accountId)?.currency ?? transaction.currency;
  const options = categories.filter((c) => c.kind === kind);
  // Al cambiar de tipo, la categoría anterior deja de servir: se propone la primera.
  const current = options.some((c) => c.id === transaction.categoryId)
    ? (transaction.categoryId ?? undefined)
    : options[0]?.id;

  return (
    <form action={action} className="flex flex-col gap-3">
      <section className="flex flex-col items-center gap-3.5 rounded-[26px] border border-lime/20 bg-[linear-gradient(180deg,#0f1e12,#070e08)] p-5 shadow-[0_0_40px_-10px_rgba(141,251,134,.25),inset_0_1px_0_rgba(255,255,255,.05)]">
        <label
          htmlFor="monto"
          className="text-[11px] font-bold tracking-[.08em] text-muted uppercase"
        >
          Monto
        </label>
        <div className="flex items-baseline justify-center gap-2">
          <span className="text-lg font-bold text-lime-soft">{CURRENCY_LABELS[currency]}</span>
          <input
            id="monto"
            className="max-w-[10ch] min-w-[2ch] bg-transparent text-[42px] [field-sizing:content] font-extrabold tracking-tight caret-lime outline-none [appearance:textfield] focus-visible:outline-none [&::-webkit-inner-spin-button]:appearance-none"
            name="amount"
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            defaultValue={transaction.amount}
            required
          />
        </div>
        <fieldset className="grid w-full grid-cols-2 gap-2">
          <legend className="sr-only">Tipo</legend>
          {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
            <label key={k} className="relative">
              <input
                type="radio"
                name="kind"
                value={k}
                checked={kind === k}
                onChange={() => setKind(k)}
                className="peer absolute inset-0 cursor-pointer opacity-0"
              />
              <span className="flex h-[52px] items-center gap-2.5 rounded-full border border-line pr-3 pl-2.5 text-sm font-bold text-[#c9d8cb] peer-checked:border-transparent peer-checked:bg-[linear-gradient(140deg,#c2ffae,#7bf27a)] peer-checked:text-on-lime peer-checked:shadow-[0_8px_22px_-8px_rgba(110,240,120,.6)] peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-lime">
                <span className="grid size-[30px] place-items-center rounded-full border-[1.5px] border-current">
                  {k === "income" ? (
                    <ArrowInIcon className="size-4" strokeWidth={2.2} />
                  ) : (
                    <ArrowOutIcon className="size-4" strokeWidth={2.2} />
                  )}
                </span>
                {KIND_LABELS[k]}
              </span>
            </label>
          ))}
        </fieldset>
      </section>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className={`${field} flex flex-col gap-0.5 px-4 py-2.5`}>
          <span className="text-[11px] text-muted">Fecha</span>
          <span className="text-sm font-semibold">{dateLabel}</span>
        </div>
        <label className={`${field} flex flex-col gap-0.5 px-4 py-2.5`}>
          <span className="text-[11px] text-muted">Cuenta (define la moneda)</span>
          <select
            className="h-7 bg-transparent text-sm font-semibold outline-none"
            name="account"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} · {CURRENCY_LABELS[a.currency]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset key={kind} className={`${field} flex flex-col gap-2.5 px-4 pt-2.5 pb-3.5`}>
        <legend className="float-left mb-1 text-[11px] text-muted">Categoría</legend>
        <div className="clear-left flex flex-wrap gap-2">
          {options.map((c) => (
            <label key={c.id} className="relative">
              <input
                type="radio"
                name="category"
                value={c.id}
                defaultChecked={c.id === current}
                className="peer absolute inset-0 cursor-pointer opacity-0"
              />
              <span className="grid h-9 place-items-center rounded-full bg-background px-3.5 text-[13px] font-semibold text-[#d8e6da] peer-checked:bg-lime peer-checked:font-bold peer-checked:text-on-lime peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-lime">
                {c.name}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {transaction.rawText ? (
        <figure className="m-0 flex items-start gap-2.5 rounded-[18px] border border-dashed border-lime/25 px-4 py-3 text-muted">
          <SendIcon className="mt-0.5 size-[18px] flex-none" strokeWidth={1.8} />
          <figcaption className="flex flex-col gap-0.5 text-xs">
            Lo que escribiste en Telegram
            <span className="text-sm font-semibold text-foreground">«{transaction.rawText}»</span>
          </figcaption>
        </figure>
      ) : null}

      {state.error ? (
        <p role="alert" className="text-sm font-semibold text-danger">
          {state.error}
        </p>
      ) : null}
      <button
        className="btn-lime mt-2 h-[54px] w-full rounded-full text-[15px] font-bold disabled:opacity-60"
        disabled={pending}
      >
        {pending ? "Guardando…" : "Guardar cambios"}
      </button>
    </form>
  );
}
