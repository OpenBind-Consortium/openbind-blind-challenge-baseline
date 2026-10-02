# OpenBind blind challenge baseline

This repository contains a simple docking baseline for the OpenBind blind challenges.

The workflow has three steps. First, `1_prepare.py` cleans up the protein and generates 3D conformers for the ligands. Then `2_dock.py` docks every ligand with [gnina](https://github.com/gnina/gnina) (the default) or [smina](https://sourceforge.net/projects/smina/). Finally, `3_prepare_submission.py` picks the best pose for each ligand and packs everything into a zip.

All three scripts work inside a single directory that you create for each run. You put your input files there, and each step writes its results into its own subfolder, so everything belonging to one run stays together:

```
OB_blind_challenge_1/
├── <ligands>.csv, <protein>.pdb      # your inputs
├── prepared/                         # written by step 1
├── docked_gnina/                     # written by step 2 (or docked_smina/)
├── submission_gnina/                 # written by step 3 (or submission_smina/)
└── submission_gnina.zip
```

Docking and submission results are kept in separate folders per engine, so you can run both gnina and smina on the same prepared inputs without them getting mixed up.

## Setting things up

You only need to do this once. Clone the repository and create the conda environment, which installs RDKit, OpenMM, PDBFixer, pandas and tqdm at pinned versions:

```bash
git clone https://github.com/OpenBind-Consortium/openbind-blind-challenge-baseline.git && cd openbind-blind-challenge-baseline
conda env create -f environment.yml
conda activate openbind-blind-challenge-baseline
```

The docking programs themselves aren't part of the repository, but there are small scripts to download them. You only need gnina or smina if you plan to dock with it:

```bash
./software/gnina/download_gnina.sh      # downloads gnina 1.3.2 (pass another version as the first argument)
./software/smina/download_smina.sh      # downloads the static smina build
```

The docking script looks for the programs in `software/gnina/gnina` and `software/smina/smina`. If you already have them installed somewhere else, you can point to them with `--exe /path/to/gnina`.

One thing to be aware of: the official gnina binary is built against CUDA and cuDNN and refuses to start if those libraries can't be found, even if you only want to run on CPUs. On a GPU machine or cluster node they usually come from a module or a CUDA installation. Running `./software/gnina/gnina --version` is a quick way to check that everything is in place.

## Worked example: blind challenge 1 (Zika virus NS2B-NS3 protease)

This section walks through a complete run for the first OpenBind blind challenge, <https://huggingface.co/spaces/openadmet/openbind-blind-challenge-1>.

### Getting the input files

Start by making a directory for the run (for example `OB_blind_challenge_1`), then download the blinded test set from the HuggingFace page, and a protein structure to dock into. For this baseline we dock into PDB entry [29HN](https://www.rcsb.org/structure/29HN).

### Step 1: preparing the protein and ligands

```bash
python scripts/1_prepare.py \
    --csv OB_blind_challenge_1/openbind-blind-challenge-1-TEST-BLINDED.csv \
    --pdb OB_blind_challenge_1/29HN.pdb \
    --outdir OB_blind_challenge_1 \
    --cpus 8
```

For the protein, the script removes waters and other heteroatoms, replaces non-standard residues, fills in missing atoms and adds hydrogens at pH 7.4.

For the ligands, it generates five 3D conformers from each SMILES and optimises them with the UFF forcefield. Each ligand is saved as its own file in `prepared/ligands/`.

Existing files are skipped on a rerun, use `--overwrite` if you've changed a setting and want everything redone.

### Step 2: docking

Once preparation has finished, you can start docking. The docking box is a 20 Å cube centered on the binding site. You give the center with `--center X Y Z`, in the coordinate frame of the prepared protein. For 29HN we use `12 17 13`.

To dock with gnina:

```bash
python scripts/2_dock.py \
    --center 12 17 13 \
    --outdir OB_blind_challenge_1 \
    --cpus 8
```

To dock with smina instead, add `--engine smina`:

```bash
python scripts/2_dock.py \
    --center 12 17 13 \
    --outdir OB_blind_challenge_1 \
    --engine smina \
    --cpus 8
```

The script picks up the prepared protein and ligands from `OB_blind_challenge_1/prepared/` automatically. If you want to dock different inputs, you can pass them explicitly with `--protein` and `--ligands`.

For each ligand you get an SDF in `docked_<engine>/` containing all poses from all of its starting conformers, with the scores stored as properties, plus a log file with the engine's output. Like step 1, the script skips ligands that are already docked, so if a run gets interrupted you can simply start it again.

### Step 3: preparing the submission

When docking is done, this step collects the results into a zip file:

```bash
python scripts/3_prepare_submission.py --outdir OB_blind_challenge_1
```

For smina results, add `--engine smina`.

For every ligand, the script looks through all of its docked poses and keeps the best one (gnina: highest CNNscore; smina: lowest minimizedAffinity). Each best pose is written as a protein-ligand complex in PDB format, named after the compound (e.g. `blind_challenge_001.pdb`), with the ligand as residue `LIG`. These files are in `submission_<engine>/` along with a `scores.csv` ranking the ligands, and they are zipped to `OB_blind_challenge_1/submission_<engine>.zip`, the file to submit.

## Changing the settings

Every script prints its options with `--help`. The defaults we use are as follows.

| Script | Setting | Default |
|--------|---------|---------|
| `1_prepare.py` | conformers per ligand (`--n_conformers`) | 5 |
| | protein pH (`--ph`) | 7.4 |
| | cores (`--cpus`) | 1 |
| `2_dock.py` | engine (`--engine`) | gnina |
| | box size (`--size`) | 20 Å |
| | exhaustiveness (`--exhaustiveness`) | 8 |
| | poses per conformer (`--num_modes`) | 8 |
| | random seed (`--seed`) | 42 |
| | cores per ligand (`--cpus`) | 8 |
| `3_prepare_submission.py` | engine (`--engine`) | gnina |

If you want to make use of a large machine, keep in mind that the docking search is split into roughly `--exhaustiveness` independent runs. Adding cores beyond that number may not make docking faster, so it's best to raise both together.

## Limitations

This is a baseline, and it keeps things simple on purpose. Ligands are used as written in the csv: counter-ions are removed, but there is no enumeration of protonation states or tautomers. The protein is docked without waters or cofactors, the binding site has to be given by hand, and poses are ranked only by the scores that gnina or smina provide.