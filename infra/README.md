# Infrastructure

This directory contains infrastructure configuration and deployment files.

## Contents
- **Docker** - Dockerfile and container configurations
- **CI/CD** - Continuous integration and deployment configs

## Structure

```
infra/
├── docker/           # Dockerfiles for services
└── github-actions/   # GitHub Actions workflows
```

## Deployment Targets

- **Local**: Docker Compose (see root `docker-compose.yml`)
- **Production**: Cloud platform (AWS/GCP/Azure)

## Getting Started

### Docker
Build and run services locally:
```bash
# Build all services
docker-compose build

# Run services
docker-compose up
```
