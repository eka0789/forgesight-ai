/**
 * ForgeSight AI — README screenshot generator.
 *
 * Usage (app running on :3000/:8000 with demo seed):
 *   cd apps/web && npm i --no-save playwright-core
 *   node ../scripts/take_screenshots.mjs
 *
 * Uses the system Edge (channel "msedge"); falls back to bundled Chromium.
 * Screenshots land in docs/screenshots/.
 */
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const OUT = join(__dirname, "..", "docs", "screenshots");
mkdirSync(OUT, { recursive: true });

const BASE = "http://localhost:3000";

async function launch() {
  for (const opts of [{ channel: "msedge" }, { channel: "chrome" }, {}]) {
    try {
      return await chromium.launch({ headless: true, ...opts });
    } catch (e) {
      console.log(`launch failed (${JSON.stringify(opts)}): ${e.message.split("\n")[0]}`);
    }
  }
  throw new Error("No browser available for playwright");
}

const browser = await launch();
const page = await browser.newPage({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1.25,
});

const shot = async (name) => {
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log("saved", name);
};
const gotoApp = async (route, waitMs = 1600) => {
  await page.goto(BASE + route, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(waitMs);
};

// 1 — Login page (themed)
await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(900);
await shot("01-login");

// Login with demo credentials
await page.fill("#email", "admin@demo.forgesight.ai");
await page.fill("#password", "Demo1234!");
await page.click('button[type="submit"]');
await page.waitForURL("**/dashboard", { timeout: 20000 });
await page.waitForTimeout(2200);

// 2 — Dashboard
await shot("02-dashboard");

// 3 — Vision workspace (history incl. the real annotated inspection)
await gotoApp("/vision", 2000);
await shot("03-vision");

// 4 — Vision result dialog (annotated image + detections)
const viewBtn = page.getByRole("button", { name: "View" }).first();
await viewBtn.click();
await page.waitForTimeout(1500);
await shot("04-vision-result");
await page.getByRole("button", { name: "Close" }).click();
await page.waitForTimeout(400);

// 5 — Predictive maintenance
await gotoApp("/maintenance", 2000);
await shot("05-maintenance");

// 6 — Knowledge AI: ask a grounded question, wait for citations
await gotoApp("/knowledge", 1400);
const chatInput = page.locator('input[placeholder^="e.g."]');
await chatInput.fill("When must the cutting tool be replaced on CNC-01?");
await page.getByRole("button", { name: "Send" }).click();
await page.waitForTimeout(3500);
await shot("06-knowledge");

// 7 — AI Agent: run a tool-calling request
await gotoApp("/agent", 1400);
const agentInput = page.locator('input[placeholder^="Give the agent"]');
await agentInput.fill("what is the status of machine 1?");
await page.getByRole("button", { name: "Run" }).click();
await page.waitForTimeout(4000);
await shot("07-agent");

// 8 — ML Laboratory: run the RL scheduling sim
await gotoApp("/lab", 1600);
await page.getByRole("button", { name: "Run", exact: true }).first().click();
await page.waitForTimeout(1200);
await shot("08-lab");

// 9 — Model registry
await gotoApp("/models", 1600);
await shot("09-models");

// 10 — Monitoring (health + drift)
await gotoApp("/monitoring", 2200);
await shot("10-monitoring");

// 11 — Reports
await gotoApp("/reports", 1800);
await shot("11-reports");

// 12 — Settings (user management)
await gotoApp("/settings", 1600);
await shot("12-settings");

await browser.close();
console.log("ALL SCREENSHOTS DONE → docs/screenshots/");
