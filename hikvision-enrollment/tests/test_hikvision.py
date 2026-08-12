from types import SimpleNamespace

from hikvision import parse_status


def response(text: str, status_code: int = 200, json_body=None):
    obj = SimpleNamespace(
        text=text,
        status_code=status_code,
        ok=200 <= status_code < 400,
        reason="OK" if status_code == 200 else "Error",
    )
    if json_body is None:
        obj.json = lambda: (_ for _ in ()).throw(ValueError())
    else:
        obj.json = lambda: json_body
    return obj


def test_json_ok_status():
    result = parse_status(response('{"statusCode":1}', json_body={"statusCode": 1, "statusString": "OK"}))
    assert result.ok


def test_xml_ok_status():
    result = parse_status(response("<ResponseStatus><statusCode>1</statusCode><statusString>OK</statusString></ResponseStatus>"))
    assert result.ok


def test_error_status():
    result = parse_status(response("<ResponseStatus><statusCode>6</statusCode><statusString>Invalid Content</statusString></ResponseStatus>"))
    assert not result.ok
    assert result.message == "Invalid Content"
