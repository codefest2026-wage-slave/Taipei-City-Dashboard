.PHONY: dev-start
dev-start:
	make -C docker dev-start

.PHONY: dev-stop
dev-stop:
	make -C docker dev-stop

.PHONY: lint
lint:
	make -C Taipei-City-Dashboard-BE lint

.PHONY: fmt
fmt:
	make -C Taipei-City-Dashboard-BE fmt