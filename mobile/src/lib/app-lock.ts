import type { KeyValueStore } from "./secure-storage";

/**
 * Bloqueo de la app con la biometría o el PIN del teléfono: quien tome el teléfono
 * desbloqueado no ve los saldos. Se pide al abrir la app y al volver del segundo plano.
 */

/** Tiempo en segundo plano que no vuelve a bloquear (cambiar de app un momento). */
export const GRACE_MS = 30_000;

/** Clave en el llavero; solo letras, números, `.`, `-` y `_` (regla de expo-secure-store). */
export const LOCK_KEY = "app-lock.enabled";

/** ¿Hay que pedir el desbloqueo al volver a primer plano? */
export function shouldLockOnResume(backgroundedAt: number | null, now: number): boolean {
  return backgroundedAt !== null && now - backgroundedAt >= GRACE_MS;
}

/** Preferencia guardada; sin valor, el bloqueo está activo (la opción segura por defecto). */
export async function readLockEnabled(store: Pick<KeyValueStore, "getItemAsync">) {
  return (await store.getItemAsync(LOCK_KEY)) !== "off";
}

export async function writeLockEnabled(
  store: Pick<KeyValueStore, "setItemAsync">,
  enabled: boolean,
): Promise<void> {
  await store.setItemAsync(LOCK_KEY, enabled ? "on" : "off");
}
