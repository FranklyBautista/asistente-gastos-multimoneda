import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * La app formatea y traduce igual que la web: estos archivos son copias exactas de los de
 * web/. Si uno cambia, hay que copiarlo (ver mobile/README.md) o este test falla.
 */
const COPIES: [mobile: string, web: string][] = [
  ["src/lib/format.ts", "../web/src/lib/format.ts"],
  ["src/lib/link-errors.ts", "../web/src/lib/link-errors.ts"],
  ["src/lib/edit-errors.ts", "../web/src/lib/edit-errors.ts"],
  ["src/lib/habits.ts", "../web/src/lib/habits.ts"],
  ["src/lib/database.types.ts", "../web/src/lib/supabase/database.types.ts"],
];

const root = join(__dirname, "..", "..", "..");
const read = (path: string) => readFileSync(join(root, path), "utf8").replace(/\r\n/g, "\n");

test.each(COPIES)("%s es igual a %s", (mobile, web) => {
  expect(read(mobile)).toBe(read(web));
});
