#!/usr/bin/env python3
"""Selenium-based scraper for MTS."""

import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Scraper:
    """Selenium-based scraper for MTS."""

    MTS_BASE = "https://moseskonto.tu-berlin.de/moses/modultransfersystem/"
    PROGRAM_SEARCH = MTS_BASE + "studiengaenge/suchen.html"
    PROGRAM_SEARCH_FORM_ID = "j_idt99"
    SHOW_COMBINED = MTS_BASE + "studiengaenge/anzeigenKombiniert.html"
    SHOW_MODULE = MTS_BASE + "bolognamodule/beschreibung/anzeigen.html"

    def __init__(self, log_level=logging.INFO, throttle_delay=2.0):
        """Create the Selenium WebDriver."""
        logging.getLogger(__name__).setLevel(log_level)
        self._logger = logging.getLogger(__name__ + ".Scraper")

        option = webdriver.ChromeOptions()
        option.add_argument("--incognito")
        self.browser = webdriver.Chrome(options=option)
        self._last_request = 0
        self._throttle_delay = throttle_delay
        self.combined_form_id = None
        self.study_area_id = None

    def __del__(self):
        """Close the Selenium WebDriver."""
        self.browser.close()

    def _throttle_request(self):
        """Check rate limit and (potentially) wait."""
        diff = self._throttle_delay - (time.time() - self._last_request)
        while diff > 0:
            self._logger.debug("Waiting %f seconds", diff)
            time.sleep(diff)
            diff = self._throttle_delay - (time.time() - self._last_request)
        self._last_request = time.time()

    def _load_page(self, url, wait_for, timeout=10.0):
        """Load a page and wait for it to load.

        url -- URL of page to load
        wait_for -- See _wait_for()
        timeout -- See _wait_for()
        """
        self._throttle_request()
        self.browser.get(url)
        self._wait_for(wait_for, timeout)

    def _wait_for(self, wait_for, timeout=10.0):
        """Wait for a condition.

        wait_for -- A tuple defining the condition to wait for.
                    The first element defines the type of condition, the
                    second defines the condition itself.
                    Possible types:
                    "cond" -> Condition from support.expected_conditions
                    "vis_css" -> CSS selector of an element that should
                                be visible
                    "vis_xpath" -> XPath of an element that should be
                                   visible
                    "vis_id" -> ID of an element that should be visible
        timeout -- Maximum time to wait for the condition. If this is
                   exceeded, a TimeoutException is raised.
        """
        if wait_for[0] == "cond":
            until = wait_for[1]
        elif wait_for[0] == "vis_css":
            self._logger.debug("Waiting for CSS selector " + wait_for[1])
            until = EC.visibility_of_element_located((
                By.CSS_SELECTOR, wait_for[1]
            ))
        elif wait_for[0] == "vis_xpath":
            self._logger.debug("Waiting for XPath " + wait_for[1])
            until = EC.visibility_of_element_located((
                By.XPATH, wait_for[1]
            ))
        elif wait_for[0] == "vis_id":
            self._logger.debug("Waiting for ID " + wait_for[1])
            until = EC.visibility_of_element_located((By.ID, wait_for[1]))
        else:
            raise RuntimeError("Unknown wait-for " + repr(wait_for))

        WebDriverWait(self.browser, timeout).until(until)

    def _click_at_element(self, element):
        """Click at the position of an element.

        Useful if the click handler isn't on the element itself, so
        element.click() doesn't work.
        """
        ActionChains(self.browser).move_to_element(element).click().perform()

    def find_programs(self, query):
        """Find degree programs.

        Returns a list of programs. Each program is a dict of the form
        {
          "name": PROGRAM_NAME,
          "degree": DEGREE (MSc/BSc etc.),
          "id": PROGRAM_ID,
        }
        """
        self._load_page(
            self.PROGRAM_SEARCH,
            ("vis_css", f"#{self.PROGRAM_SEARCH_FORM_ID} a.btn.btn-default")
        )

        search_box = self.browser.find_element_by_css_selector(
            f"#{self.PROGRAM_SEARCH_FORM_ID} input[type=text]")

        self._throttle_request()
        search_box.send_keys(query + Keys.ENTER)
        self._wait_for(
            ("vis_css", f"#{self.PROGRAM_SEARCH_FORM_ID} table.table")
        )

        table = self.browser.find_element_by_css_selector(
            f"#{self.PROGRAM_SEARCH_FORM_ID} table.table")
        programs = []
        rows = table.find_elements_by_tag_name("tr")[1:]  # Skip header row
        for row in rows:
            cells = row.find_elements_by_tag_name("td")
            link = cells[3].find_element_by_tag_name("a")
            pid = self._extract_combined_id(link.get_attribute("href"))
            programs.append({
                "name": cells[0].text,
                "degree": cells[1].text,
                "id": pid,
            })

        return programs

    @staticmethod
    def _extract_combined_id(href):
        """Extract the ID from an `anzeigenKombiniert.html` link."""
        return int(href.rsplit("=", 1)[1])

    def load_program(self, combined_id):
        """Load the page for a degree program."""
        self._load_page(
            f"{self.SHOW_COMBINED}?id={combined_id}",
            ("vis_css", "table[role=treegrid]")
        )
        self.combined_form_id = self.browser.find_element_by_css_selector(
            "main form"
        ).get_attribute("id")
        self.study_area_id = self.combined_form_id + ":studiengangsbereich"

    def get_program_info(self):
        """Get degree title and type from the currently loaded page.

        You should call load_program() before calling this function.
        """
        h1 = self.browser.find_element_by_css_selector("main h1")
        children = h1.find_elements_by_css_selector("*")
        children_text = "".join((child.text for child in children))
        title = h1.text.replace(children_text, "", 1)
        overview_table = self.browser.find_elements_by_css_selector(
            f"main form table"
        )[0]
        degree = overview_table.find_element_by_css_selector(
            "tr:first-of-type td:nth-of-type(2)"
        ).text

        return (title, degree)

    def get_areas(self):
        """Get study areas from the currently loaded page.

        You should call load_program() before calling this function.

        Returns a list of top-level areas, which may contain subareas.
        Each area is of the format

        {
            "element": web_element_for_tr,
            "title": title,
            "subareas": [area_1, area_2, ...]
        }
        """
        self._expand_treegrid("table[role=treegrid] tbody")

        rows = self.browser.find_elements_by_css_selector(
            "table[role=treegrid] tbody tr")

        if not rows:
            self._logger.warning("No areas found?!")
            return []

        areas = []
        for row in rows:
            # We need to figure out the parent to append to. Unless
            # we're at top level, this is always the last area at the
            # level above.
            indents = row.find_elements_by_css_selector(
                "td:first-child span.ui-treetable-indent"
            )
            level = len(indents)
            above = areas
            parent = None
            for i in range(level):
                parent = above[-1]
                above = above[-1].subareas

            area = Area(row, parent)
            above.append(area)

        return areas

    def _expand_treegrid(self, tbody_sel):
        """Expand a treegrid table.

        tbody_sel -- CSS selector for the tbody element.
        """
        new_expansions = True
        while new_expansions:
            new_expansions = False
            rows = self.browser.find_elements_by_css_selector(
                tbody_sel + " tr")
            self._logger.debug("Expanding treegrid with %d rows", len(rows))
            for row in rows:
                # Check if the row is already expanded
                if row.get_attribute("aria-expanded") == "true":
                    continue

                # All rows have a toggler, but it's hidden for
                # non-expandable ones
                toggler = row.find_element_by_css_selector(
                    ".ui-treetable-toggler")
                if "visibility: hidden" in toggler.get_attribute("style"):
                    continue

                new_expansions = True

                # Expanding creates a POST request, so we should throttle
                self._throttle_request()
                self._click_at_element(toggler)
                id = row.get_attribute("id").replace(":", r"\:")
                self._wait_for((
                    "vis_css",
                    f"#{id}[aria-expanded=true]"
                ))

    def get_area_modules(self, area):
        """Get modules for an area (not including subareas!)."""
        self._throttle_request()
        el = self.browser.find_element_by_id(self.study_area_id)
        self._click_at_element(area.element)
        # When the study area element is clicked (not necessarily
        # changed), the study area element is removed and a new one is
        # added.
        self._wait_for((
            "cond",
            EC.staleness_of(el)
        ))
        self._wait_for(("vis_id", self.study_area_id))

        rows = self.browser.find_elements_by_css_selector(
            "#" + self.study_area_id.replace(":", r"\:") + " tbody tr"
        )

        modules = []
        for i, row in enumerate(rows):
            cells = row.find_elements_by_tag_name("td")
            # There may be column-spanning rows like "no modules available"
            if len(cells) == 8:
                mod = Module(
                    int(cells[1].text),
                    int(cells[2].text),
                    cells[0].text,
                    int(cells[3].text),
                    cells[5].text
                )
                modules.append(mod)
            else:
                self._logger.info("No modules in row #%d for area %s", i,
                                  area.title)
        return modules

    def get_module_details(self, module_id, module_version):
        """Get module details."""
        self._load_page(
            f"{self.SHOW_MODULE}?number={module_id}&version={module_version}",
            ("vis_xpath", "//*[contains(@id,'BoxLiteratur')]")
        )
        details = self._get_module_page_details(module_id, module_version)
        module_parts = self._get_module_parts(module_id, module_version)
        return details, module_parts

    @staticmethod
    def _starts_with_any(haystack, needles):
        """Return True if the haystack start with any of the needles."""
        for n in needles:
            if haystack.startswith(n):
                return True
        return False

    def _remove_label_text(self, element, row, col, expected_text,
                           log_label=None, module_id=None,
                           module_version=None):
        """Remove the label's text from the header information.

        element -- The header information table element
        row -- The row number (starting at 1)
        col -- The column number (starting at 1)
        expected_text -- an iterable of the possible label text starts
                         we might expect. If the label's text matches
                         none of these, a warning will be logged.
        log_label -- Type of label, only used for logging
        module_id -- Only used for logging
        module_version -- Only used for logging
        """
        col = element.find_element_by_css_selector(
            f".row:nth-of-type({row}) [class^='col']:nth-of-type({col})")
        label = col.find_element_by_tag_name("label").text
        if not self._starts_with_any(label, expected_text):
            self._logger.warn("%s label for (ID=%d, V=%d) was %s", log_label,
                              module_id, module_version, label)
        return col.text.replace(label, "", 1).strip()

    def _remove_section_header(self, element, expected_header,
                               log_section=None, module_id=None,
                               module_version=None):
        """Remove a section's header from the section text.

        element -- The section element
        expected_header -- an iterable of the possible header starts we
                           might expect. If the header's text matches
                           none of these, a warning will be logged.
        log_section -- Type of section, only used for logging
        module_id -- Only used for logging
        module_version -- Only used for logging
        """
        header = element.find_element_by_css_selector("h1,h2,h3,h4,h5,h6").text
        if not self._starts_with_any(header, expected_header):
            self._logger.warn("%s section header for (ID=%d, V=%d) was %s",
                              log_section, module_id, module_version, header)
        return element.text.replace(header, "", 1).strip("\n\r")

    def _get_module_page_details(self, module_id=None, module_version=None):
        """Get the details we need from the (loaded) module page.

        This includes faculty, department, learning outcomes and
        content.

        module_id and module_version are only used for logging purposes
        and can be left at None.
        """
        header_info = self.browser.find_element_by_xpath(
            "//*[contains(@id,'BoxKopfinformationen')]")

        faculty = self._remove_label_text(
            header_info, 1, 3, ("Faculty", "Fakultät"),
            "Faculty", module_id, module_version
        )
        department = self._remove_label_text(
            header_info, 2, 2, ("Area of expertise", "Fachgebiet"),
            "Department", module_id, module_version
        )

        header_info_sel = "#" + \
            header_info.get_attribute("id").replace(":", r"\:")

        lo_el = self.browser.find_element_by_css_selector(
            f"{header_info_sel} + .row")
        learning_outcomes = self._remove_section_header(
            lo_el, ("Learning Outcomes", "Lernergebnisse"),
            "Learning Outcomes", module_id, module_version
        )

        content_el = lo_el.find_element_by_css_selector(
            f"{header_info_sel} + .row + .row")
        content = self._remove_section_header(
            content_el, ("Content", "Lehrinhalte"),
            "Content", module_id, module_version
        )

        return {
            "faculty": faculty,
            "department": department,
            "learning_outcomes": learning_outcomes,
            "content": content
        }

    def _get_module_parts(self, module_id=None, module_version=None):
        """Get the module parts from the (loaded) module page.

        module_id and module_version are only used for logging purposes
        and can be left at None.
        """
        parts_box = self.browser.find_element_by_xpath(
            "//*[contains(@id,'BoxBestandteile')]")

        header_row = parts_box.find_element_by_css_selector(".row:nth-of-type(1)")
        if not header_row.find_elements_by_css_selector("h1,h2,h3,h4,h5,h6"):
            self._logger.warn(
                "Module parts header row for (ID=%d, V=%d) did not contain"
                "header! (text instead: %s)", module_id, module_version,
                header_row.text
            )

        rows = parts_box.find_elements_by_css_selector(
            ".row:nth-of-type(2) table.table tr:not(:first-of-type)")

        parts = []
        for row in rows:
            cols = row.find_elements_by_tag_name("td")
            if len(cols) != 6:
                self._logger.warn(
                    "Module part for (ID=%d, V=%d) has weird length %d! "
                    "(text: %s)", module_id, module_version, len(cols),
                    row.text
                )
                continue
            title = cols[0].text.strip()
            type_ = cols[1].text.strip()
            number = cols[2].text.strip()
            turnus = cols[3].text.strip()
            language = cols[4].text.strip()
            sws = cols[5].text.strip()
            parts.append(ModulePart(title, language, type_, turnus, sws, number))

        return parts


