import { fireEvent, screen } from "@testing-library/react-native";
import { router, useLocalSearchParams } from "expo-router";

import EditScreen from "@/app/editar/[id]";
import { DEBT_LINKED_MESSAGE } from "@/lib/edit-errors";
import {
  editTransaction,
  type EditableTransaction,
  getAccounts,
  getCategories,
  getLinkedUser,
  getTransaction,
} from "@/lib/queries";
import { fakeLinkedUser, renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: {} }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);
jest.mock("@/lib/queries", () => ({
  ...jest.requireActual("@/lib/queries"),
  getLinkedUser: jest.fn(),
  getTransaction: jest.fn(),
  getAccounts: jest.fn(),
  getCategories: jest.fn(),
  editTransaction: jest.fn(),
}));

const lunch: EditableTransaction = {
  id: "tx1",
  kind: "expense",
  amount: 15,
  currency: "USD",
  accountId: "usd",
  categoryId: "comida",
  description: "almuerzo",
  occurredAt: "2026-11-20T16:00:00Z",
  debtLinked: false,
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(useLocalSearchParams).mockReturnValue({ id: "tx1" });
  jest.mocked(getLinkedUser).mockResolvedValue(fakeLinkedUser());
  jest.mocked(getTransaction).mockResolvedValue(lunch);
  jest.mocked(getAccounts).mockResolvedValue([
    { id: "usd", name: "Efectivo USD", currency: "USD" },
    { id: "ves", name: "Banco Bs", currency: "VES" },
  ]);
  jest.mocked(getCategories).mockResolvedValue([
    { id: "comida", name: "comida", kind: "expense" },
    { id: "transporte", name: "transporte", kind: "expense" },
    { id: "pago", name: "pago de deudas", kind: "expense" },
    { id: "sueldo", name: "sueldo", kind: "income" },
  ]);
});

test("guarda el tipo, el monto, la cuenta y la categoría elegidos, y vuelve atrás", async () => {
  jest.mocked(editTransaction).mockResolvedValue(1);
  await renderScreen(<EditScreen />);

  expect(await screen.findByText("almuerzo")).toBeTruthy();
  // Las categorías de deudas solo las usa el bot.
  expect(screen.queryByText("pago de deudas")).toBeNull();

  await fireEvent.press(screen.getByText("Banco Bs"));
  expect(screen.getByLabelText("Monto en Bs")).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText("Monto en Bs"), "550,50");
  await fireEvent.press(screen.getByText("transporte"));
  await fireEvent.press(screen.getByText("Guardar cambios"));

  expect(editTransaction).toHaveBeenCalledWith({
    id: "tx1",
    kind: "expense",
    amount: 550.5,
    accountId: "ves",
    categoryId: "transporte",
  });
  expect(router.back).toHaveBeenCalled();
});

test("al pasar a ingreso ofrece solo categorías de ingreso", async () => {
  jest.mocked(editTransaction).mockResolvedValue(1);
  await renderScreen(<EditScreen />);

  await fireEvent.press(await screen.findByText("Ingreso"));
  expect(screen.queryByText("comida")).toBeNull();
  await fireEvent.press(screen.getByText("Guardar cambios"));

  expect(editTransaction).toHaveBeenCalledWith(
    expect.objectContaining({ kind: "income", categoryId: "sueldo" }),
  );
});

test("un monto inválido no se envía", async () => {
  await renderScreen(<EditScreen />);

  await fireEvent.changeText(await screen.findByLabelText("Monto en USD"), "0");
  await fireEvent.press(screen.getByText("Guardar cambios"));

  expect(screen.getByText("El monto debe ser mayor que cero.")).toBeTruthy();
  expect(editTransaction).not.toHaveBeenCalled();
});

test("un error de la base se traduce y la pantalla no se cierra", async () => {
  jest
    .mocked(editTransaction)
    .mockRejectedValue(new Error('rate_unavailable: no hay tasa para "COP"'));
  await renderScreen(<EditScreen />);

  await fireEvent.press(await screen.findByText("Guardar cambios"));

  expect(
    await screen.findByText("Todavía no hay tasa guardada para esa moneda; inténtalo más tarde."),
  ).toBeTruthy();
  expect(router.back).not.toHaveBeenCalled();
});

test("el pago de una deuda no se puede editar", async () => {
  jest.mocked(getTransaction).mockResolvedValue({ ...lunch, debtLinked: true });
  await renderScreen(<EditScreen />);

  expect(await screen.findByText(DEBT_LINKED_MESSAGE)).toBeTruthy();
  expect(screen.queryByText("Guardar cambios")).toBeNull();
});

test("un movimiento que ya no existe lo dice", async () => {
  jest.mocked(getTransaction).mockResolvedValue(null);
  await renderScreen(<EditScreen />);

  expect(await screen.findByText("Ese movimiento no existe o ya se deshizo.")).toBeTruthy();
});
