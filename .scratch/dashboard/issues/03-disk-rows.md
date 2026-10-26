# 03: Disk rows

**What to build:** Widget shows Ubuntu root `/` used/total/percent as a bar, plus a secondary line with whole physical SSD total and free (all partitions, dual-boot aware). Disk data refreshes every 30 s. Sampler snapshot extended accordingly.

**Blocked by:** 02: Widget window, live CPU/RAM

**Status:** ready-for-agent

- [ ] Root fs bar with used/total/percent
- [ ] Whole-SSD total/free line covering all partitions
- [ ] Disk refresh every 30 s, CPU/RAM stays 1 s
- [ ] Snapshot test: disk values consistent with root fs numbers
