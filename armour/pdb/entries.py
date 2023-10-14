#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""entries"""

from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Type

from .. import crypt
from . import exc, header, s


class PdbEntry(ABC):
    """entry abstract base class"""

    entry_id: int = 0

    def __init__(
        self,
        head: header.PdbHeader,
        ehash: bytes = b"",
        fields: Optional[Dict[bytes, bytes]] = None,
    ) -> None:
        self.entry_id: int = PdbEntry.entry_id
        PdbEntry.entry_id += 1

        self.head: header.PdbHeader = head
        self.ehash: bytes = ehash
        self.fields: Dict[bytes, bytes] = {}

        if fields is not None:
            for field, value in fields.items():
                self[field] = value

    def from_entry(self, entry: bytes) -> Any:
        """creates a new entry from binary data
        ( does not validate the hash )

        :rtype: Self"""

        b: BytesIO = BytesIO(entry)

        while (ident := b.read(s.BL)) != b"\0":
            self[ident] = b.read(s.sunpack(s.L, b))

        return self

    @property
    def entry(self) -> bytes:
        """return the non-full entry as bytes"""
        return b"".join(
            field + s.pack(s.L, len(data)) + data for field, data in self.fields.items()
        )

    @property
    def full_entry(self) -> bytes:
        """return the full entry ( hash + entry + NULL ) as bytes"""
        return self.ehash + self.entry + b"\0"

    def rehash(self) -> Any:
        """rehash the entry

        :rtype: Self"""

        self.ehash = crypt.hash_walgo(
            self.head.hash_id,
            self.entry,
            self.head.password,
            self.head.salt,
            self.head.kdf_passes,
            self.head.hash_salt_len,
        )

        return self

    def hash_ok(self) -> bool:
        """is the hash of the entry valid"""
        return crypt.hash_walgo_compare(
            self.head.hash_id,
            self.entry,
            self.head.password,
            self.head.salt,
            self.head.kdf_passes,
            self.head.hash_salt_len,
            self.ehash,
        )

    def revalidate(self) -> Any:
        """revalidate the hash

        :rtype: Self"""

        if not self.hash_ok():
            raise exc.DataIntegrityError(
                f"entry #{self.entry_id} has a bad hash / signature",
                self.ehash,
            )

        return self

    def set_field_raw(self, name: bytes, value: bytes) -> Any:
        """set field name to value

        :rtype: Self"""

        self.fields[name] = value
        return self

    def get_field_raw(self, name: bytes) -> bytes:
        """set field name to value"""
        return self.fields[name]

    @abstractmethod
    def set_field(self, name: bytes, value: bytes) -> Any:
        """set field name to value

        :rtype: Self"""
        return self  # for typing

    @abstractmethod
    def get_field(self, name: bytes) -> bytes:
        """get field by name"""

    @abstractmethod
    def validate_struct(self) -> Any:
        """validate structure"""
        return self  # for typing

    @abstractmethod
    def __str__(self) -> str:
        """stringify entry"""

    def __contains__(self, name: bytes) -> bool:
        """does the entry contain `name` field"""
        return name in self.fields

    def __setitem__(self, name: bytes, value: bytes) -> None:
        """wrapper for `set_field`"""
        self.set_field(name, value)

    def __getitem__(self, name: bytes) -> bytes:
        """wrapper for `get_field`"""
        return self.get_field(name)


class PdbRawEntry(PdbEntry):
    """pdb entries raw entry"""

    def set_field(self, name: bytes, value: bytes) -> "PdbRawEntry":
        """set field name to value

        :rtype: Self"""
        return self.set_field_raw(name, value)

    def get_field(self, name: bytes) -> bytes:
        """get field by name"""
        return self.get_field_raw(name)

    def validate_struct(self) -> "PdbRawEntry":
        """validate structure"""
        return self

    def __str__(self) -> str:
        """shows all fields in the entry"""
        return "\n".join(
            f"field {field!r:10s} -- {data!r}" for field, data in self.fields.items()
        )


