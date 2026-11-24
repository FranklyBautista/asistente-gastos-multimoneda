import {
  GRACE_MS,
  LOCK_KEY,
  readLockEnabled,
  shouldLockOnResume,
  writeLockEnabled,
} from "../app-lock";

function memoryStore() {
  const data = new Map<string, string>();
  return {
    data,
    getItemAsync: async (key: string) => data.get(key) ?? null,
    setItemAsync: async (key: string, value: string) => void data.set(key, value),
  };
}

test("volver antes de 30 segundos no bloquea; después sí", () => {
  expect(shouldLockOnResume(null, 1_000_000)).toBe(false);
  expect(shouldLockOnResume(1_000_000, 1_000_000 + GRACE_MS - 1)).toBe(false);
  expect(shouldLockOnResume(1_000_000, 1_000_000 + GRACE_MS)).toBe(true);
});

test("sin preferencia guardada el bloqueo está activo", async () => {
  const store = memoryStore();
  expect(await readLockEnabled(store)).toBe(true);
  await writeLockEnabled(store, false);
  expect(store.data.get(LOCK_KEY)).toBe("off");
  expect(await readLockEnabled(store)).toBe(false);
  await writeLockEnabled(store, true);
  expect(await readLockEnabled(store)).toBe(true);
});

test("la clave es válida para expo-secure-store", () => {
  expect(LOCK_KEY).toMatch(/^[\w.-]+$/);
});
