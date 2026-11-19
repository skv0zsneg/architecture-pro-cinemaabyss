#!/usr/bin/env bash
set -euo pipefail

kubectl -n cinemaabyss rollout status deployment/fortio-deploy --timeout=180s
pod="$(kubectl -n cinemaabyss get pod -l app=fortio --field-selector=status.phase=Running \
  --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
kubectl -n cinemaabyss get pod "$pod" -o jsonpath='{.spec.initContainers[*].name} {.spec.containers[*].name}{"\n"}'
for service in movies-service monolith; do
  case "$service" in
    movies-service) port=8081 ;;
    monolith) port=8080 ;;
  esac
  printf '\n%s — 500 requests, concurrency 50\n' "$service"
  before="$(kubectl -n cinemaabyss exec "$pod" -c istio-proxy -- \
    pilot-agent request GET stats | \
    awk -F ': ' -v service="$service" 'index($0, service) && /upstream_rq_pending_overflow|upstream_cx_overflow/ {sum += $2} END {print sum+0}')"
  result="$(kubectl -n cinemaabyss exec "$pod" -c fortio -- fortio load \
    -allow-initial-errors -c 50 -qps 0 -n 500 -loglevel Error "http://$service:$port/api/movies" 2>&1)"
  printf '%s\n' "$result" | grep -E '^Fortio |^Starting |^Ended |^Code |^All done '
  printf '%s\n' "$result" | grep -E 'Code 503[ :]' >/dev/null
  stats="$(kubectl -n cinemaabyss exec "$pod" -c istio-proxy -- \
    pilot-agent request GET stats | \
    grep -E "cluster.outbound.*$service.*(upstream_rq_pending_overflow|upstream_cx_overflow|upstream_rq_pending_total)")"
  printf '%s\n' "$stats"
  after="$(printf '%s\n' "$stats" | awk -F ': ' '/upstream_rq_pending_overflow|upstream_cx_overflow/ {sum += $2} END {print sum+0}')"
  test "$after" -gt "$before"
done
