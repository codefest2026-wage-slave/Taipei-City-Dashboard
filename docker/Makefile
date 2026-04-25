.PHONY: dev-start
dev-start: 
	@docker network create --driver=bridge --subnet=192.168.128.0/24 --gateway=192.168.128.1  br_dashboard
	@docker compose -f docker-compose-db.yaml up -d
	@docker compose -f docker-compose-init.yaml up -d
	@docker compose -f docker-compose.yaml up -d

.PHONY: dev-stop
dev-stop:
	@docker compose -f docker-compose-init.yaml down
	@docker compose -f docker-compose-db.yaml down
	@docker compose -f docker-compose.yaml down
	@docker network rm br_dashboard
