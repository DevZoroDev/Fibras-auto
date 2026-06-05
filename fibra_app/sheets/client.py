"""Cliente de Google Sheets usando OAuth de usuario (gspread).

Las escrituras quedan registradas a nombre del usuario que inicia sesión
(no de una cuenta de servicio). La primera vez se abre el navegador para
autorizar; luego el token se cachea en ``token.json`` y se refresca solo.
"""

from __future__ import annotations

import logging
from pathlib import Path

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

from ..config import SHEET_COLUMNS

logger = logging.getLogger(__name__)

# Solo se solicita acceso a hojas de cálculo (consentimiento mínimo).
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsError(Exception):
    """Error de conexión o escritura en Google Sheets."""


class SheetsClient:
    """Encapsula el acceso a una planilla y pestaña concretas vía OAuth."""

    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        sheet_id: str,
        worksheet_name: str,
    ) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._sheet_id = sheet_id
        self._worksheet_name = worksheet_name
        self._client: gspread.Client | None = None

    # ----------------------------------------------------------------- auth
    def _credenciales(self) -> Credentials:
        """Obtiene credenciales OAuth válidas (token cacheado o login nuevo)."""
        creds: Credentials | None = None
        if self._token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self._token_path), _SCOPES
                )
            except (ValueError, KeyError) as exc:
                logger.warning("token.json inválido, se regenerará: %s", exc)
                creds = None

        if creds and creds.valid:
            return creds

        # Intentar refrescar un token expirado.
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._guardar_token(creds)
                return creds
            except RefreshError as exc:
                logger.warning("No se pudo refrescar el token: %s", exc)

        # Login interactivo en el navegador.
        if not self._credentials_path.exists():
            raise SheetsError(
                "No se encontró el archivo de credenciales OAuth: "
                f"{self._credentials_path}. Descárgalo desde Google Cloud "
                "(ID de cliente de OAuth, tipo 'App de escritorio')."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._credentials_path), _SCOPES
            )
            creds = flow.run_local_server(port=0, prompt="consent")
        except Exception as exc:  # noqa: BLE001
            raise SheetsError(
                f"Falló la autorización con Google: {exc}"
            ) from exc
        self._guardar_token(creds)
        return creds

    def _guardar_token(self, creds: Credentials) -> None:
        self._token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Token de usuario guardado en %s", self._token_path)

    def _connect(self) -> gspread.Client:
        if self._client is not None:
            return self._client
        if not self._sheet_id:
            raise SheetsError("Falta GOOGLE_SHEET_ID en el archivo .env.")
        creds = self._credenciales()
        self._client = gspread.authorize(creds)
        return self._client

    # ------------------------------------------------------------- planilla
    def _worksheet(self) -> gspread.Worksheet:
        client = self._connect()
        try:
            spreadsheet = client.open_by_key(self._sheet_id)
        except SpreadsheetNotFound as exc:
            raise SheetsError(
                "No se encontró la planilla. Verifica GOOGLE_SHEET_ID y que tu "
                "cuenta de Google tenga acceso de edición a ella."
            ) from exc
        except APIError as exc:
            raise SheetsError(f"Error de la API de Google: {exc}") from exc

        try:
            return spreadsheet.worksheet(self._worksheet_name)
        except WorksheetNotFound as exc:
            raise SheetsError(
                f"No existe la pestaña '{self._worksheet_name}' en la planilla."
            ) from exc

    def probar_conexion(self) -> str:
        """Verifica acceso y devuelve el título de la planilla."""
        ws = self._worksheet()
        return ws.spreadsheet.title

    def asegurar_encabezados(self) -> None:
        """Escribe la fila de encabezados si la hoja está vacía."""
        ws = self._worksheet()
        try:
            primera_fila = ws.row_values(1)
        except APIError as exc:
            raise SheetsError(f"Error leyendo la planilla: {exc}") from exc
        if not primera_fila:
            ws.update("A1", [SHEET_COLUMNS])
            logger.info("Encabezados escritos en la planilla.")

    def agregar_filas(self, filas: list[list[str]]) -> int:
        """Agrega filas al final de la hoja. Devuelve cuántas se escribieron."""
        if not filas:
            return 0
        ws = self._worksheet()
        try:
            self.asegurar_encabezados()
            ws.append_rows(
                filas,
                value_input_option="USER_ENTERED",
                insert_data_option="INSERT_ROWS",
                table_range="A1",
            )
        except APIError as exc:
            raise SheetsError(
                f"Error al escribir en Google Sheets: {exc}"
            ) from exc
        logger.info("Se escribieron %d fila(s) en la planilla.", len(filas))
        return len(filas)
