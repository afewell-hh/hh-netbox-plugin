"""DIET-715 Phase B: RED contract for the runner lifecycle.

Scope. Tests and spec support ONLY. `DietTestRunner`, the DIET-643
autovacuum guard, CI workflows and production code are untouched in
this phase.

The contract these rows encode:

  * a database-free SimpleTestCase selection must run through the
    supported wrapper, execute real bodies, create no test database and
    make zero guard or ALTER calls;
  * every database-using selection must apply the guard to exactly the
    disposable targets Django actually prepared, and to nothing else.

Both halves matter. The first is the availability defect #715 exists
for; the second is the DIET-643 safety property, which must not be
traded away to fix the first.
"""
