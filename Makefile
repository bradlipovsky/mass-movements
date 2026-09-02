.PHONY: all area-convergence artifacts-area-convergence artifacts-audited-reanalysis artifacts-denominator artifacts-event-audit artifacts-geographic-coverage artifacts-global-dem-support artifacts-native-glo90-transfer artifacts-object-relevance artifacts-reanalysis artifacts-scale-explicit check check-area-convergence check-audited-reanalysis check-denominator check-event-audit check-native-glo90-transfer check-object-relevance check-reanalysis check-scale-explicit clean denominator native-glo90-transfer notebook-area-convergence notebook-audited-reanalysis notebook-denominator notebook-event-audit notebook-geographic-coverage notebook-global-dem-support notebook-native-glo90-transfer notebook-object-relevance notebook-reanalysis notebook-scale-explicit reanalysis scale-explicit

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

check-audited-reanalysis:
	$(PYTHON_REANALYSIS) -W error -m unittest tests.test_audited_reanalysis -v

notebook-audited-reanalysis:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/audited_reanalysis.ipynb

artifacts-audited-reanalysis: check-audited-reanalysis notebook-audited-reanalysis
	latexmk -pdf -cd latex/main.tex

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

notebook-geographic-coverage:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/geographic_coverage_gate.ipynb

artifacts-geographic-coverage: notebook-geographic-coverage
	latexmk -pdf -cd latex/main.tex

notebook-global-dem-support:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/global_dem_object_support.ipynb

artifacts-global-dem-support: notebook-global-dem-support
	latexmk -pdf -cd latex/main.tex

check-object-relevance:
	$(PYTHON_REANALYSIS) -m unittest tests.test_glacier_proximity_object_relevance -v

notebook-object-relevance:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/glacier_proximity_object_relevance.ipynb

artifacts-object-relevance: check-object-relevance notebook-object-relevance
	latexmk -pdf -cd latex/main.tex

native-glo90-transfer:
	$(PYTHON_REANALYSIS) scripts/native_glo90_transfer.py --raw-manifest data/native_glo90_transfer/raw_source_manifest.json --raw-manifest-sha256 dba58bae4a36600d55adc6393f891cc0fd95a9baa577e3cb3bfc4ff64233d8a5

check-native-glo90-transfer:
	$(PYTHON_REANALYSIS) -m unittest tests.test_native_glo90_transfer -v

notebook-native-glo90-transfer:
	PATH="$(dir $(PYTHON_REANALYSIS)):$$PATH" $(JUPYTER_REANALYSIS) execute --inplace --timeout 600 --kernel_name python3 notebooks/native_glo90_transfer.ipynb

artifacts-native-glo90-transfer: native-glo90-transfer check-native-glo90-transfer notebook-native-glo90-transfer
	latexmk -pdf -cd latex/main.tex

clean:
	latexmk -C -cd latex/main.tex
