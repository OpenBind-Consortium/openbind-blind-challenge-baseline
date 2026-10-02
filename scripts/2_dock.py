#!/usr/bin/env python
"""Step 2: dock prepared ligands into the prepared protein with gnina (default) or smina.

Usage:
    python scripts/2_dock.py --center 10.0 20.0 30.0 -o my_challenge
    python scripts/2_dock.py --center 10.0 20.0 30.0 -o my_challenge --engine smina --cpus 8 --exhaustiveness 16

    # on a cluster, just wrap it:
    sbatch --cpus-per-task=8 --wrap="python scripts/2_dock.py --center 10.0 20.0 30.0 -o my_challenge --cpus 8"

-o is the challenge directory (the same one used in step 1). By default it reads
<outdir>/prepared/<name>_prepared.pdb and <outdir>/prepared/ligands/*.sdf
(override with --protein / --ligands).

Ligands are docked one after the other; each one gets all --cpus cores.

Writes into <outdir>/docked_<engine>/ (so gnina and smina results never mix):
    <name>.sdf   all docked poses of one ligand (all starting conformers, with scores as SD properties)
    <name>.log   engine output
"""
import argparse
import os
import subprocess
from pathlib import Path

from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]

# ---------------- standard settings ----------------
ENGINE = "gnina"
SIZE = 20.0              # edge length of the (cubic) docking box in Angstrom
EXHAUSTIVENESS = 8
NUM_MODES = 8            # poses per starting conformer
SEED = 42
# ----------------------------------------------------


def engine_command(engine, exe):
    """Binary given by --exe, else software/<engine>/<engine>."""
    native = Path(exe) if exe else REPO / "software" / engine / engine
    if native.exists():
        return [str(native.resolve())]
    raise SystemExit(f"Could not find {engine}: run software/{engine}/download_{engine}.sh or pass --exe")


def find_protein(outdir):
    found = sorted((outdir / "prepared").glob("*_prepared.pdb"))
    if len(found) != 1:
        raise SystemExit(f"Expected exactly one *_prepared.pdb in {outdir / 'prepared'}, found {len(found)}; use --protein")
    return found[0]


def dock_one(job):
    """Returns (name, error or None)."""
    name, cmd = job["name"], job["cmd"]
    # gnina/smina choose the output format from the extension, so the temporary file must end in .sdf;
    # it lives in its own subfolder so an interrupted run never leaves a half-written file among the results
    tmp = job["out"].parent / "_tmp" / job["out"].name
    tmp.parent.mkdir(exist_ok=True)
    tmp.unlink(missing_ok=True)
    with open(job["out"].with_suffix(".log"), "w") as log:
        rc = subprocess.run(cmd + ["-o", str(tmp)], stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        return name, f"{job['engine']} exited with code {rc} (see {job['out'].with_suffix('.log')})"
    tmp.rename(job["out"])
    return name, None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--center", type=float, nargs=3, required=True, metavar=("X", "Y", "Z"),
                   help="docking box center (same coordinate frame as the protein)")
    p.add_argument("-o", "--outdir", default=".", help="challenge directory; output goes to <outdir>/docked_<engine>/")
    p.add_argument("--protein", help="prepared protein pdb (default: the *_prepared.pdb in <outdir>/prepared)")
    p.add_argument("--ligands", help="directory with prepared ligand SDFs (default: <outdir>/prepared/ligands)")
    p.add_argument("--engine", default=ENGINE, choices=["gnina", "smina"])
    p.add_argument("--exe", help="path to the engine binary (default: software/<engine>/<engine>)")
    p.add_argument("--size", type=float, default=SIZE)
    p.add_argument("--exhaustiveness", type=int, default=EXHAUSTIVENESS)
    p.add_argument("--num_modes", type=int, default=NUM_MODES)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--cpus", type=int, default=8, help="cores per ligand; 0 or negative = all available cores")
    p.add_argument("--overwrite", action="store_true", help="redo ligands that are already docked")
    a = p.parse_args()

    root = Path(a.outdir)
    out = root / f"docked_{a.engine}"
    out.mkdir(parents=True, exist_ok=True)
    cpus = a.cpus if a.cpus > 0 else os.cpu_count()
    base = engine_command(a.engine, a.exe)
    protein = (Path(a.protein) if a.protein else find_protein(root)).resolve()
    lig_dir = Path(a.ligands) if a.ligands else root / "prepared" / "ligands"

    common = [
        "-r", str(protein),
        "--center_x", str(a.center[0]), "--center_y", str(a.center[1]), "--center_z", str(a.center[2]),
        "--size_x", str(a.size), "--size_y", str(a.size), "--size_z", str(a.size),
        "--exhaustiveness", str(a.exhaustiveness), "--num_modes", str(a.num_modes),
        "--seed", str(a.seed), "--cpu", str(cpus),
    ]

    ligs = sorted(lig_dir.glob("*.sdf"))
    if not ligs:
        raise SystemExit(f"No ligand SDFs found in {lig_dir}")
    jobs = []
    for lig in ligs:
        dest = (out / lig.name).resolve()
        if dest.exists() and not a.overwrite:
            continue
        jobs.append({"name": lig.stem, "out": dest, "engine": a.engine,
                     "cmd": base + common + ["-l", str(lig.resolve())]})

    n_skipped = len(ligs) - len(jobs)
    if n_skipped:
        print(f"Skipping {n_skipped} ligands that are already docked; use --overwrite to redo")
    print(f"Docking {len(jobs)} ligands with {a.engine}, one at a time, {cpus} cpu(s) each...")

    failed = []
    for job in tqdm(jobs):
        name, err = dock_one(job)
        if err:
            failed.append(name)
            tqdm.write(f"FAILED  {name}: {err}")

    if (out / "_tmp").exists():
        for f in (out / "_tmp").glob("*"):
            f.unlink()
        (out / "_tmp").rmdir()
    print(f"Done: {len(jobs) - len(failed)}/{len(jobs)} ligands docked -> {out}")
    if failed:
        print("  failed:", ", ".join(sorted(failed)))


if __name__ == "__main__":
    main()