import { CHUNK_SIZE, chunkedStorage, type KeyValueStore } from "../secure-storage";

/** Llavero falso en memoria que valida las claves como expo-secure-store. */
function fakeStore() {
  const items = new Map<string, string>();
  const check = (key: string) => {
    if (!/^[\w.-]+$/.test(key)) throw new Error(`Clave inválida: ${key}`);
  };
  const store: KeyValueStore = {
    async getItemAsync(key) {
      check(key);
      return items.get(key) ?? null;
    },
    async setItemAsync(key, value) {
      check(key);
      if (value.length > 2048) throw new Error("Valor demasiado grande para el llavero");
      items.set(key, value);
    },
    async deleteItemAsync(key) {
      check(key);
      items.delete(key);
    },
  };
  return { store, items };
}

const KEY = "sb-wdtbmtasrkvhntrkeekc-auth-token";

test("guarda y lee una sesión más grande que un valor del llavero", async () => {
  const { store, items } = fakeStore();
  const storage = chunkedStorage(store);
  const session = JSON.stringify({ access_token: "a".repeat(5000), refresh_token: "r" });
  await storage.setItem(KEY, session);
  expect(await storage.getItem(KEY)).toBe(session);
  expect(items.get(`${KEY}.n`)).toBe(String(Math.ceil(session.length / CHUNK_SIZE)));
});

test("sin sesión guardada devuelve null", async () => {
  const storage = chunkedStorage(fakeStore().store);
  expect(await storage.getItem(KEY)).toBeNull();
});

test("una sesión más corta no deja trozos de la anterior", async () => {
  const { store, items } = fakeStore();
  const storage = chunkedStorage(store);
  await storage.setItem(KEY, "x".repeat(CHUNK_SIZE * 3));
  await storage.setItem(KEY, "corta");
  expect(await storage.getItem(KEY)).toBe("corta");
  expect([...items.keys()].sort()).toEqual([`${KEY}.0`, `${KEY}.n`]);
});

test("al cerrar sesión no queda nada en el llavero", async () => {
  const { store, items } = fakeStore();
  const storage = chunkedStorage(store);
  await storage.setItem(KEY, "y".repeat(CHUNK_SIZE * 2 + 1));
  await storage.removeItem(KEY);
  expect(items.size).toBe(0);
});

test("una sesión a medio escribir cuenta como ausente", async () => {
  const { store, items } = fakeStore();
  const storage = chunkedStorage(store);
  await storage.setItem(KEY, "z".repeat(CHUNK_SIZE * 2));
  items.delete(`${KEY}.1`);
  expect(await storage.getItem(KEY)).toBeNull();
});
