from ethronsoft.gcspypi.utilities.queries import get_package_type
from ethronsoft.gcspypi.package.package import Package
from ethronsoft.gcspypi.exceptions import InvalidState
import json
import os
import shutil
import tarfile
import tempfile
import zipfile


class PackageBuilder(object):
    def __init__(self, raw_package):
        try:
            cwd = os.getcwd()
            tdir = tempfile.mkdtemp()
            os.chdir(tdir)
            typ = get_package_type(raw_package)
            if typ == "SOURCE":
                if ".zip" in raw_package:
                    with zipfile.ZipFile(raw_package, "r") as f:
                        self.__info = self.__extract_source(f)
                elif ".tar" in raw_package:
                    with tarfile.open(raw_package, "r") as f:
                        self.__info = self.__extract_source(f)
            elif typ == "WHEEL":
                with zipfile.ZipFile(raw_package, "r") as f:
                    self.__info = self.__extract_wheel(f)

            self.__info["type"] = typ
        finally:
            os.chdir(cwd)
            shutil.rmtree(tdir)

    def __seek_and_apply(self, zpfile, target, command):
        zpfile.extractall(".")
        for r, _, f in os.walk("."):
            for x in f:
                if target in x:
                    with open(os.path.join(r, x), "r") as target_file:
                        command(target_file)
                    return

    def __extract_source(self, zpfile):
        class InfoCmd(object):
            def __init__(self):
                self.metadata = {}

            def __call__(self, target):
                m = {}
                for line in target.readlines():
                    k, v = line.split(":")
                    m[k.upper().strip()] = v.strip()
                self.metadata["name"] = m["name".upper()]
                self.metadata["version"] = m["version".upper()]

        cmd = InfoCmd()
        self.__seek_and_apply(zpfile, "PKG-INFO", cmd)
        if not cmd.metadata:
            raise InvalidState("Could not find PKG-INFO")
        return {"name": cmd.metadata["name"],
                "version": cmd.metadata["version"],
                "requirements": self.__read_requirements(zpfile)}

    def __extract_wheel(self, zpfile):
        class InfoCmd(object):
            def __init__(self):
                self.metadata = {}

            def __call__(self, target):
                def __parse_package_name(package_name):
                    return package_name.replace(" ", "").replace("(", "").replace(")", "")

                m = {}
                requirements_key_name = "Requires-Dist"
                m[requirements_key_name.upper()] = []
                for line in target.readlines():
                    if ":" not in line:
                        break
                    k, v = line.replace(":", '@@@', 1).split('@@@')
                    if k == requirements_key_name:
                        m[k.upper().strip()].append(v.strip())
                    else:
                        m[k.upper().strip()] = v.strip()

                print(m)
                self.metadata["name"] = m["name".upper()]
                self.metadata["version"] = m["version".upper()]
                self.metadata["requirements"] = [__parse_package_name(r) for r in m[requirements_key_name.upper()]]

        cmd = InfoCmd()
        self.__seek_and_apply(zpfile, "METADATA", cmd)
        if not cmd.metadata:
            raise InvalidState("Could not find MATADATA")
        return cmd.metadata

    def __read_requirements(self, zpfile):
        class RequiresCmd(object):
            def __init__(self):
                self.requires = []

            def __call__(self, target):
                self.requires = [x for x in target.read().splitlines()]

        cmd = RequiresCmd()
        self.__seek_and_apply(zpfile, "requires", cmd)
        return cmd.requires

    def build(self):
        return Package(self.__info["name"],
                       self.__info["version"],
                       set(self.__info["requirements"]),
                       self.__info["type"])
