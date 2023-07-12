import abc
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

Target = str
Stamp = str


@dataclass
class BuildDB:
    targets: defaultdict[Target, Stamp] = field(default_factory=lambda: defaultdict(Stamp))
    dependencies: defaultdict[Target, dict[Target, Stamp]] = field(
        default_factory=lambda: defaultdict(dict[Target, Stamp])
    )

    def load(self, path):
        path = Path(path)
        try:
            with open(path, "r") as fp:
                build_db_json = json.load(fp)
        except (json.JSONDecodeError, OSError):
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
            json.dump(
                {
                    "targets": dict(self.targets),
                    "dependencies": dict(self.dependencies),
                },
                fp,
                indent=2,
            )


RegisterDependencyCallback = Callable[[Target], None]


class Handler:
    def can_handle(self, target: Target) -> bool:
        return False

    def stamp(self, target: Target) -> Stamp:
        return ""

    def stamps_match(self, a: Stamp, b: Stamp) -> bool:
        return a and b and a == b

    def build_impl(self, target: Target, register_dependency: RegisterDependencyCallback):
        pass


class FileHandler(Handler):
    def stamp(self, target: Target) -> Stamp:
        try:
            s = Path(target).stat()
            # skipped: st_nlink, st_atime_ns because they don't indicate the file's changed
            return f"{s.st_mode} {s.st_ino} {s.st_dev} {s.st_uid} {s.st_gid} {s.st_size} {s.st_mtime_ns} {s.st_ctime_ns}"
        except OSError:
            return ""


class SourceFileHandler(FileHandler):
    def can_handle(self, target: Target) -> bool:
        return True


@dataclass
class Build(abc.ABC):
    db_path: Path
    handlers: list[Handler] = field(init=False, default_factory=list)
    db: BuildDB = field(init=False, default_factory=BuildDB)

    def __post_init__(self):
        self.load_build_db()

    def get_handler(self, target: Target) -> Handler:
        for handler in self.handlers:
            if handler.can_handle(target):
                return handler
        return Handler()

    def register_dependency(self, target: Target, dependency: Target):
        dep_handler = self.get_handler(dependency)
        self.db.dependencies[target][dependency] = dep_handler.stamp(dependency)

    def rebuild(self, target: Target) -> bool:
        handler = self.get_handler(target)
        old_stamp = self.db.targets.pop(target, None)
        _ = self.db.dependencies.pop(target, None)
        handler.build_impl(target, partial(self.register_dependency, target))
        self.db.targets[target] = handler.stamp(target)
        return old_stamp is not None and handler.stamps_match(old_stamp, self.db.targets[target])

    def build(self, target: Target) -> bool:
        print(f"build({target=!r})")
        handler = self.get_handler(target)
        old_stamp = self.db.targets[target]
        cur_stamp = handler.stamp(target)
        if not handler.stamps_match(old_stamp, cur_stamp):
            return self.rebuild(target)

        for dep, old_dep_stamp in self.db.dependencies[target].items():
            # Do I care if the dep is rebuilt and gets a new stamp? This happens if e.g.:
            #   trigger build 2a -> causes build 1a
            #   commit 1a to 1b change
            #   trigger build 1b (target 1 will new up-to-date stamp, but not 2a's dep 1)
            #   commit 1b to 1a change
            #   trigger build 2a -> causes build 1a
            #       1 was not up to date, build(1) returns False
            #       but stamp(1) matches old_dep_stamp
            #       and 2a was built with 1a, so I do NOT need to build it again
            # Ergo I don't care about dep's build results.
            _ = self.build(dep)

            dep_handler = self.get_handler(dep)
            new_dep_stamp = dep_handler.stamp(dep)
            if not dep_handler.stamps_match(old_dep_stamp, new_dep_stamp):
                return self.rebuild(target)

        # the earlier handler.stamps_match(old_stamp, cur_stamp) call returned True
        return True

    def load_build_db(self):
        self.db.load(self.db_path)

    def save_build_db(self):
        self.db.save(self.db_path)
