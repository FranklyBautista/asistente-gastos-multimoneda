import { sheetFilterCount, toQuery, withKind } from "../filters";

const TZ = "America/Caracas";

beforeAll(() => {
  jest.useFakeTimers();
  // 23 de noviembre de 2026 a las 10:00 en Caracas (UTC−4).
  jest.setSystemTime(new Date("2026-11-23T14:00:00Z"));
});

afterAll(() => jest.useRealTimers());

test("los últimos N días cuentan hoy, en la zona del usuario", () => {
  expect(toQuery({ days: 7 }, TZ)).toEqual({ from: "2026-11-17", to: "2026-11-23" });
  expect(toQuery({ days: 30, kind: "expense" }, TZ)).toEqual({
    kind: "expense",
    from: "2026-10-25",
    to: "2026-11-23",
  });
  expect(toQuery({ currency: "VES" }, TZ)).toEqual({ currency: "VES" });
});

test("la moneda no cuenta como filtro de la hoja", () => {
  expect(sheetFilterCount({ currency: "USD" })).toBe(0);
  expect(sheetFilterCount({ kind: "income", categoryId: "c1", days: 7 })).toBe(3);
});

test("al cambiar el tipo se descarta una categoría del otro tipo", () => {
  const kinds: Record<string, "expense" | "income"> = { comida: "expense", sueldo: "income" };
  const lookup = (id: string) => kinds[id];
  expect(withKind({ categoryId: "comida" }, "income", lookup)).toEqual({
    kind: "income",
    categoryId: undefined,
  });
  expect(withKind({ categoryId: "comida" }, "expense", lookup)).toEqual({
    kind: "expense",
    categoryId: "comida",
  });
  expect(withKind({ categoryId: "sueldo" }, undefined, lookup).categoryId).toBe("sueldo");
});
