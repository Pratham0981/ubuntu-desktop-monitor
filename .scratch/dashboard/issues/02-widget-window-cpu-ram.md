# 02: Widget window, live CPU/RAM

**What to build:** A compact, dark, semi-transparent GTK window showing CPU and RAM as bar + number, plus a CPU sparkline of the last ~5 min. Refreshes every 1 s from the Sampler. Launchable manually.

**Blocked by:** 01: Sampler: CPU + RAM snapshot

**Status:** ready-for-agent

- [ ] Window opens with CPU bar, RAM bar, numbers, sparkline
- [ ] Updates every 1 s without visible lag
- [ ] Dark, semi-transparent, compact
- [ ] Widget's own CPU/RAM overhead is low
- [ ] No network listener
