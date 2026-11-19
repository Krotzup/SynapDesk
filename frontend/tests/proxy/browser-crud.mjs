// Edge instalado, formularios reales y checkpoints SQL independientes del navegador.
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import { randomBytes, randomUUID } from "node:crypto";
import { readRagResponse } from "./rag-result.mjs";
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE);
const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const result = {
  passed: false,
  channel: "msedge",
  executable:
    process.env.EDGE_EXECUTABLE_PATH ??
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  cases: [],
  network: [],
  tickets: [],
};
const secrets = config.accounts.map((a) => a.password);
let stage = "launch",
  browser,
  currentPage,
  sequence = 0;
function check(name, value) {
  result.cases.push({ name, passed: Boolean(value) });
  if (!value) throw new Error("Comprobación fallida: " + name);
}
async function checkpoint(account, ticket, phase) {
  const n = ++sequence;
  const requestPath = config.checkpointRequest + "." + n;
  const replyPath = config.checkpointReply + "." + n;
  const temporary = requestPath + ".new";
  fs.writeFileSync(
    temporary,
    JSON.stringify({
      sequence: n,
      phase,
      role: account.role,
      ticketId: ticket.id,
      title: ticket.title,
      description: ticket.description,
      status: ticket.status,
    })
  );
  fs.renameSync(temporary, requestPath);
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (fs.existsSync(replyPath)) {
      const reply = JSON.parse(fs.readFileSync(replyPath, "utf8"));
      if (reply.sequence === n) {
        check(account.role + "_sql_" + phase, reply.passed);
        return;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("SQL checkpoint timeout");
}
const raw = (path, headers = {}, method = "GET", body) =>
  new Promise((resolve, reject) => {
    const request = http.request(config.origin + path, { method, headers }, (response) => {
      let text = "";
      response.setEncoding("utf8");
      response.on("data", (part) => (text += part));
      response.on("end", () =>
        resolve({ status: response.statusCode, headers: response.headers, text })
      );
    });
    request.on("error", reject);
    request.end(body === undefined ? undefined : JSON.stringify(body));
  });
const responseFor = (page, path, method) =>
  page.waitForResponse(
    (r) => new URL(r.url()).pathname === path && r.request().method() === method,
    { timeout: 60000 }
  );
async function browserRequest(page, path, method, body, token) {
  return page.evaluate(
    async ({ path, method, body, token }) => {
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "X-CSRF-Token": token } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await response.text();
      return {
        status: response.status,
        data: JSON.parse(text),
        text,
        cache: response.headers.get("cache-control"),
      };
    },
    { path, method, body, token }
  );
}
try {
  browser = await chromium.launch({
    channel: "msedge",
    executablePath: result.executable,
    headless: true,
  });
  result.browser = browser.version();
  const privateCookies = [];
  const orderedAccounts = [...config.accounts].sort(
    (a, b) => Number(b.role === "admin") - Number(a.role === "admin")
  );
  for (const account of orderedAccounts) {
    const role = account.role;
    stage = role + "_login";
    const context = await browser.newContext();
    const page = (currentPage = await context.newPage());
    page.setDefaultTimeout(45000);
    const errors = [],
      writes = [];
    let passwordInUrl = false;
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (request) => {
      const path = new URL(request.url()).pathname;
      if (path === "/api/v1/tickets" && request.method() === "POST") writes.push(path);
      passwordInUrl ||= request.url().includes("password=");
    });
    page.on("response", (response) => {
      const path = new URL(response.url()).pathname;
      if (path.startsWith("/api/"))
        result.network.push({
          role,
          path,
          method: response.request().method(),
          status: response.status(),
        });
    });
    await page.goto(config.origin + "/login", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Iniciar sesión", exact: true }).waitFor();
    await page.waitForFunction(() => !document.querySelector('button[type="submit"]')?.disabled);
    await page.getByLabel("Correo electrónico", { exact: true }).fill(account.email);
    await page.getByLabel("Contraseña", { exact: true }).fill(account.password);
    const csrfResponse = responseFor(page, "/api/local/csrf", "POST");
    const loginResponse = responseFor(page, "/api/v1/auth/login", "POST");
    await page.getByRole("button", { name: "Iniciar sesión", exact: true }).click();
    check(role + "_csrf_before_login", (await csrfResponse).status() === 200);
    const login = await loginResponse;
    check(role + "_login_browser", login.status() === 200);
    const me = await browserRequest(page, "/api/v1/auth/me", "GET");
    check(role + "_me_persisted_session", me.status === 200 && me.data.user.role === role);
    await page.goto(config.origin + "/tickets?status=open", { waitUntil: "domcontentloaded" });
    await page.locator("#ticket-status").waitFor();
    check(
      role + "_filters_enabled",
      (await page.locator("#ticket-status").isEnabled()) &&
        (await page.locator("#ticket-priority").isEnabled()) &&
        (await page.locator("#ticket-status").inputValue()) === "open"
    );
    await page.goto(config.origin + "/tickets", { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Gestión de tickets", exact: true }).waitFor();
    if (config.searchEnabled) {
      stage = role + "_search";
      const searched = responseFor(page, "/api/v1/search", "POST");
      await page.goto(
        config.origin + "/busqueda?q=" + encodeURIComponent("Comprobar DNS en Windows"),
        { waitUntil: "domcontentloaded" }
      );
      const response = await searched;
      const payload = await response.json();
      check(role + "_search_authenticated", response.status() === 200);
      check(role + "_search_no_store", response.headers()["cache-control"] === "no-store");
      check(
        role + "_search_contract",
        ["results", "no_documents", "insufficient_information"].includes(payload.status) &&
          Array.isArray(payload.items)
      );
      if (config.searchMode === "fixture") {
        check(
          role + "_search_fixture_result",
          payload.status === "results" && payload.items.length > 0
        );
        await page
          .getByRole("heading", { name: `📑 ${payload.items[0].title}`, exact: true })
          .first()
          .waitFor();
        check(
          role + "_search_source_visible",
          payload.status === "results" && payload.items.length > 0
        );
      }
    }
    stage = role + "_new_ticket_page";
    const newPage = await page.goto(config.origin + "/tickets/nuevo", {
      waitUntil: "domcontentloaded",
    });
    check(role + "_new_ticket_page", newPage.status() === 200);
    const title =
      config.ragEnabled && role === "agent"
        ? "Consultas DNS expiran en Windows"
        : "MVP09 " + role + " " + randomUUID();
    const description =
      config.ragEnabled && role === "agent"
        ? "Las consultas DNS expiran; necesito comprobar el servidor configurado y el archivo hosts."
        : "Creación desde formulario en Edge real; comprobación de commit y cambio de estado en PostgreSQL.";
    await page.getByLabel("Título", { exact: true }).fill(title);
    await page.getByLabel("Descripción", { exact: true }).fill(description);
    stage = role + "_create";
    const createResponse = responseFor(page, "/api/v1/tickets", "POST");
    await page.getByRole("button", { name: "Crear ticket", exact: true }).click();
    const creation = await createResponse;
    check(role + "_create_browser_http201", creation.status() === 201);
    const ticket = await creation.json();
    check(
      role + "_created_data",
      ticket.title === title &&
        ticket.description === description &&
        ticket.status === "open" &&
        ticket.createdBy.id === account.id
    );
    check(role + "_single_submit", writes.length === 1);
    check(role + "_create_no_store", creation.headers()["cache-control"] === "no-store");
    await checkpoint(account, ticket, "created");
    result.tickets.push({ role, id: ticket.id, title, status: ticket.status });
    await page.getByRole("heading", { name: ticket.title, exact: true }).waitFor();
    check(role + "_detail_navigation", new URL(page.url()).pathname === "/tickets/" + ticket.id);
    stage = role + "_list_detail";
    await page.getByRole("link", { name: "← Volver a tickets", exact: true }).click();
    await page.getByRole("link", { name: title, exact: true }).first().waitFor();
    check(role + "_list_browser", true);
    const pagination = page.getByRole("navigation", { name: "Paginación de tickets" });
    await pagination.getByRole("link", { name: "Siguiente →", exact: true }).click();
    await pagination.getByText("Página 2 de 2", { exact: true }).waitFor();
    check(role + "_list_second_page", new URL(page.url()).searchParams.get("page") === "2");
    await pagination.getByRole("link", { name: "← Anterior", exact: true }).click();
    await page.getByRole("link", { name: title, exact: true }).first().waitFor();
    const huge = "1" + "0".repeat(80);
    const extreme = await browserRequest(
      page,
      "/api/v1/tickets?page=" + huge + "&pageSize=100",
      "GET"
    );
    check(
      role + "_extreme_page_no_503",
      extreme.status === 200 &&
        extreme.data.items.length === 0 &&
        extreme.data.totalItems === config.tickets.length + result.tickets.length &&
        extreme.data.totalPages === 1 &&
        extreme.data.pageSize === 100 &&
        new RegExp('"page":\\s*' + huge + "(?:,|})").test(extreme.text)
    );
    await page.getByRole("link", { name: title, exact: true }).first().click();
    await page.getByRole("heading", { name: title, exact: true }).waitFor();
    check(role + "_detail_browser", await page.getByText(description, { exact: true }).isVisible());
    if (config.ragEnabled) {
      await page.getByText("Aún no hay recomendaciones para este ticket.").waitFor();
      check(role + "_recommendations_loaded", true);
      if (role === "agent") {
        stage = role + "_rag_generate";
        const ragPath = `/api/v1/tickets/${ticket.id}/recommendations`;
        const generationResponse = responseFor(page, ragPath, "POST");
        await page.getByRole("button", { name: "Generar recomendación" }).click();
        const generated = await generationResponse;
        const { payload, summary, validContract } = await readRagResponse(generated, config);
        result.rag = summary;
        check(role + "_rag_generation_contract", validContract);
        check(
          role + "_rag_generation_no_store",
          generated.headers()["cache-control"] === "no-store"
        );
        if (summary.outcome === "abstention") {
          await page
            .getByRole("alert")
            .filter({
              hasText:
                "La documentación recuperada no alcanza para generar una recomendación fundamentada.",
            })
            .waitFor();
          const listed = await browserRequest(page, ragPath, "GET");
          check(
            role + "_rag_abstention_empty_list",
            listed.status === 200 && listed.data.length === 0
          );
          await checkpoint(account, ticket, "recommendation_abstained");
          await page.reload({ waitUntil: "domcontentloaded" });
          await page.getByText("Aún no hay recomendaciones para este ticket.").waitFor();
          check(role + "_rag_abstention_persisted_in_ui", true);
        } else {
          check(role + "_rag_generation_http201", generated.status() === 201);
          const draft = payload;
          check(
            role + "_rag_draft_with_sources",
            draft.status === "pending" &&
              typeof draft.content === "string" &&
              draft.content.trim().length > 0 &&
              Array.isArray(draft.sources) &&
              draft.sources.length > 0 &&
              draft.ticketId === ticket.id
          );
          // La interfaz transforma las referencias UUID del texto en enlaces a fuentes.
          const sourceLink = page.getByRole("link", {
            name: `Consultar fuente 1: ${draft.sources[0].title}`,
            exact: true,
          });
          await sourceLink.waitFor();
          await sourceLink.click();
          const sourceDetails = page.locator(
            `#source-${draft.id}-${draft.sources[0].documentChunkId}`
          );
          check(role + "_rag_source_opened", await sourceDetails.getAttribute("open") !== null);
          stage = role + "_rag_review";
          const reviewResponse = responseFor(
            page,
            `/api/v1/recommendations/${draft.id}/reviews`,
            "POST"
          );
          await page.getByRole("button", { name: /Aceptar recomendación/ }).click();
          check(role + "_rag_review_http204", (await reviewResponse).status() === 204);
          await page.getByText("La recomendación fue aceptada.").waitFor();
          await checkpoint(account, ticket, "recommendation_accepted");
          await page.reload({ waitUntil: "domcontentloaded" });
          await page.getByText("La recomendación fue aceptada.").waitFor();
          check(role + "_rag_review_persisted_in_ui", true);
          result.rag.reviewVerified = true;
        }
        check(
          role + "_rag_expected_outcome",
          result.rag.expectedOutcome === "either" ||
            result.rag.expectedOutcome === result.rag.outcome
        );
      }
    } else {
      const optionalRecommendations = page.getByRole("alert").filter({
        hasText: "No se pudieron cargar las recomendaciones del ticket.",
      });
      await optionalRecommendations.waitFor();
      check(
        role + "_optional_recommendations_do_not_block",
        await optionalRecommendations.isVisible()
      );
    }
    stage = role + "_status";
    const target = role === "agent" ? "in_progress" : "resolved";
    await page.getByLabel("Cambiar estado", { exact: true }).selectOption(target);
    const updateResponse = responseFor(page, "/api/v1/tickets/" + ticket.id, "PATCH");
    await page.getByRole("button", { name: "Guardar estado", exact: true }).click();
    const update = await updateResponse;
    check(role + "_status_browser_http200", update.status() === 200);
    const saved = await update.json();
    check(
      role + "_status_only",
      saved.status === target && saved.title === title && saved.description === description
    );
    await page.getByText(/^Estado actualizado a/).waitFor();
    ticket.status = target;
    await checkpoint(account, ticket, "updated");
    stage = role + "_reload";
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: title, exact: true }).waitFor();
    check(
      role + "_reload_persistence",
      (await page.getByLabel("Cambiar estado", { exact: true }).inputValue()) === target
    );
    await checkpoint(account, ticket, "reloaded");
    await page.screenshot({
      path: config.screenshotBase + "-" + role + "-detail.png",
      fullPage: true,
    });
    result.tickets.at(-1).status = target;
    stage = role + "_security";
    const tokenResponse = await browserRequest(page, "/api/local/csrf", "POST");
    check(role + "_session_csrf", tokenResponse.status === 200);
    let token = tokenResponse.data.csrfToken;
    secrets.push(token);
    const invalidState = await browserRequest(
      page,
      "/api/v1/tickets/" + ticket.id,
      "PATCH",
      { status: "invalid" },
      token
    );
    check(role + "_invalid_state", invalidState.status === 422);
    const invalidCsrf = await browserRequest(
      page,
      "/api/v1/tickets/" + ticket.id,
      "PATCH",
      { status: "closed" },
      randomBytes(32).toString("base64url")
    );
    check(
      role + "_invalid_csrf",
      invalidCsrf.status === 403 && invalidCsrf.data.error.code === "CSRF_INVALID"
    );
    const extras = await browserRequest(
      page,
      "/api/v1/tickets/" + ticket.id,
      "PATCH",
      { status: "closed", title: "No modificar" },
      token
    );
    check(role + "_reject_unrelated_field", extras.status === 422);
    const cookies = await context.cookies();
    secrets.push(...cookies.map((c) => c.value));
    let cookie = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    privateCookies.push({ role, cookie });
    const headers = {
      Cookie: cookie,
      Origin: config.origin,
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
    };
    const path = "/api/v1/tickets/" + ticket.id;
    check(
      role + "_invalid_origin",
      (
        await raw(path, { ...headers, Origin: "https://ajeno.invalid" }, "PATCH", {
          status: "closed",
        })
      ).status === 403
    );
    check(
      role + "_invalid_cookie_nbsp",
      (await raw(path, { ...headers, Cookie: cookie + "\u00a0" }, "PATCH", { status: "closed" }))
        .status === 503
    );
    check(role + "_anonymous_read", (await raw(path)).status === 401);
    check(
      role + "_anonymous_create",
      (
        await raw(
          "/api/v1/tickets",
          { Origin: config.origin, "Content-Type": "application/json" },
          "POST",
          { title, description }
        )
      ).status === 401
    );
    await checkpoint(account, ticket, "negative_unchanged");
    stage = role + "_logout";
    const invalidLogout = await browserRequest(
      page,
      "/api/v1/auth/logout",
      "POST",
      {},
      randomBytes(32).toString("base64url")
    );
    check(role + "_logout_invalid_csrf", invalidLogout.status === 403);
    check(
      role + "_logout_rejection_keeps_session",
      (await browserRequest(page, "/api/v1/auth/me", "GET")).status === 200
    );
    await page
      .getByRole("button", { name: "Menú de usuario: " + account.email, exact: true })
      .click();
    const logoutResponse = responseFor(page, "/api/v1/auth/logout", "POST");
    await page.getByRole("button", { name: "Cerrar sesión", exact: true }).click();
    check(role + "_logout_browser_http204", (await logoutResponse).status() === 204);
    await page.waitForURL(config.origin + "/login");
    check(
      role + "_logout_cookie_removed",
      !(await context.cookies()).some((c) => c.name === "synapdesk_session_dev")
    );
    check(
      role + "_logout_me_rejected",
      (await browserRequest(page, "/api/v1/auth/me", "GET")).status === 401
    );
    check(
      role + "_logout_old_cookie_rejected",
      (await raw("/api/v1/auth/me", { Cookie: cookie })).status === 401
    );
    await checkpoint(account, ticket, "logged_out");

    // Segunda sesión HTTP para probar revocación/inactividad sin confundirlas con logout.
    stage = role + "_security_relogin";
    await page.waitForFunction(() => !document.querySelector('button[type="submit"]')?.disabled);
    await page.getByLabel("Correo electrónico", { exact: true }).fill(account.email);
    await page.getByLabel("Contraseña", { exact: true }).fill(account.password);
    const reloginResponse = responseFor(page, "/api/v1/auth/login", "POST");
    await page.getByRole("button", { name: "Iniciar sesión", exact: true }).click();
    check(role + "_security_relogin_http200", (await reloginResponse).status() === 200);
    check(
      role + "_security_relogin_me",
      (await browserRequest(page, "/api/v1/auth/me", "GET")).data.user.role === role
    );
    const freshCsrf = await browserRequest(page, "/api/local/csrf", "POST");
    check(role + "_security_relogin_csrf", freshCsrf.status === 200);
    token = freshCsrf.data.csrfToken;
    const freshCookies = await context.cookies();
    secrets.push(token, ...freshCookies.map((c) => c.value));
    cookie = freshCookies.map((c) => `${c.name}=${c.value}`).join("; ");
    privateCookies.at(-1).cookie = cookie;
    await page.goto(config.origin + "/tickets/" + ticket.id, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: title, exact: true }).waitFor();
    await checkpoint(account, ticket, role === "agent" ? "revoke" : "deactivate");
    const rejectedWrite = await browserRequest(page, path, "PATCH", { status: "closed" }, token);
    check(
      role + "_" + (role === "agent" ? "revoked_session" : "inactive_account") + "_write",
      rejectedWrite.status === 401
    );
    check(
      role + "_revoked_or_inactive_read",
      (await browserRequest(page, path, "GET")).status === 401
    );
    await checkpoint(account, ticket, "negative_unchanged");
    check(role + "_no_js_errors", errors.length === 0);
    check(role + "_no_password_in_urls", !passwordInUrl);
    check(role + "_no_secret_in_errors", !secrets.some((s) => s && errors.join("\n").includes(s)));
    await context.close();
  }
  fs.writeFileSync(config.privateCookies, JSON.stringify(privateCookies), { mode: 0o600 });
  result.passed = true;
} catch (error) {
  result.failure_stage = stage;
  result.error_type = error.name;
  result.error_message = secrets
    .reduce(
      (message, secret) => (secret ? message.split(secret).join("[redacted]") : message),
      String(error.message)
    )
    .slice(0, 1000);
  if (currentPage && !currentPage.isClosed())
    await currentPage
      .screenshot({ path: config.screenshotBase + "-failure.png", fullPage: true })
      .catch(() => {});
} finally {
  await browser?.close();
  fs.writeFileSync(config.output, JSON.stringify(result, null, 2));
}
process.exit(result.passed ? 0 : 1);
