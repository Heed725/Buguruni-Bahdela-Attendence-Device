from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import RequestException


class HikvisionError(RuntimeError):
    pass


@dataclass
class DeviceStatus:
    ok: bool
    code: str = ""
    message: str = ""


@dataclass
class FingerprintCapture:
    finger_data: str | None
    quality: int | None
    message: str = ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_values(text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    return {_local_name(node.tag): (node.text or "").strip() for node in root.iter()}


def parse_status(response: requests.Response) -> DeviceStatus:
    if not response.text:
        return DeviceStatus(response.ok, str(response.status_code), "")
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        status = body.get("ResponseStatus", body)
        raw_code = status.get("statusCode", response.status_code)
        ok = response.ok and str(raw_code) in {"1", "200"}
        message = status.get("subStatusCode") or status.get("statusString") or response.reason
        return DeviceStatus(ok, str(raw_code), str(message))
    values = _xml_values(response.text)
    raw_code = values.get("statusCode") or values.get("statusValue") or str(response.status_code)
    ok = response.ok and raw_code in {"1", "200", "OK", "ok"}
    message = values.get("subStatusCode") or values.get("statusString") or response.reason
    return DeviceStatus(ok, raw_code, message)


class HikvisionClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 30,
        verify_tls: bool = False,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise HikvisionError("Device URL must begin with http:// or https://")
        if not username or not password:
            raise HikvisionError("Device username and password are required.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(username, password)
        self.session.headers.update({"User-Agent": "Hikvision-Streamlit/1.0"})

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify_tls)
        try:
            response = self.session.request(method, f"{self.base_url}{path}", **kwargs)
        except RequestException as exc:
            raise HikvisionError(f"Could not communicate with the Hikvision device: {exc}") from exc
        if response.status_code == 401:
            raise HikvisionError("Authentication failed. Check the Hikvision username and password.")
        return response

    def device_info(self) -> requests.Response:
        return self.request("GET", "/ISAPI/System/deviceInfo")

    def access_control_capabilities(self) -> requests.Response:
        return self.request("GET", "/ISAPI/AccessControl/capabilities")

    @staticmethod
    def _user_payload(
        employee_no: str,
        name: str,
        user_type: str,
        begin_time: str,
        end_time: str,
        plan_template_no: int,
    ) -> dict[str, Any]:
        return {
            "UserInfo": {
                "employeeNo": employee_no,
                "name": name,
                "userType": user_type,
                "doorRight": "1",
                "RightPlan": [{"doorNo": 1, "planTemplateNo": str(plan_template_no)}],
                "Valid": {
                    "enable": True,
                    "beginTime": begin_time,
                    "endTime": end_time,
                    "timeType": "local",
                },
            }
        }

    def create_user(self, **values: Any) -> requests.Response:
        return self.request(
            "POST",
            "/ISAPI/AccessControl/UserInfo/Record?format=json",
            json=self._user_payload(**values),
        )

    def modify_user(self, **values: Any) -> requests.Response:
        return self.request(
            "PUT",
            "/ISAPI/AccessControl/UserInfo/Modify?format=json",
            json=self._user_payload(**values),
        )

    def search_users(self, employee_no: str | None = None, max_results: int = 20) -> requests.Response:
        condition: dict[str, Any] = {
            "searchID": "streamlit-search",
            "searchResultPosition": 0,
            "maxResults": max_results,
        }
        if employee_no:
            condition["EmployeeNoList"] = [{"employeeNo": employee_no}]
        return self.request(
            "POST",
            "/ISAPI/AccessControl/UserInfo/Search?format=json",
            json={"UserInfoSearchCond": condition},
        )

    @staticmethod
    def extract_users(response: requests.Response) -> list[dict[str, Any]]:
        try:
            body = response.json()
        except ValueError:
            return []
        result = body.get("UserInfoSearch", body)
        users = result.get("UserInfo", [])
        if isinstance(users, dict):
            users = [users]
        rows = []
        for user in users:
            rows.append(
                {
                    "Employee No.": user.get("employeeNo", ""),
                    "Name": user.get("name", ""),
                    "Type": user.get("userType", ""),
                    "Face": user.get("numOfFace", ""),
                    "Fingerprint": user.get("numOfFP", ""),
                }
            )
        return rows

    def upload_face(
        self,
        employee_no: str,
        image_bytes: bytes,
        filename: str,
        fdid: str = "1",
        face_lib_type: str = "blackFD",
        image_field: str = "FaceImage",
    ) -> requests.Response:
        metadata = {
            "faceLibType": face_lib_type,
            "FDID": fdid,
            "FPID": employee_no,
        }
        files = {
            "FaceDataRecord": (None, json.dumps(metadata), "application/json"),
            image_field: (filename, image_bytes, "image/jpeg"),
        }
        return self.request(
            "POST",
            "/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json",
            files=files,
        )

    def capture_fingerprint(self, finger_id: int = 1) -> FingerprintCapture:
        response = self.request(
            "POST",
            "/ISAPI/AccessControl/CaptureFingerPrint?format=json",
            json={"CaptureFingerPrint": {"fingerNo": finger_id}},
            timeout=max(self.timeout, 45),
        )
        status = parse_status(response)
        if not response.ok:
            return FingerprintCapture(None, None, status.message)
        try:
            body = response.json()
            capture = body.get("CaptureFingerPrint", body)
            data = capture.get("fingerData") or capture.get("fingerPrintData")
            quality = capture.get("fingerPrintQuality") or capture.get("quality")
            return FingerprintCapture(data, int(quality) if quality is not None else None, status.message)
        except (ValueError, TypeError):
            values = _xml_values(response.text)
            data = values.get("fingerData") or values.get("fingerPrintData")
            quality_text = values.get("fingerPrintQuality") or values.get("quality")
            quality = int(quality_text) if quality_text and quality_text.isdigit() else None
            return FingerprintCapture(data, quality, status.message)

    def apply_fingerprint(
        self,
        employee_no: str,
        finger_data: str,
        fingerprint_id: int = 1,
        card_reader_no: int = 1,
    ) -> requests.Response:
        payload = {
            "FingerPrintCfg": {
                "employeeNo": employee_no,
                "enableCardReader": [card_reader_no],
                "fingerPrintID": fingerprint_id,
                "fingerType": "normalFP",
                "fingerData": finger_data,
            }
        }
        return self.request(
            "POST",
            "/ISAPI/AccessControl/FingerPrintDownload?format=json",
            json=payload,
        )
