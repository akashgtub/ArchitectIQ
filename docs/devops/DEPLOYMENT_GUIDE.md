# ArchitectIQ — Deployment Guide

## 1. Overview

This guide provides step-by-step procedures for deploying ArchitectIQ across local development environments, standalone Docker Compose setups, and production Kubernetes clusters.

---

## 2. Pre-Deployment Checklist

Before deploying:
1. Ensure `.env` is configured (or copy `.env.example` to `.env`).
2. Verify that Docker, kubectl, and your local Kubernetes cluster (Docker Desktop, Minikube, or Kind) are running.
3. Confirm that required ports (`8000`, `80` or `30080`, `9090`, `3001`) are available on the host.

---

## 3. Local Deployment via Docker Compose

Ideal for rapid local development, manual testing, and reviewing monitoring dashboards.

### Steps (Reference Only)
```bash
git clone https://github.com/akashgtub/ArchitectIQ.git
cd ArchitectIQ

docker-compose up -d --build

docker-compose ps

```

---

## 4. Kubernetes Deployment via Manifests / Kustomize

### Steps (Reference Only)
```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml

kubectl apply -f infrastructure/kubernetes/configmap.yaml
kubectl apply -f infrastructure/kubernetes/secrets.example.yaml

kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/backend-service.yaml
kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/frontend-service.yaml

kubectl apply -f infrastructure/kubernetes/ingress.yaml

kubectl rollout status deployment/architectiq-backend -n architectiq
kubectl rollout status deployment/architectiq-frontend -n architectiq
```

---

## 5. Automated CI/CD Deployment via Jenkins

1. Push your changes to branch `main` or trigger a build with parameters in Jenkins.
2. Select target environment (`local`, `staging`, or `production`).
3. Jenkins automatically runs unit tests, compiles the frontend, builds Docker images, validates infrastructure configurations, and applies the rolling update to Kubernetes.
4. For production targets, approve the deployment prompt in the Jenkins UI.

