#!/bin/python
import logging
import os
import sys
import traceback
from pathlib import Path

import toml
import yaml

nvchecker_toml = {}

for i in Path("config").rglob("*.yaml"):
    if i.stem in ["example"]:
        continue
    try:
        with open(i) as f:
            config = yaml.safe_load(f)
            if i.stem == "__config__":
                if not 'GITHUB_TOKEN' in os.environ:
                    del config['keyfile']
            else:
                config = config["nvchecker"]
                config["user_agent"] = "nvchecker"
            nvchecker_toml[i.stem] = config
        print("Loaded", i)
    except:
        print("Failed to load", i)
        traceback.print_exc()

with open("nvchecker.toml", "w") as f:
    toml.dump(nvchecker_toml, f)
