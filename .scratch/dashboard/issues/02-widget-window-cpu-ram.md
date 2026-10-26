# 02: Widget window, live CPU/RAM

**What to build:** A compact, dark, semi-transparent GTK window showing CPU and RAM as bar + number, plus a CPU sparkline of the last ~5 min. Refreshes every 1 s from the Sampler. Launchable manually.

**Blocked by:** 01: Sampler: CPU + RAM snapshot

**Status:** done

- [x] Window opens with CPU bar, RAM bar, numbers, sparkline
- [x] Updates every 1 s without visible lag
- [x] Dark, semi-transparent, compact
- [x] Widget's own CPU/RAM overhead is low
- [x] No network listener
