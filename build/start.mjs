import path from "node:path";

// vinext's static-file cache keys are URL paths, but path.relative() returns
// Windows separators. Normalize it before vinext scans dist/client so cached
// asset requests (/assets/...) match the keys it creates on Windows.
const relative = path.relative;
path.relative = (...args) => relative(...args).replaceAll("\\", "/");

const { startProdServer } = await import("vinext/server/prod-server");

const args = process.argv.slice(2);
const portIndex = args.findIndex((arg) => arg === "--port" || arg === "-p");
const hostIndex = args.findIndex((arg) => arg === "--hostname" || arg === "-H");
const port = portIndex >= 0 ? Number(args[portIndex + 1]) : Number(process.env.PORT ?? 3000);
const host = hostIndex >= 0 ? args[hostIndex + 1] : "0.0.0.0";

await startProdServer({
  port,
  host,
  outDir: path.resolve(process.cwd(), "dist"),
});
