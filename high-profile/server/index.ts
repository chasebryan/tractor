import { createServer } from "node:http";
import { resolve } from "node:path";
import express from "express";
import { openDatabase } from "./db.js";
import { seedDatabase } from "./seed.js";
import { createApp } from "./app.js";
const production = process.env.NODE_ENV === "production";
const host = process.env.HOST ?? "127.0.0.1";
if (!production && !["127.0.0.1", "localhost", "::1"].includes(host))
  throw new Error(
    "Development mode binds only to loopback. Use production mode for external access.",
  );
if (production && !process.env.DATABASE_URL)
  console.warn(
    JSON.stringify({
      event: "embedded_database",
      message:
        "Single-process local production preview. Use DATABASE_URL for deployed PostgreSQL.",
    }),
  );
const db = await openDatabase({
  url: process.env.DATABASE_URL,
  path: process.env.DATA_DIR,
});
if (
  process.env.SEED_FIXTURES === "true" ||
  (!production && process.env.SEED_FIXTURES !== "false")
)
  await seedDatabase(db);
const app = createApp(db, {
  production,
  reviewToken: process.env.REVIEW_TOKEN,
});
const server = createServer(app);
if (production) {
  app.use(express.static(resolve("dist"), { index: false, maxAge: "1h" }));
  app.get("/{*path}", (req, res) => {
    if (req.path.includes(".")) return res.status(404).send("Not found");
    res.sendFile(resolve("dist/index.html"));
  });
} else {
  const { createServer: createViteServer } = await import("vite");
  const vite = await createViteServer({
    server: { middlewareMode: true, hmr: { server } },
    appType: "spa",
  });
  app.use(vite.middlewares);
}
server.listen(Number(process.env.PORT ?? 4310), host, () =>
  console.log(
    JSON.stringify({
      event: "server_started",
      url: `http://${host}:${process.env.PORT ?? 4310}`,
      mode: production ? "production" : "development",
    }),
  ),
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => {
    server.close(async () => {
      await db.close();
      process.exit(0);
    });
  });
