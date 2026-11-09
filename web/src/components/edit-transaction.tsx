"use client";

import { useActionState, useState } from "react";

import { editTransaction, type FormState } from "@/app/actions";
import type { Account, Category, EditableTransaction } from "@/lib/data";
import { CURRENCY_LABELS, type Kind, KIND_LABELS } from "@/lib/format";

const input =
  "w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2.5 text-base outline-none " +
  "focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/30 dark:border-zinc-700";

export function EditTransactionForm({
  transaction,
  accounts,
  categories,
}: {
  transaction: EditableTransaction;
  accounts: Account[];
  categories: Category[];
}) {
  const [state, action, pending] = useActionState<FormState, FormData>(
    editTransaction.bind(null, transaction.id),
    {},
  );
  const [kind, setKind] = useState<Kind>(transaction.kind);
  const options = categories.filter((c) => c.kind === kind);
  // Al cambiar de tipo, la categoría anterior deja de servir: se propone la primera.
  const current = options.some((c) => c.id === transaction.categoryId)
    ? (transaction.categoryId ?? undefined)
    : options[0]?.id;

  return (
    <form action={action} className="flex flex-col gap-4">
      <fieldset className="flex gap-4 text-sm">
        <legend className="mb-1 text-sm">Tipo</legend>
        {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
          <label key={k} className="flex items-center gap-2">
            <input
              type="radio"
              name="kind"
              value={k}
              checked={kind === k}
              onChange={() => setKind(k)}
            />
            {KIND_LABELS[k]}
          </label>
        ))}
      </fieldset>
      <label className="flex flex-col gap-1 text-sm">
        Monto
        <input
          className={`${input} font-mono`}
          name="amount"
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          defaultValue={transaction.amount}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Cuenta (define la moneda)
        <select className={input} name="account" defaultValue={transaction.accountId}>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} · {CURRENCY_LABELS[a.currency]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Categoría
        <select key={kind} className={input} name="category" defaultValue={current}>
          {options.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {state.error ? (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {state.error}
        </p>
      ) : null}
      <button
        className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
        disabled={pending}
      >
        {pending ? "Guardando…" : "Guardar cambios"}
      </button>
    </form>
  );
}
