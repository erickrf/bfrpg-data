# BFRPG Data

This repository contains scripts to extract structured data from the 
[Basic Fantasy RPG](https://basicfantasy.org/) books.

Its main purpose is to generate data compatible with Foundry VTT.

# Running Scripts

## Input File

The scripts were written for the [Field Guide Omnibus r4](https://basicfantasy.org/downloads.html) file and the [Core Rules 4th Edition](https://basicfantasy.org/downloads.html). 

Hopefully future versions will still be compatible.

## Scripts

- `extract_monsters.py` extracts a rough JSON file from the Field Guide
- `extract_monsters_core.py` extracts a similar JSON from the Core Rules
- To merge both extracted pdfs, use `jq -s 'map(keys) | .[0] - (.[0] - .[1])'  monsters-field-guide.json monsters-rulebook.json`
  - You might need to install `jq`.
- `split_monsters.py` splits multiple monsters that are grouped together in the Field Guide's descriptions and tables
  - The naming patterns used in the Field Guide is not so consistent, so it is not possible to automatize the splitting of monsters
    while still producing meaningful names like _Wolf, Winter_ and _Blade Spirit Common_. Therefore, I manually fixed some resulting 
    names in the file `monsters-split.json`.
- `postprocess_tables.py` reads the JSON file generated in the previous step and extracts monster stats from the tables.
  It takes care of spelling inconsistencies and warns about missing or extra stats. Its outputs are saved in the file `monsters-final-stats.json`.
- `create_foundry_monsters.py` creates individual JSON files that can later be imported to 
  Foundry with `fvtt`.


# License

Basic Fantasy RPG is distributed under the terms of the CC BY-SA 4.0 
International license.

Any data generated with this repository, out of the BF RPG books is also 
subject to the license.