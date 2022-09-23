#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time

try:
    from bicchiere import Bicchiere
except:
    print("Bicchiere can't be imported, so operation can't proceed.\nStop.")
    os.sys.exit(-1)

def usage():
    "Prints usage message in case parameters provided are incorrect"
    print("\nUsage: build_bicchiere.py 'major' 'minor' 'revision'\n")
    return -1

def cleaning_src():
    time.sleep(1)
    print("Cleaning src directory")
    if not os.path.exists("src"):
        os.system("mkdir src")
    os.system("rm -r src/*")

def update_version():
    time.sleep(1)
    print("Updating bicchiere version.")
    os.system(
        f"sed -i 's/Current version: {oversion}/Current version: {version}/' README*.md")
    os.system(
        f"sed -i 's/{omajor}, {ominor}, {orevision}/{major}, {minor}, {revision}/' bicchiere.py")
    os.system(
        f"sed -i 's/version = \"{oversion}\"/version = \"{version}\"/' pyproject.toml")

def copy_files_src():
    time.sleep(1)
    print("Copying files to 'src' directory.")
    os.system("cp pyproject.toml src/")
    os.system("cp bicchiere.py src/")
    os.system("cp README.md src/")
    os.system("cp LICENSE src/")

def build_dist():
    time.sleep(1)
    print("Building source distribution.")
    os.system("python3 -m build --sdist src")

    time.sleep(1)
    print("Building wheel.")
    os.system("python3 -m build --wheel src")

def upload_pypi():
    time.sleep(1)
    print("Uploading package to Pypi.")
    os.system(
        f"twine upload src/dist/bicchiere-{version}.tar.gz src/dist/bicchiere-{version}-py3-none-any.whl")

def clean_src():
    time.sleep(1)
    print("Performing final clean of 'src' directory.")
    os.system("rm src/pyproject.toml")
    os.system("rm src/bicchiere.py")
    os.system("rm src/README.md")
    os.system("rm src/LICENSE")

def upgrade_oven():
    stages = []
    stages.append("cd oven")
    stages.append(". bin/activate")
    stages.append(f"pip install bicchiere --upgrade")
    stages.append("pip freeze > requirements.txt")
    stages.append("deactivate")
    stages.append("cd ..")
    command = " && ".join(stages)
    print(f"\nExecuting '{command}'")
    time.sleep(3)
    os.system(command)

def update_git():
    time.sleep(1)
    print("\nUpdating git.")
    os.system("git add .")
    os.system(f"git tag {version}")
    os.system(f"git commit -m'version {version} {commit_message}'")
    os.system("git push origin main --tags")

tasks = [cleaning_src,
            update_version,
            copy_files_src,
            build_dist,
            upload_pypi,
            clean_src,
            upgrade_oven,
            update_git
        ]

def init_vars():
    global args, major, minor, revision, commit_message
    global omajor, ominor, orevision
    global oversion, version

    args = os.sys.argv[1:]
    if len(args) < 3:
        usage()
        return False

    major, minor, revision = args[:3]
    commit_message = args[3] if len(args) > 3 else ""

    omajor, ominor, orevision = Bicchiere.__version__
    oversion = f"{omajor}.{ominor}.{orevision}"
    version = f"{major}.{minor}.{revision}"

    return True

def main():
    """
    Auxiliary tool that updates version, builds packages, uploads them to Pypi and updates github repo.
    """

    os.system("clear")

    if not init_vars():
        os.sys.exit(-1)

    if commit_message == "--upgrade":
        upgrade_oven()
        update_git()
        return 0

    print(f"\nAttemping to build bicchiere version: {major}.{minor}.{revision}\n")
    print(f"\nCurrent bicchiere version: {omajor}.{ominor}.{orevision}\n")

    if oversion == version:
        print("One of major, minor or revision must differ from existing in order to proceed.\nAborting build.\n")
        return -2

    print(f"\nBuilding bicchiere from {oversion} to {version}\n")

    for task in tasks:
        task()

    time.sleep(1)
    print(f"\nBuilding of version {version} finished succesfully.\n")
    return 0


if __name__ == "__main__":
    main()
