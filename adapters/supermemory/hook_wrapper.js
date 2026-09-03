/*
 * AMB's only wrapper around the official Supermemory hook.
 * It preserves stdin, stdout, stderr, exit status, and the vendor script itself, while recording
 * enough evidence for the admission gate to distinguish a loaded hook from a missing hook.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

const event = process.argv[2];
const target = process.argv[3];
const ledger = process.env.SUPERMEMORY_HOOK_LEDGER;
const home = process.env.SUPERMEMORY_HOOK_HOME;

if (!event || !target || !ledger) {
  process.stderr.write('Supermemory hook wrapper needs event, target, and ledger\n');
  process.exit(64);
}

let input = '';
try {
  input = fs.readFileSync(0, 'utf8');
} catch (error) {
  process.stderr.write(`Could not read hook input: ${error.message}\n`);
}

const childEnv = { ...process.env };
if (home) {
  childEnv.HOME = home;
  childEnv.USERPROFILE = home;
}

const started = performance.now();
const result = spawnSync(process.execPath, [target], {
  input,
  encoding: 'utf8',
  env: childEnv,
  windowsHide: true,
  maxBuffer: 10 * 1024 * 1024,
});
const stdout = result.stdout || '';
const stderr = result.stderr || '';
if (stdout) process.stdout.write(stdout);
if (stderr) process.stderr.write(stderr);

const entry = {
  event,
  session_id: (() => {
    try { return JSON.parse(input).session_id || null; } catch { return null; }
  })(),
  exit_code: result.error ? null : (typeof result.status === 'number' ? result.status : 1),
  output_sha256: crypto.createHash('sha256').update(stdout).digest('hex'),
  elapsed_ms: performance.now() - started,
};
try {
  fs.mkdirSync(require('node:path').dirname(ledger), { recursive: true });
  fs.appendFileSync(ledger, `${JSON.stringify(entry)}\n`, 'utf8');
} catch (error) {
  process.stderr.write(`Could not write Supermemory hook ledger: ${error.message}\n`);
}

if (result.error) {
  process.exit(1);
}
process.exit(typeof result.status === 'number' ? result.status : 1);
