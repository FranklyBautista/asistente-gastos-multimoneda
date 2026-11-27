import { waitFor } from "@testing-library/react-native";
import { router, useLocalSearchParams } from "expo-router";

import AuthCallbackScreen from "@/app/auth/callback";
import { supabase } from "@/lib/supabase";
import { renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: { auth: { exchangeCodeForSession: jest.fn() } } }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);

const exchange = jest.mocked(supabase.auth.exchangeCodeForSession);
const toLoginWithError = { pathname: "/login", params: { error: "confirmacion" } };

beforeEach(() => jest.clearAllMocks());

test("canjea el código del correo una sola vez y entra al panel", async () => {
  jest.mocked(useLocalSearchParams).mockReturnValue({ code: "abc" });
  exchange.mockResolvedValue({ data: {}, error: null } as never);
  await renderScreen(<AuthCallbackScreen />);

  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
  expect(exchange).toHaveBeenCalledTimes(1);
  expect(exchange).toHaveBeenCalledWith("abc");
});

test("un enlace vencido manda al login con el aviso, sin canjear nada", async () => {
  jest
    .mocked(useLocalSearchParams)
    .mockReturnValue({ error: "access_denied", error_code: "otp_expired" });
  await renderScreen(<AuthCallbackScreen />);

  await waitFor(() => expect(router.replace).toHaveBeenCalledWith(toLoginWithError));
  expect(exchange).not.toHaveBeenCalled();
});

test("si Supabase rechaza el código (otro dispositivo), también avisa", async () => {
  jest.mocked(useLocalSearchParams).mockReturnValue({ code: "abc" });
  exchange.mockResolvedValue({ data: {}, error: new Error("code verifier") } as never);
  await renderScreen(<AuthCallbackScreen />);

  await waitFor(() => expect(router.replace).toHaveBeenCalledWith(toLoginWithError));
});
