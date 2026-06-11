PY ?= python3
GRAPHIFY ?= graphify

.PHONY: test graphify run docker-build docker-up docker-down docker-health-check

test:
	cd backend && $(PY) -m unittest discover -s tests

run:
	cd backend && VPN_ROUTER_REPOSITORY=sqlite $(PY) -m app.api.server

docker-build:
	docker compose build

docker-up:
	docker compose up api

docker-down:
	docker compose down

docker-health-check:
	docker compose --profile jobs run --rm health-check

graphify:
	$(GRAPHIFY) update . --force --no-cluster || $(PY) tools/mini_graphify.py
