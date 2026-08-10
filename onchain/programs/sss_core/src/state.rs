use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub count: u64,
    pub authority: Pubkey,
}

#[account]
#[derive(InitSpace)]
pub struct Campaign {
    pub creator: Pubkey,
    pub usdc_mint: Pubkey,
    pub escrow_token_account: Pubkey,
    pub nonce: [u8; 16],
    pub unit_price_atomic: u64,
    pub minimum_success_threshold_atomic: u64,
    pub main_goal_atomic: u64,
    pub start_at: i64,
    pub end_at: i64,
    pub raised_atomic: u64,
    pub active_units: u64,
    pub pending_units: u64,
    pub status: u8,
    pub metadata_hash: [u8; 32],
    #[max_len(200)]
    pub metadata_uri: String,
    #[max_len(8)]
    pub stretch_goals_atomic: Vec<u64>,
}

#[account]
#[derive(InitSpace)]
pub struct SubscriptionPosition {
    pub campaign: Pubkey,
    pub supporter: Pubkey,
    pub active_units: u64,
    pub pending_units: u64,
    pub contributed_atomic: u64,
}
