import { createClient } from "@supabase/supabase-js";
import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * Hábitos (Fase 12): Inicio muestra el colchón en días y los topes del mes con lo mismo que
 * calcula el bot. Los datos del "bot" se crean con la llave de servicio de Supabase local.
 *
 * Un ingreso de 400 USD hace 29 días (30 días de historial) y 145 USD de gasto hoy: 4,83 USD
 * al día y 255 USD de saldo, unos 52 días de colchón. Topes: comida 85 de 100 (cerca) y
 * transporte 60 de 50 (pasado).
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:55321";
const secretKey = process.env.SUPABASE_SECRET_KEY;
test.skip(!secretKey, "Falta SUPABASE_SECRET_KEY (sale de `supabase status`)");

const shown = (locator: Locator) => locator.filter({ visible: true });

const admin = createClient(url, secretKey ?? "", { auth: { persistSession: false } });
const telegramId = 800_000_000_000 + Math.floor(Math.random() * 99_999_999_999);
const email = `habitos-${telegramId}@test.invalid`;
const password = "contraseña-de-prueba-123";
let authUserId = "";

test.beforeAll(async () => {
  const { data: auth, error: authError } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (authError) throw authError;
  authUserId = auth.user.id;

  const { data: user, error } = await admin
    .from("users")
    .insert({ telegram_id: telegramId, display_name: "Hábitos E2E", auth_user_id: authUserId })
    .select("id")
    .single();
  if (error) throw error;

  const { data: account } = await admin
    .from("accounts")
    .select("id")
    .eq("user_id", user.id)
    .eq("currency", "USD")
    .single();
  const { data: categories } = await admin
    .from("categories")
    .select("id, name")
    .is("user_id", null);
  const category = (n: string) => categories!.find((c) => c.name === n)!.id;

  // Todas las filas llevan occurred_at: en una inserción masiva, PostgREST manda null (no el
  // valor por defecto) a la columna que falte en alguna fila.
  const now = new Date().toISOString();
  const usd = (kind: "income" | "expense", amount: number, name: string, occurredAt = now) => ({
    user_id: user.id,
    account_id: account!.id,
    currency: "USD",
    kind,
    amount,
    category_id: category(name),
    usd_per_unit: 1,
    rate_source: "pivot",
    amount_usd: amount,
    occurred_at: occurredAt,
  });
  const { error: txError } = await admin
    .from("transactions")
    .insert([
      usd("income", 400, "salario", new Date(Date.now() - 29 * 86_400_000).toISOString()),
      usd("expense", 85, "comida"),
      usd("expense", 60, "transporte"),
    ]);
  if (txError) throw txError;

  const { error: budgetError } = await admin.from("budgets").insert([
    { user_id: user.id, category_id: category("comida"), limit_usd: 100 },
    { user_id: user.id, category_id: category("transporte"), limit_usd: 50 },
  ]);
  if (budgetError) throw budgetError;
});

test.afterAll(async () => {
  await admin.from("users").delete().eq("telegram_id", telegramId);
  if (authUserId) await admin.auth.admin.deleteUser(authUserId);
});

async function login(page: Page) {
  await page.goto("/login");
  await shown(page.getByLabel("Correo")).fill(email);
  await shown(page.getByLabel("Contraseña")).fill(password);
  await shown(page.getByRole("button", { name: "Entrar" })).click();
  await expect(page).toHaveURL(/\/$/);
}

const card = (page: Page, title: string) =>
  shown(page.locator("section").filter({ has: page.getByRole("heading", { name: title }) }));

test("colchón en días y topes del mes en Inicio", async ({ page }) => {
  await login(page);

  const runway = card(page, "Colchón");
  await expect(runway.getByLabel("Cubres unos 52 días de tus gastos")).toBeVisible();
  await expect(runway).toContainText(
    "Gastas $4,83 al día, tu promedio desde que empezaste a anotar hace 30 días.",
  );
  await expect(runway).toContainText("Siguiente escalón: 60 días.");

  const budgets = shown(page.getByRole("list", { name: "Topes del mes" }));
  await expect(budgets.getByRole("listitem")).toHaveCount(2);
  await expect(budgets.getByRole("listitem").nth(0)).toContainText("85 % · te quedan $15,00");
  await expect(budgets.getByRole("listitem").nth(1)).toContainText(
    "120 % · $10,00 por encima del tope",
  );
  await expect(page.getByRole("progressbar", { name: "Tope de transporte" })).toHaveAttribute(
    "aria-valuenow",
    "100",
  );
});
