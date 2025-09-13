.PHONY: setup api ingest build verify devnet e2e clean test

setup:
	@echo "Setting up VeriMinutes..."
	pip install -e .
	@mkdir -p ~/.veriminutes/keys
	@mkdir -p output
	@echo "Setup complete!"

api:
	@echo "Starting FastAPI server..."
	uvicorn src.app.api:app --host localhost --port 8787 --reload

web:
	@echo "Starting VeriMinutes Web Interface..."
	@echo "Open http://localhost:8787 in your browser"
	uvicorn src.app.api:app --host localhost --port 8787 --reload

ingest:
	@echo "Ingesting transcript..."
	python3 -m src.cli ingest --path $(PATH) --date $(DATE) --attendees "$(ATTENDEES)" --title "$(TITLE)"

build:
	@echo "Building credentials and proofs..."
	python3 -m src.cli build --slug $(SLUG)

verify:
	@echo "Verifying artifacts..."
	python3 -m src.cli verify --slug $(SLUG)

devnet:
	@echo "Starting local devnet..."
	./scripts/setup_devnet.sh

e2e:
	@echo "Running end-to-end test..."
	@echo "1. Ingesting sample transcript..."
	python3 -m src.cli ingest --path samples/meeting_generic.txt --date 2025-09-12 --attendees "Alice,Bob,Carol" --title "Q3 Board Meeting"
	@echo "2. Building credentials and proofs..."
	python3 -m src.cli build --slug 2025-09-12-q3-board-meeting
	@echo "3. Verifying artifacts..."
	python3 -m src.cli verify --slug 2025-09-12-q3-board-meeting
	@echo "E2E test complete!"

test:
	@echo "Running tests..."
	pytest tests/ -v

clean:
	@echo "Cleaning output directory..."
	rm -rf output/*
	@echo "Clean complete!"