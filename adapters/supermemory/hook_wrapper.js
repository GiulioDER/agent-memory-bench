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

let payload = null;
try {
  payload = JSON.parse(stdout.trim());
} catch {
  // The ledger still records the process result. A malformed hook response is surfaced below.
}
const hookSpecificOutput = payload && typeof payload === 'object'
  ? payload.hookSpecificOutput
  : null;
const additionalContext = hookSpecificOutput && typeof hookSpecificOutput.additionalContext === 'string'
  ? hookSpecificOutput.additionalContext
  : '';
const systemMessage = payload && typeof payload.systemMessage === 'string'
  ? payload.systemMessage
  : '';
const combinedOutput = `${systemMessage}\n${additionalContext}`;
const errorMatch = combinedOutput.match(
  /<supermemory-status>[\s\S]*?(?:unreachable|failed|without memory|could not be loaded)[\s\S]*?<\/supermemory-status>/i,
);
const recallMatch = systemMessage.match(/\brecalled\s+(\d+)/i);

const entry = {
  event,
  session_id: (() => {
    try { return JSON.parse(input).session_id || null; } catch { return null; }
  })(),
  exit_code: result.error ? null : (typeof result.status === 'number' ? result.status : 1),
  output_sha256: crypto.createHash('sha256').update(stdout).digest('hex'),
  elapsed_ms: performance.now() - started,
  hook_event_name: hookSpecificOutput && typeof hookSpecificOutput.hookEventName === 'string'
    ? hookSpecificOutput.hookEventName
    : null,
  additional_context_bytes: Buffer.byteLength(additionalContext, 'utf8'),
  additional_context_sha256: crypto.createHash('sha256').update(additionalContext).digest('hex'),
  injection_status: errorMatch ? 'error' : (additionalContext ? 'context' : 'empty'),
  hook_error: errorMatch ? errorMatch[0].slice(0, 500) : null,
  recalled_count: recallMatch ? Number(recallMatch[1]) : null,
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
