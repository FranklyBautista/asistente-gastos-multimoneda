import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DarkTheme, Stack, ThemeProvider } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { AuthProvider } from "@/lib/auth";
import { colors } from "@/theme";

// Datos financieros personales: se guardan solo en memoria, nunca en disco sin cifrar.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
});

const theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.background,
    primary: colors.lime,
    text: colors.foreground,
    border: colors.line,
  },
};

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider value={theme}>
          <StatusBar style="light" />
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="(panel)" />
            <Stack.Screen name="(cuenta)" />
            <Stack.Screen
              name="vincular"
              options={{
                headerShown: true,
                title: "Vincular con Telegram",
                presentation: "modal",
              }}
            />
          </Stack>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
