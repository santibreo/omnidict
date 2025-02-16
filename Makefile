test:
	pytest --exitfirst

.coverage:
	coverage erase && \
	coverage run -m pytest --doctest-modules ./tests

coverage: .coverage
	coverage report

coverage-html: .coverage
	echo 'Not implemented yet. Incorporated when docs.'

clean:
	rm -rf .coverage build/ docs/build/*/ .mypy_cache/ .pytest_cache/ .ruff_cache/

build:
	python3 -m build .

mypy:
	mypy src/
