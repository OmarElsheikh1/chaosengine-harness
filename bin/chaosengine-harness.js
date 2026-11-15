#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const installPy = fs.realpathSync(path.join(__dirname, "..", "install.py"));
const result = spawnSync("python3", [installPy, ...process.argv.slice(2)], {
  stdio: "inherit",
});
process.exit(result.status === null ? 1 : result.status);
