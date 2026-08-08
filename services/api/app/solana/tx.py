"""Transaction construction.

The backend builds *unsigned* transactions and hands them to the browser to
sign. It never holds a user key, so it is out of scope for custody. Anything
that moves value is authorised on-chain by the program, not here.

The one signature the backend could legitimately add is a fee-payer or
co-signer key for sponsored transactions. That is not wired up; if you add it,
keep the key in a KMS and never in an env var.
"""

from __future__ import annotations

import base64

from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.message import MessageV0
from solders.null_signer import NullSigner
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.transaction import VersionedTransaction

from app.solana.anchor import instruction_discriminator

COUNTER_SEED = b"counter"


def counter_pda(program_id: Pubkey) -> tuple[Pubkey, int]:
    """Mirror of the `seeds = [COUNTER_SEED]` constraint in the Anchor program.

    If you change the seeds in Rust, change them here. A mismatch surfaces as a
    ConstraintSeeds error at runtime, which is a slow way to learn about it.
    """
    return Pubkey.find_program_address([COUNTER_SEED], program_id)


def build_initialize_ix(program_id: Pubkey, payer: Pubkey) -> Instruction:
    counter, _bump = counter_pda(program_id)
    return Instruction(
        program_id=program_id,
        accounts=[
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey=counter, is_signer=False, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        data=instruction_discriminator("initialize"),
    )


def build_increment_ix(program_id: Pubkey, authority: Pubkey) -> Instruction:
    # Account order must match `#[derive(Accounts)] pub struct Increment` exactly:
    # counter, then authority. Anchor resolves accounts positionally.
    counter, _bump = counter_pda(program_id)
    return Instruction(
        program_id=program_id,
        accounts=[
            AccountMeta(pubkey=counter, is_signer=False, is_writable=True),
            AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
        ],
        data=instruction_discriminator("increment"),
    )


def to_unsigned_transaction(
    instructions: list[Instruction],
    payer: Pubkey,
    blockhash: str,
) -> str:
    """Compile instructions into a base64 v0 transaction with empty signatures.

    NullSigner reserves the signature slot without producing a real signature,
    so the wallet can drop its own in when it signs.
    """
    message = MessageV0.try_compile(
        payer=payer,
        instructions=instructions,
        address_lookup_table_accounts=[],
        recent_blockhash=Hash.from_string(blockhash),
    )
    tx = VersionedTransaction(message, [NullSigner(payer)])
    return base64.b64encode(bytes(tx)).decode()
