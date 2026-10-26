# 04: CPU temp + top processes

**What to build:** Widget shows CPU temperature and a short list of top processes by CPU/RAM. Missing temperature sensor shows "n/a" and never crashes.

**Blocked by:** 02: Widget window, live CPU/RAM

**Status:** done

- [x] CPU temp displayed when sensor exists
- [x] "n/a" shown when no sensor, no exception
- [x] Top processes list updates with the 1 s refresh
- [x] Snapshot test: missing temp sensor returns none, not an error
