"""Shared base class for the whole team (this is the team's one demonstration of
inheritance + encapsulation).

Think of it as the lock on the filing cabinet: it opens the file safely and puts
it back safely. It deliberately does NOT contain Create / Read / Update / Delete.
Each member writes those four operations themselves in their own subclass, because
the course requires the CRUD logic to be each student's own work.

What this class gives every subclass:
    * load()           read the CSV with try/except/else/finally and friendly errors
    * _save()          write safely (temp file, then replace) so the CSV is never half-written
    * data (property)  read-only copy of the table (the protected _data attribute is encapsulated)
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd


class DataFileError(Exception):
    """Raised with a message that is safe to show on the page (no traceback)."""


class CSVManager:
    def __init__(self, csv_path, required_columns=None, numeric_columns=None):
        self._path = Path(csv_path)
        self._required = list(required_columns or [])
        self._numeric = list(numeric_columns or [])
        self._data = pd.DataFrame()          # protected: subclasses use it, pages use .data
        self.warnings = []                   # non-fatal notes, e.g. "3 bad numbers were blanked"
        self.last_loaded = None
        self.load()

    # ---------- encapsulation ----------
    @property
    def data(self) -> pd.DataFrame:
        """A copy, so a page can never change the table by accident."""
        return self._data.copy()

    @property
    def path(self) -> Path:
        return self._path

    # ---------- safe read ----------
    def load(self) -> pd.DataFrame:
        """Load the CSV fresh from disk. Raises DataFileError with a friendly message."""
        self.warnings = []
        try:
            df = pd.read_csv(self._path)
        except FileNotFoundError:
            raise DataFileError(f"The data file '{self._path.name}' was not found in the data folder.")
        except pd.errors.EmptyDataError:
            raise DataFileError(f"The data file '{self._path.name}' is empty.")
        except pd.errors.ParserError:
            raise DataFileError(f"The data file '{self._path.name}' is damaged and could not be read.")
        except PermissionError:
            raise DataFileError(f"'{self._path.name}' is open in another program. Close it and try again.")
        else:
            missing = [c for c in self._required if c not in df.columns]
            if missing:
                raise DataFileError(f"'{self._path.name}' is missing column(s): {', '.join(missing)}.")
            for col in self._numeric:                      # wrong column types
                before = df[col].isna().sum()
                df[col] = pd.to_numeric(df[col], errors="coerce")
                bad = int(df[col].isna().sum() - before)
                if bad:
                    self.warnings.append(f"{bad} non-numeric value(s) in '{col}' were treated as missing.")
            self._data = df
        finally:
            self.last_loaded = datetime.now()
        return self._data

    # ---------- safe write ----------
    def _save(self) -> None:
        """Write _data to disk without ever leaving a half-written file.

        We write to a temporary file first. Only if that succeeds do we swap it in
        for the real file, so a crash mid-write cannot corrupt the CSV.
        """
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix=".csv", dir=self._path.parent)
            os.close(fd)
            self._data.to_csv(tmp_name, index=False)
            pd.read_csv(tmp_name)                          # prove the new file re-loads
        except (OSError, pd.errors.ParserError) as exc:
            if tmp_name and os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise DataFileError(f"Could not save changes to '{self._path.name}': {exc}")
        else:
            os.replace(tmp_name, self._path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.remove(tmp_name)
