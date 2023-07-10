import json
from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import InitVar, dataclass, field
from io import IOBase
from pathlib import Path
from typing import Optional


# BuildDBDict:
#   - [type]:
#       - [target]:
#           - [stamp]
#           - [dependency]: [stamp]

@dataclass(eq=True, order=True, frozen=True)
class BuildTarget:
    kind: str
    name: str

BuildStamp = Optional[str]


@dataclass
class BuildDB:
    targets: dict[BuildTarget, BuildStamp] = field(default_factory=dict)
    dependencies: defaultdict[BuildTarget, dict[BuildTarget, BuildStamp]] = field(default_factory=defaultdict(dict))

    def load(self, path):
        path = Path(path)
        with open(path, "r") as fp:
            try:
                build_db_json = json.load(fp)
            except json.JSONDecodeError:
                build_db_json = {}
        build_db_json = build_db_json if isinstance(build_db_json, dict) else {}

        self.targets = {}
        targets = build_db_json.get("targets", {})
        targets = targets if isinstance(targets, dict) else {}
        for target_id, stamp in targets.items():
            kind, target = target_id.split(":", 1)
            self.targets[BuildTarget(kind, target)] = stamp

        self.dependencies = defaultdict(dict)
        dependencies = build_db_json.get("dependencies", {})
        dependencies = dependencies if isinstance(dependencies, dict) else {}
        for target_id, deps in dependencies.items():
            target_kind, target = target_id.split(":", 1)
            for dep_id, stamp in deps.items():
                dep_kind, dep = dep_id.split(":", 1)
                self.dependencies[BuildTarget(target_kind, target)][BuildTarget(dep_kind, dep)] = stamp

    

@dataclass
class Build(AbstractContextManager):
    build_db_path: Path
    build_db: BuildDB = field(init=False, default_factory=BuildDB)

    def register_dependency(self, target: str, dependency: str):...

    def __post_init__(self):
        self.load_build_db()

    def load_build_db(self):

    def save_build_db(self):
        with open(self.build_db_path, "r+") as fp:
            json.dump(self.build_db_dict, fp)
