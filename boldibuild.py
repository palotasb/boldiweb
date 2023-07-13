import abc
import json
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

Target = str
Stamp = str
RegisterDependencyCallback = Callable[[Target], None]


logger = logging.getLogger(__name__)


@dataclass
class BuildDB:
    targets: defaultdict[Target, Stamp] = field(default_factory=lambda: defaultdict(Stamp))
    dependencies: defaultdict[Target, dict[Target, Stamp]] = field(
        default_factory=lambda: defaultdict(dict[Target, Stamp])
    )

    def load(self, path: Path):
        try:
            with open(path, "r") as fp:
                build_db_json = json.load(fp)
        except (json.JSONDecodeError, OSError):
            build_db_json = {}
        build_db_json = build_db_json if isinstance(build_db_json, dict) else {}

        self.targets = defaultdict(Stamp)
        self.targets.update(build_db_json.get("targets", {}))

        self.dependencies = defaultdict(dict)
        self.dependencies.update(build_db_json.get("dependencies", {}))

    def save(self, path: Path):
        with open(path, "w") as fp:
            build_db_json = {"targets": dict(self.targets), "dependencies": dict(self.dependencies)}
            json.dump(build_db_json, fp, indent=2)


class Handler:
    def can_handle(self, target: Target) -> bool:
        return False

    def stamp(self, target: Target) -> Stamp:
        return ""

    def stamps_match(self, a: Stamp, b: Stamp) -> bool:
        return a and b and a == b

    def build_impl(self, target: Target, register_dependency: RegisterDependencyCallback):
        raise NotImplementedError(f"{self} cannot build {target!r}")


class FileHandler(Handler):
    def can_handle(self, target: Target) -> bool:
        return True

    def stamp(self, target: Target) -> Stamp:
        try:
            s = Path(target).stat()
            # skipped: st_nlink, st_atime_ns because they don't indicate the file's changed
            return f"{s.st_mode} {s.st_ino} {s.st_dev} {s.st_uid} {s.st_gid} {s.st_size} {s.st_mtime_ns} {s.st_ctime_ns}"
        except OSError:
            return ""


@dataclass
class Build(abc.ABC):
    db_path: Path
    handlers: list[Handler] = field(init=False, default_factory=list)
    db: BuildDB = field(init=False, default_factory=BuildDB)

    def get_handler(self, target: Target) -> Handler:
        for handler in self.handlers:
            if handler.can_handle(target):
                return handler
        return Handler()

    def register_dependency(self, target: Target, dependency: Target):
        dep_handler = self.get_handler(dependency)
        self.db.dependencies[target][dependency] = dep_handler.stamp(dependency)

    def rebuild(self, target: Target, level: int = 0):
        logger.info(f"{' '*2*level}rebuild({target=!r})")
        handler = self.get_handler(target)
        self.db.dependencies.pop(target, None)
        handler.build_impl(target, partial(self.register_dependency, target))
        self.db.targets[target] = handler.stamp(target)

    def build(self, target: Target, level: int = 0):
        logger.info(f"{' '*2*level}build({target=!r})")
        handler = self.get_handler(target)
        old_stamp = self.db.targets[target]
        cur_stamp = handler.stamp(target)
        if not handler.stamps_match(old_stamp, cur_stamp):
            self.rebuild(target, level + 1)
            return

        for dep, old_dep_stamp in self.db.dependencies[target].items():
            if dep in self.db.targets:
                self.build(dep, level + 1)
            dep_handler = self.get_handler(dep)
            new_dep_stamp = dep_handler.stamp(dep)
            if not dep_handler.stamps_match(old_dep_stamp, new_dep_stamp):
                self.rebuild(target, level + 1)
                return

    def load_build_db(self):
        self.db.load(self.db_path)

    def save_build_db(self):
        self.db.save(self.db_path)
