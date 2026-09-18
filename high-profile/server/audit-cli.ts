import { openDatabase } from "./db.js";
import { auditDatabase } from "./audit.js";
const db = await openDatabase({
  url: process.env.DATABASE_URL,
  path: process.env.DATA_DIR,
});
try {
  const r = await auditDatabase(db);
  console.log(JSON.stringify(r, null, 2));
  if (!r.ok) process.exitCode = 1;
} finally {
  await db.close();
}
