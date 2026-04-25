LOCALBIN ?= $(shell pwd)/bin
GOLANGCI_LINT_VERSION ?= v2.4.0

COLOR_RESET   := \033[0m
COLOR_BOLD    := \033[1m
COLOR_GREEN   := \033[32m
COLOR_YELLOW  := \033[33m
COLOR_BLUE    := \033[36m

.PHONY: fmt
fmt: ## Run go fmt to format code
	@echo "$(COLOR_GREEN)Formatting Go code...$(COLOR_RESET)"
	@go fmt ./...

.PHONY: vet
vet: ## Run go vet to examine code
	@echo "$(COLOR_GREEN)Running go vet...$(COLOR_RESET)"
	@go vet ./...

GOLANGCI_LINT = $(LOCALBIN)/golangci-lint

.PHONY: golangci-lint
golangci-lint: $(GOLANGCI_LINT) ## Download golangci-lint locally if necessary
$(GOLANGCI_LINT): $(LOCALBIN)
	@echo "$(COLOR_GREEN)Installing golangci-lint $(GOLANGCI_LINT_VERSION)...$(COLOR_RESET)"
	@$(call go-install-tool,$(GOLANGCI_LINT),github.com/golangci/golangci-lint/v2/cmd/golangci-lint,$(GOLANGCI_LINT_VERSION))

$(LOCALBIN):
	@mkdir -p $(LOCALBIN)

# go-install-tool will 'go install' any package with custom target and name of binary, if it doesn't exist
# $1 - target path with name of binary
# $2 - package url which can be installed
# $3 - specific version of package
define go-install-tool
@[ -f "$(1)-$(3)" ] && [ "$$(readlink -- "$(1)" 2>/dev/null)" = "$(1)-$(3)" ] || { \
set -e; \
package=$(2)@$(3) ;\
echo "  Downloading $${package}" ;\
rm -f $(1) ;\
GOBIN=$(LOCALBIN) go install $${package} ;\
mv $(1) $(1)-$(3) ;\
} ;\
ln -sf $$(basename $(1)-$(3)) $(1)
endef

.PHONY: lint
lint: golangci-lint ## Run golangci-lint linter (skips *_test.go files)
	@echo "$(COLOR_GREEN)Running golangci-lint (skipping tests)...$(COLOR_RESET)"
	@$(GOLANGCI_LINT) run --tests=false

.PHONY: lint-all
lint-all: golangci-lint ## Run golangci-lint linter (includes all files)
	@echo "$(COLOR_GREEN)Running golangci-lint (including tests)...$(COLOR_RESET)"
	@$(GOLANGCI_LINT) run

.PHONY: lint-fix
lint-fix: golangci-lint ## Run golangci-lint and automatically fix issues (skips *_test.go files)
	@echo "$(COLOR_GREEN)Running golangci-lint with auto-fix (skipping tests)...$(COLOR_RESET)"
	@$(GOLANGCI_LINT) run --fix --tests=false