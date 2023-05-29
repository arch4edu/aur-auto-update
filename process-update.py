#!/bin/python
import json
import logging
import os
import sys
import traceback
from pathlib import Path

import toml
import yaml
from github import Github

token = toml.load("config/keyfile.toml")["keys"]["github"]
github = Github(token)

with open("nvchecker.log") as f:
    lines = f.readlines()

nvtake = []
for line in lines:
    line = json.loads(line.strip("\n"))
    package = line["name"]
    if line["event"] == "updated":
        version = line["version"]
        try:
            config = next(Path("config").rglob(f"{package}.yaml"))
            with open(config) as f:
                config = yaml.safe_load(f)
                flag = False if not "flag" in config else config["flag"]
                test = False if not "test" in config else config["test"]
            if test:
                github.get_repo('arch4edu/aur-auto-update').get_workflow("build.yml").create_dispatch('main', {'pkgbase': package, 'pkgver': version})
                print(f"Triggered build test for {package} {version}.")
            elif flag:
                print(f"TODO: Flag {package} on AUR.")
                # TODO: Flag the package on AUR
                # nvtake.append(package)
            else:
                print(f"No action is configured for {package}.")
                # TODO: Comment the error to AUR
        except:
            print(f"Failed to process update for {package}.")
            traceback.print_exc()
    elif line["event"] != "up-to-date":
        print(f"Failed to check update for {package}.")
        # TODO: Comment the error to AUR

with open("nvtake.txt", "w") as f:
    f.write(" ".join(nvtake))
