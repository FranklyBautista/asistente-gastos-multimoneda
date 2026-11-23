import { budgetState, daysLeftInMonth, runway, usedPct } from "../habits";

// Los mismos casos que bot/tests de runway y budget: la app y el bot deben dar la misma cifra.

test("sin movimientos, con menos de dos semanas o sin gastos no hay colchón", () => {
  expect(runway(500, 0, null)).toEqual({ known: false, reason: "no_history", historyDays: 0 });
  expect(runway(500, 100, 10)).toEqual({ known: false, reason: "short_history", historyDays: 10 });
  expect(runway(500, 0, 30)).toEqual({ known: false, reason: "no_expenses", historyDays: 30 });
});

test("el colchón es el saldo entre el gasto diario, redondeado hacia abajo", () => {
  // 900 USD en 90 días = 10 al día; 455 USD cubren 45 días y el siguiente escalón es 60.
  expect(runway(455, 900, 90)).toEqual({
    known: true,
    availableUsd: 455,
    dailySpendUsd: 10,
    days: 45,
    windowDays: 90,
    nextStep: 60,
  });
  // Saldo negativo: no alcanza ni para un día.
  expect(runway(-20, 900, 90)).toMatchObject({ days: 0, nextStep: 14 });
  // Pasado el último escalón no hay siguiente.
  expect(runway(5000, 900, 90)).toMatchObject({ days: 500, nextStep: null });
});

test("los topes avisan desde el 80 % y pasan a «por encima» al superarlo", () => {
  expect(budgetState(79.99, 100)).toBe("ok");
  expect(budgetState(80, 100)).toBe("near");
  expect(budgetState(100, 100)).toBe("near");
  expect(budgetState(100.01, 100)).toBe("over");
  expect(usedPct(62.5, 100)).toBe(63);
});

test("los días que quedan del mes cuentan hoy", () => {
  expect(daysLeftInMonth("2026-11-30")).toBe(1);
  expect(daysLeftInMonth("2026-11-23")).toBe(8);
  expect(daysLeftInMonth("2028-02-01")).toBe(29);
});
