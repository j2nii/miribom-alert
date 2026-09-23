import mysql from "mysql2/promise";

// Module-scope pool so warm serverless invocations reuse the same
// connections instead of opening a fresh one per request. The account is
// SELECT/SHOW VIEW only (docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf)
// -- this module never writes.
let pool;

export function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      host: process.env.MYSQL_HOST,
      port: Number(process.env.MYSQL_PORT || 3306),
      user: process.env.MYSQL_USER,
      password: process.env.MYSQL_PASSWORD,
      database: process.env.MYSQL_DATABASE,
      // The server requires SSL (SSL Mode: Require) -- without this option
      // the connection fails with ER_ACCESS_DENIED_ERROR even with correct
      // credentials, not a clearer TLS error.
      ssl: process.env.MYSQL_SSL === "true" ? { rejectUnauthorized: false } : undefined,
      connectionLimit: 5,
    });
  }
  return pool;
}
