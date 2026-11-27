---
name: lab-motherdata-deploy
description: Publish MotherData master to Mini, with an isolated Flyway check and the switch. Use it to upgrade MotherData, not for the weekly check.
---

# Publish master to Mini

## 1. Lock the source and the running state

Fetch `refs/heads/master` from [MotherData on Gitee](https://gitee.com/clougence/motherdata). Record the full commit SHA. Use a separate build directory. Read the checkout and deploy config already on Mini. Leave uncommitted edits in the workspace. Confirm that `master` on Mini can fast-forward to the target SHA.

When Mini has no Gitee credentials, fetch the target commit on Air or Pro, where an authorized Git session already exists. Transfer a bundle whose Git history you can verify. On Mini, verify the bundle before you fetch from it. Check the SHA. Confirm that the update is a fast-forward. Do not transfer Git credentials.

Confirm the current image, the shared network, and the persistent MySQL. Read them from `compose.yaml`, `start.sh`, and the running container. Save the health check, the application records, and the `flyway_schema_history` baseline. Find the newest migration in the target commit. Review that commit's edits to migrations after the current version. Compare the text of migrations that are already applied.

## 2. Build and test the migration

1. Build the frontend from the lockfile, as the target commit's project notes describe.
   Package the backend boot JAR and the external plugins with JDK 17.
   Run the frontend tests and the backend tests for that version.
   Record a failure in the test infrastructure apart from an application failure.
2. Build a `linux/arm64` image with `deploy/docker/Dockerfile` and the entry script in that same directory.
   Include `motherdata.jar`, `plugins/`, and `docker-entrypoint.sh` in the build context.
   Check the architecture of `RUNTIME_IMAGE`.
   Choose an ARM64 JRE compatible with Mini's already verified deployment.
   Put the short commit SHA in the image tag.
   Record the full SHA in `org.opencontainers.image.revision`.
   When you export the image on the build machine, record its SHA-256 first.
   After the file is on Mini, verify the file before you import it.
   Check the platform and the commit of the imported image.
3. To test the migration in isolation, start a temporary MySQL on its own Docker network on Mini.
   Give that MySQL temporary credentials.
   Record that instance under [Manual install on Mini](../../SKILL.md#manual-install-on-mini).
   Restore a test copy of `motherdata` onto that instance.
   That copy is the input for this migration check.
   Do not archive it as an extra rollback backup.
   Attach the new image.
   Let the application run Flyway when it starts.
   Confirm that every expected migration succeeded.
   Confirm that the frontend and the API respond.
   Match nodes, datasources, and install records to what the migration should produce.
   Delete only the temporary container and network this step created.

## 3. Switch and recheck

1. Confirm that the publish is authorized and that the live migration test passed.
   Confirm that no database task is still installing or cleaning up.
   Record the old image and the old config.
   Stop the MotherData application for the switch.
   When the user asks for a backup, create it as [Backups](../../../cloudcanal-dev-test/references/backups.md) describes.
   When a backup already exists, only move it and check it.
   Do not copy or append to that backup.
   Keep the deploy record in Mini's private directory.
   When a backup exists, record where the restore list is.
2. Update the image and the start script in the persistent Compose file.
   Recreate only the MotherData service with `docker compose up -d --no-deps --pull never motherdata`.
   Keep the shared network, the database connection settings, and the MySQL container that are already there.
3. From Air or Pro, open `http://mini:8765/`.
   Check the home page and `/actuator/health`.
   Check the key records and the latest successful Flyway version.
   Compare the running container's image SHA with the target commit.
   See that the shared CloudCanal infrastructure still responds.
   After those checks pass, fast-forward the Mini checkout to the published commit.
   Report the commit you published, the migration start and end versions, and the check result.
   When a backup exists, include where the restore list is.

If the switch fails, read the Flyway history and the database state first. Restore the old config and image only after you confirm the database has no incompatible change.

When the migration has already moved forward, or when you cannot tell the state, keep the evidence you have. If a database backup already exists, leave that backup as it is. Do not create another one on your own.

Before any restore that overwrites data, tell the user which objects it affects. Confirm the restore plan.
