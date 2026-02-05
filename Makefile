.PHONY: help sync-dry sync ai-prompt ai-prompt-json curated_v0_round ops_guard postprocess postprocess-baseline curated_v0_baseline golden-apply judgment commands-update

# Default variables (override with make VAR=value)
BASELINE_RUN_DIR ?= verification/runs/facts/curated_v0/round20_20260125_164801
GOLDEN_REGISTRY ?= docs/verification/golden_registry.json

# Default target
help:
	@echo "Available targets:"
	@echo "  make sync-dry ARGS=\"--set snapshot.status=candidate\""
	@echo "  make sync ARGS=\"--set last_update.trigger=manual_test\""
	@echo "  make ai-prompt"
	@echo "  make ai-prompt-json"
	@echo "  make curated_v0_round RUN_DIR=<out_dir> [SKIP_RUNNER=1]"
	@echo "  make ops_guard [BASE=main]"
	@echo ""
	@echo "Round Ops Shortcuts:"
	@echo "  make postprocess RUN_DIR=<dir>"
	@echo "  make postprocess-baseline"
	@echo "  make curated_v0_baseline"
	@echo "  make golden-apply PATCH=<patch.json> [FORCE=1]"
	@echo "  make judgment FROM_RUN=<run_dir> [OUT_DIR=docs/judgments] [SLUG=...] [DRY_RUN=1]"
	@echo "  make commands-update"
	@echo ""
	@echo "Examples:"
	@echo "  make sync-dry ARGS=\"--set snapshot.status=candidate\""
	@echo "  make sync ARGS=\"--set snapshot.status=hold --set last_update.trigger=test\""
	@echo "  make ai-prompt"
	@echo "  make ai-prompt-json"
	@echo "  make curated_v0_round RUN_DIR=verification/runs/facts/curated_v0/round20_20260125_164801"
	@echo "  make curated_v0_round RUN_DIR=verification/runs/facts/curated_v0/round20_20260125_164801 SKIP_RUNNER=1"
	@echo "  make ops_guard"
	@echo "  make postprocess RUN_DIR=verification/runs/facts/curated_v0/round20_20260125_164801"
	@echo "  make postprocess-baseline"
	@echo "  make curated_v0_baseline"
	@echo "  make golden-apply PATCH=verification/runs/facts/curated_v0/round20_20260125_164801/CANDIDATES/GOLDEN_REGISTRY_PATCH.json"
	@echo "  make golden-apply PATCH=<path> FORCE=1"
	@echo "  make judgment FROM_RUN=verification/runs/facts/curated_v0/round20_20260125_164801"
	@echo "  make judgment FROM_RUN=<run_dir> DRY_RUN=1 SLUG=smoke"

sync-dry:
	python tools/sync_state.py --dry-run $(ARGS)

sync:
	python tools/sync_state.py $(ARGS)

ai-prompt:
	python tools/render_ai_prompt.py

ai-prompt-json:
	python tools/render_ai_prompt.py --format json

# Round execution wrapper
curated_v0_round:
	@if [ -z "$(RUN_DIR)" ]; then \
		echo "Error: RUN_DIR is required. Usage: make curated_v0_round RUN_DIR=<out_dir>"; \
		exit 1; \
	fi
	@if [ "$(SKIP_RUNNER)" != "1" ]; then \
		if [ ! -f "$(RUN_DIR)/facts_summary.json" ]; then \
			echo "Running curated_v0 facts runner..."; \
			python verification/runners/run_curated_v0_facts_round1.py \
				--npz verification/datasets/golden/core_measurements_v0/golden_real_data_v0.npz \
				--out_dir $(RUN_DIR); \
		else \
			echo "facts_summary.json already exists in $(RUN_DIR), skipping runner."; \
			echo "To force re-run, delete $(RUN_DIR)/facts_summary.json or run without SKIP_RUNNER=1"; \
		fi \
	else \
		echo "SKIP_RUNNER=1: Skipping runner execution."; \
	fi
	@echo "Running postprocess_round.py (always executed)..."
	@python tools/postprocess_round.py --current_run_dir $(RUN_DIR) || true

