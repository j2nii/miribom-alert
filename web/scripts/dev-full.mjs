import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const commands = [
  ["웹", path.join(webDir, "node_modules", "vite", "bin", "vite.js"), process.argv.slice(2)],
  ["질의 API", path.join(webDir, "dev-server.mjs")],
];

let stopping = false;
const children = commands.map(([name, entry, args = []]) => {
  const child = spawn(process.execPath, [entry, ...args], { cwd: webDir, stdio: "inherit" });
  child.on("error", (error) => {
    console.error(`[${name}] 실행 실패: ${error.message}`);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) {
      console.error(`[${name}] 종료되었습니다 (코드 ${code ?? "없음"}).`);
      stop(code || 1);
    }
  });
  return child;
});

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode === null) child.kill();
  }
  process.exitCode = code;
}

process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());

console.log("웹과 질의 API를 시작합니다. 아래 Vite 주소를 브라우저에서 여세요.");
