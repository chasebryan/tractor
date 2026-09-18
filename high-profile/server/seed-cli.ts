import { openDatabase } from "./db.js";
import { seedDatabase } from "./seed.js";
const db = await openDatabase({
  url: process.env.DATABASE_URL,
  path: process.env.DATA_DIR,
});
try {
  await seedDatabase(db);
  console.log(
    "Seed complete (idempotent). Development reference collection only.",
  );
} finally {
  await db.close();
}
