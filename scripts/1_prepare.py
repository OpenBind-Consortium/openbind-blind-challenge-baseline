#!/usr/bin/env python
"""Step 1: prepare the apo protein and/or the ligands (give --pdb, --csv, or both).

Usage:
    python scripts/1_prepare.py --pdb apo.pdb --csv ligands.csv -o my_challenge
    python scripts/1_prepare.py --csv ligands.csv -o my_challenge --n_conformers 10 --cpus 8
    python scripts/1_prepare.py --pdb apo.pdb -o my_challenge

-o is the challenge directory; everything is written to <outdir>/prepared/:
    <pdb name>_prepared.pdb  cleaned + protonated protein (original residue numbering kept)
    ligands/<name>.sdf       one SDF per ligand with up to --n_conformers 3D conformers
"""
import argparse
import os
from multiprocessing import Pool
from pathlib import Path

import pandas as pd
from openmm.app import ForceField, PDBFile
from pdbfixer import PDBFixer
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.MolStandardize import rdMolStandardize
from tqdm import tqdm

# ---------------- standard settings ----------------
ID_COL = "Molecule_Name"
SMILES_COL = "SMILES"
N_CONFORMERS = 5
UFF_MAX_ITERS = 2000
PH = 7.4
SEED = 42
# ----------------------------------------------------


def prepare_protein(pdb, out, ph):
    fixer = PDBFixer(filename=str(pdb))
    fixer.missingResidues = {}
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(keepWater=False)   # waters, ions, crystallisation additives, ...
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(pH=ph, forcefield=ForceField("amber19-all.xml"))
    with open(out, "w") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f, keepIds=True)


def prepare_ligand(job):
    """Returns (name, n_generated, error). Never raises."""
    name, smiles, out, n_conf = job
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("invalid SMILES")
        mol = rdMolStandardize.LargestFragmentChooser().choose(mol)   # drop counter-ions
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = SEED
        params.useRandomCoords = True
        cids = list(AllChem.EmbedMultipleConfs(mol, n_conf, params))
        if not cids:
            return name, 0, None
        AllChem.UFFOptimizeMoleculeConfs(mol, maxIters=UFF_MAX_ITERS)
        mol.SetProp("_Name", name)
        writer = Chem.SDWriter(str(out))
        for cid in cids:
            writer.write(mol, confId=cid)
        writer.close()
        return name, len(cids), None
    except Exception as e:
        return name, 0, str(e)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pdb", help="apo protein structure to prepare")
    p.add_argument("--csv", help=f"ligands to prepare (columns: {ID_COL}, {SMILES_COL})")
    p.add_argument("-o", "--outdir", default=".", help="challenge directory; output goes to <outdir>/prepared/")
    p.add_argument("--n_conformers", type=int, default=N_CONFORMERS)
    p.add_argument("--cpus", type=int, default=1, help="0 or negative = all available cores")
    p.add_argument("--ph", type=float, default=PH)
    p.add_argument("--id_col", default=ID_COL)
    p.add_argument("--smiles_col", default=SMILES_COL)
    p.add_argument("--overwrite", action="store_true",
                   help="redo files that already exist (default: skip them)")
    a = p.parse_args()

    if not (a.pdb or a.csv):
        p.error("give --pdb, --csv, or both")
    out = Path(a.outdir) / "prepared"
    out.mkdir(parents=True, exist_ok=True)

    if a.pdb:
        protein_out = out / f"{Path(a.pdb).stem}_prepared.pdb"
        if protein_out.exists() and not a.overwrite:
            print(f"Protein already prepared, skipping ({protein_out}); use --overwrite to redo")
        else:
            print("Preparing protein...")
            prepare_protein(a.pdb, protein_out, a.ph)
            print(f"  -> {protein_out}")

    if a.csv:
        (out / "ligands").mkdir(exist_ok=True)
        df = pd.read_csv(a.csv)
        jobs = [(str(n), s, out / "ligands" / f"{n}.sdf", a.n_conformers)
                for n, s in zip(df[a.id_col], df[a.smiles_col])]
        n_total = len(jobs)
        if not a.overwrite:
            jobs = [j for j in jobs if not j[2].exists()]
        n_skipped = n_total - len(jobs)
        if n_skipped:
            print(f"Skipping {n_skipped} ligands that already exist; use --overwrite to redo")
        cpus = a.cpus if a.cpus > 0 else os.cpu_count()
        print(f"Preparing {len(jobs)} ligands ({a.n_conformers} conformers each) on {cpus} cpu(s)...")

        partial, failed = [], []
        with Pool(cpus) as pool:
            for name, n, err in tqdm(pool.imap_unordered(prepare_ligand, jobs), total=len(jobs)):
                if n == 0:
                    failed.append(name)
                    tqdm.write(f"FAILED  {name}: no conformers generated" + (f" ({err})" if err else ""))
                elif n < a.n_conformers:
                    partial.append(name)
                    tqdm.write(f"WARNING {name}: only {n}/{a.n_conformers} conformers generated")

        print(f"Done: {len(jobs) - len(failed)}/{len(jobs)} ligands prepared -> {out / 'ligands'}")
        print(f"  {len(partial)} with fewer conformers than requested, {len(failed)} failed")
        if failed:
            print("  failed:", ", ".join(sorted(failed)))


if __name__ == "__main__":
    main()