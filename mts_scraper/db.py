#!/usr/bin/env python3

import logging
import sqlite3

from .scraper import Module


class Database:
    """Database connection."""

    def __init__(self, db_file, log_level=logging.INFO):
        """Create the database connection.

        If the tables do not yet exist, they are created.
        """
        logging.getLogger(__name__).setLevel(log_level)
        self._logger = logging.getLogger(__name__ + ".Database")

        self._con = sqlite3.connect(db_file)
        self._create_tables()

    def __del__(self):
        self._con.close()

    def _create_tables(self):
        """Create the tables if they do not yet exist."""
        with self._con:
            self._con.execute(
                """CREATE TABLE IF NOT EXISTS programs (
                  id INTEGER PRIMARY KEY,
                  title TEXT NOT NULL,
                  degree TEXT NOT NULL
                );"""
            )
            self._con.execute(
                """CREATE TABLE IF NOT EXISTS study_areas (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  parent_id INTEGER,
                  program_id INTEGER NOT NULL,
                  FOREIGN KEY (program_id)
                    REFERENCES programs (id)
                    ON UPDATE NO ACTION
                    ON DELETE CASCADE
                );"""
            )
            self._con.execute(
                """CREATE TABLE IF NOT EXISTS modules (
                  id INTEGER,
                  version INTEGER,
                  title TEXT NOT NULL,
                  ects INTEGER NOT NULL,
                  exam_type TEXT NOT NULL,
                  details_fetched BOOLEAN DEFAULT FALSE,
                  faculty TEXT,
                  department TEXT,
                  learning_outcomes TEXT,
                  content TEXT,
                  PRIMARY KEY (id, version)
                );"""
            )
            self._con.execute(
                """CREATE TABLE IF NOT EXISTS modules_study_areas (
                  study_area_id INTEGER,
                  module_id INTEGER,
                  module_version INTEGER,
                  PRIMARY KEY (study_area_id, module_id, module_version),
                  FOREIGN KEY (study_area_id)
                    REFERENCES study_areas (id)
                    ON UPDATE NO ACTION
                    ON DELETE CASCADE,
                  FOREIGN KEY (module_id, module_version)
                    REFERENCES modules (id, version)
                    ON UPDATE NO ACTION
                    ON DELETE CASCADE
                );"""
            )
            self._con.execute(
                """CREATE TABLE IF NOT EXISTS module_parts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  language TEXT NOT NULL,
                  type TEXT NOT NULL,
                  turnus TEXT NOT NULL,
                  sws INTEGER NOT NULL,
                  number TEXT,
                  module_id INTEGER NOT NULL,
                  module_version INTEGER NOT NULL,
                  FOREIGN KEY (module_id, module_version)
                    REFERENCES modules (id, version)
                    ON UPDATE NO ACTION
                    ON DELETE CASCADE
                );"""
            )

    def program_exists(self, program_id):
        """Check if a degree program exists in the database."""
        row = self._con.execute("SELECT id FROM programs WHERE id = ?",
                                (program_id,)).fetchone()
        return row is not None

    def get_program_info(self, program_id):
        """Get degree type and title from the databse."""
        row = self._con.execute(
            "SELECT title, degree FROM programs WHERE id = ?", (program_id,)
        ).fetchone()
        return row

    def save_program(self, program_id, title, degree_type):
        """Save a degree program to the DB."""
        with self._con:
            self._con.execute("INSERT INTO programs VALUES (?, ?, ?);",
                              (program_id, title, degree_type))

    def save_area(self, area, program_id):
        """Save an area and its subareas to the DB.

        Also creates the area <-> module mapping in modules_study_areas.

        area must not have a parent.
        """
        first_id = self._con.execute(
            "SELECT max(id) from study_areas;").fetchone()
        if first_id[0] is None:
            first_id = 1
        else:
            first_id = first_id[0] + 1

        a_data = []
        ma_data = []
        areas = area.flatten()
        for i, a in enumerate(areas):
            if a.parent is None:
                parent_id = None
            else:
                parent_id = first_id + areas.index(a.parent)

            a_data.append((
                first_id + i,
                a.title,
                parent_id,
                program_id
            ))
            ma_data += [(first_id + i, m.id, m.version) for m in a.modules]

        with self._con:
            self._con.executemany(
                "INSERT INTO study_areas VALUES (?, ?, ?, ?);", a_data
            )
            self._con.executemany(
                "INSERT INTO modules_study_areas VALUES (?, ?, ?);", ma_data
            )

    def save_module(self, module):
        """Save a module to the DB."""
        self._logger.debug("Saving %s", str(module))
        with self._con:
            self._con.execute(
                """INSERT INTO modules (id, version, title, ects, exam_type)
                VALUES (?, ?, ?, ?, ?);""",
                (module.id, module.version, module.title, module.ects,
                 module.exam_type)
            )

    def unfetched_modules(self, program_id):
        """Get a list of modules in a program with unfetched details."""
        return self._con.execute(
            """\
            SELECT DISTINCT M.id, M.version, M.title FROM modules M
            INNER JOIN modules_study_areas I ON M.id = I.module_id AND M.version = I.module_version
            INNER JOIN study_areas A on A.id = I.study_area_id
            WHERE A.program_id = ? AND M.details_fetched = FALSE
            """,
            (program_id,)
        ).fetchall()

    def get_modules(self, identity_only=False):
        """Get an iterator over the modules from the database.

        If identity_only is True, only the id and version fields are
        set.
        """
        rows = self._con.execute("SELECT id, version FROM modules").fetchall()
        return map(lambda r: Module(*r), rows)
