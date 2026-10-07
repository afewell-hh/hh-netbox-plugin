"""In-container rescue owner for #716. Test-only; no Docker access.

Runs inside the scenario container, invoked by the host prover with a
registry of what that prover created. It verifies ownership against a
pinned process instance and signals only what both sides agree on.

Why pinned. `/proc/<pid>/...` resolves by PID number, so a PID recycled
between observation and signal lands the signal on a stranger. A
`/proc/<pid>` directory fd and a pidfd both pin the process *instance*:
once it exits, reads and signals fail ESRCH instead of silently describing
or hitting a different process. Measured in this lane before the design was
accepted.

Why two sides. An environment marker is a claim: any process can set one.
Ownership requires the host registry to say this scenario launched a child
with that nonce, and the live process to publish the same nonce from inside
itself. Either alone authorizes nothing.

There is no pkill, killall, prefix match or time-window match here, and no
signal to a PID that was not individually pinned and verified.
"""

from __future__ import annotations

import errno
import json
import os
import signal
import sys


UNKNOWN = "unknown"


def _read_at(dirfd, name):
    fd = os.open(name, os.O_RDONLY, dir_fd=dirfd)
    try:
        return os.read(fd, 65536)
    finally:
        os.close(fd)


def _start_ticks(stat_bytes):
    return stat_bytes.decode(errors="replace").rsplit(")", 1)[1].split()[19]


def _fdinfo_pid(pidfd):
    with open(f"/proc/self/fdinfo/{pidfd}", "r") as handle:
        for line in handle:
            if line.startswith("Pid:"):
                return line.split()[1]
    return None


def verify_and_signal(entry, send_signal):
    """Pin, verify every field, then signal through the pinned reference.

    Returns a report dict. Any failure to observe is UNKNOWN -- never a
    conclusion that the process is absent or that cleanup succeeded.
    """
    pid = entry.get("pid")
    report = {"nonce": entry.get("nonce"), "pid": pid, "verified": False,
              "signalled": False, "outcome": UNKNOWN, "reasons": []}
    if not isinstance(pid, int) or pid <= 1:
        report["reasons"].append("no usable pid in the publication")
        return report

    try:
        dirfd = os.open(f"/proc/{pid}", os.O_RDONLY | os.O_DIRECTORY)
    except OSError as exc:
        report["reasons"].append(f"cannot pin /proc/{pid}: {errno.errorcode.get(exc.errno)}")
        return report
    try:
        try:
            pidfd = os.pidfd_open(pid)
        except OSError as exc:
            report["reasons"].append(
                f"cannot pin pidfd: {errno.errorcode.get(exc.errno)}")
            return report
        try:
            if _fdinfo_pid(pidfd) != str(pid):
                report["reasons"].append("pidfd and pid disagree")
                return report

            try:
                stat = _read_at(dirfd, "stat")
                cmdline = _read_at(dirfd, "cmdline").replace(b"\x00", b" ").strip()
                environ = _read_at(dirfd, "environ")
            except OSError as exc:
                report["reasons"].append(
                    f"observation failed: {errno.errorcode.get(exc.errno)}")
                return report

            checks = {
                "start_ticks": _start_ticks(stat) == str(entry.get("start_ticks")),
                "nonce_in_environ": f"HH716_NONCE={entry.get('nonce')}".encode()
                                    in environ,
                "cmdline_matches": entry.get("expected_cmdline", "").encode()
                                   in cmdline,
            }
            report["checks"] = checks
            if not all(checks.values()):
                report["reasons"].append(
                    f"ownership mismatch: {[k for k, v in checks.items() if not v]}")
                return report

            report["verified"] = True
            if not send_signal:
                report["outcome"] = "verified_not_signalled"
                return report

            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                report["signalled"] = True
            except OSError as exc:
                report["reasons"].append(
                    f"signal failed: {errno.errorcode.get(exc.errno)}")
                return report

            # SIGKILL is asynchronous, and this container's PID 1 does not
            # reap orphans, so a killed process lingers as a zombie and the
            # pidfd still resolves. A zombie holds a PID slot and nothing
            # else: no CPU, no file handles, and it cannot spawn. Treating
            # it as "still present" would report a successful cleanup as a
            # failure -- the mirror of the #711 reaper defect, where
            # counting zombies reported four survivors for a tree that had
            # been killed.
            import time as _time

            deadline = _time.monotonic() + 10
            while _time.monotonic() < deadline:
                try:
                    signal.pidfd_send_signal(pidfd, 0)
                except OSError as exc:
                    # No process entry at all: the kernel has reaped it.
                    report["outcome"] = ("reaped" if exc.errno == errno.ESRCH
                                         else UNKNOWN)
                    return report
                try:
                    state = _read_at(dirfd, "stat").decode(
                        errors="replace").rsplit(")", 1)[1].split()[0]
                except OSError:
                    report["outcome"] = "reaped"
                    return report
                if state == "Z":
                    # Terminated but NOT reaped. No live execution, yet a
                    # process entry still exists and holds a PID slot. These
                    # are different facts and the evidence must not collapse
                    # them: "nothing is running" is not "nothing is there".
                    report["outcome"] = "terminated_zombie"
                    report["reasons"].append(
                        "terminated; process entry remains unreaped because "
                        "this container's PID 1 does not reap orphans")
                    return report
                _time.sleep(0.2)
            report["outcome"] = "still_present"
            return report
        finally:
            os.close(pidfd)
    finally:
        os.close(dirfd)


def main(argv=None):
    payload = json.loads(sys.stdin.read())
    send = bool(payload.get("send_signal"))
    reports = [verify_and_signal(entry, send)
               for entry in payload.get("entries", [])]
    print(json.dumps({"reports": reports}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
