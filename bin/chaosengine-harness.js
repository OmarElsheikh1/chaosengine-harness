#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const installPy = fs.realpathSync(path.join(root, "install.py"));
const bootstrapPy = fs.realpathSync(path.join(root, "bootstrap.py"));
const commands = new Set([
  "install",
  "status",
  "doctor",
  "rollback",
  "uninstall",
  "repair",
  "addons",
  "init",
  "upgrade",
  "bundle",
  "cache",
  "explain",
  "verify",
  "restore-edits",
]);

function pythonOk(command, prefix) {
  const probe = spawnSync(
    command,
    [...prefix, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
    { encoding: "utf8" },
  );
  return probe.status === 0;
}

function findPython() {
  if (pythonOk("python3", [])) return ["python3"];
  if (pythonOk("python", [])) return ["python"];
  if (pythonOk("py", ["-3"])) return ["py", "-3"];
  return null;
}

const argv = process.argv.slice(2);
const useInstaller = argv.length > 0 && commands.has(argv[0]);
const target = useInstaller ? installPy : bootstrapPy;
let args = argv.slice();
if (!useInstaller) {
  if (!args.includes("--repository")) {
    args.push("--repository", "ShaftHQ/chaosengine-harness");
  }
  if (!args.includes("--project")) {
    args.push("--project", process.cwd());
  }
}
const python = findPython();
if (python === null) {
  console.error(
    "ChaosEngine requires Python 3.11 or newer. fix-next: install Python 3.11+ or the Windows py launcher.",
  );
  process.exit(1);
}
const result = spawnSync(python[0], [...python.slice(1), target, ...args], {
  stdio: "inherit",
});
process.exit(result.status === null ? 1 : result.status);