class Area:
    """A study area from the combined page."""

    def __init__(self, element, parent):
        """Create the area for a tr from the combined page."""
        self._logger = logging.getLogger(__name__ + ".Area")
        self.element = element
        self.parent = parent
        self.title = element.find_element_by_css_selector(":first-child").text
        self.subareas = []
        self.modules = []

    def __str__(self):
        if self.subareas:
            return self.title + " -> [" + \
                ", ".join(map(str, self.subareas)) + "]"
        else:
            return self.title

    def __repr__(self):
        return str(self)

    def fetch_modules(self, scraper, include_subareas=True):
        """Fetch the modules for this area.

        scraper -- The scraper to use for fetching
        include_subareas -- Fetch the modules for all subareas too
        """
        self._logger.debug("Fetching modules for %s", self.title)
        self.modules = scraper.get_area_modules(self)
        if include_subareas:
            for area in self.subareas:
                area.fetch_modules(scraper, True)

    def flatten(self):
        """Return a pre-order list of this area and its subareas."""
        areas = [self]
        for area in self.subareas:
            areas += area.flatten()
        return areas


class Module:
    """A module to fetch."""

    def __init__(self, id, version, title=None, ects=None, exam_type=None):
        self.id = id
        self.version = version
        self.title = title
        self.ects = ects
        self.exam_type = exam_type

    def __str__(self):
        return f"{self.title} (ID={self.id}, V={self.version})"

    def __hash__(self):
        return hash((self.id, self.version))

    def __eq__(self, other):
        return self.id == other.id and self.version == other.version


class ModulePart:
    """A module part."""

    def __init__(self, title, language, type_, turnus, sws, number):
        self.title = title
        self.language = language
        self.type_ = type_
        self.turnus = turnus
        self.sws = sws
        self.number = number

    def __str__(self):
        if self.number:
            return f"{self.title} ({self.number})"
        return self.title

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id
