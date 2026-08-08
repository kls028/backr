"""Transaction construction.

The account lists here are hand-written to mirror the Anchor `#[derive(Accounts)]`
structs. Anchor resolves accounts positionally, so a wrong order fails on-chain
with an opaque constraint error rather than anything that points at the cause.
These assertions are checked against the generated IDL — if you change the Rust,
run `pnpm chain:build && pnpm idl:sync` and update both together.
"""

from __future__ import annotations

import base64

from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from app.solana.anchor import instruction_discriminator
from app.solana.tx import (
    build_increment_ix,
    build_initialize_ix,
    counter_pda,
    to_unsigned_transaction,
)

PROGRAM = Pubkey.from_string("5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe")
PAYER = Pubkey.from_string("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
# All-zero hash. Valid base58, and never a real blockhash.
BLOCKHASH = "11111111111111111111111111111111"


def test_counter_pda_is_deterministic() -> None:
    first, bump = counter_pda(PROGRAM)
    second, same_bump = counter_pda(PROGRAM)
    assert first == second
    assert bump == same_bump
    # A PDA must be off-curve, otherwise the program could not sign for it.
    assert not first.is_on_curve()


def test_initialize_matches_idl_layout() -> None:
    ix = build_initialize_ix(PROGRAM, PAYER)
    counter, _ = counter_pda(PROGRAM)

    assert ix.data == instruction_discriminator("initialize")
    assert [meta.pubkey for meta in ix.accounts][:2] == [PAYER, counter]
    assert [(m.is_signer, m.is_writable) for m in ix.accounts] == [
        (True, True),  # payer
        (False, True),  # counter
        (False, False),  # system_program
    ]


def test_increment_matches_idl_layout() -> None:
    ix = build_increment_ix(PROGRAM, PAYER)
    counter, _ = counter_pda(PROGRAM)

    assert ix.data == instruction_discriminator("increment")
    # counter comes FIRST, and authority is a non-writable signer.
    assert [meta.pubkey for meta in ix.accounts] == [counter, PAYER]
    assert [(m.is_signer, m.is_writable) for m in ix.accounts] == [
        (False, True),
        (True, False),
    ]


def test_unsigned_transaction_round_trips() -> None:
    encoded = to_unsigned_transaction([build_increment_ix(PROGRAM, PAYER)], PAYER, BLOCKHASH)
    decoded = VersionedTransaction.from_bytes(base64.b64decode(encoded))

    # One reserved, empty signature slot for the wallet to fill in. If this ever
    # comes back non-default, the backend has started signing for the user.
    assert len(decoded.signatures) == 1
    assert decoded.signatures[0] == Signature.default()

    keys = decoded.message.account_keys
    assert keys[0] == PAYER, "fee payer must be the first account key"
    assert PROGRAM in keys
