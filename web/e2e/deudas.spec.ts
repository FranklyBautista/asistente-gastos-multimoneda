import { createClient } from "@supabase/supabase-js";
import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * Deudas (Fase 11): lo que anota el bot aparece pendiente; al liquidarla (como lo hace el bot:
 * un pago y su gasto en «pago de deudas») pasa a Liquidadas, tachada. Los datos del "bot" se
 * crean con la llave de servicio de Supabase local, que solo usa esta prueba.
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:55321";
const secretKey = process.env.SUPABASE_SECRET_KEY;
test.skip(!secretKey, "Falta SUPABASE_SECRET_KEY (sale de `supabase status`)");

const shown = (locator: Locator) => locator.filter({ visible: true });

const admin = createClient(url, secretKey ?? "", { auth: { persistSession: false } });
const telegramId = 800_000_000_000 + Math.floor(Math.random() * 99_999_999_999);
const email = `deudas-${telegramId}@test.invalid`;
const password = "contraseña-de-prueba-123";
let authUserId = "";
let userId = "";
let miguelDebt = "";

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
    .insert({ telegram_id: telegramId, display_name: "Deudas E2E", auth_user_id: authUserId })
    .select("id")
    .single();
  if (error) throw error;
  userId = user.id;

  // «le debo 20 dólares a miguel» y «luisa me debe 50 mil pesos del mercado».
  const { data: debts, error: debtsError } = await admin
    .from("debts")
    .insert([
      {
        user_id: userId,
        direction: "i_owe",
        counterparty: "Miguel",
        currency: "USD",
        amount: 20,
        description: "almuerzo",
        usd_per_unit: 1,
        rate_source: "pivot",
        amount_usd: 20,
      },
      {
        user_id: userId,
        direction: "owed_to_me",
        counterparty: "Luisa",
        currency: "COP",
        amount: 50000,
        description: "mercado",
        usd_per_unit: 0.00025,
        rate_source: "fx",
        amount_usd: 12.5,
      },
    ])
    .select("id, counterparty");
  if (debtsError) throw debtsError;
  miguelDebt = debts.find((d) => d.counterparty === "Miguel")!.id;
});

test.afterAll(async () => {
  await admin.from("users").delete().eq("telegram_id", telegramId);
  if (authUserId) await admin.auth.admin.deleteUser(authUserId);
});

/** Lo que hace el bot con «le pagué a miguel» y la cuenta en dólares, en dos pasos. */
async function settleMiguel() {
  const { data: account } = await admin
    .from("accounts")
    .select("id")
    .eq("user_id", userId)
    .eq("currency", "USD")
    .single();
  const { data: category } = await admin
    .from("categories")
    .select("id")
    .is("user_id", null)
    .eq("name", "pago de deudas")
    .single();
  const { data: tx, error: txError } = await admin
    .from("transactions")
    .insert({
      user_id: userId,
      account_id: account!.id,
      currency: "USD",
      kind: "expense",
      amount: 20,
      category_id: category!.id,
      description: "deuda con Miguel",
      usd_per_unit: 1,
      rate_source: "pivot",
      amount_usd: 20,
      raw_text: "le pagué a miguel",
    })
    .select("id")
    .single();
  if (txError) throw txError;
  const { error } = await admin.from("debt_payments").insert({
    user_id: userId,
    debt_id: miguelDebt,
    currency: "USD",
    amount: 20,
    transaction_id: tx.id,
  });
  if (error) throw error;
}

async function login(page: Page) {
  await page.goto("/login");
  await shown(page.getByLabel("Correo")).fill(email);
  await shown(page.getByLabel("Contraseña")).fill(password);
  await shown(page.getByRole("button", { name: "Entrar" })).click();
  await expect(page).toHaveURL(/\/$/);
}

test("deudas pendientes, filtros y liquidada tachada", async ({ page }) => {
  await login(page);
  await shown(page.getByRole("navigation", { name: "Secciones" }))
    .getByRole("link", { name: "Deudas" })
    .click();
  await expect(page).toHaveURL(/\/deudas$/);
  await expect(shown(page.getByRole("heading", { name: "Deudas", level: 1 }))).toBeVisible();

  const totals = shown(page.getByRole("region", { name: "Total pendiente" }));
  await expect(totals).toContainText("Debes20,00 USD");
  await expect(totals).toContainText("Te deben50.000 COP");

  const pending = shown(page.getByRole("list", { name: "Deudas pendientes" }));
  await expect(pending.getByRole("listitem")).toHaveCount(2);
  await expect(pending).toContainText("Le debes 20,00 USD a Miguel");
  await expect(pending).toContainText("Luisa te debe 50.000 COP");

  // Filtro por tipo: solo lo que me deben.
  await shown(page.getByRole("navigation", { name: "Tipo de deuda" }))
    .getByRole("link", { name: "Me deben" })
    .click();
  await expect(page).toHaveURL(/tipo=owed_to_me/);
  await expect(pending.getByRole("listitem")).toHaveCount(1);
  await expect(pending).toContainText("Luisa");

  // El bot liquida la de Miguel: sale de pendientes y aparece tachada.
  await settleMiguel();
  await page.goto("/deudas");
  await expect(totals).toContainText("No le debes nada a nadie.");
  await expect(pending.getByRole("listitem")).toHaveCount(1);
  const settled = shown(page.getByRole("list", { name: "Deudas liquidadas" }));
  const miguel = settled.getByText("Le debes 20,00 USD a Miguel");
  await expect(miguel).toBeVisible();
  await expect(miguel).toHaveCSS("text-decoration-line", "line-through");
  await expect(settled).toContainText("Liquidada");

  // Filtro por persona.
  await shown(page.getByRole("navigation", { name: "Persona" }))
    .getByRole("link", { name: "Luisa" })
    .click();
  await expect(page).toHaveURL(/persona=luisa/);
  await expect(page.getByRole("list", { name: "Deudas liquidadas" })).toHaveCount(0);
});