geo_v0_s1_round:
	@if [ -z "$(RUN_DIR)" ]; then \
		echo "Error: RUN_DIR is required. Usage: make geo_v0_s1_round RUN_DIR=<out_dir>"; \
		exit 1; \
	fi
	@if [ "$(SKIP_RUNNER)" != "1" ]; then \
		if [ ! -f "$(RUN_DIR)/facts_summary.json" ]; then \
			echo "Running geo v0 S1 facts runner..."; \
			python verification/runners/run_geo_v0_s1_facts.py \
				--manifest verification/datasets/golden/s1_mesh_v0/s1_manifest_v0.json \
				--out_dir $(RUN_DIR); \
		else \
			echo "facts_summary.json already exists in $(RUN_DIR), skipping runner."; \
			echo "To force re-run, delete $(RUN_DIR)/facts_summary.json or run without SKIP_RUNNER=1"; \
		fi \
	else \
		echo "SKIP_RUNNER=1: Skipping runner execution."; \
	fi
	@echo "Running postprocess_round.py (always executed)..."
	@python tools/postprocess_round.py --current_run_dir $(RUN_DIR) || true

# Ops lock warning sensor
ops_guard:
	@python tools/ops/check_ops_lock.py --base $(BASE) || true

# Postprocess shortcut
postprocess:
	@if [ -z "$(RUN_DIR)" ]; then \
		echo "Error: RUN_DIR is required. Usage: make postprocess RUN_DIR=<dir>"; \
		echo "Example: make postprocess RUN_DIR=verification/runs/facts/curated_v0/round20_20260125_164801"; \
		exit 1; \
	fi
	@python tools/postprocess_round.py --current_run_dir $(RUN_DIR)

# Postprocess baseline (uses BASELINE_RUN_DIR)
postprocess-baseline:
	@echo "Running postprocess for baseline: $(BASELINE_RUN_DIR)"
	@python tools/postprocess_round.py --current_run_dir $(BASELINE_RUN_DIR)

# Curated v0 baseline round (runner skip, postprocess only)
curated_v0_baseline:
	@echo "Running curated_v0_round for baseline: $(BASELINE_RUN_DIR) (SKIP_RUNNER=1)"
	@$(MAKE) curated_v0_round RUN_DIR=$(BASELINE_RUN_DIR) SKIP_RUNNER=1

# Golden registry patch apply
golden-apply:
	@if [ -z "$(PATCH)" ]; then \
		echo "Error: PATCH is required. Usage: make golden-apply PATCH=<patch.json> [FORCE=1]"; \
		echo "Example: make golden-apply PATCH=verification/runs/facts/curated_v0/round20_20260125_164801/CANDIDATES/GOLDEN_REGISTRY_PATCH.json"; \
		exit 1; \
	fi
	@if [ "$(FORCE)" = "1" ]; then \
		python tools/golden_registry.py --add-entry $(PATCH) --registry $(GOLDEN_REGISTRY) --force; \
	else \
		python tools/golden_registry.py --add-entry $(PATCH) --registry $(GOLDEN_REGISTRY); \
	fi

# Judgment creation
judgment:
	@if [ -z "$(FROM_RUN)" ]; then \
		echo "Error: FROM_RUN is required. Usage: make judgment FROM_RUN=<run_dir> [OUT_DIR=docs/judgments] [SLUG=...] [DRY_RUN=1]"; \
		echo "Example: make judgment FROM_RUN=verification/runs/facts/curated_v0/round20_20260125_164801"; \
		exit 1; \
	fi
	@OUT_DIR="$(if $(OUT_DIR),$(OUT_DIR),docs/judgments)"; \
	DRY_RUN_FLAG=""; \
	if [ "$(DRY_RUN)" = "1" ]; then \
		DRY_RUN_FLAG="--dry-run"; \
	fi; \
	SLUG_FLAG=""; \
	if [ -n "$(SLUG)" ]; then \
		SLUG_FLAG="--slug $(SLUG)"; \
	fi; \
	python tools/judgments.py --from-run $(FROM_RUN) --out-dir $$OUT_DIR $$SLUG_FLAG $$DRY_RUN_FLAG

# Commands documentation generator
commands-update:
	@python tools/ops/generate_commands_md.py
