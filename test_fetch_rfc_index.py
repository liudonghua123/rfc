from pathlib import Path

import fetch_rfc_index


def test_write_additional_formats(tmp_path: Path) -> None:
    payload = {
        "total": 2,
        "data": [
            {"number": 1, "title": "RFC 1", "authors": [{"name": "A"}]},
            {"number": 2, "title": "RFC 2", "authors": [{"name": "B"}]},
        ],
    }

    written = fetch_rfc_index.write_additional_formats(payload, tmp_path)

    assert written["json"] == tmp_path / "index.json"
    assert written["msgpack"] == tmp_path / "index.msgpack"
    assert written["cbor"] == tmp_path / "index.cbor"
    assert written["protobuf"] == tmp_path / "index.pb"
    assert written["parquet"] == tmp_path / "index.parquet"

    for path in written.values():
        assert path.exists(), f"Expected file to be created: {path}"
