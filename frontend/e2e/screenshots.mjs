// Screenshots of the app for the README, taken against a running, seeded
// stack (`make up && make seed`). Not a test; run by hand:
//
//   cd frontend && node e2e/screenshots.mjs ../docs/images
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const out = process.argv[2] ?? "../docs/images";
const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
const shot = async (name) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`saved ${name}.png`);
};

await page.goto(`${base}/login`);
await shot("login");
await page.getByLabel("Email").fill("ada@example.com");
await page.getByLabel("Password").fill("insurance-demo");
await page.getByRole("button", { name: "Log in" }).click();
await page.waitForURL(/\/boards$/);
await shot("boards");

await page.getByRole("link", { name: "Insurance Policy Automation" }).click();
await page.waitForURL(/\/boards\/\d+$/);
await page.getByLabel("Backlog", { exact: true }).waitFor();
await shot("board");

// Open a card's detail modal (every card title is a button titled "Open card").
await page.getByTitle("Open card").nth(2).click();
await page.getByRole("dialog").waitFor();
await shot("card-modal");
await page.keyboard.press("Escape");

await page.getByRole("link", { name: /dashboard/i }).click();
await page.waitForURL(/\/dashboard$/);
await page.getByText("Total tasks").waitFor();
await shot("dashboard");

await browser.close();
