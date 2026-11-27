import { fireEvent, screen } from "@testing-library/react-native";
import { router } from "expo-router";

import LinkScreen from "@/app/vincular";
import { redeemLinkCode } from "@/lib/queries";
import { renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: {} }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);
jest.mock("@/lib/queries", () => ({
  ...jest.requireActual("@/lib/queries"),
  redeemLinkCode: jest.fn(),
}));

beforeEach(() => jest.clearAllMocks());

test("canjea el código normalizado, recarga los datos y cierra", async () => {
  jest.mocked(redeemLinkCode).mockResolvedValue();
  const { client } = await renderScreen(<LinkScreen />);
  const invalidate = jest.spyOn(client, "invalidateQueries");

  await fireEvent.changeText(screen.getByLabelText("Código"), "abcd-2345");
  await fireEvent.press(screen.getByText("Vincular"));

  expect(redeemLinkCode).toHaveBeenCalledWith("ABCD2345");
  expect(invalidate).toHaveBeenCalled();
  expect(router.back).toHaveBeenCalled();
});

test("un código con el formato equivocado no llega a la base", async () => {
  await renderScreen(<LinkScreen />);

  await fireEvent.changeText(screen.getByLabelText("Código"), "ABCD0001");
  await fireEvent.press(screen.getByText("Vincular"));

  expect(screen.getByText("El código tiene 8 letras y números (sin I, O, 0 ni 1).")).toBeTruthy();
  expect(redeemLinkCode).not.toHaveBeenCalled();
});

test("un código vencido muestra el mensaje de la web", async () => {
  jest.mocked(redeemLinkCode).mockRejectedValue(new Error("invalid_code"));
  await renderScreen(<LinkScreen />);

  await fireEvent.changeText(screen.getByLabelText("Código"), "ABCD2345");
  await fireEvent.press(screen.getByText("Vincular"));

  expect(await screen.findByText(/no es válido o ya venció/)).toBeTruthy();
  expect(router.back).not.toHaveBeenCalled();
});
