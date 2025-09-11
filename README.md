# BFRPG Data

This repository contains scripts to extract structured data from the 
[Basic Fantasy RPG](https://basicfantasy.org/) books.

Its main purpose is to generate data compatible with Foundry VTT.

# Running Scripts

## Input File

The scripts were written for the [Field Guide Omnibus r4](https://basicfantasy.org/downloads.html) file. Hopefully future versions will still be compatible.

## Scripts

- `extract_monsters.py` extracts a rough JSON file from the Field Guide
- `split_monsters.py` splits multiple monsters that are grouped together in the Field Guide's descriptions and tables
  - The naming patterns used in the Field Guide is not so consistent, so it is not possible to automatize the splitting of monsters
    while still producing meaningful names like _Wolf, Winter_ and _Blade Spirit Common_. Therefore, I manually fixed some resulting 
    names in the file `monsters-split.json`.

# License

Basic Fantasy RPG is distributed under the terms of the CC BY-SA 4.0 
International license.

Any data generated with this repository, out of the BF RPG books is also 
subject to the license.