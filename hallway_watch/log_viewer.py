"""Interactive log viewer for hwatch logs / hwatch debug."""

from __future__ import annotations

import argparse
import curses
import gzip
import re
import sys
import time
from datetime import date
from pathlib import Path

import yaml

POLL_MS = 400


def load_log_dir(project_dir: Path, mode: str) -> tuple[Path, str]:
    config_path = project_dir / "config.yaml"
    defaults = {
        "detections": ("logs/detections", "detections"),
        "debug": ("logs/debug", "debug"),
    }
    if config_path.exists():
        with config_path.open() as f:
            raw = yaml.safe_load(f) or {}
        logging_cfg = raw.get("logging", {})
        if mode == "detections":
            rel = logging_cfg.get("detection_log_dir", defaults["detections"][0])
        else:
            rel = logging_cfg.get("debug_log_dir", defaults["debug"][0])
        prefix = defaults[mode][1]
        return project_dir / rel, prefix
    rel, prefix = defaults[mode]
    return project_dir / rel, prefix


def read_log_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def list_log_files(log_dir: Path, prefix: str) -> list[Path]:
    if not log_dir.exists():
        return []
    files = list(log_dir.glob(f"{prefix}-*.log"))
    files.extend(log_dir.glob(f"{prefix}-*.log.gz"))
    return sorted(files, key=lambda p: p.name)


def today_log_path(log_dir: Path, prefix: str) -> Path:
    return log_dir / f"{prefix}-{date.today().isoformat()}.log"


