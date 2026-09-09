# DXcam dependency assessment

Assessment read-only on 2026-09-09. Installed runtime remains DXcam0.0.5; no candidate version was installed or used for capture.

PyPI metadata reports0.3.0, Python>=3.10, and a CPython3.11 Windows x64 wheel uploaded2026-03-12. Runtime requirements are comtypes/numpy, with optional OpenCV and WinRT extras. This establishes published interpreter/platform support, not compatibility with this repository's complete pinned runtime or measured device behavior. [PyPI release metadata](https://pypi.org/pypi/dxcam/0.3.0/json)

Upstream main inspected at1e595ff55e57263c4b5d0414828f74104afa86f4 (2026-03-18). The changelog describes changes since0.0.5 to DXGI acquisition/recovery, timestamps, region copies, pacing and grab semantics, followed by processor/WinRT additions and mode-switch handling in0.3.0. These changes warrant adapter, lifecycle and packaging revalidation. [Versioned changelog](https://github.com/ra1nty/DXcam/blob/1e595ff55e57263c4b5d0414828f74104afa86f4/CHANGELOG.md)

Current documentation offers timestamp and borrowed-view APIs. Borrowed views may be overwritten by later captures; using them would still require ownership at publication. The current API's active-capture grab behavior differs from direct native polling. These documented APIs must not be used against installed0.0.5. [Versioned README](https://github.com/ra1nty/DXcam/blob/1e595ff55e57263c4b5d0414828f74104afa86f4/README.md)

Decision: retain0.0.5 for this modernization. The implemented adapter was characterized against its actual installed source and isolates documented shutdown risks. There is no same-machine live capture/latency evidence or candidate binary compatibility test to justify coupling this migration to an upgrade. This is a compatibility/scope decision, not a claim that0.0.5 is faster or more reliable. A future upgrade requires a separate environment, real lifecycle/mode-switch/restart tests, unchanged NumPy/OpenCV/native ABI checks, and equal-definition latency measurements. DXcam remains the default independently of this version decision.
