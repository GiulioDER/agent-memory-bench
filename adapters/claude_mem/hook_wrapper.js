/*
 * AMB's evidence wrapper around the official Claude-Mem hook command.
 * It preserves stdin, stdout, stderr, and exit status, while recording only hashes and sizes.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const event = process.argv[2];
const argv = JSON.parse(Buffer.from(process.argv[3] || '', 'base64').toString('utf8') || '[]');
const ledger = process.env.CLAUDE_MEM_HOOK_LEDGER;

if (!event || !Array.isArray(argv) || argv.length === 0 || !ledger) {
  process.stderr.write('Claude-Mem hook wrapper needs an event, argv, and ledger\n');
  process.exit(64);
}

let input = '';
try {
  input = fs.readFileSync(0, 'utf8');
} catch (error) {
  process.stderr.write(`Could not read hook input: ${error.message}\n`);
}

const started = performance.now();
const result = spawnSync(process.execPath, argv, {
  input,
  encoding: 'utf8',
  env: { ...process.env },
  windowsHide: true,
  maxBuffer: 20 * 1024 * 1024,
});
const stdout = result.stdout || '';
const stderr = result.stderr || '';
if (stdout) process.stdout.write(stdout);
if (stderr) process.stderr.write(stderr);

let payload = null;
try {
  payload = JSON.parse(stdout.trim());
} catch {
  // The ledger still records the process result. A non-JSON hook response is visible in output.
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
const entry = {
  event,
  session_id: (() => {
    try { return JSON.parse(input).session_id || null; } catch { return null; }
  })(),
  exit_code: result.error ? null : (typeof result.status === 'number' ? result.status : 1),
  output_sha256: crypto.createHash('sha256').update(stdout).digest('hex'),
  elapsed_ms: performance.now() - started,
  additional_context_bytes: Buffer.byteLength(additionalContext, 'utf8'),
  additional_context_sha256: crypto.createHash('sha256').update(additionalContext).digest('hex'),
  injection_status: (additionalContext || systemMessage) ? 'context' : 'empty',
  hook_error: result.error ? String(result.error.message || result.error) : null,
};
try {
  fs.mkdirSync(path.dirname(ledger), { recursive: true });
  fs.appendFileSync(ledger, `${JSON.stringify(entry)}\n`, 'utf8');
} catch (error) {
  process.stderr.write(`Could not write Claude-Mem hook ledger: ${error.message}\n`);
}

if (result.error) process.exit(1);
process.exit(typeof result.status === 'number' ? result.status : 1);
