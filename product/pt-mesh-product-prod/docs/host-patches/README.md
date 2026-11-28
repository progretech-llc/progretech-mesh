# Imagen availability prerequisite

The workstation host must register `imagen` in both `control_center.mesh_runtime.ROLE_NAMES` and the factory workday controller's `ROLE` mapping. The local release includes the Mesh mapping. The accompanying patch records the reviewed change against the existing factory workday source (baseline 6dcf455).

Apply only against that source after checking the diff. Run `python3 -m unittest discover -s factory/workday -p 'test*.py'`. Restart the control-center bridge after active requests finish. The controller initializes the missing availability row without changing other roles or assigning Imagen scheduled work. A running model is not evidence of active agent work. Wake changes availability and may preload the configured model; it does not replay previous tasks.

Unknown or unavailable host status must not be presented as Awake. Web controls require a connected, verified, owned enrollment and the existing same-origin control relay. An offline host must reconnect before it can receive a wake request.
