#!/usr/bin/env bash
set -euo pipefail

directory="$(dirname "$0")"
kubectl apply -f "$directory/namespace.yaml"
kubectl apply -f "$directory/configmap.yaml" -f "$directory/secret.yaml" \
  -f "$directory/postgres-init-configmap.yaml"
if ! kubectl -n cinemaabyss get secret dockerconfigjson >/dev/null 2>&1; then
  kubectl apply -f "$directory/dockerconfigsecret.yaml"
fi
kubectl apply -f "$directory/postgres.yaml" -f "$directory/kafka/kafka.yaml"
kubectl -n cinemaabyss rollout status statefulset/postgres --timeout=300s
kubectl -n cinemaabyss rollout status statefulset/zookeeper --timeout=300s
kubectl -n cinemaabyss rollout status statefulset/kafka --timeout=300s
kubectl apply -f "$directory/monolith.yaml" -f "$directory/movies-service.yaml" \
  -f "$directory/events-service.yaml" -f "$directory/proxy-service.yaml"
for service in monolith movies-service events-service proxy-service; do
  kubectl -n cinemaabyss rollout status "deployment/$service" --timeout=300s
done
kubectl apply -f "$directory/ingress.yaml"
kubectl -n cinemaabyss get pods,services,ingress
