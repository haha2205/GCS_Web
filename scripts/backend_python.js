const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function canUsePython(candidate) {
  if (!candidate) {
    return false;
  }

  if (candidate === 'python') {
    return true;
  }

  return fs.existsSync(candidate);
}

function hasBackendRuntimeDeps(pythonPath) {
  if (!canUsePython(pythonPath)) {
    return false;
  }

  const probe = [
    'import importlib.util, sys',
    "required = ['torch', 'fastapi', 'uvicorn']",
    'missing = [name for name in required if importlib.util.find_spec(name) is None]',
    "has_ws = importlib.util.find_spec('websockets') is not None or importlib.util.find_spec('wsproto') is not None",
    'sys.exit(0 if not missing and has_ws else 1)',
  ].join('; ');

  const result = spawnSync(pythonPath, ['-c', probe], {
    stdio: 'ignore',
    shell: false,
  });

  return result.status === 0;
}

function resolveBackendPython() {
  const repoRoot = path.resolve(__dirname, '..');
  const explicitPython = process.env.APOLLO_BACKEND_PYTHON;

  if (explicitPython) {
    return explicitPython;
  }

  const condaPrefix = process.env.CONDA_PREFIX;
  const condaCandidates = condaPrefix
    ? [
        path.join(condaPrefix, 'python.exe'),
        path.join(condaPrefix, 'bin', 'python'),
      ]
    : [];
  const candidates = [
    path.join(repoRoot, '.venv-torch311', 'Scripts', 'python.exe'),
    path.join(repoRoot, '.venv-torch311', 'bin', 'python'),
    ...condaCandidates,
    process.env.PYTHON,
    'python',
  ];

  for (const candidate of candidates) {
    if (hasBackendRuntimeDeps(candidate)) {
      return candidate;
    }
  }

  for (const candidate of candidates) {
    if (canUsePython(candidate)) {
      return candidate;
    }
  }

  return 'python';
}

module.exports = {
  resolveBackendPython,
};
