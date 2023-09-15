from oauth2client.service_account import ServiceAccountCredentials
import gspread


class GSQLClass:
    def __init__(self, sheetName: str, tableName: str) -> None:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "client_secret.json", scope
        )
        client = gspread.authorize(creds)
        self.sheet = client.open(sheetName)
        try:
            self.table = self.sheet.worksheet(tableName)
        except Exception:
            self.sheet.add_worksheet(title=tableName, rows=1, cols=1)
            self.table = self.sheet.worksheet(tableName)

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
        return len([value for value in self.table.col_values(1) if value])

    def row_len(self) -> int:
        return len([value for value in self.table.row_values(1) if value])

    def resize(self, row: int, col: int) -> None:
        self.table.resize(row, col)

    def clear(self) -> None:
        self.table.clear()

    def autoFit(self) -> None:
        self.table.rows_auto_resize(0, self.table.row_count - 1)
        self.table.columns_auto_resize(0, self.table.col_count - 1)
