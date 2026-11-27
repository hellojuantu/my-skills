# Sync IDEA dependencies after a version change

CloudCanal's Gradle projects and Product's Maven project meet through internal artifacts. After Git changes a version, the new coordinates have to be in the repository IDEA actually uses. Opening those repositories in IDEA does not switch every cross-build dependency over to source.

Read the local repository from IDEA's Maven settings and from the matching `settings.xml`. Confirm that Gradle `mavenLocal()` uses that same directory. Do not point the IDE at one round's temporary build repository.

When the artifacts are not built yet, build and publish them from a separate checkout at the matching SHA. Publish in dependency order. That order is Utils, Parser, License, RDP, Drivers, Schema, then CloudCanal. Publish only to the local repository. Do not run `dev_all_build.sh`. That script installs services on this machine. Do not switch the branch of a repository this change did not edit.

When this round already has a verified isolated Maven Local, and its versions match the development workspace, run this from the skill directory.

```sh
python3 scripts/sync_idea_dependencies.py \
  --workspace '<development workspace>' \
  --source '<isolated Maven Local>' \
  --target '<Maven Local IDEA uses>'
```

The script keeps internal artifacts at the workspace's current versions. It checks that Utils, Parser, Schema, RDP, and Drivers publish the version CloudCanal requires. It copies each JAR, sources JAR, POM, Gradle module, and local snapshot metadata, and it fills in internal parent POMs. It exits before it writes when a dependency series is missing, or when a selected POM or JAR is incomplete. It removes failed-download markers only for those coordinates. It does not copy the whole repository, and it does not create a backup. A later run skips a file whose SHA-256 already matches.

`--check` compares hashes and writes nothing. Artifact sync is not dependency resolution. Resolve the real files from the normal repositories.

- In CloudCanal, and in each separate Gradle project that failed, run `./gradlew -I '<skill directory>/scripts/check_idea_dependencies.gradle' checkIdeaDependencies`. The task resolves the main, test, and annotation-processor files. It exits non-zero when a file is missing, and it does not run tests. A plain `dependencies` report can print `FAILED` and still finish with `BUILD SUCCESSFUL`.
- In Product, check the compile dependencies for `sidecar` and for the modules this round changes. Use the Maven settings IDEA uses. Skip tests when you build.
- After resolution succeeds, reload the Gradle projects in IDEA and run **Reload All Maven Projects**. An unchanged POM can keep the old resolution. When you cannot see the UI, report the command-line result only.

When IDEA still shows a red mark, open Problems and read the coordinate. A default compile does not resolve plugins from a profile that is off. `output-proguard` is one of those profiles. It needs `proguard-maven-plugin` and `proguard-base`. Download a missing artifact with `maven-dependency-plugin:get -Dartifact=<group:artifact:version> -Dtransitive=false` and the Maven settings IDEA uses. Do not enable that release profile, and do not run it.

When resolution and the Gradle import both succeed, and the Gradle tree is still red, confirm the project has no running task. Close the project and open it again. Check the Gradle tree and Problems in IDEA.

A local repository fix does not mean the team repository can resolve the new version. For a release upgrade, publish the dependency artifacts first, then change the consumer version. A remote publish needs that authorization.
