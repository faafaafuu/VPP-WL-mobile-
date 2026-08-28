"""Build an unsigned SOL transfer for a browser wallet to sign.

Phantom's desktop extension never registers the ``solana:`` URI scheme — it
injects a provider instead — so a payment link does nothing there. The page
talks to that provider, and the provider wants a serialized transaction
message, which is what this builds.

Doing it here rather than pulling a Solana library into the page keeps the
recipient and the amount on our side: the page only relays bytes it cannot
usefully alter, because changing any of them invalidates nothing the wallet
would accept as ours.

Legacy message layout, per Solana's own encoding:

    header          3 bytes: required signatures, readonly signed, readonly unsigned
    accountKeys     compact-u16 count, then 32 bytes each
    recentBlockhash 32 bytes
    instructions    compact-u16 count, then for each:
                      program id index (u8)
                      compact-u16 account count, then one u8 index each
                      compact-u16 data length, then the data
"""

from __future__ import annotations

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: i for i, char in enumerate(_B58_ALPHABET)}

SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
_TRANSFER_INSTRUCTION = 2


class SolanaTxError(Exception):
    pass


def b58encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    out = ""
    while number > 0:
        number, rem = divmod(number, 58)
        out = _B58_ALPHABET[rem] + out
    # Every leading zero byte is one leading "1" — they carry no value but
    # are part of the address, so they survive the integer round trip only
    # if put back by hand.
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + out


def b58decode(text: str) -> bytes:
    number = 0
    for char in text:
        digit = _B58_INDEX.get(char)
        if digit is None:
            raise SolanaTxError(f"not base58: {char!r}")
        number = number * 58 + digit
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\x00" * pad + body


def _pubkey(address: str) -> bytes:
    raw = b58decode(address)
    if len(raw) != 32:
        raise SolanaTxError(f"address is not a 32-byte public key: {address}")
    return raw


def _compact_u16(value: int) -> bytes:
    out = bytearray()
    while True:
        chunk = value & 0x7F
        value >>= 7
        if value:
            out.append(chunk | 0x80)
        else:
            out.append(chunk)
            return bytes(out)


def build_transfer_message(sender: str, recipient: str, lamports: int, recent_blockhash: str) -> str:
    """Serialize a one-instruction SOL transfer, base58-encoded for the wallet."""
    if lamports <= 0:
        raise SolanaTxError("amount must be positive")
    if sender == recipient:
        raise SolanaTxError("sender and recipient are the same account")
    keys = [_pubkey(sender), _pubkey(recipient), _pubkey(SYSTEM_PROGRAM_ID)]
    blockhash = b58decode(recent_blockhash)
    if len(blockhash) != 32:
        raise SolanaTxError("recent blockhash is not 32 bytes")

    data = _TRANSFER_INSTRUCTION.to_bytes(4, "little") + int(lamports).to_bytes(8, "little")

    message = bytearray()
    message += bytes([1, 0, 1])  # one signer, no readonly signers, system program readonly
    message += _compact_u16(len(keys))
    for key in keys:
        message += key
    message += blockhash
    message += _compact_u16(1)
    message += bytes([2])  # program id index -> system program
    message += _compact_u16(2) + bytes([0, 1])  # sender, recipient
    message += _compact_u16(len(data)) + data
    return b58encode(bytes(message))
