/**
 * Almacenamiento de la sesión de Supabase en el llavero del teléfono (Keystore en Android,
 * Keychain en iOS), nunca en texto plano: con la sesión se leen todas tus finanzas.
 *
 * La sesión (JSON con dos tokens) suele pasar de 2 KB, y algunos iOS rechazan valores más
 * grandes, así que se guarda en trozos: `<clave>.n` con el número de trozos y `<clave>.0`,
 * `<clave>.1`… con el texto. Las claves solo usan letras, números, `.`, `-` y `_`.
 */

export type KeyValueStore = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
};

export const CHUNK_SIZE = 1800;

export function chunkedStorage(store: KeyValueStore) {
  async function removeItem(key: string): Promise<void> {
    const count = Number((await store.getItemAsync(`${key}.n`)) ?? 0);
    for (let i = 0; i < count; i++) await store.deleteItemAsync(`${key}.${i}`);
    await store.deleteItemAsync(`${key}.n`);
  }

  return {
    async getItem(key: string): Promise<string | null> {
      const raw = await store.getItemAsync(`${key}.n`);
      if (raw === null) return null;
      const parts: string[] = [];
      for (let i = 0; i < Number(raw); i++) {
        const part = await store.getItemAsync(`${key}.${i}`);
        if (part === null) return null; // a medio escribir: mejor pedir sesión de nuevo
        parts.push(part);
      }
      return parts.join("");
    },

    async setItem(key: string, value: string): Promise<void> {
      await removeItem(key); // sin restos de una sesión anterior más larga
      const count = Math.max(1, Math.ceil(value.length / CHUNK_SIZE));
      for (let i = 0; i < count; i++) {
        await store.setItemAsync(`${key}.${i}`, value.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
      }
      // El contador va al final: si algo falla antes, la sesión simplemente no existe.
      await store.setItemAsync(`${key}.n`, String(count));
    },

    removeItem,
  };
}
