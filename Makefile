.PHONY: setup data build-data baseline train eval gguf redteam serve ui test lint docker-up

setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e .

data:
	bash scripts/download_spider.sh

build-data:
	python -m src.t2s.data.build_dataset

baseline:
	python scripts/run_baseline.py

train:
	python -m src.t2s.train.train_qlora

eval:
	python scripts/evaluate.py

eval-finetuned:
	python scripts/evaluate_finetuned.py

gguf:
	bash scripts/to_gguf.sh

benchmark:
	python scripts/benchmark.py

redteam:
	python scripts/run_redteam.py

serve:
	uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port 8000

ui:
	streamlit run app_ui/streamlit_app.py

react-dev:
	cd frontend && npm run dev

test:
	pytest tests/

lint:
	ruff check .

docker-up:
	docker-compose up --build
