---- MODULE SlotClaim ----
\* One slot, as change_claim sees it while slot_lock is held.
\* Acquire and Release are each one step because the lock in
\* change_claim covers the read and the write.
\* owner is the claim id in owner.json. 0 means the claim directory is absent.
\* live is not code. It is the id that matching releases have not archived.
\* memory[p] is the claim id that caller still has and may send again.

EXTENDS Naturals

CONSTANTS Procs, MaxId, CheckIds
VARIABLES owner, live, memory, nextId

vars == <<owner, live, memory, nextId>>
None == 0

Init ==
  /\ owner = None
  /\ live = None
  /\ memory = [p \in Procs |-> None]
  /\ nextId = 1

\* acquire_claim after read_claim returns nothing.
Acquire(p) ==
  /\ owner = None
  /\ nextId <= MaxId
  /\ owner' = nextId
  /\ live' = nextId
  /\ memory' = [memory EXCEPT ![p] = nextId]
  /\ nextId' = nextId + 1

\* change_claim returns "Slot is already claimed" and does not write.
AcquireBusy(p) ==
  /\ owner # None
  /\ UNCHANGED vars

\* release. CheckIds is the comparison owner["claimId"] != args.claim_id
\* before directory.rename. FALSE deletes that comparison.
Release(p) ==
  /\ memory[p] # None
  /\ \/ /\ CheckIds
        /\ \/ /\ owner = memory[p]
              /\ owner' = None
              /\ live' = None
           \/ /\ owner # memory[p]
              /\ UNCHANGED <<owner, live>>
     \/ /\ ~CheckIds
        /\ owner' = None
        /\ live' = IF memory[p] = live THEN None ELSE live
  /\ UNCHANGED <<memory, nextId>>

\* update writes phase, job ids, or note, and keeps the same claim id.
Update(p) ==
  /\ CheckIds
  /\ owner # None
  /\ owner = memory[p]
  /\ UNCHANGED vars

Next ==
  \E p \in Procs: Acquire(p) \/ AcquireBusy(p) \/ Release(p) \/ Update(p)

\* The directory's claim id is the claim that has not been released by that same id.
OwnerIsLive == owner = live

Spec == Init /\ [][Next]_vars
====
