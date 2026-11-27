import { fireEvent, screen } from "@testing-library/react-native";

import ProfileScreen from "@/app/perfil";
import { useAuth } from "@/lib/auth";
import { getLinkedUser, type LinkedUser, updatePreferences } from "@/lib/queries";
import { renderScreen } from "@/test-utils";

jest.mock("@/lib/supabase", () => ({ supabase: { auth: { signOut: jest.fn() } } }));
jest.mock("expo-router", () =>
  jest.requireActual<typeof import("@/test-utils")>("@/test-utils").expoRouterMock(),
);
jest.mock("@/lib/auth", () => ({ useAuth: jest.fn() }));
jest.mock("@/lib/app-lock-provider", () => ({
  useAppLock: () => ({ available: true, enabled: true, setEnabled: jest.fn() }),
}));
jest.mock("@/lib/queries", () => ({
  ...jest.requireActual("@/lib/queries"),
  getLinkedUser: jest.fn(),
  updatePreferences: jest.fn(),
}));

const ANA: LinkedUser = {
  displayName: "Ana Pérez",
  timezone: "America/Caracas",
  vesRateSource: "parallel",
  defaultCurrency: "USD",
  contextReplies: true,
  createdAt: "2026-10-05T15:00:00Z",
};

function signedIn() {
  jest.mocked(useAuth).mockReturnValue({
    session: { user: { email: "ana@example.com" } },
    loading: false,
  } as unknown as ReturnType<typeof useAuth>);
}

beforeEach(() => {
  jest.clearAllMocks();
  signedIn();
});

test("sin sesión vuelve al login (por ejemplo, justo después de cerrarla aquí)", async () => {
  jest
    .mocked(useAuth)
    .mockReturnValue({ session: null, loading: false } as unknown as ReturnType<typeof useAuth>);
  await renderScreen(<ProfileScreen />);

  expect(screen.getByText("Redirige a /login")).toBeTruthy();
  expect(screen.queryByText("Cerrar sesión")).toBeNull();
});

test("muestra quién eres y tus preferencias", async () => {
  jest.mocked(getLinkedUser).mockResolvedValue(ANA);
  await renderScreen(<ProfileScreen />);

  expect(await screen.findByText("Ana Pérez")).toBeTruthy();
  // Las iniciales son decorativas: están ocultas para el lector de pantalla.
  expect(screen.getByText("AP", { includeHiddenElements: true })).toBeTruthy();
  expect(screen.getByText("ana@example.com")).toBeTruthy();
  expect(screen.getByLabelText("Moneda por defecto: USD")).toBeTruthy();
  expect(screen.getByLabelText("Tasa de los Bs: Paralelo")).toBeTruthy();
  expect(screen.getByLabelText("Zona horaria: Caracas")).toBeTruthy();
  expect(screen.queryByText(/vincular otra cuenta/)).toBeNull();
});

test("elegir otra moneda la guarda y recarga los datos", async () => {
  jest.mocked(getLinkedUser).mockResolvedValue(ANA);
  jest.mocked(updatePreferences).mockResolvedValue();
  const { client } = await renderScreen(<ProfileScreen />);
  const invalidate = jest.spyOn(client, "invalidateQueries");

  await fireEvent.press(await screen.findByLabelText("Moneda por defecto: USD"));
  await fireEvent.press(screen.getByText("Bs"));

  expect(jest.mocked(updatePreferences).mock.calls[0][0]).toEqual({ defaultCurrency: "VES" });
  expect(invalidate).toHaveBeenCalled();
});

test("un error de la base se muestra con un mensaje claro", async () => {
  jest.mocked(getLinkedUser).mockResolvedValue(ANA);
  jest.mocked(updatePreferences).mockRejectedValue(new Error("invalid_timezone"));
  await renderScreen(<ProfileScreen />);

  await fireEvent.press(await screen.findByLabelText("Zona horaria: Caracas"));
  await fireEvent.press(screen.getByText("Bogotá"));

  expect(await screen.findByText("Esa zona horaria no está disponible.")).toBeTruthy();
});

test("sin vínculo con Telegram pide vincular en vez de mostrar preferencias", async () => {
  jest.mocked(getLinkedUser).mockResolvedValue(null);
  await renderScreen(<ProfileScreen />);

  expect(await screen.findByText("Vincula tu cuenta de Telegram")).toBeTruthy();
  expect(screen.queryByText("Preferencias")).toBeNull();
});
