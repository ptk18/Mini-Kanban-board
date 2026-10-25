// Screenshot the provisioned Grafana dashboard for the docs.
//
//   cd frontend && node ../observability/screenshot.mjs ../docs/images/grafana-dashboard.png
//
// Runs from frontend/ so Playwright (a frontend dev dependency) resolves; the
// stack must be up (`make observe`) and ideally carrying some traffic.
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "package.json"));
const { chromium } = require("@playwright/test");

const out = process.argv[2] ?? "grafana-dashboard.png";
const url =
  process.argv[3] ??
  "http://localhost:3001/d/mini-kanban?orgId=1&from=now-30m&to=now&kiosk";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1250 } });
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(6000); // let every panel run its query and render
const panels = await page.locator("[data-testid^='data-testid Panel header']").count();
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log(`saved ${out}; ${panels} panel headers rendered`);
