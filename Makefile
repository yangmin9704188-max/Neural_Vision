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
	@echo "[DEPRECATED] sync-dry is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

sync:
	@echo "[DEPRECATED] sync is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

ai-prompt:
	@echo "[DEPRECATED] ai-prompt is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

ai-prompt-json:
	@echo "[DEPRECATED] ai-prompt-json is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

# Round execution wrapper (legacy verification/runners/* not present; use modules/body/src/runners/*)
curated_v0_round:
	@echo "[DEPRECATED] curated_v0_round is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

geo_v0_s1_round:
	@echo "[DEPRECATED] geo_v0_s1_round is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

# Ops lock warning sensor
ops_guard:
	@echo "[DEPRECATED] ops_guard is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

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
	@echo "[DEPRECATED] curated_v0_baseline is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

# Golden registry patch apply
golden-apply:
	@echo "[DEPRECATED] golden-apply is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

# Judgment creation
judgment:
	@echo "[DEPRECATED] judgment is not supported in this repo layout."
	@echo "See ops/HUB.md"
	@exit 2

# Commands documentation generator
commands-update:
	@python tools/ops/generate_commands_md.py
