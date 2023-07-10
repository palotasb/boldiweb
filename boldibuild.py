import abc
import json
from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import InitVar, dataclass, field
from io import IOBase
from pathlib import Path
from typing import Optional

Target = str
Stamp = str


@dataclass
class BuildDB:
    targets: defaultdict[Target, Stamp] = field(
        default_factory=lambda: defaultdict(Stamp)
    )
    dependencies: defaultdict[Target, dict[Target, Stamp]] = field(
        default_factory=lambda: defaultdict(dict[Target, Stamp])
    )

    def load(self, path):
        path = Path(path)
        with open(path, "r") as fp:
            try:
                build_db_json = json.load(fp)
            except json.JSONDecodeError:
                build_db_json = {}
        build_db_json = build_db_json if isinstance(build_db_json, dict) else {}

        self.targets = defaultdict(Stamp)
        self.targets.update(build_db_json.get("targets", {}))

        self.dependencies = defaultdict(dict)
        for target, targets_deps in build_db_json.get("dependencies", {}).items():
            self.dependencies[target] = targets_deps

    def save(self, path):
        path = Path(path)
        with open(path, "w") as fp:
            json.dump(vars(self), fp)


@dataclass
class Build(abc.ABC):
    db_path: Path
    db: BuildDB = field(init=False, default_factory=BuildDB)

    def __post_init__(self):
        self.load_build_db()

    @abc.abstractmethod
    def build_implementation(self, target: Target):
        raise NotImplementedError

    @abc.abstractmethod
    def stamp(self, target: Target) -> Stamp:
        raise NotImplementedError

    def stamps_match(self, a: Stamp, b: Stamp) -> bool:
        return a and b and a == b

    def register_dependency(self, target: Target, dependency: Target):
        self.db.dependencies[target][dependency] = self.stamp(dependency)

    def rebuild(self, target: Target) -> bool:
        old_stamp = self.db.targets.pop(target)
        _ = self.db.dependencies.pop(target)
        self.build_implementation(target)
        self.db.targets[target] = self.stamp(target)
        return self.stamps_match(old_stamp, self.db.targets[target])

    def build(self, target: Target) -> bool:
        old_stamp = self.db.targets[target]
        cur_stamp = self.stamp(target)
        if not self.stamps_match(old_stamp, cur_stamp):
            return self.rebuild(target)

        for dep, old_dep_stamp in self.db.dependencies[target].items():
            # Do I care if the target is rebuilt and gets a new stamp? This happens if e.g.:
            #   build 2a -> causes build 1a
            #   commit 1a to 1b change
            #   build 1b (1 itself will have new stamp and be up to date, but 2a's dep not)
            #   commit 1b to 1a change
            #   build 2a -> causes build 1a
            #       1 was not up to date, build(1) returns False
            #       but stamp(1) matches old_dep_stamp
            #       and 2a was built with 1a, so I do NOT need to build it again
            # Ergo I don't care about dep's build results.
            _ = self.build(dep)

            new_dep_stamp = self.stamp(dep)
            target_dep_stamps_match = self.stamps_match(old_dep_stamp, new_dep_stamp)
            if not target_dep_stamps_match:
                return self.rebuild(target)

        return self.stamps_match(cur_stamp, cur_stamp)

    def load_build_db(self):
        self.db.load(self.db_path)

    def save_build_db(self):
        self.db.save(self.db_path)
