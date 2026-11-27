---
name: lab-weekly-check
description: Run the Datasource Lab weekly read-only check and write the Mini CHECK report. Use it for the scheduled check, not to publish MotherData or install a database by hand.
---

# Datasource Lab weekly check

On every run, read [Datasource Lab](../../SKILL.md) and the workspace `AGENTS.md` first. Follow the weekly check and the disk check in that skill.

1. Start from the full MotherData list and the Lab ledger of manual instances on Mini.
   Check private connections and each CloudCanal slot.
   Archive a full candidate snapshot for each scope.
   Run authenticated read-only probes.
   Compare this round with the previous one.
   Cite existing slot Worker page evidence, and note when it was tested.
   Mark an entry with no page evidence this round as not tested this round.
   Skip **Test Connection** on a registered datasource during this read-only check.
   That action can update version metadata on a relational database.
2. In the same round, run `disk-status.py --weekly` on Mini.
   Check the macOS and Colima data disks, Docker containers, volumes, images, and slot database space.
   See whether a finished temporary environment left an orphan datasource or container.
   Check jobs, registrations, container state, and mount references.
   List the exact cleanup candidates and the space you expect to free.
   In Mini's private release directory, check old JARs, metadata database snapshots, and temporary release volumes.
   Use the slot's current publish record, its reservation, and its rollback record to see which of those are still in use.
   For a backup with no remaining reference, add its path, publish time, and freeable space to the cleanup candidates.
3. Write one report from the [Mini CHECK report](../../references/check-report.md) template.
   List datasources, Workers, disk, orphan resources, failures and recoveries, and each action waiting for confirmation.
   Include the check time, the scope, the blockers, and where the raw redacted evidence is.
4. The scheduled job only reads and archives evidence.
   Write each publish of the usable list, config change, deploy, restart, and cleanup into the report as its own item.
   Wait for the user to confirm each item.
   Before you run a confirmed scope, check the live state again.
   After you run it, add the verification result.
