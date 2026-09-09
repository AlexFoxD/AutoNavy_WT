# Packaging investigation for M8

Source inspection (45fc36c), before implementation:

- `scripts/run.ps1` accepts only CheckOnly/NoPause and constructs a PowerShell string argument list; it cannot forward v2 CLI flags.
- `scripts/launcher.ps1:Ensure-SourceEnvironment` checks the entire hardware import set even for CheckOnly, runs installer on failure, emits installer success-stream output and then returns the Python path. The caller assigns the whole success stream to RuntimePath, which subsequently fails binding to string. This is the concrete root-cause hypothesis supported by baseline log, not an execution-policy problem.
- `Invoke-Launcher` always runs hardware preflight before deciding CheckOnly; default launch can offer driver installation/configuration. New v2 default must resolve/validate config without devices, not invoke automatic driver helpers. Explicit hardware preflight remains available separately and must not offer driver/system mutations during checks.
- `scripts/install.ps1` currently targets full pinned runtime and calls installation-only checker. Add explicit core/dev options, fail clearly on incompatible existing venv instead of deleting unrequested environments, and preserve runtime native/DLL resource checks.
- Build uses Nuitka root autonavy.py and explicitly includes start_prog and pyvjoy. Add package/config inclusion and keep exact native ABI resource. `-SkipCompile` test is ZIP assembly with synthetic executable, not a compiled-executable smoke.
- Existing CI publishes on release; v2 validation CI must not publish. Linux cannot import winreg or the bundled Windows extension, so split truly platform tests while retaining all pure tests.

Required regression commands: invoke source shim/package from a temporary working directory with absolute fixture/config paths; PowerShell run and batch launcher CheckOnly must return0 and not run installation, capture or vJoy. Replay flags must reach child unchanged; invalid flags/nonzero child code must survive wrapper. Core preflight cannot import dxcam (its module import initializes a native factory).

Keep full Windows native and device diagnostics as explicit manual commands and mark authored workflow/real executable/hardware checks NOT RUN until actually executed.

Build-tool availability checked read-only during M2: standard vswhere locator finds VC x86/x64 build tools at `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`. The local venv does not yet contain Nuitka; requirements-build.txt pins Nuitka4.2.1, ordered-set4.1.0, zstandard0.23.0. M8 should install these only in the worktree venv and attempt the actual available Windows build after migrating safe preflight/resources, using project-local caches. No compiler or global system installation is authorized or needed based on this probe. This discovery is not a successful build claim.

M2 build integration requirement: live capture uses multiprocessing spawn. M8 must add/verify multiprocessing.freeze_support at frozen executable entrypoints and explicitly include dynamically selected capture modules in Nuitka. Python spawn tests are not evidence that the packaged child invocation works. A packaged non-device spawn smoke is needed alongside packaged resource/CLI checks.
