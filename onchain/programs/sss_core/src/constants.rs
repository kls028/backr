use anchor_lang::prelude::*;

#[constant]
pub const COUNTER_SEED: &[u8] = b"counter";

#[constant]
pub const HELLO_WORLD_LAMPORTS: u64 = 1;

#[constant]
pub const MAX_COUNT: u64 = 10;

pub const CAMPAIGN_SEED: &[u8] = b"campaign";
pub const POSITION_SEED: &[u8] = b"position";
pub const MAX_STRETCH_GOALS: usize = 8;
pub const MAX_METADATA_URI: usize = 500;
pub const MAX_ACTIVE_UNITS: u64 = 12;
pub const STATUS_SCHEDULED: u8 = 0;
pub const STATUS_ACTIVE: u8 = 1;
pub const STATUS_FUNDED: u8 = 2;
pub const STATUS_SUCCESSFUL: u8 = 3;
pub const STATUS_UNSUCCESSFUL: u8 = 4;
pub const STATUS_CANCELLED: u8 = 5;
