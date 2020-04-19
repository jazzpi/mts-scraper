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

    def __init__(self, log_level, throttle_delay=2.0):
        """Create the Selenium WebDriver."""
        logging.getLogger(__name__).setLevel(log_level)
        self._logger = logging.getLogger(__name__ + ".Scraper")

        option = webdriver.ChromeOptions()
        option.add_argument("--incognito")
        self.browser = webdriver.Chrome(options=option)
        self._last_request = 0
        self._throttle_delay = throttle_delay

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

    def get_areas(self, combined_id):
        """Get study areas for a combined ID.

        Returns a list of top-level areas, which may contain subareas.
        Each area is of the format

        {
            "element": web_element_for_tr,
            "title": title,
            "subareas": [area_1, area_2, ...]
        }
        """
        self._load_page(
            f"{self.SHOW_COMBINED}?id={combined_id}",
            ("vis_css", "table[role=treegrid]")
        )

        self._expand_treegrid("table[role=treegrid] tbody")

        rows = self.browser.find_elements_by_css_selector(
            "table[role=treegrid] tbody tr")

        if not rows:
            self._logger.warning("No areas found?!")
            return []

        areas = []
        for row in rows:
            area = Area(row)

            # We need to figure out the parent to append to. Unless
            # we're at top level, this is always the last area at the
            # level above.
            indents = row.find_elements_by_css_selector(
                "td:first-child span.ui-treetable-indent"
            )
            level = len(indents)
            above = areas
            for i in range(level):
                above = above[-1].subareas
            above.append(area)

        return areas

    def _expand_treegrid(self, tbody_sel):
        """Expand a treegrid table.

        tbody_sel -- CSS selector for the tbody element.
        """
        rows = self.browser.find_elements_by_css_selector(f"{tbody_sel} tr")
        for row in rows:
            # Check if the row is already expanded
            if row.get_attribute("aria-expanded") == "true":
                continue

            # All rows have a toggler, but it's hidden for
            # non-expandable ones
            toggler = row.find_element_by_css_selector(".ui-treetable-toggler")
            if "visibility: hidden" in toggler.get_attribute("style"):
                continue

            # Expanding creates a POST request, so we should throttle
            self._throttle_request()
            # There is no event listener on the toggler itself, so we
            # can't click it
            ActionChains(self.browser) \
                .move_to_element(toggler).click().perform()
            id = row.get_attribute("id").replace(":", r"\:")
            self._wait_for((
                "vis_css",
                f"#{id}[aria-expanded=true]"
            ))


class Area:
    """A study area from the combined page."""

    def __init__(self, element):
        """Create the area for a tr from the combined page."""
        self._logger = logging.getLogger(__name__ + ".Area")
        self.element = element
        self.title = element.find_element_by_css_selector(":first-child").text
        self.subareas = []

    def __str__(self):
        if self.subareas:
            return self.title + " -> [" + ", ".join(map(str, self.subareas)) + \
                "]"
        else:
            return self.title

    def __repr__(self):
        return str(self)
