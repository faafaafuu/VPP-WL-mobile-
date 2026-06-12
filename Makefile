PY ?= python3
GRAPHIFY ?= graphify

.PHONY: test compile compose-config check-tracked-artifacts graphify sing-box-check run docker-build docker-up docker-down docker-health-check ci

test:
	cd backend && $(PY) -m unittest discover -s tests

compile:
	$(PY) -m compileall backend tools

compose-config:
	VPN_ROUTER_ENV_FILE=.env.example docker compose config >/tmp/vpn-router-compose-config.yml

check-tracked-artifacts:
	$(PY) tools/check_tracked_artifacts.py

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

sing-box-check:
	$(PY) tools/check_sing_box_config.py

ci: test compile compose-config check-tracked-artifacts sing-box-check
	$(PY) -c "import json; json.load(open('graphify-out/graph.json')); print('graphify graph json ok')"
