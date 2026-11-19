# CinemaAbyss Helm chart

```bash
helm lint src/kubernetes/helm
helm upgrade --install cinemaabyss src/kubernetes/helm \
  --namespace cinemaabyss --create-namespace --wait --timeout 5m
```

Chart устанавливает PostgreSQL, ZooKeeper, Kafka, Monolith, Movies, Events, Proxy и Ingress. Namespace задаётся через `--namespace`.

Основные настройки в `values.yaml`:

| Настройка | Назначение |
|---|---|
| `*.image.repository`, `*.image.tag` | Образы четырёх приложений |
| `*.replicas`, `*.resources` | Реплики и ресурсы |
| `config.gradualMigration`, `config.moviesMigrationPercent` | Feature Flag |
| `imagePullSecrets.name` | Имя существующего registry secret |
| `imagePullSecrets.dockerconfigjson` | Необязательный config в base64 для создания secret |
| `ingress.hosts` | Домен и маршруты |
| `*.persistence.enabled` | Постоянное хранилище |
| `istio.enabled` | Создание Circuit Breaker; требует установленного Istio |

Изменение ConfigMap автоматически перезапускает приложения через checksum-аннотации.

Локальная проверка до публикации образов: `bash src/kubernetes/load-local-images.sh`.
Результаты заданий и скриншоты: [Project_template.md](../../../Project_template.md#задание-4).
