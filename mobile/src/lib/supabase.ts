import "react-native-url-polyfill/auto";

import { createClient } from "@supabase/supabase-js";
import * as SecureStore from "expo-secure-store";
import { AppState } from "react-native";

import type { Database } from "./database.types";
import { chunkedStorage } from "./secure-storage";

// Expo solo incrusta las EXPO_PUBLIC_* cuando se leen así, con el nombre completo.
const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const publishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

if (!url || !publishableKey) {
  throw new Error(
    "Faltan EXPO_PUBLIC_SUPABASE_URL o EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY (ver mobile/.env.example)",
  );
}

/**
 * Cliente único de la app. Usa solo la llave publicable: todo lo que lee pasa por la RLS de
 * la sesión y las escrituras van por funciones (ADR 0012 y 0014), igual que en la web.
 */
export const supabase = createClient<Database>(url, publishableKey, {
  auth: {
    storage: chunkedStorage(SecureStore),
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// En segundo plano no se refresca el token (no hay timers fiables); al volver, sí.
AppState.addEventListener("change", (state) => {
  if (state === "active") supabase.auth.startAutoRefresh();
  else supabase.auth.stopAutoRefresh();
});
