# 03: Disk rows

**What to build:** Widget shows Ubuntu root `/` used/total/percent as a bar, plus a secondary line with whole physical SSD total and free (all partitions, dual-boot aware). Disk data refreshes every 30 s. Sampler snapshot extended accordingly.

**Blocked by:** 02: Widget window, live CPU/RAM

**Status:** done

- [x] Root fs bar with used/total/percent
- [x] Whole-SSD total/free line covering all partitions
- [x] Disk refresh every 30 s, CPU/RAM stays 1 s
- [x] Snapshot test: disk values consistent with root fs numbers
