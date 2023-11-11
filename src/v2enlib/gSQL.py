from oauth2client.service_account import ServiceAccountCredentials
import gspread, re


scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("client_secret.json", scope)
client = gspread.authorize(creds)


class GSQL:
    class Table:
        # Section:_Find
        def findRow(self, value: any):
            row = self.table.find(str(value))
            return False if row is None else row.row

        # Section:_Write
        def writeLRow(self, value: list) -> None:
            if len(value) and isinstance(value[0], list):
                self.table.append_rows(self._convert_to_str(value))
            else:
                self.table.append_row(self._convert_to_str(value))

        def writeRow(self, row, value: list) -> None:
            for i, e in enumerate(value):
                if not isinstance(e, list):
                    self.writeCell(row, i + 1, e)

        def writeCol(self, col, value: list):
            for i, e in enumerate(value):
                if not isinstance(e, list):
                    self.writeCell(i + 1, col, e)

        def writeCell(self, row, col, value):
            self.table.update(
                self._convert_to_label(row, col), self._convert_to_str(value)
            )

        # Section:_Delete
        def deleteRow(self, row: int) -> None:
            try:
                self.table.delete_row(row)
            except:
                self.table.clear()

        # Section:_Read
        def getRow(self, row: int) -> any:
            return self._convert_to_auto(self.table.row_values(row))

        def getCol(self, col: int) -> any:
            return self._convert_to_auto(self.table.col_values(col))

        def getAll(self) -> any:
            return self._convert_to_auto(self.table.get_values())

        # Section:_Utils
        def _convert_to_label(self, row, col):
            col_label = chr(ord("A") + col - 1)
            return col_label + str(row)

        def _convert_to_str(self, value):
            if isinstance(value, list):
                return [self._convert_to_str(e) for e in value]
            return str(value)

        def _convert_to_auto(self, value):
            if isinstance(value, list):
                return [self._convert_to_auto(e) for e in value]
            return int(value) if value.isdigit() else str(value)

        def col_len(self) -> int:
            return self.table.col_count

        def row_len(self) -> int:
            return self.table.row_count

        def resize(self, row: int, col: int) -> None:
            self.table.resize(row, col)

        def clear(self) -> None:
            self.table.clear()

        def autoFit(self) -> None:
            self.table.rows_auto_resize(0, self.table.row_count - 1)
            self.table.columns_auto_resize(0, self.table.col_count - 1)

        def __init__(self, sheet, name) -> None:
            try:
                self.table = sheet.worksheet(name)
            except Exception:
                sheet.add_worksheet(title=name, rows=1, cols=1)
                self.table = sheet.worksheet(name)

    @staticmethod
    def __is_link_using_regex(string):
        pattern = re.compile(r"https?://\S+")
        return bool(re.match(pattern, string))

    def __init__(self, sheetName: str, tableName: list = [], prefix="", reverse=False):
        if self.__is_link_using_regex(sheetName):
            sheet = client.open_by_url(sheetName)
        else:
            sheet = client.open(sheetName)
        for e in tableName:
            setattr(self, e, self.Table(sheet, "_".join([prefix, e])))
            getattr(self, e).autoFit()
        self.prefix = prefix
        self.sheet = sheet

        worksheets = sheet.worksheets()
        sorted_worksheets = sorted(worksheets, key=lambda x: x.title, reverse=reverse)
        for i, worksheet in enumerate(sorted_worksheets):
            worksheet.update_index(i + 1)

    def append(self, tableName: list):
        for e in tableName:
            if not hasattr(self, e):
                setattr(self, e, self.Table(self.sheet, "_".join([self.prefix, e])))
