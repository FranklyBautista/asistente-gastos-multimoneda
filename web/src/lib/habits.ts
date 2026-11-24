/**
 * Colchón en días y estado de los topes (Fase 12, ADR 0017), con las mismas reglas que el bot
 * (bot/src/gastos/domain/runway.py y budget.py). Las sumas en USD vienen de la base
 * (`spending_pace`, `budget_progress` y `account_balances_usd`); aquí solo se divide y se
 * compara, como indica la migración de la Fase 12.
 */

export const WINDOW_DAYS = 90;
export const MIN_HISTORY_DAYS = 14;
/** Escalones del colchón: el primero que se pasa es el siguiente objetivo. */
export const STEPS = [14, 30, 60, 90] as const;
/** Desde el 80 % del tope se avisa que va cerca. */
export const NEAR_SHARE = 0.8;

export type Runway =
  | {
      known: true;
      availableUsd: number;
      dailySpendUsd: number;
      days: number;
      windowDays: number;
      nextStep: number | null;
    }
  | { known: false; reason: "no_history" | "short_history" | "no_expenses"; historyDays: number };

/** El colchón, o por qué todavía no se puede calcular. `days` es null sin movimientos. */
export function runway(availableUsd: number, expensesUsd: number, days: number | null): Runway {
  if (days === null) return { known: false, reason: "no_history", historyDays: 0 };
  if (days < MIN_HISTORY_DAYS) return { known: false, reason: "short_history", historyDays: days };
  if (expensesUsd <= 0) return { known: false, reason: "no_expenses", historyDays: days };
  const daily = expensesUsd / days;
  const covered = Math.floor(Math.max(availableUsd, 0) / daily);
  return {
    known: true,
    availableUsd,
    dailySpendUsd: Math.round(daily * 100) / 100,
    days: covered,
    windowDays: days,
    nextStep: STEPS.find((s) => s > covered) ?? null,
  };
}

export type BudgetState = "ok" | "near" | "over";

export function budgetState(spentUsd: number, limitUsd: number): BudgetState {
  if (spentUsd > limitUsd) return "over";
  if (spentUsd >= limitUsd * NEAR_SHARE) return "near";
  return "ok";
}

/** Qué % del tope se lleva, sin decimales. */
export function usedPct(spentUsd: number, limitUsd: number): number {
  return Math.round((spentUsd / limitUsd) * 100);
}

/** Días que quedan del mes contando hoy, para un día local "YYYY-MM-DD": el 30/11 queda 1. */
export function daysLeftInMonth(today: string): number {
  const [year, month, day] = today.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return lastDay - day + 1;
}

export function daysText(n: number): string {
  return n === 1 ? "1 día" : `${n} días`;
}
