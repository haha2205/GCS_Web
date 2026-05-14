const path = require('path');
const { spawn } = require('child_process');
const { resolveBackendPython } = require('./backend_python');

const repoRoot = path.resolve(__dirname, '..');
const pythonPath = resolveBackendPython();
const requirementsPath = path.join(repoRoot, 'src-python', 'requirements.txt');

const child = spawn(pythonPath, ['-m', 'pip', 'install', '-r', requirementsPath], {
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
  console.error(`Failed to install backend dependencies with ${pythonPath}:`, error.message);
  process.exit(1);
});
