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
            if isinstance(value, int):
                value = str(value)
            row = self.table.find(value)
            return False if row is None else row.row

        # Section:_Write
        def writeLRow(self, value: list) -> None:
            if len(value) and isinstance(value[0], list):
                self.table.append_rows(list(value))
            else:
                self.table.append_row(list(value))

        # Section:_Delete
        def deleteRow(self, row: int) -> None:
            if self.col_len() == 1:
                self.writeLRow([""])
            self.table.delete_row(row)

        def writeCell(self, row: int, col: int, value: any) -> None:
            self.table.update_cell(row, col, value)

        # Section:_Read
        def getRow(self, row: int) -> any:
            return self.table.row_values(row)

        def getCol(self, col: int) -> any:
            return self.table.col_values(col)

        def getAll(self) -> any:
            return self.table.get_values()

        # Section:_Utils
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

    def __init__(self, sheetName: str, tableName: list, prefix=""):
        if self.__is_link_using_regex(sheetName):
            sheet = client.open_by_url(sheetName)
        else:
            sheet = client.open(sheetName)
        for e in tableName:
            setattr(self, e, self.Table(sheet, "_".join([prefix, e])))
        self.prefix = prefix
        self.sheet = sheet

    def append(self, tableName: list):
        for e in tableName:
            setattr(self, e, self.Table(self.sheet, "_".join([self.prefix, e])))
