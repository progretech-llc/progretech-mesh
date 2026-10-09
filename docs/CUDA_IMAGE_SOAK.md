# CUDA image execution for the first factory soak

Image generation defaults to the isolated comfyui-cuda Python environment on NVIDIA RTX5060Ti. The existing ROCm environment/core/models remain available; explicit FACTORY_IMAGE_DEVICE=rocm selects AMD. Video/music remain their previous routes and are not qualified for CUDA by this change.

Generation requires an owned factory-heavy-command ancestor lease, mounted PT_CONTEXT, an explicit allowed backend and at least11,000MiB free NVIDIA VRAM. An occupied cache is a scheduling condition; do not kill another active task to free it. Coordinate native completion/cache expiry or release only a known idle factory model under the owned lease. The generator fails closed instead of switching silently toCPU/AMD.

Intermediates and generated rasters stay under /mnt/pt-context/job-artifacts/factory-media/<job>. ComfyUI binds loopback and writes into the owned job. The router rejects artifacts outside that job. A graceful SIGINT then bounded termination/kill/reap sequence owns cleanup. No cloud inference, downloads of new model weights or production publication is performed by this code.

Actual qualification on2026-10-09: PyTorch2.14.1+cu130, CUDA13.0, compute capability12.0; CUDA512x512 matrix result correct. SDXL1024x1024 Euler ancestral16steps/fp32VAE completed in23.4seconds including startup; prompt execution12.4seconds. Raster is coherent but exactthreecards/ribbon/teal brief failed independent visual acceptance. This qualifies basic backend execution, not unattended design/brand fidelity. Explicit per-asset visual acceptance remains required.

Fifteen media routing/runtime tests include unmounted-storage refusal, unsupported backend rejection and foreign-artifact exclusion. Existing scope/owner-active capability gate remains. Runtime environment lock and actual GPU/kernel/render evidence: /mnt/pt-context/job-artifacts/factory-recovery-20261009/cuda-qualification/.

Use the existing media-capability-invoke wrapper with FACTORY_ADMISSION_ROLE=imagen and an explicit canonical FACTORY_PROJECT. Final accepted exports belong in /mnt/pt-context/deliverables/<task>; rejected draft stays evidence, not a product asset. Native Imagen memory compliance must be observed separately from this renderer execution.

Support: preserve run metadata/device/model/exit/visual decision; keep private prompts/customer images out of shared memory. Stop new dispatch during backend maintenance, verify actual native terminal state and admission, then resume. Keep prior script/launcher for rollback.

Primary compatibility reference: https://pytorch.org/blog/pytorch-2-12-release-blog/ . Real device/kernel tests govern this workstation qualification.
