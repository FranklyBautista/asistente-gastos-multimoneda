import { createClient } from "@supabase/supabase-js";
import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * Panel de la Fase 10: consolidado en USD, lista con filtros, edición de un movimiento,
 * gráficas e historial de cambios. Los datos del "bot" se crean con la llave de servicio
 * de Supabase local, que solo usa esta prueba.
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:55321";
const secretKey = process.env.SUPABASE_SECRET_KEY;
test.skip(!secretKey, "Falta SUPABASE_SECRET_KEY (sale de `supabase status`)");

const shown = (locator: Locator) => locator.filter({ visible: true });

const admin = createClient(url, secretKey ?? "", { auth: { persistSession: false } });
const telegramId = 800_000_000_000 + Math.floor(Math.random() * 99_999_999_999);
const email = `panel-${telegramId}@test.invalid`;
const password = "contraseña-de-prueba-123";
let authUserId = "";
const rateIds: number[] = [];

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
    .insert({
      telegram_id: telegramId,
      display_name: "Panel E2E",
      auth_user_id: authUserId,
      ves_rate_source: "bcv",
    })
    .select("id")
    .single();
  if (error) throw error;

  const { data: accounts } = await admin
    .from("accounts")
    .select("id, currency")
    .eq("user_id", user.id);
  const account = (c: string) => accounts!.find((a) => a.currency === c)!.id;
  const { data: categories } = await admin
    .from("categories")
    .select("id, name")
    .is("user_id", null);
  const category = (n: string) => categories!.find((c) => c.name === n)!.id;

  // Tasas BCV de hace 10 días y de ahora: el bolívar perdió 20 %.
  const tenDaysAgo = new Date(Date.now() - 10 * 86_400_000).toISOString();
  const now = new Date().toISOString();
  const { data: rates, error: ratesError } = await admin
    .from("exchange_rates")
    .insert([
      { currency: "VES", source: "bcv", usd_per_unit: 0.0025, fetched_at: tenDaysAgo },
      { currency: "VES", source: "bcv", usd_per_unit: 0.002, fetched_at: now },
      { currency: "USDT", source: "coingecko", usd_per_unit: 1, fetched_at: now },
    ])
    .select("id");
  if (ratesError) throw ratesError;
  rateIds.push(...rates.map((r) => r.id));

  const { error: txError } = await admin.from("transactions").insert([
    {
      user_id: user.id,
      account_id: account("USD"),
      currency: "USD",
      kind: "expense",
      amount: 15,
      category_id: category("comida"),
      description: "almuerzo",
      usd_per_unit: 1,
      rate_source: "pivot",
      amount_usd: 15,
      raw_text: "gasté 15 en el almuerzo",
    },
    {
      user_id: user.id,
      account_id: account("VES"),
      currency: "VES",
      kind: "expense",
      amount: 1000,
      category_id: category("transporte"),
      description: "pasaje",
      usd_per_unit: 0.002,
      rate_source: "bcv",
      amount_usd: 2,
      raw_text: "pasaje 1000 bs",
    },
  ]);
  if (txError) throw txError;

  const { error: exError } = await admin.from("exchanges").insert({
    user_id: user.id,
    from_account_id: account("USDT"),
    to_account_id: account("VES"),
    from_amount: 50,
    to_amount: 49250,
    effective_rate: 985,
    reference_rate: 1000,
  });
  if (exError) throw exError;
});

test.afterAll(async () => {
  await admin.from("users").delete().eq("telegram_id", telegramId);
  if (rateIds.length) await admin.from("exchange_rates").delete().in("id", rateIds);
  if (authUserId) await admin.auth.admin.deleteUser(authUserId);
});

async function onPage(page: Page, path: RegExp, heading: string) {
  await expect(page).toHaveURL(path);
  await expect(shown(page.getByRole("heading", { name: heading, level: 1 }))).toBeVisible();
}

