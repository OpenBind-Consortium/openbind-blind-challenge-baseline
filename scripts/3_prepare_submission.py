#!/usr/bin/env python
"""Step 3 (prepare submission): pick the best pose of each ligand and zip the complexes for submission.

Best pose per ligand:  gnina -> highest CNNscore,  smina -> lowest minimizedAffinity.

Usage:
    python scripts/3_prepare_submission.py -o my_challenge
    python scripts/3_prepare_submission.py -o my_challenge --engine smina

-o is the challenge directory (the same one used in steps 1 and 2). By default it reads
<outdir>/docked_<engine>/*.sdf and the single <outdir>/prepared/*_prepared.pdb
(override with --docked / --protein).

Writes into <outdir>/submission_<engine>/:
    <name>.pdb    protein + best pose of the ligand (residue name LIG), one file per compound
    scores.csv    best-pose scores, ranked best first
and zips the PDB files (only those) to <outdir>/submission_<engine>.zip, which is the file to submit.
"""
import argparse
import zipfile
from pathlib import Path

import pandas as pd
from rdkit import Chem, RDLogger
from tqdm import tqdm

RDLogger.DisableLog("rdApp.warning")   # gnina writes 3D poses tagged as 2D; harmless

# ---------------- standard settings ----------------
ENGINE = "gnina"
# score used to pick the best pose, and whether higher is better
SCORES = {"gnina": ("CNNscore", True), "smina": ("minimizedAffinity", False)}
# ----------------------------------------------------


def best_pose(sdf, score_name, higher_is_better):
    """Return (mol, score) of the best pose in a docked SDF, or None."""
    best = None
    for mol in Chem.SDMolSupplier(str(sdf), removeHs=False):
        if mol is None or not mol.HasProp(score_name):
            continue
        score = float(mol.GetProp(score_name))
        if best is None or (score > best[1] if higher_is_better else score < best[1]):
            best = (mol, score)
    return best


def write_complex(protein_pdb, mol, path):
    """Protein, followed by the ligand as one residue named LIG in the protein's last chain.

    The ligand is written without hydrogens: the challenge validator rebuilds the ligand from the PDB and
    compares it with the SMILES, which fails for ligands with explicit hydrogens on e.g. [nH] atoms.
    """
    with open(protein_pdb) as fh:
       lines = [l.rstrip("\n") for l in fh if l.startswith("ATOM")]

    last = lines[-1]
    chain, resnum, serial = last[21], int(last[22:26]) + 1, int(last[6:11])

    mol = Chem.RemoveHs(mol)
    counts = {}
    for atom in mol.GetAtoms():                      # unique atom names: C1, C2, N1, ...
        sym = atom.GetSymbol()
        counts[sym] = counts.get(sym, 0) + 1
        name = f"{sym}{counts[sym]}"
        info = Chem.AtomPDBResidueInfo()
        info.SetName(name[:4].ljust(4) if len(sym) == 2 else (" " + name[:3]).ljust(4))
        info.SetResidueName("LIG")
        info.SetChainId(chain)
        info.SetResidueNumber(resnum)
        info.SetIsHeteroAtom(True)
        atom.SetMonomerInfo(info)

    lines.append("TER")
    for l in Chem.MolToPDBBlock(mol).splitlines():
        if l.startswith("HETATM"):
            serial += 1
            lines.append(l[:6] + f"{serial:5d}" + l[11:])
    lines.append("END")
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--outdir", default=".", help="challenge directory; output goes to <outdir>/submission_<engine>/")
    p.add_argument("--docked", help="directory with docked SDFs (default: <outdir>/docked_<engine>)")
    p.add_argument("--protein", help="prepared protein pdb (default: the *_prepared.pdb in <outdir>/prepared)")
    p.add_argument("--engine", default=ENGINE, choices=list(SCORES), help="engine used for docking")
    a = p.parse_args()

    score_name, higher = SCORES[a.engine]
    root = Path(a.outdir)
    out = root / f"submission_{a.engine}"
    out.mkdir(parents=True, exist_ok=True)
    docked = Path(a.docked) if a.docked else root / f"docked_{a.engine}"
    protein = a.protein
    if not protein:
        found = sorted((root / "prepared").glob("*_prepared.pdb"))
        if len(found) != 1:
            raise SystemExit(f"Expected exactly one *_prepared.pdb in {root / 'prepared'}, found {len(found)}; use --protein")
        protein = found[0]

    rows, missing = [], []
    sdfs = sorted(docked.glob("*.sdf"))
    for sdf in tqdm(sdfs):
        best = best_pose(sdf, score_name, higher)
        if best is None:
            missing.append(sdf.stem)
            tqdm.write(f"WARNING {sdf.stem}: no poses with a {score_name} score (wrong --engine?)")
            continue
        mol, score = best
        write_complex(protein, mol, out / f"{sdf.stem}.pdb")
        rows.append({"id": sdf.stem, score_name: score})

    if not rows:
        raise SystemExit(f"No docked poses found in {docked}")
    df = pd.DataFrame(rows).sort_values(score_name, ascending=not higher)
    df.to_csv(out / "scores.csv", index=False)
    zip_path = root / f"submission_{a.engine}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in df["id"]:
            zf.write(out / f"{r}.pdb", arcname=f"{r}.pdb")
    print(f"Done: {len(df)}/{len(sdfs)} ligands -> {zip_path}")
    if missing:
        print("  no usable poses:", ", ".join(missing))


if __name__ == "__main__":
    main()