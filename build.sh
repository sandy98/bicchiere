python3 -m build --sdist src
python3 -m build --wheel src
twine upload src/dist/bicchiere-$1.tar.gz src/dist/bicchiere-$1-py3-none-any.whl
