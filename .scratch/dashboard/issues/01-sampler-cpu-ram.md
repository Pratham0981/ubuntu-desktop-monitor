# 01: Sampler: CPU + RAM snapshot

**What to build:** A Sampler module that, on one call, returns a plain snapshot of CPU load %, RAM used/total, and ~5 min of in-memory CPU history (1 s samples). No UI yet. This is the single test seam for the whole project.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Snapshot call returns CPU %, RAM used, RAM total, CPU history list
- [ ] CPU % within 0-100, RAM used <= total
- [ ] History capped at ~5 min, oldest dropped first
- [ ] Tests assert external snapshot behavior only
- [ ] Runs on Ubuntu with psutil, no extra deps
