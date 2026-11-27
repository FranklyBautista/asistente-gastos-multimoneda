import { screen } from "@testing-library/react-native";

import ExchangesScreen from "@/app/(panel)/cambios";
import { type ExchangeRow, getExchanges, getLinkedUser } from "@/lib/queries";
import { fakeLinkedUser, renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: {} }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);
jest.mock("@/lib/queries", () => ({
  ...jest.requireActual("@/lib/queries"),
  getLinkedUser: jest.fn(),
  getExchanges: jest.fn(),
}));

const user = fakeLinkedUser();
const sale: ExchangeRow = {
  id: "1",
  occurredAt: "2026-11-20T15:00:00Z",
  fromAmount: 50,
  fromCurrency: "USDT",
  toAmount: 49250,
  toCurrency: "VES",
  effectiveRate: 985,
  referenceRate: 1000,
  differencePct: -1.5,
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(getLinkedUser).mockResolvedValue(user);
});

test("muestra cada cambio con su tasa y el promedio contra la referencia", async () => {
  jest
    .mocked(getExchanges)
    .mockResolvedValue([
      sale,
      { ...sale, id: "2", differencePct: 2.5 },
      { ...sale, id: "3", referenceRate: null, differencePct: null },
    ]);
  await renderScreen(<ExchangesScreen />);

  expect(await screen.findByText("Diferencia promedio contra la tasa de referencia")).toBeTruthy();
  // El promedio solo cuenta los cambios que tienen referencia: (−1,5 + 2,5) / 2.
  expect(screen.getByText("+0,5 %")).toBeTruthy();
  expect(screen.getAllByText("50,00 USDT → 49.250,00 Bs")).toHaveLength(3);
  expect(screen.getAllByText("Tasa 985,00 · referencia 1.000,00")).toHaveLength(2);
  expect(screen.getByText("Tasa 985,00")).toBeTruthy();
  expect(screen.getByText("-1,5 %")).toBeTruthy();
});

test("sin cambios explica cómo anotar uno", async () => {
  jest.mocked(getExchanges).mockResolvedValue([]);
  await renderScreen(<ExchangesScreen />);

  expect(await screen.findByText(/cambié 50 usdt a bs a 985/)).toBeTruthy();
  expect(screen.queryByText(/Diferencia promedio/)).toBeNull();
});
