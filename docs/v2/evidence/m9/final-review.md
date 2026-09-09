# Independent whole-branch review and final re-review

Reviewer: /root/m9_review. Original range: source45fc36cc4d173fb1e46eac2dcd1be3338157c500 to272be6f1c7cbbae903edbed8db89d3423c70bc2d. Final fix range:272be6f to e4d207e57fb9ade311a8df15ea27da3d218871f9. Review was read-only, with no suites, compilation, benchmarks, devices or old executables rerun. One resolver-only reproduction used a deterministic Test-Path stub and wrote no files.

Initial verdict was changes required for the P1 manifestless legacy build fallback in scripts/launcher.ps1. Related schema inspection identified unchecked legacy manifest CLI compatibility. The original implementation worker reproduced/fixed both aspects and verified the extracted final package; report ../M9-fix.md. Compact statements were classified as nonblocking style debt, not another functional finding.

Final reviewer verdict: **SPEC PASS. QUALITY PASS.** Both aspects are closed: manifestless legacy executables cannot override source or run from candidate-only roots; packaged execution requires integer schema1 and string launcher2.0.0 before dispatch, rejecting missing/legacy/unsupported/coerced metadata. Existing path containment, forwarding and valid-package behavior remain covered. No new actionable regression was found.

The reviewer inspected97 focused passes, scoped lint, nine actual final extracted-package commands and74 trapped guards. Frozen capture/planner exits remain0 with91 route points; compiled sources/executable are unchanged. Final whole-branch review approves completion and local branch/worktree retention, with no outstanding mandatory implementation finding. A25 and affected A32/A37 portions are satisfied; A39 independent review requirement is fulfilled. Coordinator final preservation and document reconciliation are separate recorded checks.

## Acceptance-to-caller review map

| Group | Actual callers and evidence reviewed |
|---|---|
| A01–A02 | Recorded isolated baseline, AUDIT source inventory, native characterization and preservation evidence. |
| A03–A08 | CLI/shims to Application.run, capture factory/ProcessCapture/ReplayCapture, FramePacket/LatestFrameSlot; import/ownership/restart/startup/cancel/cleanup tests. |
| A09–A12 | VisionPipeline.observe, FrameContext, TemplateRegistry, match_edges/detect_degree; real-asset synthetic math, channel/cache/crop and immutable preview tests. |
| A13–A14 | GeometrySnapshot/WindowsGeometry/source_geometry/LiveWindowGuard/Application._input_guard; negative origins, asymmetric OBS and queued-dispatch invalidation. |
| A15–A17 | TelemetryService._poll/snapshot/map_image and actual policy/navigation consumers; legacy facades issue no HTTP; immediate metadata failure invalidation, serial requests and TTL tests. |
| A18–A23 | Application.close/InputController/Pending/policy deadlines/WindowsBackend/OwnedVJoy; uncertain holds, release failures, late pause, pointer arbitration, queue deadline and canceled recovery tests. |
| A24–A25 | Actual scripted Application.run battle lifecycle, purchase pause and corrected source/packaged launchers. |
| A26–A28 | Navigation.tick through PlanningService/NativeJob/plan_encoded to real native adapter; ordered RouteCursor and separate PID states; stale results/dense turns/off-route progress/native tests. |
| A29–A30 | Supervised OBSSource, exact index/API, BGR validation/no fallback, native hang doubles and geometry parity. |
| A31–A32 | Validated settings, distribution-root paths, offline conflicts and guarded CLI/replay; final legacy/version launcher guards. |
| A33–A35 | Actual metrics/logging/preview callers, startup traceback cleanup and correctness-gated pipeline/capture benchmarks; measured rate shortfall/source latency limits disclosed. |
| A36–A37 | Core requirements/static readiness/platform guards/authored CI and actual Nuitka build3/resources/workers, final wrapper restaging and extracted verification. |
| A38–A39 | English operation/migration/manual checks, complete requirement map and final fix/re-review records. |

This approval does not certify live recognition, device identity, bindings/physical cleanup, driver recovery, game behavior, external/Linux CI or30Hz. The historical M8b test-isolation incident remains disclosed and is not a hardware PASS.
