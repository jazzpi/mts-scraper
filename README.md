# MTS Scraper

This is a scraper for the *Modultransfersystem* of TUB's *MOSES* system.

Since the *MTS* uses [PrimeFaces](https://www.primefaces.org), which is really
annoying to reverse engineer, this scraper uses Selenium to do the requests.

## Installation

TODO

## Running

``` sh
python -m mts_scraper -h
```

## Output

The scraper saves the results in a SQLite database. This database has the
following tables:

### Degree Programs

- ID (from MTS)
- Title
- Degree (MSc/BSc/etc.)

### Study Areas

- ID (only for unique identification)
- Title
- Parent ID (NULL if there is no parent study area)
- Degree Program ID

### Modules

- ID (from MTS)
- Version
- Title
- ECTS
- Exam type
- Details/Parts Fetched?
- Faculty
- Department
- Learning Outcomes
- Content

### Modules <> Study Areas

- Study area ID
- Module ID
- Module version

### Module Parts

- ID (only for unique identification)
- Title
- Language
- Type (VL/UE/SEM etc.)
- Turnus
- SWS
- Veranstaltungsnummer (if available)
- Module ID
- Module version

## Continuing a scraping session

If the database specified by `-d` exists, only modules (and module parts) that
are not already in it are fetched.

Modules are identified by ID and version (i.e., two modules with the same title
but different IDs count as two different modules, as do two modules with the
same ID but different versions).

The scraper executes these steps:

1. Check if the degree program exists. If no, start from scratch. If yes, we can
   be sure the study areas and their respective module lists have been fetched
   already.
2. Compile a list of all modules in any study area in the degree program (from
   the modules table) _that have not been fetched already_.
3. Sequentially fetch each unfetched module.
