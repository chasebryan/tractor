import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout } from "node:timers/promises";

const directory = await mkdtemp(join(tmpdir(), "high-profile-production-"));
const port = process.env.SMOKE_PORT ?? "4312";
const origin = `http://127.0.0.1:${port}`;
const token = randomUUID();
const { DATABASE_URL, REVIEW_TOKEN, PUBLIC_ORIGIN, ...environment } =
  process.env;
let log = "";
const server = spawn(process.execPath, ["--import", "tsx", "server/index.ts"], {
  env: {
    ...environment,
    NODE_ENV: "production",
    HOST: "127.0.0.1",
    PORT: port,
    DATA_DIR: join(directory, "postgres"),
    SEED_FIXTURES: "true",
    REVIEW_TOKEN: token,
  },
  stdio: ["ignore", "pipe", "pipe"],
});
for (const stream of [server.stdout, server.stderr])
  stream.on("data", (data) => {
    log = (log + data.toString()).slice(-12000);
  });
const checks = [];
try {
  let ready = false;
  for (let attempt = 0; attempt < 160; attempt++) {
    if (server.exitCode !== null) throw new Error(`Server exited: ${log}`);
    try {
      ready = (await fetch(`${origin}/api/health`)).ok;
    } catch {}
    if (ready) break;
    await setTimeout(250);
  }
  assert.ok(ready, `Startup timed out: ${log}`);
  checks.push("fresh production database and health");
  const page = await fetch(`${origin}/profiles/china-program`);
  assert.equal(page.status, 200);
  assert.match(
    page.headers.get("content-security-policy"),
    /script-src 'self'/,
  );
  const html = await page.text();
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^\"]+)"/g)].map(
    (m) => m[1],
  );
  assert.ok(assets.some((path) => path.endsWith(".js")));
  assert.ok(assets.some((path) => path.endsWith(".css")));
  for (const asset of assets)
    assert.equal((await fetch(origin + asset)).status, 200);
  checks.push("SPA deep link, production assets and CSP");
  const search = await (await fetch(`${origin}/api/search?q=China`)).json();
  assert.equal(search.total, 3);
  checks.push("seeded production search");
  const integrity = await (await fetch(`${origin}/api/integrity`)).json();
  assert.equal(integrity.ok, true);
  assert.equal(integrity.checks.length, 9);
  checks.push("nine data-integrity checks");
  assert.equal((await fetch(`${origin}/api/investigations`)).status, 401);
  assert.equal(
    (
      await fetch(`${origin}/api/review/claims`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      })
    ).status,
    401,
  );
  checks.push("private workspace and review authorization");
  const created = await fetch(`${origin}/api/investigations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      title: "Production smoke verification",
      description: "Disposable test workspace",
    }),
  });
  assert.equal(created.status, 201);
  const investigations = await (
    await fetch(`${origin}/api/investigations`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  assert.ok(
    investigations.items.some(
      (item) => item.title === "Production smoke verification",
    ),
  );
  checks.push("authorized production workspace write and read");
  assert.equal(
    (
      await fetch(`${origin}/api/investigations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "https://untrusted.example",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: "Rejected origin" }),
      })
    ).status,
    403,
  );
  checks.push("cross-origin write rejection");
  console.log(JSON.stringify({ ok: true, checks }, null, 2));
} finally {
  if (server.exitCode === null) {
    const closed = once(server, "close");
    server.kill("SIGINT");
    await closed;
  }
  await rm(directory, { recursive: true, force: true });
}
