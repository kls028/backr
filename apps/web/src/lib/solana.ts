import { Connection, PublicKey, VersionedTransaction } from '@solana/web3.js'

export const RPC_URL = import.meta.env.VITE_SOLANA_RPC_URL ?? 'http://127.0.0.1:8899'

export const connection = new Connection(RPC_URL, 'confirmed')

/** Decode a base64 unsigned transaction returned by the backend. */
export function decodeTransaction(base64: string): VersionedTransaction {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return VersionedTransaction.deserialize(bytes)
}

/**
 * Sign a backend-built transaction and submit it.
 *
 * The backend already simulated it, so a failure here is almost always a real
 * on-chain problem rather than a malformed instruction.
 */
export async function signAndSend(
  base64: string,
  lastValidBlockHeight: number,
  blockhash: string,
  signTransaction: (tx: VersionedTransaction) => Promise<VersionedTransaction>,
): Promise<string> {
  const transaction = await signTransaction(decodeTransaction(base64))
  const signature = await connection.sendRawTransaction(transaction.serialize(), {
    skipPreflight: false,
    maxRetries: 3,
  })

  await connection.confirmTransaction(
    { signature, blockhash, lastValidBlockHeight },
    'confirmed',
  )

  return signature
}

const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')
const ASSOCIATED_TOKEN_PROGRAM_ID = new PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')

/**
 * Derive the owner's associated token account for a mint.
 *
 * Mirrors `associated_token_address()` in services/api/app/solana/anchor.py. The
 * supporter's own USDC account is deterministic, so the browser derives it rather
 * than asking the user to paste an address.
 */
export function associatedTokenAddress(owner: PublicKey, mint: PublicKey): PublicKey {
  const [address] = PublicKey.findProgramAddressSync(
    [owner.toBuffer(), TOKEN_PROGRAM_ID.toBuffer(), mint.toBuffer()],
    ASSOCIATED_TOKEN_PROGRAM_ID,
  )
  return address
}

/** Truncate a base58 address for display: 7xKX…gAsU */
export function shortAddress(address: string, chars = 4): string {
  if (address.length <= chars * 2 + 1) return address
  return `${address.slice(0, chars)}…${address.slice(-chars)}`
}
