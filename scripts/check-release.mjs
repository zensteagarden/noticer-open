// SPDX-License-Identifier: Apache-2.0
import { spawnSync } from "node:child_process";

if (Number(process.versions.node.split(".")[0]) !== 24) {
  console.error(`RELEASE_CHECK: NOT_RUN. Node 24 is required; found ${process.version}.`);
  process.exitCode = 2;
} else {
  const run = spawnSync(process.execPath, ["--test"], { stdio: "inherit", shell: false });
  process.exitCode = run.error || run.status === null ? 1 : run.status;
  console.log("This checks the local test suite only. It does not publish, deploy, authorize actions, or certify security.");
}
