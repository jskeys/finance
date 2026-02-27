build_dir=./build

run_black := python3 -m black --line-length 100 -v

py_dir=${CURDIR}
py_src_dir=$(py_dir)/src
py_dist=$(build_dir)/dist
py_src=$(shell find $(py_src_dir) -name "*.py")

py_version=$(py_src_dir)/version.py

all:
	@echo $(py_dir)
	@echo $(py_src)

.PHONY: dist
dist: $(build_dir)/.dist
$(build_dir)/.dist: $(py_src)
	python3 -m build --sdist --wheel --no-isolation -o $(py_dist)
	touch $@

.PHONY: check
check: format lint typecheck

.PHONY: format
format: $(build_dir)/.format
$(build_dir)/.format: $(py_src) | $(build_dir)
	$(run_black) $^
	touch $@

.PHONY: typecheck
typecheck: $(build_dir)/.typecheck
$(build_dir)/.typecheck: $(py_src) | $(build_dir)
	python3 -m mypy $(py_dir)/src --config-file=$(py_dir)/mypy.ini
	touch $@

.PHONY: install
install: $(build_dir)/.install
$(build_dir)/.install: $(py_dir)/pyproject.toml $(py_src) | $(build_dir)
	python3 -m pip install -e $(py_dir)[dev]
	touch $@

.PHONY: lint
lint: $(build_dir)/.lint
$(build_dir)/.lint: $(py_src) .flake8 | $(build_dir)
	python3 -m flake8 -v --tee --output-file $(build_dir)/flake.log --color never --config .flake8 $(py_src)
	touch $@

$(build_dir):
	mkdir -p $(build_dir)

.PHONY: clean
clean:
	rm -rf $(py_dist) $(build_dir) $(py_version)
	rm -rf .mypy_cache
