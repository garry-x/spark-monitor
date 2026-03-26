.PHONY: up down logs clean cli-status cli-start cli-stop cli-restart cli-logs cli-health

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
	./spark-monitor-cli status

cli-start:
	./spark-monitor-cli start

cli-stop:
	./spark-monitor-cli stop

cli-restart:
	./spark-monitor-cli restart

cli-logs:
	./spark-monitor-cli logs

cli-health:
	./spark-monitor-cli health