class PdbPwdEntry(PdbEntry):
    """pdb entries password entry"""

    all_fields: Tuple[bytes, ...] = b"n", b"u", b"p", b"r"
    encrypted_fields: Tuple[bytes, ...] = b"u", b"p"

    def _get_crypt(self, name: bytes) -> bytes:
        """get an encrypted value"""
        return crypt.decrypt_secure(
            self.get_field_raw(name),
            self.head.password,
            self.head.salt,
            self.head.hash_id,
            self.head.hash_salt_len,
            self.head.sec_crypto_passes,
            self.head.kdf_passes,
        )

    def _set_crypt(self, name: bytes, value: bytes) -> None:
        """set an encrypted value"""
        self.set_field_raw(
            name,
            crypt.encrypt_secure(
                value,
                self.head.password,
                self.head.salt,
                self.head.hash_id,
                self.head.hash_salt_len,
                self.head.sec_crypto_passes,
                self.head.kdf_passes,
                self.head.zstd_comp_lvl,
            ),
        )

    # name

    @property
    def name(self) -> bytes:
        """get name"""
        return self[b"n"]

    @name.setter
    def name(self, value: bytes) -> None:
        """set username"""
        self[b"n"] = value

    # username

    @property
    def username(self) -> bytes:
        """get username"""
        return self[b"u"]

    @username.setter
    def username(self, value: bytes) -> None:
        """set username"""
        self[b"u"] = value

    # password

    @property
    def password(self) -> bytes:
        """get name"""
        return self[b"p"]

    @password.setter
    def password(self, value: bytes) -> None:
        """set username"""
        self[b"p"] = value

    # remark

    @property
    def remark(self) -> bytes:
        """get name"""
        return self[b"r"]

    @remark.setter
    def remark(self, value: bytes) -> None:
        """set username"""
        self[b"r"] = value

    def set_field(
        self,
        name: bytes,
        value: bytes,
    ) -> "PdbPwdEntry":
        """set field name to value"""

        if name in self.encrypted_fields:
            self._set_crypt(name, value)
        else:
            self.set_field_raw(name, value)

        return self

    def get_field(self, name: bytes) -> bytes:
        """set field name to value"""
        return (
            self._get_crypt(name)
            if name in self.encrypted_fields
            else self.get_field_raw(name)
        )

    def validate_struct(self) -> "PdbPwdEntry":
        """validate structure"""

        if not all(field in self.fields for field in PdbPwdEntry.all_fields):
            raise exc.StructureError(self.entry_id)

        return self

    def __str__(self) -> str:
        """shows all fields in the entry"""
        return "\n".join(
            f"field {field!r:10s} -- \
{'***' if field in self.encrypted_fields else repr(data)}"
            for field, data in self.fields.items()
        )


class PdbEntries:
    """stores all entries in a database"""

    def __init__(
        self,
        head: header.PdbHeader,
    ) -> None:
        self.ents: List[PdbEntry] = []
        self.head: header.PdbHeader = head

    def gather(
        self,
        entry_t: Type[PdbEntry] = PdbPwdEntry,
    ) -> "PdbEntries":
        """gather all entries from the header"""

        self.head.decrypt()

        if not self.head.entries:
            return self

        b: BytesIO = BytesIO(self.head.entries)

        while (h := b.read(self.head.ds())) != b"":
            e: PdbEntry = entry_t(self.head, h)

            while (ident := b.read(s.BL)) != b"\0":
                e.set_field_raw(ident, b.read(s.sunpack(s.L, b)))

            self.ents.append(e.revalidate().validate_struct())

        return self

    def add_entry(self, entry: PdbEntry) -> "PdbEntries":
        """add entry"""

        self.ents.append(entry.revalidate().validate_struct())
        return self

    @property
    def db_entries(self) -> bytes:
        """get all entries as bytes"""
        return b"".join(e.full_entry for e in self.ents)

    def commit(self) -> "PdbEntries":
        """push all entries to the database"""

        self.head.decrypt()
        self.head.entries = self.db_entries
        return self

    def __str__(self) -> str:
        """lists all entries"""
        return "\n\n".join(
            f"--- entry #{idx} ---\n{e}" for idx, e in enumerate(self.ents)
        )
