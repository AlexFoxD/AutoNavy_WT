# Benchmark record

No benchmark has run yet. DXcam remains the required default. Configured capture FPS is not measured FPS. Receive timestamps cannot measure prior camera/OBS buffering or original render latency.

## Source and process rationale (for implementation)

The pinned DXcam 0.0.5 has a documented unbounded native-recovery path, established by local source inspection rather than device testing. Capture-only supervised process isolation is justified under CAP-03. Input release must occur before native termination waits. This is a safety tradeoff, not a claimed acceleration; benchmark IPC/copy costs honestly.
