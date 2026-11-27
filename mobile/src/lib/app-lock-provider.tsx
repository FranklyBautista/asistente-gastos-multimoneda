import * as LocalAuthentication from "expo-local-authentication";
import * as ScreenCapture from "expo-screen-capture";
import * as SecureStore from "expo-secure-store";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { AppState, Platform } from "react-native";

import { readLockEnabled, shouldLockOnResume, writeLockEnabled } from "./app-lock";
import { useAuth } from "./auth";
import { supabase } from "./supabase";

/** Llave propia, para no chocar con otro uso de expo-screen-capture. */
const SCREEN_CAPTURE_KEY = "app-lock";

type AppLock = {
  /** El teléfono tiene bloqueo de pantalla (huella, rostro, PIN o patrón); null mientras se revisa. */
  available: boolean | null;
  enabled: boolean;
  /** Hay sesión y falta desbloquear: la app tapa el contenido. */
  locked: boolean;
  /** Ya se leyó la preferencia y se revisó el teléfono: recién ahí se pide desbloquear. */
  ready: boolean;
  unlock: () => Promise<boolean>;
  /** Activa o desactiva el bloqueo; pide autenticarse antes. Devuelve un error o null. */
  setEnabled: (enabled: boolean) => Promise<string | null>;
};

const AppLockContext = createContext<AppLock>({
  available: null,
  enabled: false,
  locked: false,
  ready: false,
  unlock: async () => true,
  setEnabled: async () => null,
});

export function AppLockProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [available, setAvailable] = useState<boolean | null>(null);
  const [enabled, setEnabledState] = useState(false);
  // Se arranca bloqueado para no mostrar saldos mientras se lee la preferencia.
  const [locked, setLocked] = useState(true);
  const authenticating = useRef(false);
  const backgroundedAt = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([LocalAuthentication.getEnrolledLevelAsync(), readLockEnabled(SecureStore)])
      .then(([level, on]) => {
        if (!active) return;
        const hasLock = level !== LocalAuthentication.SecurityLevel.NONE;
        setAvailable(hasLock);
        setEnabledState(on);
        if (!hasLock || !on) setLocked(false);
      })
      .catch(() => {
        // Sin poder revisar el teléfono no se bloquea: mejor que dejar a la persona fuera.
        if (!active) return;
        setAvailable(false);
        setLocked(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Al cerrar sesión se quita el bloqueo: quien vuelva a entrar ya escribió la contraseña.
  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") setLocked(false);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const active = Boolean(available && enabled);
  const protect = active && Boolean(session);

  // Con el bloqueo activo, los saldos tampoco se ven fuera de la app: en Android, FLAG_SECURE deja
  // en blanco la vista de apps recientes e impide capturas; en iOS, se difumina el selector de
  // apps. Quien quiera capturas (para una demo) desactiva el bloqueo en Perfil.
  useEffect(() => {
    const done = protect
      ? Promise.all([
          ScreenCapture.preventScreenCaptureAsync(SCREEN_CAPTURE_KEY),
          Platform.OS === "ios" ? ScreenCapture.enableAppSwitcherProtectionAsync(0.9) : null,
        ])
      : Promise.all([
          ScreenCapture.allowScreenCaptureAsync(SCREEN_CAPTURE_KEY),
          Platform.OS === "ios" ? ScreenCapture.disableAppSwitcherProtectionAsync() : null,
        ]);
    // Si el módulo falla, la app sigue funcionando: el bloqueo al abrir sigue protegiendo.
    done.catch(() => undefined);
  }, [protect]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      // El diálogo del PIN abre otra pantalla y manda la app al segundo plano.
      if (authenticating.current) return;
      if (state === "background") backgroundedAt.current = Date.now();
      if (state === "active") {
        if (active && shouldLockOnResume(backgroundedAt.current, Date.now())) setLocked(true);
        backgroundedAt.current = null;
      }
    });
    return () => subscription.remove();
  }, [active]);

  const authenticate = useCallback(async (promptMessage: string) => {
    authenticating.current = true;
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage,
        cancelLabel: "Cancelar",
      });
      return result.success;
    } finally {
      authenticating.current = false;
    }
  }, []);

  const unlock = useCallback(async () => {
    const ok = await authenticate("Desbloquea tus finanzas");
    if (ok) setLocked(false);
    return ok;
  }, [authenticate]);

  const setEnabled = useCallback(
    async (next: boolean) => {
      if (next && !available) return "Activa un bloqueo de pantalla en tu teléfono primero.";
      const ok = await authenticate(
        next ? "Confirma para activar el bloqueo" : "Confirma para quitar el bloqueo",
      );
      if (!ok) return "No se pudo confirmar que eres tú.";
      await writeLockEnabled(SecureStore, next);
      setEnabledState(next);
      return null;
    },
    [authenticate, available],
  );

  return (
    <AppLockContext.Provider
      value={{
        available,
        enabled,
        locked: Boolean(session) && locked,
        ready: available !== null,
        unlock,
        setEnabled,
      }}
    >
      {children}
    </AppLockContext.Provider>
  );
}

export function useAppLock(): AppLock {
  return useContext(AppLockContext);
}