async function nav(page: Page, name: string) {
  await shown(page.getByRole("navigation", { name: "Secciones" }))
    .getByRole("link", { name })
    .click();
}

test("saldos, movimientos con edición, gráficas y cambios", async ({ page }) => {
  await page.goto("/login");
  await onPage(page, /\/login$/, "Iniciar sesión");
  await shown(page.getByLabel("Correo")).fill(email);
  await shown(page.getByLabel("Contraseña")).fill(password);
  await shown(page.getByRole("button", { name: "Entrar" })).click();

  // Inicio: saldos por cuenta con su equivalente en USD y consolidado.
  await onPage(page, /\/$/, "Tus finanzas");
  await expect(shown(page.getByTestId("total-usd"))).toContainText("$");
  const ves = shown(page.getByRole("listitem")).filter({ hasText: "efectivo Bs" });
  await expect(ves).toContainText("48.250,00");
  await expect(ves).toContainText("≈ $96,50");
  await expect(shown(page.getByText("1 USD = 500,00 Bs"))).toBeVisible();

  // Movimientos: lista, filtro por moneda y edición.
  await nav(page, "Movimientos");
  await onPage(page, /\/movimientos$/, "Movimientos");
  const list = shown(page.getByRole("list", { name: "Movimientos" }));
  await expect(list.getByRole("listitem")).toHaveCount(2);

  await shown(page.getByLabel("Moneda")).selectOption("VES");
  await shown(page.getByRole("button", { name: "Filtrar" })).click();
  await expect(page).toHaveURL(/moneda=VES/);
  await expect(
    shown(page.getByRole("list", { name: "Movimientos" })).getByRole("listitem"),
  ).toHaveCount(1);
  await expect(shown(page.getByRole("list", { name: "Movimientos" }))).toContainText("pasaje");

  await shown(page.getByRole("link", { name: "Limpiar" })).click();
  await expect(page).toHaveURL(/\/movimientos$/);
  await shown(page.getByRole("link", { name: "Editar almuerzo" })).click();
  await onPage(page, /\/movimientos\/editar\?id=/, "Editar movimiento");
  await expect(shown(page.getByText("«gasté 15 en el almuerzo»"))).toBeVisible();
  await shown(page.getByLabel("Monto")).fill("20");
  await shown(page.getByLabel("Categoría")).selectOption({ label: "ocio" });
  await shown(page.getByRole("button", { name: "Guardar cambios" })).click();

  await onPage(page, /\/movimientos\?editado=2$/, "Movimientos");
  await expect(shown(page.getByRole("status"))).toContainText("Movimiento corregido");
  const edited = shown(page.getByRole("listitem")).filter({ hasText: "almuerzo" });
  await expect(edited).toContainText("20,00");
  await expect(edited).toContainText("ocio");
  await expect(edited).toContainText("corregido");

  // Gráficas: las tres secciones y la caída del bolívar (0,0025 → 0,002 = −20 %).
  await nav(page, "Gráficas");
  await onPage(page, /\/graficas$/, "Gráficas");
  await expect(shown(page.getByRole("heading", { name: "Gasto por categoría" }))).toBeVisible();
  await expect(shown(page.getByRole("heading", { name: "Gasto por semana" }))).toBeVisible();
  await expect(shown(page.getByTestId("bolivar-change"))).toHaveText("-20 %");
  await shown(page.getByText("Ver datos").first()).click();
  await expect(shown(page.getByRole("cell", { name: "ocio" }))).toBeVisible();

  // Cambios: tasa efectiva contra referencia.
  await nav(page, "Cambios");
  await onPage(page, /\/cambios$/, "Cambios entre monedas");
  const exchange = shown(page.getByRole("list", { name: "Cambios" })).getByRole("listitem");
  await expect(exchange).toContainText("50,00 USDT → 49.250,00 Bs");
  await expect(exchange).toContainText("985,00 Bs por USDT");
  await expect(exchange).toContainText("-1,5 % en contra");
});
