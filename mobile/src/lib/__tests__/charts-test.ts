import { bolivarChange, bolivarSeries, bolivarVerdict, compactUsd, shortDay } from "../charts";

test("los ejes usan cifras cortas con el símbolo $", () => {
  expect(compactUsd(200)).toBe("$200");
  expect(compactUsd(1250)).toBe("$1,3 mil");
  expect(compactUsd(0)).toBe("$0");
});

test("la serie del bolívar pasa a Bs por cada dólar", () => {
  expect(bolivarSeries([{ day: "2026-11-01", usdPerUnit: 0.002 }])).toEqual([
    { day: "2026-11-01", bsPerUsd: 500 },
  ]);
});

test("la variación es negativa cuando el bolívar compra menos dólares", () => {
  // De 500 a 625 Bs por dólar: cada bolívar compra un 20 % menos.
  expect(bolivarChange(0.002, 0.0016)).toBe(-20);
  expect(bolivarVerdict(-20)).toMatch(/menos dólares/);
  expect(bolivarVerdict(3.5)).toMatch(/más dólares/);
  expect(bolivarVerdict(0)).toMatch(/no cambió/);
});

test("los días cortos no se corren por la zona horaria", () => {
  expect(shortDay("2026-11-03")).toMatch(/^3 nov/);
  expect(shortDay("2026-01-01")).toMatch(/^1 ene/);
});
