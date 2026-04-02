.PHONY: build up down restart logs ps setup help

APP_DIR := infinite-campus-exporter

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  setup    Create virtualenv and install dependencies"
	@echo "  build    Build the Docker image"
	@echo "  up       Start all services"
	@echo "  down     Stop all services"
	@echo "  restart  Restart all services"
	@echo "  logs     Tail logs for all services"
	@echo "  ps       Show running services"

setup:
	cd $(APP_DIR) && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps
