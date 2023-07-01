test:
	pytest

install:
	python -m pip install .

install-editable:
	python -m pip install --editable .

gitpull:
	git pull --rebase

gitpush:
	git add .
	git commit -m "$(m)"
	git push origin

gitrefresh:
	#after any change to .gitignore
	git rm -r --cached .

pypi:
	rm dist/*
	#python setup.py bdist_wheel --universal
	python -m build  --sdist  --outdir dist .
	gpg --detach-sign -a dist/*
	twine upload -r pypi dist/*


pypi-test:
	rm dist/*
	#python setup.py bdist_wheel --universal
	python -m build  --sdist  --outdir dist .
	gpg --detach-sign -a dist/*
	twine upload -r test-pypi dist/* --verbose
