.PHONY: all area-convergence artifacts-area-convergence artifacts-denominator artifacts-event-audit artifacts-reanalysis artifacts-scale-explicit check check-area-convergence check-denominator check-event-audit check-reanalysis check-scale-explicit clean denominator notebook-area-convergence notebook-denominator notebook-event-audit notebook-reanalysis notebook-scale-explicit reanalysis scale-explicit

PYTHON_REANALYSIS ?= .venv/bin/python
JUPYTER_REANALYSIS ?= $(dir $(PYTHON_REANALYSIS))jupyter

all:
	latexmk -pdf -cd latex/main.tex

check:
	python3 scripts/check_catalog.py
	python3 scripts/check_discovery.py
	python3 scripts/check_event_audit.py

check-event-audit:
	python3 -m unittest tests.test_event_audit -v

reanalysis:
	$(PYTHON_REANALYSIS) scripts/reanalysis_pilot.py

notebook-reanalysis:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/era5_pilot.ipynb

notebook-event-audit:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/source_time_audit.ipynb

artifacts-event-audit: check-event-audit notebook-event-audit

artifacts-reanalysis: reanalysis
	$(MAKE) notebook-reanalysis PYTHON_REANALYSIS=$(PYTHON_REANALYSIS) JUPYTER_REANALYSIS=$(JUPYTER_REANALYSIS)
	latexmk -pdf -cd latex/main.tex

check-reanalysis:
	$(PYTHON_REANALYSIS) -m unittest tests.test_reanalysis_pilot -v

denominator:
	$(PYTHON_REANALYSIS) scripts/denominator_pilot.py

check-denominator:
	$(PYTHON_REANALYSIS) -m unittest tests.test_denominator_pilot -v

notebook-denominator:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/denominator_pilot.ipynb

artifacts-denominator: denominator notebook-denominator check-denominator
	latexmk -pdf -cd latex/main.tex

area-convergence:
	$(PYTHON_REANALYSIS) scripts/susceptible_area_convergence.py

check-area-convergence:
	$(PYTHON_REANALYSIS) -m unittest tests.test_susceptible_area_convergence -v

notebook-area-convergence:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/susceptible_area_convergence.ipynb

artifacts-area-convergence: area-convergence notebook-area-convergence check-area-convergence
	latexmk -pdf -cd latex/main.tex

scale-explicit:
	$(PYTHON_REANALYSIS) scripts/scale_explicit_steep_area.py

check-scale-explicit:
	$(PYTHON_REANALYSIS) -m unittest tests.test_scale_explicit_steep_area -v

notebook-scale-explicit:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/scale_explicit_steep_area.ipynb

artifacts-scale-explicit: scale-explicit
	$(MAKE) notebook-scale-explicit PYTHON_REANALYSIS=$(PYTHON_REANALYSIS) JUPYTER_REANALYSIS=$(JUPYTER_REANALYSIS)
	$(MAKE) check-scale-explicit PYTHON_REANALYSIS=$(PYTHON_REANALYSIS)
	latexmk -pdf -cd latex/main.tex

clean:
	latexmk -C -cd latex/main.tex
