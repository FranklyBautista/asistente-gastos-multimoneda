import { categoryOptions, parseAmount, pickCategory } from "../edit";
import { editErrorMessage } from "../edit-errors";
import type { Category } from "../queries";

const CATEGORIES: Category[] = [
  { id: "comida", name: "comida", kind: "expense" },
  { id: "pago", name: "pago de deudas", kind: "expense" },
  { id: "salario", name: "salario", kind: "income" },
  { id: "cobro", name: "cobro de deudas", kind: "income" },
];

test("las categorías de deudas solo aparecen si el movimiento ya está en una", () => {
  expect(categoryOptions(CATEGORIES, "expense", "comida").map((c) => c.id)).toEqual(["comida"]);
  expect(categoryOptions(CATEGORIES, "expense", "pago").map((c) => c.id)).toEqual([
    "comida",
    "pago",
  ]);
  expect(categoryOptions(CATEGORIES, "income", "comida").map((c) => c.id)).toEqual(["salario"]);
});

test("al cambiar el tipo se propone la primera categoría del nuevo tipo", () => {
  const income = categoryOptions(CATEGORIES, "income", "comida");
  expect(pickCategory(income, "comida")).toBe("salario");
  expect(pickCategory(income, "salario")).toBe("salario");
  expect(pickCategory([], "comida")).toBeUndefined();
});

test("el monto acepta coma o punto y rechaza cero, negativos y texto", () => {
  expect(parseAmount("12,50")).toBe(12.5);
  expect(parseAmount(" 7.25 ")).toBe(7.25);
  expect(parseAmount("0")).toBeNull();
  expect(parseAmount("-3")).toBeNull();
  expect(parseAmount("")).toBeNull();
  expect(parseAmount("abc")).toBeNull();
});

test("los errores de la base se traducen igual que en la web", () => {
  expect(editErrorMessage("P0001: debt_linked")).toMatch(/pago de una deuda/);
  expect(editErrorMessage("rate_unavailable")).toMatch(/tasa/);
  expect(editErrorMessage("algo raro")).toBe("No se pudo guardar. Inténtalo de nuevo.");
});
