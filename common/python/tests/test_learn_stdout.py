import io
import sys

from learn.api import handle_learn_rpc


def test_learn_rpc_stdout_cleanliness():
    """
    Ensures that calling Preppy Learn RPC actions emits ZERO stray stdout (§1, §11).
    All debug output must route to stderr/loggers only.
    """
    captured_stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_stdout

    try:
        # 1. Status action
        res_status = handle_learn_rpc("learn.status", {})
        assert res_status.get("success") is True

        # 2. Materials upload action
        res_upload = handle_learn_rpc(
            "learn.materials.upload",
            {"title": "Test Doc", "content": "# Header\nContent line.", "kind": "notes"},
        )
        assert res_upload.get("success") is True

        # 3. List materials action
        res_list = handle_learn_rpc("learn.materials.list", {})
        assert res_list.get("success") is True

        # 4. Unknown action
        res_unk = handle_learn_rpc("learn.unknown_action", {})
        assert res_unk.get("success") is False

    finally:
        sys.stdout = old_stdout

    stray_stdout = captured_stdout.getvalue()
    assert stray_stdout == "", f"Stray stdout detected in Learn code paths: {stray_stdout!r}"

