## Задание 1

![Контексты To-Be](/diagrams/c4_container_to_be/c4_container_to_be.png)

*[Картинка](/diagrams/c4_container_to_be/c4_container_to_be.png) — [PlantUML](/diagrams/c4_container_to_be/c4_container_to_be.puml)*

> **Комментарий** Лэндскейп разработчиков кинобездны не предусматривает фронт разработчиков, однако упомянуты интеграции через браузер, мобильные приложения и SmartTV. Подразумеваю что разработчики для этого есть, значит есть экспертиза в JS стэке.

## Задание 2

### Реализованное решение

Реализованы два сервиса на Python + FastAPI:

- [Proxy](src/microservices/proxy) — API Gateway с постепенным переключением запросов фильмов с монолита на Movies Service.
- [Events](src/microservices/events) — API событий Movie/User/Payment, producer и consumer Kafka с обработкой событий в логах.

При `GRADUAL_MIGRATION=true` процент задаётся через `MOVIES_MIGRATION_PERCENT`: 0 — монолит, 100 — Movies Service. При выключенном флаге все запросы фильмов идут в Movies Service. Проверены значения 0, 50 и 100%.

Postman: **22 запроса, 42 проверки, 0 ошибок**.

![Результаты Postman](/screenshots/postman_tests.png)

![Запрос к API Gateway](/screenshots/curl_movies_result.png)

![Топики Kafka](/screenshots/kafka_ui.png)

## Задание 3

### Реализованное решение

- [CI/CD](.github/workflows/docker-build-push.yml) — тестирование, сборка и публикация четырёх образов в GHCR для AMD64 и ARM64. Workflow запускается при push в любую ветку; тесты выполняются перед публикацией.
- [Kubernetes](src/kubernetes) — Deployment и Service для Proxy и Events, Ingress и конфигурация Feature Flag. Проверены HTTPS `/api/movies`, обработка событий и переключение 0/100%.

Для локальной проверки образы собраны через `bash src/kubernetes/load-local-images.sh`, установка выполнена через `bash src/kubernetes/deploy.sh`.

Postman (`npm run test:kubernetes` из `tests/postman`): **22 запроса, 42 проверки, 0 ошибок**. Проверка workflow через `actionlint` также пройдена.

> Зелёный запуск GitHub Actions и публикацию GHCR осталось подтвердить после push. Локальный деплой проверен на загруженных в Minikube образах.

![Postman в Kubernetes](/screenshots/postman_tests_kubernetes.png)

![Kubernetes и HTTPS API](/screenshots/kubernetes_movies.png)

![Обработка событий в Kubernetes](/screenshots/kubernetes_events.png)

## Задание 4

### Реализованное решение

Доработан [Helm chart](src/kubernetes/helm). Образы, ресурсы, namespace и Feature Flag настраиваются через values и параметры установки. При изменении процента миграции приложения автоматически перезапускаются.

```bash
helm upgrade --install cinemaabyss src/kubernetes/helm \
  --namespace cinemaabyss --create-namespace --wait --timeout 5m
```

Проверена чистая установка после удаления ручного деплоя. Релиз — `deployed`, HTTPS возвращает фильмы, Postman — **42/42**.

![Helm и HTTPS API](/screenshots/helm_movies.png)

## Задание 5

### Реализованное решение

Развёрнут Istio 1.30.8. Для Monolith и Movies настроены [Circuit Breaker и отключение повторов запросов](src/kubernetes/circuit-breaker-config.yaml). Те же политики доступны в Helm через `istio.enabled=true`. Для приложений и Fortio включена sidecar injection.

Проверка после установки Istio и включения injection:

```bash
kubectl apply -f src/kubernetes/fortio.yaml
bash src/kubernetes/check-circuit-breaker.sh
```

Fortio отправляет по 500 запросов с параллелизмом 50. Movies: **6 ответов 200 и 494 ответа 503**; Monolith: **12 ответов 200 и 488 ответов 503**. У обоих сервисов выросли overflow-счётчики. Обычные Postman-тесты после нагрузки — **42/42**.

![Fortio и счётчики Circuit Breaker](/screenshots/istio_circuit_breaker.png)
