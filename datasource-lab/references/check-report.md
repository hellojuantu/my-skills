# Mini CHECK report

Write the check time and the scope on the first line. In the next sentence, say how many items passed, how many failed, and which ones need action.

## Connection results

| Datasource | Lab | 8111 | 8112 | Notes |
| --- | --- | --- | --- | --- |
| One row for each MotherData instance or Lab manual instance | passed, failed, or not tested | Successful, failed, or not tested | Successful, failed, or not tested | Only a change, an error, or why it was not tested |

List the slots for the Console ports in this round. Fill a slot result when this round has Console Worker connection evidence. Otherwise write "not tested this round".

Note the time of an older result in Notes. Put detailed ids, times, and redacted evidence in a link.

## Disk and orphan datasources

- For macOS and for Colima, write free space, percent used, and the change since last time.
- List only Docker resources that changed, and orphan datasources that need action. Say what was left behind, why it belongs to a temporary environment, and how much space it can free. Put exact container ids, volumes, images, and references in the evidence.

## Actions waiting for confirmation

- **A.** Name the object, the effect, and how to roll it back. Set the state to waiting for confirmation, confirmed, or the retest result after the action.
- When nothing is waiting, write "none". Before you act, wait for the user to confirm by item number. Then check the live state again.
