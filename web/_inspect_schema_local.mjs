import mysql from "mysql2/promise";

const conn = await mysql.createConnection({
  host: process.env.MYSQL_HOST,
  port: Number(process.env.MYSQL_PORT || 3306),
  user: process.env.MYSQL_USER,
  password: process.env.MYSQL_PASSWORD,
  database: process.env.MYSQL_DATABASE,
  ssl: { rejectUnauthorized: false },
});

const [ytRegions] = await conn.query(`
  SELECT y.region_id, d.region_name, COUNT(*) AS video_count
  FROM youtube_video y LEFT JOIN dim_region d ON d.region_id = y.region_id
  GROUP BY y.region_id, d.region_name
  ORDER BY video_count DESC
`);
console.log("--- youtube_video regions ---");
console.table(ytRegions);

const [srcCheck] = await conn.query(`
  SELECT region_id, source_region_id, COUNT(*) AS c
  FROM fact_signal
  WHERE region_id <> source_region_id
  GROUP BY region_id, source_region_id
  LIMIT 20
`);
console.log("--- fact_signal region_id != source_region_id ---");
console.table(srcCheck);

const [srcSame] = await conn.query(`SELECT COUNT(*) AS same_count FROM fact_signal WHERE region_id = source_region_id`);
const [srcDiff] = await conn.query(`SELECT COUNT(*) AS diff_count FROM fact_signal WHERE region_id <> source_region_id`);
console.log("same:", srcSame[0].same_count, "diff:", srcDiff[0].diff_count);

const [geojeCheck] = await conn.query(`SELECT region_id, region_name FROM dim_region WHERE region_name LIKE '%거제%'`);
console.log("--- 거제 in dim_region ---");
console.table(geojeCheck);

const [chungjuCheck] = await conn.query(`SELECT region_id, region_name FROM dim_region WHERE region_name LIKE '%충주%'`);
console.log("--- 충주 in dim_region ---");
console.table(chungjuCheck);

await conn.end();
