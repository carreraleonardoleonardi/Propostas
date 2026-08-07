# =========================================================
# pages/zipcrypto_util.py — Gerador de .zip com senha (ZipCrypto puro Python)
# =========================================================
#
# Implementação própria do ZipCrypto (criptografia clássica do formato ZIP),
# sem NENHUMA dependência externa — não usa pyzipper, não chama o binário
# `zip` do sistema. É só Python padrão (struct, zlib, random).
#
# Por que ZipCrypto e não AES: é o único método de criptografia de zip que
# o "Extrair Tudo" nativo do Windows (e o Archive Utility do macOS) sabe
# abrir sem instalar nada. WinRAR e 7-Zip também abrem normalmente.
# É uma proteção mais fraca que AES (não é para dados ultrassensíveis),
# mas garante compatibilidade universal — que era o requisito aqui.
#
# Testado manualmente: o zip gerado foi validado com o módulo zipfile do
# Python (leitura + rejeição de senha errada) e com o utilitário unzip.

import struct
import zlib
import random

# ── Tabela CRC32 padrão usada pelo algoritmo PKZIP tradicional ──────────
_CRC_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (0xEDB88320 ^ (_c >> 1)) if (_c & 1) else (_c >> 1)
    _CRC_TABLE.append(_c)


def _crc32_step(key, ch):
    return (_CRC_TABLE[(key ^ ch) & 0xFF] ^ (key >> 8)) & 0xFFFFFFFF


class _ZipCryptoKeys:
    def __init__(self, password: bytes):
        self.key0 = 0x12345678
        self.key1 = 0x23456789
        self.key2 = 0x34567890
        for b in password:
            self._update(b)

    def _update(self, byte_val):
        self.key0 = _crc32_step(self.key0, byte_val)
        self.key1 = (self.key1 + (self.key0 & 0xFF)) & 0xFFFFFFFF
        self.key1 = (self.key1 * 134775813 + 1) & 0xFFFFFFFF
        self.key2 = _crc32_step(self.key2, (self.key1 >> 24) & 0xFF)

    def _keystream_byte(self):
        temp = (self.key2 | 2) & 0xFFFF
        return ((temp * (temp ^ 1)) >> 8) & 0xFF

    def encrypt_byte(self, plain_byte):
        ks = self._keystream_byte()
        cipher_byte = (plain_byte ^ ks) & 0xFF
        self._update(plain_byte)
        return cipher_byte


def _encrypt_bytes(data: bytes, password: bytes, crc32_of_data: int) -> bytes:
    keys = _ZipCryptoKeys(password)
    header = bytearray(random.getrandbits(8) for _ in range(12))
    header[11] = (crc32_of_data >> 24) & 0xFF  # último byte = byte alto do CRC-32
    out = bytearray()
    for b in header:
        out.append(keys.encrypt_byte(b))
    for b in data:
        out.append(keys.encrypt_byte(b))
    return bytes(out)


def gerar_zip_com_senha_bytes(arquivos: list, senha: str) -> bytes:
    """
    arquivos: lista de tuplas (nome_no_zip, conteudo_bytes).
    Retorna os bytes de um .zip protegido por senha (ZipCrypto clássico).
    """
    import io
    buf = io.BytesIO()
    senha_bytes = senha.encode("utf-8")
    central_dir = []
    offset = 0

    for nome, conteudo in arquivos:
        crc = zlib.crc32(conteudo) & 0xFFFFFFFF
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        dados_comprimidos = comp.compress(conteudo) + comp.flush()
        if len(dados_comprimidos) >= len(conteudo):
            dados_comprimidos = conteudo
            metodo = 0  # stored
        else:
            metodo = 8  # deflate

        dados_criptografados = _encrypt_bytes(dados_comprimidos, senha_bytes, crc)

        nome_bytes = nome.encode("utf-8")
        flag = 0x01 | 0x0800  # bit0 = criptografado, bit11 = nome em UTF-8
        dostime, dosdate = 0, 0x21

        local_header = struct.pack(
            "<4s2B4HL2L2H",
            b"PK\x03\x04", 20, 0, flag, metodo, dostime, dosdate,
            crc, len(dados_criptografados), len(conteudo),
            len(nome_bytes), 0
        )
        buf.write(local_header)
        buf.write(nome_bytes)
        buf.write(dados_criptografados)

        central_dir.append((
            nome_bytes, flag, metodo, dostime, dosdate, crc,
            len(dados_criptografados), len(conteudo), offset
        ))
        offset += len(local_header) + len(nome_bytes) + len(dados_criptografados)

    cd_start = offset
    for nome_bytes, flag, metodo, dostime, dosdate, crc, csize, usize, rel_offset in central_dir:
        cd_header = struct.pack(
            "<4s4B4HL2L5H2L",
            b"PK\x01\x02",
            20, 0, 20, 0,
            flag, metodo, dostime, dosdate,
            crc, csize, usize,
            len(nome_bytes), 0, 0, 0, 0,
            0, rel_offset
        )
        buf.write(cd_header)
        buf.write(nome_bytes)
    cd_size = buf.tell() - cd_start

    eocd = struct.pack(
        "<4s4H2LH",
        b"PK\x05\x06", 0, 0, len(central_dir), len(central_dir),
        cd_size, cd_start, 0
    )
    buf.write(eocd)

    return buf.getvalue()