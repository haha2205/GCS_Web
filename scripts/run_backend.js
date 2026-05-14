const path = require('path');
const { spawn } = require('child_process');
const { resolveBackendPython } = require('./backend_python');

const repoRoot = path.resolve(__dirname, '..');
const pythonPath = resolveBackendPython();
const scriptPath = path.join(repoRoot, 'src-python', 'main.py');

const child = spawn(pythonPath, [scriptPath], {
  cwd: path.join(repoRoot, 'src-python'),
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

child.on('error', (error) => {
  console.error(`Failed to start backend with ${pythonPath}:`, error.message);
  process.exit(1);
});
