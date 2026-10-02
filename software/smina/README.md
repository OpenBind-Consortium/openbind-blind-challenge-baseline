# smina installation

smina is intentionally not committed to this repository. Download the static Linux binary with the convenience
script:

```bash
./software/smina/download_smina.sh
```

This fetches `smina.static` from SourceForge, saves it as `software/smina/smina` and makes it executable. No
container or extra libraries are needed.

```text
software/smina/
+-- smina
```

`scripts/2_dock.py --engine smina` finds it there automatically. If smina is installed somewhere else, point to it
with `--exe /path/to/smina`.

## Checking the install

```bash
./software/smina/smina --help
```