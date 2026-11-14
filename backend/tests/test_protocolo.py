import io
import socket
import threading

import pytest

from comum.protocolo import ProtocolError, receive, send


def pair():
    a, b = socket.socketpair()
    return a, b, a.makefile("rwb"), b.makefile("rwb")


def test_roundtrip_with_unicode():
    a, b, fa, fb = pair()
    with a, b, fa, fb:
        sent = send(fa, {"cmd": "SEARCH", "q": "feijão açúcar"})
        message, received = receive(fb)
        assert message == {"cmd": "SEARCH", "q": "feijão açúcar"}
        assert sent == received


def test_message_is_one_json_line():
    buf = io.BytesIO()
    send(buf, {"a": "x\ny"})  # a quebra de linha dentro do texto vira \n escapado
    assert buf.getvalue().count(b"\n") == 1 and buf.getvalue().endswith(b"\n")


def test_message_split_in_many_tcp_segments():
    """O TCP pode entregar a mensagem em pedaços: readline() junta até achar o \\n."""
    a, b = socket.socketpair()
    buf = io.BytesIO()
    send(buf, {"items": list(range(2000))})
    data = buf.getvalue()

    def slow_sender():
        for i in range(0, len(data), 7):
            a.sendall(data[i : i + 7])

    with a, b, b.makefile("rb") as fb:
        t = threading.Thread(target=slow_sender)
        t.start()
        assert receive(fb)[0] == {"items": list(range(2000))}
        t.join()


def test_two_messages_back_to_back():
    stream = io.BytesIO(b'{"n":1}\n{"n":2}\n')
    assert receive(stream)[0] == {"n": 1}
    assert receive(stream)[0] == {"n": 2}


def test_clean_close_returns_none():
    assert receive(io.BytesIO(b"")) == (None, 0)


def test_close_in_the_middle_raises():
    with pytest.raises(ProtocolError):
        receive(io.BytesIO(b'{"inc'))


def test_invalid_json_raises():
    with pytest.raises(ProtocolError):
        receive(io.BytesIO(b"isso nao e json\n"))
