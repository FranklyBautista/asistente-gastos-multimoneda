import { fireEvent, screen } from "@testing-library/react-native";

import DebtsScreen from "@/app/(panel)/deudas";
import { type DebtRow, getDebts, getLinkedUser } from "@/lib/queries";
import { renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: {} }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);
jest.mock("@/lib/queries", () => ({
  ...jest.requireActual("@/lib/queries"),
  getLinkedUser: jest.fn(),
  getDebts: jest.fn(),
}));

const linkedUser = jest.mocked(getLinkedUser);
const debts = jest.mocked(getDebts);

const user = { displayName: "Frankly", timezone: "America/Caracas", vesRateSource: "bcv" };
const debt: DebtRow = {
  id: "1",
  direction: "i_owe",
  counterparty: "Miguel",
  currency: "USD",
  amount: 20,
  remaining: 20,
  status: "open",
  description: null,
  incurredAt: "2026-11-20T15:00:00Z",
};

beforeEach(() => jest.clearAllMocks());

test("suma lo pendiente por moneda y deja las liquidadas al final, tachadas", async () => {
  linkedUser.mockResolvedValue(user);
  debts.mockResolvedValue([
    { ...debt, id: "s", counterparty: "Ana", status: "settled", remaining: 0 },
    debt,
    { ...debt, id: "p", counterparty: "Luis", status: "partial", amount: 30, remaining: 10 },
    { ...debt, id: "o", direction: "owed_to_me", counterparty: "Rosa", currency: "VES" },
  ]);
  await renderScreen(<DebtsScreen />);

  expect(await screen.findByText("Le debes 20,00 USD a Miguel")).toBeTruthy();
  // Debes: 20 de Miguel + 10 que quedan de Luis; la de Ana ya no cuenta.
  expect(screen.getByText(/^30,00/)).toBeTruthy();
  expect(screen.getByText("Rosa te debe 20,00 Bs")).toBeTruthy();
  expect(screen.getByText("Quedan 10,00")).toBeTruthy();
  const items = screen.getAllByLabelText(/Le debes|te debe/);
  expect(items.at(-1)?.props.accessibilityLabel).toBe("Le debes 20,00 USD a Ana, liquidada");
});

test("sin vincular con Telegram muestra cómo hacerlo y no pide las deudas", async () => {
  linkedUser.mockResolvedValue(null);
  await renderScreen(<DebtsScreen />);

  expect(await screen.findByText("Vincula tu cuenta de Telegram")).toBeTruthy();
  expect(debts).not.toHaveBeenCalled();
});

test("si falla la lectura ofrece reintentar", async () => {
  linkedUser.mockResolvedValue(user);
  debts.mockRejectedValueOnce(new Error("sin red")).mockResolvedValueOnce([]);
  await renderScreen(<DebtsScreen />);

  await fireEvent.press(await screen.findByText("Reintentar"));
  expect(await screen.findByText(/Sin deudas/)).toBeTruthy();
  expect(debts).toHaveBeenCalledTimes(2);
});
