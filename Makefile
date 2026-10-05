.PHONY: install test demo

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

demo:
	python -m lora_queue_desk --demo status
