.PHONY: all check clean

all:
	latexmk -pdf -cd latex/main.tex

check:
	python3 scripts/check_catalog.py
	python3 scripts/check_discovery.py

clean:
	latexmk -C -cd latex/main.tex
