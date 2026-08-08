import { Connection, VersionedTransaction } from '@solana/web3.js'

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

/** Truncate a base58 address for display: 7xKX…gAsU */
export function shortAddress(address: string, chars = 4): string {
  if (address.length <= chars * 2 + 1) return address
  return `${address.slice(0, chars)}…${address.slice(-chars)}`
}
