#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

function parseArgs(argv) {
  const out = {
    force: false,
    target: null,
    name: "feishu-remote-mcp",
    dryRun: false
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--force") {
      out.force = true;
      continue;
    }
    if (arg === "--dry-run") {
      out.dryRun = true;
      continue;
    }
    if (arg === "--target") {
      out.target = argv[i + 1] || null;
      i += 1;
      continue;
    }
    if (arg === "--name") {
      out.name = argv[i + 1] || out.name;
      i += 1;
      continue;
    }
    if (arg === "-h" || arg === "--help") {
      out.help = true;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }
  return out;
}

function printHelp() {
  const help = `
install-feishu-remote-mcp-skill

Install feishu-remote-mcp skill into local Codex skills folder.

Usage:
  install-feishu-remote-mcp-skill [--target <path>] [--name <skillName>] [--force] [--dry-run]

Options:
  --target   Install root path. Default: $CODEX_HOME/skills or ~/.codex/skills
  --name     Target skill folder name. Default: feishu-remote-mcp
  --force    Overwrite if destination already exists
  --dry-run  Print actions without writing files
`;
  process.stdout.write(help.trimStart() + "\n");
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyFile(src, dst) {
  ensureDir(path.dirname(dst));
  fs.copyFileSync(src, dst);
}

function shouldSkip(relativePath) {
  const normalized = relativePath.replace(/\\/g, "/");
  if (normalized.includes("/config/") || normalized.startsWith("config/")) {
    return true;
  }
  if (normalized.includes("/__pycache__/") || normalized.endsWith(".pyc")) {
    return true;
  }
  return false;
}

function copyDir(srcRoot, dstRoot, rel = "") {
  const src = path.join(srcRoot, rel);
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const childRel = rel ? path.join(rel, entry.name) : entry.name;
    if (shouldSkip(childRel)) {
      continue;
    }
    const childSrc = path.join(srcRoot, childRel);
    const childDst = path.join(dstRoot, childRel);
    if (entry.isDirectory()) {
      ensureDir(childDst);
      copyDir(srcRoot, dstRoot, childRel);
      continue;
    }
    if (entry.isFile()) {
      copyFile(childSrc, childDst);
    }
  }
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    process.stderr.write(`[error] ${err.message}\n`);
    process.exit(2);
  }

  if (args.help) {
    printHelp();
    return;
  }

  const pkgRoot = path.resolve(__dirname, "..");
  const skillSrc = path.join(pkgRoot, "feishu-remote-mcp");
  if (!fs.existsSync(skillSrc)) {
    process.stderr.write(`[error] skill source not found: ${skillSrc}\n`);
    process.exit(2);
  }

  const defaultRoot = process.env.CODEX_HOME
    ? path.join(process.env.CODEX_HOME, "skills")
    : path.join(os.homedir(), ".codex", "skills");
  const targetRoot = path.resolve(args.target || defaultRoot);
  const skillDst = path.join(targetRoot, args.name);

  const exists = fs.existsSync(skillDst);
  if (exists && !args.force) {
    process.stderr.write(`[error] destination exists: ${skillDst}\n`);
    process.stderr.write("Use --force to overwrite.\n");
    process.exit(1);
  }

  const actions = {
    packageRoot: pkgRoot,
    skillSource: skillSrc,
    targetRoot,
    skillDestination: skillDst,
    force: args.force,
    dryRun: args.dryRun
  };

  if (args.dryRun) {
    process.stdout.write(JSON.stringify(actions, null, 2) + "\n");
    return;
  }

  ensureDir(targetRoot);
  if (exists) {
    fs.rmSync(skillDst, { recursive: true, force: true });
  }
  ensureDir(skillDst);

  copyFile(path.join(skillSrc, "SKILL.md"), path.join(skillDst, "SKILL.md"));
  if (fs.existsSync(path.join(skillSrc, "agents"))) {
    copyDir(path.join(skillSrc, "agents"), path.join(skillDst, "agents"));
  }
  if (fs.existsSync(path.join(skillSrc, "references"))) {
    copyDir(path.join(skillSrc, "references"), path.join(skillDst, "references"));
  }
  if (fs.existsSync(path.join(skillSrc, "scripts"))) {
    copyDir(path.join(skillSrc, "scripts"), path.join(skillDst, "scripts"));
  }

  process.stdout.write(
    JSON.stringify(
      {
        ok: true,
        installedSkill: skillDst,
        note: "Install completed. Restart agent session if needed to re-index skills."
      },
      null,
      2
    ) + "\n"
  );
}

main();
