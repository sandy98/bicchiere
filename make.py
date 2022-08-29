#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import time

def usage():
    print("Usage: build_bicchiere.py 'major' 'minor' 'revision'")
    return -1

def main():
    """
    Auxiliary tool that updates version, builds packages, uploads them to Pypi and updates github repo.
    """
    
    os.system("clear")

    args = os.sys.argv[1:]
    if len(args) < 3:
        return usage()              
    major, minor, revision = args[:3]
    commit_message = args[3] if len(args) > 3 else ""

    print(f"Attemping to build bicchiere version: {major}.{minor}.{revision}")

    from bicchiere import Bicchiere
    omajor, ominor, orevision = Bicchiere.__version__
    print(f"Current bicchiere version: {omajor}.{ominor}.{orevision}")

    oversion = f"{omajor}.{ominor}.{orevision}"
    version = f"{major}.{minor}.{revision}"

    if oversion == version:
        print("One of major, minor or revision must differ from existing in order to proceed.\nAborting build.")
        return -2

    time.sleep(1)
    print(f"Building bicchiere from {oversion} to {version}")

    time.sleep(1) 
    print("Cleaning src directory")
    if not os.path.exists("src"):
        os.system("mkdir src")
    os.system("rm -r src/*")

    time.sleep(1)   
    print("Updating bicchiere version.")
    os.system(f"sed -i 's/Current version: {oversion}/Current version: {version}/' README.md")
    os.system(f"sed -i 's/{omajor}, {ominor}, {orevision}/{major}, {minor}, {revision}/' bicchiere.py")
    os.system(f"sed -i 's/version = \"{oversion}\"/version = \"{version}\"/' pyproject.toml")
    
    time.sleep(1)   
    print("Copying files to 'src' directory.")
    os.system("cp pyproject.toml src/")
    os.system("cp bicchiere.py src/")
    os.system("cp README.md src/")
    os.system("cp LICENSE src/")

    time.sleep(1)   
    print("Building source distribution.")
    os.system("python3 -m build --sdist src")

    time.sleep(1)   
    print("Building wheel.")
    os.system("python3 -m build --wheel src")

    time.sleep(1)   
    print("Uploading package to Pypi.")
    os.system(f"twine upload src/dist/bicchiere-{version}.tar.gz src/dist/bicchiere-{version}-py3-none-any.whl")

    time.sleep(1)   
    print("Performing final clean of 'src' directory.")
    os.system("rm src/pyproject.toml")
    os.system("rm src/bicchiere.py")
    os.system("rm src/README.md")
    os.system("rm src/LICENSE")

    time.sleep(1)   
    stages = []
    stages.append("cd oven")
    stages.append(". bin/activate")
    stages.append("pip install --upgrade bicchiere")
    stages.append("deactivate")
    stages.append("cd ..")
    command = " && ".join(stages)
    print(f"Executing '{command}'")
    os.system(command)

    time.sleep(1)   
    print("Updating git.")
    os.system("git add .")
    os.system(f"git tag {version}")
    os.system(f"git commit -m'version {version} {commit_message}'")
    os.system("git push origin main --tags")

    time.sleep(1)
    print(f"Building of version {version} finished succesfully.")
    return 0

if __name__ == "__main__":
    main()

