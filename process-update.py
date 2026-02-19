#!/bin/python
import json
import logging
import os
import requests
import sys
import traceback
from pathlib import Path

import toml
import yaml
from github import Github

token = toml.load("config/keyfile.toml")["keys"]["github.com"]
github = Github(token)
session = requests.Session()

with open("nvchecker.log") as f:
    lines = f.readlines()

nvtake = []
for line in lines:
    try:
        data = json.loads(line.strip("\n"))
    except json.JSONDecodeError:
        # 非 JSON 行（例如 nvchecker 的人类可读输出），跳过
        continue
    
    if not 'name' in data:
        print(f"Failed to process update for {data}.")
        continue
    
    package = data["name"]
    event = data.get("event", "")
    
    if event == "updated":
        version = data["version"]
        try:
            config = next(Path("config").rglob(f"{package}.yaml"))
            with open(config) as f:
                config = yaml.safe_load(f)
            flag = False if not "flag" in config else config["flag"]
            test = False if not "test" in config else config["test"]
            if session.get(f'https://aur.archlinux.org/pkgbase/{package}').status_code == 404:
                print(f"{package} doesn't exist on AUR.")
                continue
            if test:
                clean = 'false' if not "clean-up-ubuntu" in config else config["clean-up-ubuntu"]
                github.get_repo('arch4edu/aur-auto-update').get_workflow("build.yml").create_dispatch('main', {'pkgbase': package, 'pkgver': version, 'clean-up-ubuntu': clean})
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
    elif event == "up-to-date":
        # 包是最新的，无需操作
        pass
    else:
        # 其他事件（如错误、调试信息等）不视为失败
        pass

with open("nvtake.txt", "w") as f:
    f.write(" ".join(nvtake))