class LogViewer:
    def __init__(
        self,
        stdscr,
        log_dir: Path,
        prefix: str,
        title: str,
    ) -> None:
        self.stdscr = stdscr
        self.log_dir = log_dir
        self.prefix = prefix
        self.title = title
        self.lines: list[str] = []
        self.offset = 0
        self.follow = True
        self.search = ""
        self.search_hits: list[int] = []
        self.search_index = 0
        self.status = ""
        self.current_file = today_log_path(log_dir, prefix)
        self._last_size = 0
        self._input_buf = ""
        self._input_mode: str | None = None

        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)

    def reload(self, tail: bool = False) -> None:
        path = self.current_file
        if path.exists():
            size = path.stat().st_size
            if size != self._last_size:
                self.lines = read_log_lines(path)
                self._last_size = size
                if tail or self.follow:
                    self.scroll_to_bottom()
        elif not self.lines:
            self.lines = [f"(waiting for {path.name}...)"]

    def scroll_to_bottom(self) -> None:
        max_rows = max(1, curses.LINES - 3)
        self.offset = max(0, len(self.lines) - max_rows)

    def visible_rows(self) -> int:
        return max(1, curses.LINES - 3)

    def run_search(self, query: str) -> None:
        self.search = query.strip()
        self.search_hits = []
        self.search_index = 0
        if not self.search:
            self.status = "Search cleared"
            return
        pattern = re.compile(re.escape(self.search), re.IGNORECASE)
        self.search_hits = [i for i, line in enumerate(self.lines) if pattern.search(line)]
        if self.search_hits:
            self.status = f"Found {len(self.search_hits)} matches"
            self.goto_line(self.search_hits[0])
        else:
            self.status = f"No matches for '{self.search}'"

    def goto_line(self, line_no: int) -> None:
        self.offset = max(0, min(line_no, max(0, len(self.lines) - self.visible_rows())))

    def next_hit(self, reverse: bool = False) -> None:
        if not self.search_hits:
            return
        if reverse:
            self.search_index = (self.search_index - 1) % len(self.search_hits)
        else:
            self.search_index = (self.search_index + 1) % len(self.search_hits)
        self.goto_line(self.search_hits[self.search_index])
        self.status = f"Match {self.search_index + 1}/{len(self.search_hits)}"

    def pick_file(self, index: int) -> None:
        files = list_log_files(self.log_dir, self.prefix)
        if not files:
            self.status = "No log files found"
            return
        idx = max(0, min(index, len(files) - 1))
        self.current_file = files[idx]
        self._last_size = -1
        self.follow = self.current_file == today_log_path(self.log_dir, self.prefix)
        self.reload(tail=True)
        self.status = f"Viewing {self.current_file.name}"

    def draw(self) -> None:
        self.stdscr.erase()
        max_cols = max(1, curses.COLS - 1)
        rows = self.visible_rows()

        header = (
            f" {self.title} | {self.current_file.name} | "
            f"lines={len(self.lines)} | follow={'ON' if self.follow else 'OFF'}"
        )
        if self.search:
            header += f" | /{self.search}"
        self.stdscr.addnstr(0, 0, header.ljust(max_cols), max_cols, curses.color_pair(2))

        help_text = " j/k/u/d  / search  n/N  f follow  g/G  o older  q quit "
        if self._input_mode == "search":
            help_text = f" Search: {self._input_buf}_ "
        self.stdscr.addnstr(1, 0, help_text.ljust(max_cols), max_cols)

        pattern = None
        if self.search:
            pattern = re.compile(re.escape(self.search), re.IGNORECASE)

        for row in range(rows):
            line_idx = self.offset + row
            if line_idx >= len(self.lines):
                break
            line = self.lines[line_idx]
            attr = 0
            if line.startswith("ALERT") or "\tALERT\t" in line:
                attr = curses.color_pair(4)
            elif line.startswith("HEAD") or "\tHEAD\t" in line:
                attr = curses.color_pair(3)
            if pattern and pattern.search(line):
                attr = curses.color_pair(1)
            self.stdscr.addnstr(2 + row, 0, line[:max_cols], max_cols, attr)

        status = self.status or "Ready"
        self.stdscr.addnstr(curses.LINES - 1, 0, status[:max_cols], max_cols)

        self.stdscr.refresh()

    def handle_key(self, key: int) -> bool:
        if self._input_mode == "search":
            if key in (27,):  # esc
                self._input_mode = None
                self._input_buf = ""
            elif key in (curses.KEY_ENTER, 10, 13):
                self.run_search(self._input_buf)
                self._input_mode = None
                self._input_buf = ""
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self._input_buf = self._input_buf[:-1]
            elif 32 <= key <= 126:
                self._input_buf += chr(key)
            return True

        if key in (ord("q"), ord("Q")):
            return False
        if key in (ord("j"), curses.KEY_DOWN):
            self.follow = False
            self.offset = min(self.offset + 1, max(0, len(self.lines) - self.visible_rows()))
        elif key in (ord("k"), curses.KEY_UP):
            self.follow = False
            self.offset = max(0, self.offset - 1)
        elif key in (ord("d"), curses.KEY_NPAGE):
            self.follow = False
            self.offset = min(self.offset + self.visible_rows(), max(0, len(self.lines) - self.visible_rows()))
        elif key in (ord("u"), curses.KEY_PPAGE):
            self.follow = False
            self.offset = max(0, self.offset - self.visible_rows())
        elif key in (ord("g"),):
            self.follow = False
            self.offset = 0
        elif key in (ord("G"),):
            self.follow = True
            self.scroll_to_bottom()
        elif key in (ord("f"), ord("F")):
            self.follow = not self.follow
            if self.follow:
                self.scroll_to_bottom()
            self.status = f"Follow {'ON' if self.follow else 'OFF'}"
        elif key in (ord("/"),):
            self._input_mode = "search"
            self._input_buf = ""
        elif key in (ord("n"),):
            self.next_hit(reverse=False)
        elif key in (ord("N"),):
            self.next_hit(reverse=True)
        elif key in (ord("o"), ord("O")):
            files = list_log_files(self.log_dir, self.prefix)
            if len(files) > 1:
                cur = files.index(self.current_file) if self.current_file in files else len(files) - 1
                self.pick_file(cur - 1)
            else:
                self.status = "No older log files"
        elif key in (ord("r"), ord("R")):
            self._last_size = -1
            self.reload(tail=self.follow)
            self.status = "Refreshed"
        return True

    def loop(self) -> None:
        self.reload(tail=True)
        while True:
            self.reload(tail=self.follow)
            self.draw()
            key = self.stdscr.getch()
            if key == -1:
                time.sleep(POLL_MS / 1000.0)
                continue
            if not self.handle_key(key):
                break


def run_viewer(project_dir: Path, mode: str) -> int:
    log_dir, prefix = load_log_dir(project_dir, mode)
    title = "Detection logs" if mode == "detections" else "Debug logs"
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        path = today_log_path(log_dir, prefix)
        print(f"Tailing {path} (pipe mode — use: tail -f {path})")
        if path.exists():
            print(path.read_text(encoding="utf-8", errors="replace"), end="")
        return 0

    def _main(stdscr) -> None:
        LogViewer(stdscr, log_dir, prefix, title).loop()

    curses.wrapper(_main)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Hallway Watch log viewer")
    parser.add_argument(
        "--mode",
        choices=("detections", "debug"),
        default="detections",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help="Hallway Watch project directory",
    )
    args = parser.parse_args()
    raise SystemExit(run_viewer(args.project_dir.resolve(), args.mode))


if __name__ == "__main__":
    main()
