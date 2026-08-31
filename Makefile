.PHONY: all check check-reanalysis clean reanalysis

PYTHON_REANALYSIS ?= .venv/bin/python

all:
	latexmk -pdf -cd latex/main.tex

check:
	python3 scripts/check_catalog.py
	python3 scripts/check_discovery.py

reanalysis:
	$(PYTHON_REANALYSIS) scripts/reanalysis_pilot.py

check-reanalysis:
	$(PYTHON_REANALYSIS) -m unittest tests.test_reanalysis_pilot -v

clean:
	latexmk -C -cd latex/main.tex
