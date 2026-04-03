.PHONY: up down logs clean cli-status cli-start cli-stop cli-restart cli-logs cli-health install uninstall upgrade deps verify

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f

init: up
	@echo "Services started. Access:"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000 (admin/admin)"

# CLI tool commands
cli-status:
	./spark-monitor status

cli-start:
	./spark-monitor start

cli-stop:
	./spark-monitor stop

cli-restart:
	./spark-monitor restart

cli-logs:
	./spark-monitor logs

cli-health:
	./spark-monitor health

# Installation commands
install:
	./spark-monitor install

uninstall:
	./spark-monitor uninstall

upgrade:
	./spark-monitor upgrade

deps:
	./spark-monitor deps

verify:
	./spark-monitor verify