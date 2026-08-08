/**
 * Shared Anchor IDL and generated types.
 *
 * The contents of ./generated are produced by `pnpm idl:sync` after
 * `pnpm chain:build`, and are gitignored — a committed IDL that has drifted
 * from the deployed program is a slow, confusing class of bug.
 *
 * Until you have run a build, this module exports nothing and the re-export
 * below will fail to resolve. That is intentional: it fails at build time
 * rather than at runtime in a user's browser.
 */
export * from './generated'
