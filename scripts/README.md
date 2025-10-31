# Scripts

Utility scripts for development, deployment, and maintenance.

## Available Scripts

- `check_deps.sh` - Verify all dependencies are installed
- `reset_redis.sh` - Clear Redis data for local development

## Usage

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

Run a script:
```bash
./scripts/check_deps.sh
```

## Script Guidelines

- Use `#!/usr/bin/env bash` shebang
- Include error handling with `set -euo pipefail`
- Add help text with `-h` or `--help` flag
- Log actions clearly
- Make scripts idempotent when possible
