import { cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const standaloneRoot = path.join(projectRoot, ".next", "standalone");
const standaloneNextRoot = path.join(standaloneRoot, ".next");

await mkdir(standaloneNextRoot, { recursive: true });

const publicSource = path.join(projectRoot, "public");
const publicTarget = path.join(standaloneRoot, "public");
await rm(publicTarget, { recursive: true, force: true });
await cp(publicSource, publicTarget, { recursive: true });

const staticSource = path.join(projectRoot, ".next", "static");
const staticTarget = path.join(standaloneNextRoot, "static");
await rm(staticTarget, { recursive: true, force: true });
await cp(staticSource, staticTarget, { recursive: true });
