# gnina installation

gnina is intentionally not committed to this repository. Download the precompiled binary with the
convenience script:

```bash
# downloads gnina 1.3.2 (the version used for the baseline); pass another version as the first argument
./software/gnina/download_gnina.sh
```

This saves the binary as `software/gnina/gnina` and makes it executable.

```text
software/gnina/
└── gnina
```

`scripts/2_dock.py` finds it there automatically. If gnina is installed somewhere else, point to it with
`--exe /path/to/gnina`.

## Checking the install

```bash
./software/gnina/gnina --version
```

The official gnina binary is linked against CUDA and cuDNN libraries (for example `libcudnn.so.9`) and will not
start without them, even if you only want to run on CPUs. On a GPU machine or cluster node they usually come from a
module or a CUDA installation, so load those first (or put them on `LD_LIBRARY_PATH`).

## Optional: Apptainer/Singularity image

If the native binary will not run on your system, you can pull a container image that bundles the libraries:

```bash
./software/gnina/pull_singularity.sh
```

`2_dock.py` does not use the image directly. To use it, write a small wrapper script that calls the container
and pass that script with `--exe`, for example:

```bash
#!/usr/bin/env bash
exec singularity exec --nv --bind /path/to/your/data software/gnina/gnina_singularity.sif gnina "$@"
```

Remember to bind the directory that holds your challenge directory, and drop `--nv` on machines without a GPU.