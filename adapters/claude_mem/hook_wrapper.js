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
let hookInput = {};
try {
  hookInput = JSON.parse(input) || {};
} catch {
  hookInput = {};
}
const guardEnabled = process.env.CLAUDE_MEM_ENFORCE_FIRST_SEARCH === '1';
const firstSearchSentinel = process.env.CLAUDE_MEM_FIRST_SEARCH_SENTINEL;
const firstSearchTool = process.env.CLAUDE_MEM_FIRST_SEARCH_TOOL || 'mcp__mcp-search__search';
const toolName = hookInput.tool_name || hookInput.toolName || '';
const appendLedger = (entry) => {
  try {
    fs.mkdirSync(path.dirname(ledger), { recursive: true });
    fs.appendFileSync(ledger, `${JSON.stringify(entry)}\n`, 'utf8');
  } catch (error) {
    process.stderr.write(`Could not write Claude-Mem hook ledger: ${error.message}\n`);
  }
};

if (event === 'PreToolUse' && guardEnabled && firstSearchSentinel && toolName) {
  if (toolName === firstSearchTool) {
    fs.mkdirSync(path.dirname(firstSearchSentinel), { recursive: true });
    fs.writeFileSync(firstSearchSentinel, 'search attempted\n', 'utf8');
  } else if (!fs.existsSync(firstSearchSentinel)) {
    const reason = `AMB Claude-Mem protocol requires ${firstSearchTool} before ${toolName}`;
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason: reason,
      },
    }));
    appendLedger({
      event,
      session_id: hookInput.session_id || null,
      exit_code: 0,
      vendor_exit_code: null,
      guard_decision: 'deny',
      guard_reason: reason,
      tool_name: toolName,
      output_sha256: crypto.createHash('sha256').update('').digest('hex'),
      elapsed_ms: performance.now() - started,
      retry_count: 0,
      additional_context_bytes: 0,
      additional_context_sha256: crypto.createHash('sha256').update('').digest('hex'),
      injection_status: 'empty',
      hook_error: null,
    });
    process.exit(0);
  }
}
const isContextHook = event === 'SessionStart'
  && argv.includes('hook')
  && argv.includes('context');
let retryCount = 0;
let result;
while (true) {
  result = spawnSync(process.execPath, argv, {
    input,
    encoding: 'utf8',
    env: { ...process.env },
    windowsHide: true,
    maxBuffer: 20 * 1024 * 1024,
  });
  const status = result.error ? null : (typeof result.status === 'number' ? result.status : 1);
  // Claude Code may dispatch the two official SessionStart hooks concurrently. If context wins
  // the race, the first request sees a worker that is still starting. Retry that one transient
  // failure after a short delay, while leaving all other vendor exit statuses untouched.
  if (!isContextHook || status === 0 || retryCount >= 2) break;
  retryCount += 1;
  spawnSync('sleep', ['2']);
}
const stdout = result.stdout || '';
const stderr = result.stderr || '';
if (stdout) process.stdout.write(stdout);
if (stderr) process.stderr.write(stderr);
const vendorExitCode = result.error ? null : (typeof result.status === 'number' ? result.status : 1);
const idempotentPrestart = event === 'SessionStartWorker'
  && vendorExitCode !== 0
  && process.env.CLAUDE_MEM_BENCHMARK_PRESTARTED === '1';
const exitCode = idempotentPrestart ? 0 : vendorExitCode;

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
  session_id: hookInput.session_id || null,
  exit_code: exitCode,
  vendor_exit_code: vendorExitCode,
  idempotent_prestart: idempotentPrestart,
  output_sha256: crypto.createHash('sha256').update(stdout).digest('hex'),
  elapsed_ms: performance.now() - started,
  retry_count: retryCount,
  additional_context_bytes: Buffer.byteLength(additionalContext, 'utf8'),
  additional_context_sha256: crypto.createHash('sha256').update(additionalContext).digest('hex'),
  injection_status: (additionalContext || systemMessage) ? 'context' : 'empty',
  hook_error: result.error ? String(result.error.message || result.error) : null,
};
appendLedger(entry);

if (result.error) process.exit(1);
process.exit(exitCode);
