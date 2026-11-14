import socket
import struct
import threading

import pytest

from common.protocol import HEADER, ProtocolError, encode, recv_msg, send_msg


def test_roundtrip_with_unicode():
    a, b = socket.socketpair()
    with a, b:
        send_msg(a, {"cmd": "SEARCH", "q": "feijão açúcar"})
        assert recv_msg(b) == {"cmd": "SEARCH", "q": "feijão açúcar"}


def test_frame_has_length_prefix():
    frame = encode({"a": 1})
    (size,) = HEADER.unpack(frame[:4])
    assert size == len(frame) - 4


def test_message_split_in_many_tcp_segments():
    """recv() pode devolver pedaços: o framing precisa remontar a mensagem."""
    a, b = socket.socketpair()
    frame = encode({"items": list(range(2000))})

    def slow_sender():
        for i in range(0, len(frame), 7):
            a.sendall(frame[i : i + 7])

    with a, b:
        t = threading.Thread(target=slow_sender)
        t.start()
        assert recv_msg(b) == {"items": list(range(2000))}
        t.join()


def test_two_messages_back_to_back():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(encode({"n": 1}) + encode({"n": 2}))
        assert recv_msg(b) == {"n": 1}
        assert recv_msg(b) == {"n": 2}


def test_clean_close_returns_none():
    a, b = socket.socketpair()
    a.close()
    with b:
        assert recv_msg(b) is None


def test_close_in_the_middle_raises():
    a, b = socket.socketpair()
    a.sendall(struct.pack(">I", 100) + b'{"inc')
    a.close()
    with b, pytest.raises(ProtocolError):
        recv_msg(b)


def test_absurd_size_rejected():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(struct.pack(">I", 2**31))
        with pytest.raises(ProtocolError):
            recv_msg(b)
