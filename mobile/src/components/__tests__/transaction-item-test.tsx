import { render, screen } from "@testing-library/react-native";

import type { TransactionRow } from "@/lib/queries";

import { TransactionItem } from "../transaction-item";

// transaction-item solo usa el tipo de queries; el cliente real pide variables de entorno.
jest.mock("@/lib/supabase", () => ({ supabase: {} }));

const base: TransactionRow = {
  id: "1",
  occurredAt: "2026-11-21T01:00:00Z",
  kind: "expense",
  amount: 70,
  currency: "VES",
  accountName: "Efectivo Bs",
  categoryName: "transporte",
  description: "pasaje",
  amountUsd: 0.11,
  edited: false,
};

test("un gasto en Bs muestra el monto, su equivalente y la fecha local", async () => {
  await render(<TransactionItem t={base} timeZone="America/Caracas" />);
  expect(screen.getByText("pasaje")).toBeTruthy();
  expect(screen.getByText("transporte · Efectivo Bs")).toBeTruthy();
  expect(screen.getByLabelText("Gasto de 70,00 Bs")).toBeTruthy();
  expect(screen.getByText("≈ $0,11")).toBeTruthy();
  // 01:00 UTC es la noche anterior en Caracas.
  expect(screen.getByText(/20 nov/)).toBeTruthy();
});

test("un ingreso en USD no repite el equivalente y marca lo corregido", async () => {
  await render(
    <TransactionItem
      t={{ ...base, kind: "income", currency: "USD", amount: 200, amountUsd: 200, edited: true }}
      timeZone="America/Caracas"
    />,
  );
  expect(screen.getByLabelText("Ingreso de 200,00 USD")).toBeTruthy();
  expect(screen.queryByText(/≈/)).toBeNull();
  expect(screen.getByText(/corregido/)).toBeTruthy();
});
