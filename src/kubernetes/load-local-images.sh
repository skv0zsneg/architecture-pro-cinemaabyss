#!/usr/bin/env bash
set -euo pipefail

root="$(dirname "$0")/../.."
profile="${MINIKUBE_PROFILE:-cinemaabyss}"
repository="ghcr.io/skv0zsneg/architecture-pro-cinemaabyss"

for service in monolith movies-service events-service proxy-service; do
  case "$service" in
    monolith) context="$root/src/monolith" ;;
    movies-service) context="$root/src/microservices/movies" ;;
    events-service) context="$root/src/microservices/events" ;;
    proxy-service) context="$root/src/microservices/proxy" ;;
  esac
  image="$repository/$service:cinema"
  docker build -t "$image" "$context"
  minikube -p "$profile" image load "$image"
done
