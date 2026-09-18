import { PGlite } from "@electric-sql/pglite";
import pg from "pg";
import { readFile, mkdir, readdir, open, unlink } from "node:fs/promises";
import { resolve, dirname } from "node:path";

export type Row = Record<string, any>;
export interface Database {
  query(sql: string, params?: any[]): Promise<{ rows: Row[] }>;
  exec(sql: string): Promise<unknown>;
  transaction<T>(fn: (tx: Database) => Promise<T>): Promise<T>;
  close(): Promise<void>;
}
export async function openDatabase(
  options: { url?: string; path?: string; memory?: boolean } = {},
): Promise<Database> {
  let db: Database;
  if (options.url) {
    const pool = new pg.Pool({
      connectionString: options.url,
      max: 10,
      connectionTimeoutMillis: 10000,
      statement_timeout: 10000,
    });
    const wrap = (client: pg.Pool | pg.PoolClient): Database => ({
      query: async (sql, params) => await client.query(sql, params),
      exec: (sql) => client.query(sql),
      close: () => pool.end(),
      transaction: async (fn) => {
        const c = await pool.connect();
        try {
          await c.query("BEGIN");
          const result = await fn(wrap(c));
          await c.query("COMMIT");
          return result;
        } catch (e) {
          await c.query("ROLLBACK");
          throw e;
        } finally {
          c.release();
        }
      },
    });
    db = wrap(pool);
  } else {
    const path = resolve(options.path ?? ".data/postgres");
    if (!options.memory) await mkdir(dirname(path), { recursive: true });
    let lockPath: string | undefined;
    if (!options.memory) {
      lockPath = path + ".lock";
      try {
        const lock = await open(lockPath, "wx", 0o600);
        await lock.writeFile(String(process.pid));
        await lock.close();
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "EEXIST")
          throw new Error(
            `Embedded database is already in use or has a stale lock: ${lockPath}. Stop its owner before opening another process. For concurrent access use DATABASE_URL.`,
          );
        throw error;
      }
    }
    const pglite = new PGlite(options.memory ? undefined : path);
    await pglite.waitReady;
    const wrap = (client: any): Database => ({
      query: (s, p) => client.query(s, p),
      exec: (s) => client.exec(s),
      close: async () => {
        await pglite.close();
        if (lockPath) await unlink(lockPath);
      },
      transaction: (fn) => client.transaction((tx: any) => fn(wrap(tx))),
    });
    db = wrap(pglite);
  }
  const { rows } = await db.query(
    "SELECT to_regclass('public.schema_migrations') AS present",
  );
  if (!rows[0].present) {
    await db.transaction(async (tx) => {
      await tx.exec(
        await readFile(
          new URL("./migrations/001_index.sql", import.meta.url),
          "utf8",
        ),
      );
    });
  }
  const current = (
    await db.query("SELECT max(version) AS version FROM schema_migrations")
  ).rows[0].version;
  for (const file of (await readdir(new URL("./migrations/", import.meta.url)))
    .filter((f) => /^\d+.*\.sql$/.test(f))
    .sort()) {
    const version = Number(file.split("_")[0]);
    if (version <= current) continue;
    await db.transaction(async (tx) => {
      await tx.exec(
        await readFile(
          new URL(`./migrations/${file}`, import.meta.url),
          "utf8",
        ),
      );
      await tx.query("INSERT INTO schema_migrations(version) VALUES($1)", [
        version,
      ]);
    });
  }
  return db;
}
