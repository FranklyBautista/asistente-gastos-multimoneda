/**
 * Ayudas para las pruebas de pantallas. No lo importa la app: solo los archivos de
 * `__tests__`, que simulan `@/lib/queries` para no tocar Supabase.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react-native";
import { createElement, type ReactElement, type ReactNode } from "react";
import { Text } from "react-native";

import type { LinkedUser } from "@/lib/queries";

/** Un QueryClient por prueba, sin reintentos, para que los errores se vean de inmediato. */
export async function renderScreen(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  const result = await render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  return { ...result, client };
}

/** Un usuario vinculado de prueba; se cambia solo lo que importe en cada caso. */
export function fakeLinkedUser(overrides: Partial<LinkedUser> = {}): LinkedUser {
  return {
    displayName: null,
    timezone: "America/Caracas",
    vesRateSource: "bcv",
    defaultCurrency: "USD",
    contextReplies: true,
    createdAt: "2026-10-05T15:00:00Z",
    ...overrides,
  };
}

/** Sustituto de expo-router: `router` y los parámetros se pueden revisar y fijar en cada prueba. */
export function expoRouterMock() {
  return {
    router: { back: jest.fn(), replace: jest.fn(), push: jest.fn() },
    useLocalSearchParams: jest.fn(() => ({})),
    Link: ({ children, asChild }: { children: ReactNode; asChild?: boolean }) =>
      asChild ? children : createElement(Text, null, children),
    /** Se ve como el texto «Redirige a <href>», para comprobar a dónde mandaría la pantalla. */
    Redirect: ({ href }: { href: string }) => createElement(Text, null, `Redirige a ${href}`),
  };
}
