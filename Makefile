PY ?= python3
GRAPHIFY ?= graphify

.PHONY: test graphify run

test:
	cd backend && $(PY) -m unittest discover -s tests

run:
	cd backend && VPN_ROUTER_REPOSITORY=sqlite $(PY) -m app.api.server

graphify:
	$(GRAPHIFY) update . --force --no-cluster || $(PY) tools/mini_graphify.py
