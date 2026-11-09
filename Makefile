.PHONY: verify test api ui preview model-status
verify:
	python scripts/repository_audit.py

test:
	python -m unittest discover -s tests -v
api:
	python serve.py --open
ui:
	cd frontend && npm ci && npm run build
preview:
	docker compose up --build
model-status:
	python scripts/model_assets.py status
