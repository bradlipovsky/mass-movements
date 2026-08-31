.PHONY: all artifacts-reanalysis check check-reanalysis clean notebook-reanalysis reanalysis

PYTHON_REANALYSIS ?= .venv/bin/python
JUPYTER_REANALYSIS ?= $(dir $(PYTHON_REANALYSIS))jupyter

all:
	latexmk -pdf -cd latex/main.tex

check:
	python3 scripts/check_catalog.py
	python3 scripts/check_discovery.py

reanalysis:
	$(PYTHON_REANALYSIS) scripts/reanalysis_pilot.py

notebook-reanalysis:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/era5_pilot.ipynb

artifacts-reanalysis: reanalysis
	$(MAKE) notebook-reanalysis PYTHON_REANALYSIS=$(PYTHON_REANALYSIS) JUPYTER_REANALYSIS=$(JUPYTER_REANALYSIS)
	latexmk -pdf -cd latex/main.tex

check-reanalysis:
	$(PYTHON_REANALYSIS) -m unittest tests.test_reanalysis_pilot -v

clean:
	latexmk -C -cd latex/main.tex
