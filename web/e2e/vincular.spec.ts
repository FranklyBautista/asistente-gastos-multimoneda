import { createClient } from "@supabase/supabase-js";
import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * Flujo completo de la Fase 9: crear cuenta → vincular con el código de /vincular → ver los
 * saldos del bot. El "bot" se simula con la llave de servicio de Supabase local, que solo
 * usa esta prueba (la web nunca la tiene).
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:55321";
const secretKey = process.env.SUPABASE_SECRET_KEY;
test.skip(!secretKey, "Falta SUPABASE_SECRET_KEY (sale de `supabase status`)");

/** Con Cache Components las páginas anteriores quedan ocultas en el DOM (Activity). */
const shown = (locator: Locator) => locator.filter({ visible: true });

const admin = createClient(url, secretKey ?? "", { auth: { persistSession: false } });
const telegramId = 900_000_000_000 + Math.floor(Math.random() * 99_999_999_999);
const email = `e2e-${telegramId}@test.invalid`;
const password = "contraseña-de-prueba-123";
const code = "E2E" + String(telegramId).slice(-5).replace(/[01]/g, "7");

test.afterAll(async () => {
  await admin.from("users").delete().eq("telegram_id", telegramId);
  const { data } = await admin.auth.admin.listUsers({ perPage: 1000 });
  const user = data?.users.find((u) => u.email === email);
  if (user) await admin.auth.admin.deleteUser(user.id);
});

async function createBotUserWithCode() {
  const { data: user, error } = await admin
    .from("users")
    .insert({ telegram_id: telegramId, display_name: "Prueba E2E" })
    .select("id")
    .single();
  if (error) throw error;
  const { data: account } = await admin
    .from("accounts")
    .select("id")
    .eq("user_id", user.id)
    .eq("currency", "USD")
    .single();
  await admin.from("transactions").insert({
    user_id: user.id,
    account_id: account!.id,
    currency: "USD",
    kind: "income",
    amount: 150,
    usd_per_unit: 1,
    rate_source: "pivot",
    amount_usd: 150,
  });
  const expires = new Date(Date.now() + 10 * 60_000).toISOString();
  const { error: codeError } = await admin
    .from("link_codes")
    .insert({ code, user_id: user.id, expires_at: expires });
  if (codeError) throw codeError;
}

/** Espera a que la página nueva esté visible antes de tocar su formulario. */
async function onPage(page: Page, path: RegExp, heading: string) {
  await expect(page).toHaveURL(path);
  await expect(shown(page.getByRole("heading", { name: heading }))).toBeVisible();
}

async function fillCredentials(page: Page, pass: string) {
  await shown(page.getByLabel("Correo")).fill(email);
  await shown(page.getByLabel("Contraseña")).fill(pass);
}

const formAlert = (page: Page) => shown(page.locator("form")).getByRole("alert");

test("crear cuenta, vincular con Telegram y ver los saldos", async ({ page }) => {
  // Sin sesión, el inicio manda al login.
  await page.goto("/");
  await onPage(page, /\/login$/, "Iniciar sesión");

  // Registro (en local no hay confirmación de correo).
  await shown(page.getByRole("link", { name: "Créala aquí" })).click();
  await onPage(page, /\/registro$/, "Crear cuenta");
  await fillCredentials(page, password);
  await shown(page.getByRole("button", { name: "Crear cuenta" })).click();
  await onPage(page, /\/$/, "Tus finanzas");
  await expect(shown(page.getByText("todavía no está unida"))).toBeVisible();

  // Código equivocado y luego el correcto, en minúsculas.
  await createBotUserWithCode();
  await shown(page.getByRole("link", { name: "Vincular con Telegram" })).click();
  await onPage(page, /\/vincular$/, "Vincular con Telegram");
  await shown(page.getByLabel("Código de /vincular")).fill("ZZZZ2345");
  await shown(page.getByRole("button", { name: "Vincular" })).click();
  await expect(formAlert(page)).toContainText("no es válido o ya venció");

  await shown(page.getByLabel("Código de /vincular")).fill(code.toLowerCase());
  await shown(page.getByRole("button", { name: "Vincular" })).click();
  await onPage(page, /\/$/, "Tus finanzas");
  await expect(shown(page.getByText("Cuenta vinculada con Telegram (Prueba E2E)"))).toBeVisible();
  await expect(shown(page.getByRole("listitem")).filter({ hasText: "efectivo USD" })).toContainText(
    "150,00",
  );

  // Cerrar sesión y volver a entrar.
  await shown(page.getByRole("button", { name: "Cerrar sesión" })).click();
  await onPage(page, /\/login$/, "Iniciar sesión");
  await fillCredentials(page, password);
  await shown(page.getByRole("button", { name: "Entrar" })).click();
  await onPage(page, /\/$/, "Tus finanzas");
  await expect(shown(page.getByText("Cuenta vinculada con Telegram"))).toBeVisible();
});

test("una contraseña equivocada muestra un error claro", async ({ page }) => {
  await page.goto("/login");
  await onPage(page, /\/login$/, "Iniciar sesión");
  await fillCredentials(page, "incorrecta");
  await shown(page.getByRole("button", { name: "Entrar" })).click();
  await expect(formAlert(page)).toHaveText("Correo o contraseña incorrectos.");
});
