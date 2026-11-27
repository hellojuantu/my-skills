#!/usr/bin/env python3
"""Sync current CloudCanal internal artifacts from a verified build to IDEA's Maven Local."""

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET


NS = {"m": "http://maven.apache.org/POM/4.0.0"}
CHECKSUMS = (".sha1", ".sha256", ".sha512", ".md5")


def properties(path):
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith(("#", "!")):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def current_versions(workspace):
    main = properties(workspace / "cloudcanal/gradle.properties")
    producers = [
        ("clougence-utils", "cg.utils.version", "cg.utils.version"),
        ("clougence-parser", "cg.parser.version", "cg.parser.version"),
        ("clougence-schema", "cg.schema.version", "cg.schema.version"),
        ("clougence-rdp", "cg.project.version", "cg.rdp.version"),
        ("clougence-drivers", "cg.drivers.api.version", "cg.lib.driver.version"),
    ]
    for repo, produced, consumed in producers:
        value = properties(workspace / repo / "gradle.properties")[produced]
        if value != main[consumed]:
            raise ValueError(f"{repo} produces {value}, but cloudcanal requires {main[consumed]}")
    rdp = properties(workspace / "clougence-rdp/gradle.properties")
    return [
        ("com.clougence", ("clougence-utils",), main["cg.utils.version"]),
        ("com.clougence", ("cg-parser-",), main["cg.parser.version"]),
        ("com.clougence", ("cg-schema-", "cg-engine-", "cg-dslparser-"), main["cg.schema.version"]),
        ("com.clougence", ("cg-driver-", "cg-drivers-"), main["cg.lib.driver.version"]),
        ("com.clougence.rdp", ("",), main["cg.rdp.version"]),
        ("com.clougence.cloudcanal", ("base-api", "base-metadata", "base-service", "llm-core"), main["cg.project.version"]),
        ("com.clougence.cloudcanal", ("cloudcanal-sdk",), main["cg.sdk.version"]),
        ("com.clougence.license", ("license-sdk",), rdp["cg.license.version"]),
    ]


def artifact_matches(artifact, names):
    for name in names:
        if name == "" or (name.endswith("-") and artifact.startswith(name)) or artifact == name:
            return True
    return False


def artifact_files(source, versions):
    coordinates = set()
    for pom in (source / "com/clougence").rglob("*.pom"):
        relative = pom.relative_to(source)
        group = ".".join(relative.parts[:-3])
        artifact, version = relative.parts[-3:-1]
        if any(group == g and artifact_matches(artifact, names) and version == v for g, names, v in versions):
            coordinates.add((group, artifact, version))
    for group, names, version in versions:
        if not any(g == group and artifact_matches(a, names) and v == version for g, a, v in coordinates):
            raise ValueError(f"Build repository has no {group}:{'/'.join(names) or '*'}:{version}; build this dependency first")

    pending = sorted(coordinates)
    files = set()
    while pending:
        group, artifact, version = pending.pop()
        directory = Path(*group.split(".")) / artifact / version
        stem = f"{artifact}-{version}"
        pom = directory / f"{stem}.pom"
        if not (source / pom).is_file():
            raise ValueError(f"Build repository is missing {pom}")
        root = ET.parse(source / pom).getroot()
        packaging = root.findtext("m:packaging", "jar", NS)
        if packaging != "pom" and not (source / directory / f"{stem}.jar").is_file():
            raise ValueError(f"Build repository is missing {stem}.jar")
        parent = root.find("m:parent", NS)
        if parent is not None:
            coordinate = tuple(parent.findtext("m:" + field, namespaces=NS) for field in ("groupId", "artifactId", "version"))
            if coordinate[0] and coordinate[0].startswith("com.clougence") and coordinate not in coordinates:
                coordinates.add(coordinate)
                pending.append(coordinate)
        for path in (source / directory).iterdir():
            if path.name.startswith(stem) and path.suffix in (".jar", ".pom", ".module"):
                files.add(path.relative_to(source))
        metadata = directory / "maven-metadata-local.xml"
        if (source / metadata).is_file():
            files.add(metadata)
    return sorted(files), len(coordinates)


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.close()
            temporary.chmod(0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="Maven Local from the verified isolated build")
    parser.add_argument("--target", type=Path, required=True, help="Actual Maven Local used by IDEA")
    parser.add_argument("--check", action="store_true", help="Compare hashes without writing files")
    args = parser.parse_args()
    source, target = args.source.expanduser().resolve(), args.target.expanduser().resolve()
    if source == target:
        parser.error("source and target must be different repositories")
    try:
        files, count = artifact_files(source, current_versions(args.workspace.expanduser()))
        changed = [path for path in files if not (target / path).is_file() or digest(source / path) != digest(target / path)]
        if args.check:
            for path in changed[:12]:
                print(f"OUTDATED {path}")
            print(f"{count} coordinates, {len(files)} files, {len(changed)} missing or different")
            return int(bool(changed))
        for relative in changed:
            destination = target / relative
            atomic_write(destination, (source / relative).read_bytes())
            for extension in CHECKSUMS:
                destination.with_name(destination.name + extension).unlink(missing_ok=True)
        for directory in {path.parent for path in files}:
            for marker in (target / directory).glob("*.lastUpdated"):
                marker.unlink()
            # These files are now local artifacts, not cached remote downloads.
            (target / directory / "_remote.repositories").unlink(missing_ok=True)
        for relative in files:
            if digest(source / relative) != digest(target / relative):
                raise ValueError(f"Hash mismatch after sync: {relative}")
        print(f"Synced {count} coordinates to {target}: {len(changed)} updated, {len(files) - len(changed)} unchanged; SHA-256 verified")
        return 0
    except (OSError, KeyError, ValueError, ET.ParseError) as error:
        parser.exit(1, f"Dependency sync failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
