use anchor_lang::prelude::*;
use anchor_spl::token::{transfer_checked, Mint, Token, TokenAccount, TransferChecked};

use crate::{
    constants::*,
    error::ErrorCode,
    state::{Campaign, SubscriptionPosition},
};

/// USDC has 6 decimals. transfer_checked verifies this against the mint, which
/// is what makes a wrong-mint transfer fail rather than silently move the wrong
/// value.
const USDC_DECIMALS: u8 = 6;

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct InitializeCampaignArgs {
    pub nonce: [u8; 16],
    pub unit_price_atomic: u64,
    pub minimum_success_threshold_atomic: u64,
    pub main_goal_atomic: u64,
    pub stretch_goals_atomic: Vec<u64>,
    pub start_at: i64,
    pub end_at: i64,
    pub metadata_uri: String,
    pub metadata_hash: [u8; 32],
}

#[derive(Accounts)]
#[instruction(args: InitializeCampaignArgs)]
pub struct InitializeCampaign<'info> {
    #[account(mut)]
    pub creator: Signer<'info>,
    #[account(
        init,
        payer = creator,
        space = 8 + Campaign::INIT_SPACE,
        seeds = [CAMPAIGN_SEED, creator.key().as_ref(), args.nonce.as_ref()],
        bump
    )]
    pub campaign: Account<'info, Campaign>,
    /// CHECK: The deployment's USDC mint is checked against this address at purchase time.
    pub usdc_mint: UncheckedAccount<'info>,
    /// CHECK: The campaign escrow token account is stored and checked on every purchase.
    pub escrow_token_account: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

pub fn handle_initialize_campaign(
    ctx: Context<InitializeCampaign>,
    args: InitializeCampaignArgs,
) -> Result<()> {
    validate_initialize_args(&args, ctx.accounts.usdc_mint.key())?;

    let campaign = &mut ctx.accounts.campaign;
    campaign.creator = ctx.accounts.creator.key();
    campaign.usdc_mint = ctx.accounts.usdc_mint.key();
    campaign.escrow_token_account = ctx.accounts.escrow_token_account.key();
    campaign.nonce = args.nonce;
    campaign.unit_price_atomic = args.unit_price_atomic;
    campaign.minimum_success_threshold_atomic = args.minimum_success_threshold_atomic;
    campaign.main_goal_atomic = args.main_goal_atomic;
    campaign.start_at = args.start_at;
    campaign.end_at = args.end_at;
    campaign.raised_atomic = 0;
    campaign.active_units = 0;
    campaign.pending_units = 0;
    campaign.status = STATUS_DRAFT;
    campaign.metadata_hash = args.metadata_hash;
    campaign.metadata_uri = args.metadata_uri;
    campaign.stretch_goals_atomic = args.stretch_goals_atomic;

    emit!(CampaignInitialized {
        campaign: campaign.key(),
        creator: campaign.creator,
        usdc_mint: campaign.usdc_mint,
        snapshot_hash: campaign.metadata_hash,
    });
    Ok(())
}

fn validate_initialize_args(args: &InitializeCampaignArgs, usdc_mint: Pubkey) -> Result<()> {
    require!(usdc_mint != Pubkey::default(), ErrorCode::InvalidUsdcMint);
    require!(args.unit_price_atomic > 0, ErrorCode::InvalidCampaignTerms);
    require!(
        args.minimum_success_threshold_atomic > 0
            && args.main_goal_atomic >= args.minimum_success_threshold_atomic,
        ErrorCode::InvalidCampaignTerms
    );
    require!(args.end_at > args.start_at, ErrorCode::InvalidCampaignTerms);
    require!(
        args.stretch_goals_atomic.len() <= MAX_STRETCH_GOALS,
        ErrorCode::TooManyStretchGoals
    );
    let mut previous_goal = args.main_goal_atomic;
    for goal in &args.stretch_goals_atomic {
        require!(*goal > previous_goal, ErrorCode::InvalidGoalOrder);
        previous_goal = *goal;
    }
    require!(
        args.metadata_uri.len() <= MAX_METADATA_URI,
        ErrorCode::MetadataUriTooLong
    );
    Ok(())
}

#[derive(Accounts)]
pub struct PurchaseSubscription<'info> {
    #[account(mut)]
    pub campaign: Account<'info, Campaign>,
    #[account(
        init_if_needed,
        payer = supporter,
        space = 8 + SubscriptionPosition::INIT_SPACE,
        seeds = [POSITION_SEED, campaign.key().as_ref(), supporter.key().as_ref()],
        bump
    )]
    pub position: Account<'info, SubscriptionPosition>,
    #[account(mut)]
    pub supporter: Signer<'info>,
    // Typed token accounts with explicit owner/mint constraints. The previous
    // UncheckedAccount version relied on the SPL CPI to catch problems, which
    // does not check *whose* account it is -- only that it is a token account.
    #[account(
        mut,
        constraint = source_token_account.owner == supporter.key() @ ErrorCode::InvalidTokenAccountOwner,
        constraint = source_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub source_token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        address = campaign.escrow_token_account @ ErrorCode::InvalidEscrowAccount,
        constraint = escrow_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub escrow_token_account: Account<'info, TokenAccount>,
    /// Destination for the immediately activated unit. That unit is
    /// non-refundable (spec F/§156), so its USDC must never enter escrow --
    /// escrow holds refundable money only.
    #[account(
        mut,
        constraint = athlete_token_account.owner == campaign.creator @ ErrorCode::InvalidTokenAccountOwner,
        constraint = athlete_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub athlete_token_account: Account<'info, TokenAccount>,
    #[account(address = campaign.usdc_mint @ ErrorCode::InvalidUsdcMint)]
    pub usdc_mint: Account<'info, Mint>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

/// Split a purchase into immediately-activated and pending units.
///
/// Spec §73/§80/§81: during an active campaign **at most one unit per supporter
/// per campaign** activates immediately, no matter how many units are bought.
/// Everything else stays pending until settlement. A supporter who already holds
/// an immediate unit in this campaign gets none; a supporter at the forward
/// active-unit limit also gets none, and their first unit is processed as an
/// excess unit at settlement instead.
///
/// Extracted so the rule is unit-testable without standing up SPL token
/// accounts — an earlier version activated `min(purchased, 12 - active)`, which
/// silently gave a first-time buyer of ten units ten active months.
pub(crate) fn allocate_units(
    purchased_units: u64,
    position_active_units: u64,
) -> Result<(u64, u64)> {
    let has_capacity = position_active_units < MAX_ACTIVE_UNITS;
    let immediate: u64 = if position_active_units == 0 && has_capacity {
        1
    } else {
        0
    };
    let pending = purchased_units
        .checked_sub(immediate)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    Ok((immediate, pending))
}

pub fn handle_purchase_subscription(
    ctx: Context<PurchaseSubscription>,
    purchased_units: u64,
) -> Result<()> {
    require!(purchased_units > 0, ErrorCode::InvalidPurchaseUnits);
    let now = Clock::get()?.unix_timestamp;
    let campaign = &mut ctx.accounts.campaign;
    require!(
        now >= campaign.start_at && now < campaign.end_at,
        ErrorCode::CampaignNotOpen
    );
    let amount = campaign
        .unit_price_atomic
        .checked_mul(purchased_units)
        .ok_or(ErrorCode::ArithmeticOverflow)?;

    let (immediate, pending) = allocate_units(purchased_units, ctx.accounts.position.active_units)?;

    let immediate_amount = campaign
        .unit_price_atomic
        .checked_mul(immediate)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    let pending_amount = amount
        .checked_sub(immediate_amount)
        .ok_or(ErrorCode::ArithmeticOverflow)?;

    // Two destinations, because the two halves have different refund rules.
    // The immediate unit is non-refundable and goes straight to the athlete
    // (the off-chain payout worker applies the monthly vesting schedule to it).
    // The pending units are refundable and are the only funds held in escrow,
    // which keeps the escrow balance exactly equal to what settlement may owe
    // back to supporters.
    if immediate_amount > 0 {
        transfer_checked(
            CpiContext::new(
                ctx.accounts.token_program.key(),
                TransferChecked {
                    from: ctx.accounts.source_token_account.to_account_info(),
                    mint: ctx.accounts.usdc_mint.to_account_info(),
                    to: ctx.accounts.athlete_token_account.to_account_info(),
                    authority: ctx.accounts.supporter.to_account_info(),
                },
            ),
            immediate_amount,
            USDC_DECIMALS,
        )?;
    }

    if pending_amount > 0 {
        transfer_checked(
            CpiContext::new(
                ctx.accounts.token_program.key(),
                TransferChecked {
                    from: ctx.accounts.source_token_account.to_account_info(),
                    mint: ctx.accounts.usdc_mint.to_account_info(),
                    to: ctx.accounts.escrow_token_account.to_account_info(),
                    authority: ctx.accounts.supporter.to_account_info(),
                },
            ),
            pending_amount,
            USDC_DECIMALS,
        )?;
    }

    let position = &mut ctx.accounts.position;
    position.campaign = campaign.key();
    position.supporter = ctx.accounts.supporter.key();
    position.active_units = position
        .active_units
        .checked_add(immediate)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    position.pending_units = position
        .pending_units
        .checked_add(pending)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    position.contributed_atomic = position
        .contributed_atomic
        .checked_add(amount)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    campaign.active_units = campaign
        .active_units
        .checked_add(immediate)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    campaign.pending_units = campaign
        .pending_units
        .checked_add(pending)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    campaign.raised_atomic = campaign
        .raised_atomic
        .checked_add(amount)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    if campaign.raised_atomic >= campaign.minimum_success_threshold_atomic {
        campaign.status = STATUS_FUNDED;
    } else {
        campaign.status = STATUS_ACTIVE;
    }

    emit!(SubscriptionPurchased {
        campaign: campaign.key(),
        supporter: position.supporter,
        amount_atomic: amount,
        purchased_units,
        immediate_units: immediate,
        pending_units: pending,
    });
    Ok(())
}

#[derive(Accounts)]
pub struct SettlePosition<'info> {
    #[account(mut)]
    pub campaign: Account<'info, Campaign>,
    #[account(
        mut,
        seeds = [POSITION_SEED, campaign.key().as_ref(), position.supporter.as_ref()],
        bump
    )]
    pub position: Account<'info, SubscriptionPosition>,
    /// Settlement is permissionless: it only pays out to destinations derived
    /// from on-chain state, so anyone may crank it. Requiring the athlete's
    /// signature meant an athlete who walked away could strand every
    /// supporter's refund indefinitely.
    #[account(mut)]
    pub cranker: Signer<'info>,
    /// Refund destination. Constrained to the supporter recorded in the
    /// position -- without this, a cranker could redirect refunds to itself.
    #[account(
        mut,
        constraint = supporter_token_account.owner == position.supporter @ ErrorCode::InvalidTokenAccountOwner,
        constraint = supporter_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub supporter_token_account: Account<'info, TokenAccount>,
    /// Payout destination on success.
    #[account(
        mut,
        constraint = athlete_token_account.owner == campaign.creator @ ErrorCode::InvalidTokenAccountOwner,
        constraint = athlete_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub athlete_token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        address = campaign.escrow_token_account @ ErrorCode::InvalidEscrowAccount,
        constraint = escrow_token_account.mint == campaign.usdc_mint @ ErrorCode::InvalidUsdcMint,
    )]
    pub escrow_token_account: Account<'info, TokenAccount>,
    #[account(address = campaign.usdc_mint @ ErrorCode::InvalidUsdcMint)]
    pub usdc_mint: Account<'info, Mint>,
    pub token_program: Program<'info, Token>,
}

pub fn handle_settle_position(ctx: Context<SettlePosition>, successful: bool) -> Result<()> {
    let now = Clock::get()?.unix_timestamp;
    let campaign = &mut ctx.accounts.campaign;
    require!(now >= campaign.end_at, ErrorCode::SettlementNotReady);
    require!(
        campaign.status == STATUS_ACTIVE
            || campaign.status == STATUS_FUNDED
            || (successful && campaign.status == STATUS_SUCCESSFUL)
            || (!successful && campaign.status == STATUS_UNSUCCESSFUL),
        ErrorCode::SettlementNotReady
    );
    if successful {
        require!(
            campaign.raised_atomic >= campaign.minimum_success_threshold_atomic,
            ErrorCode::ThresholdNotReached
        );
    } else {
        require!(
            campaign.raised_atomic < campaign.minimum_success_threshold_atomic,
            ErrorCode::ThresholdNotReached
        );
    }

    let (expected_campaign, campaign_bump) = Pubkey::find_program_address(
        &[
            CAMPAIGN_SEED,
            campaign.creator.as_ref(),
            campaign.nonce.as_ref(),
        ],
        &crate::ID,
    );
    require_keys_eq!(
        campaign.key(),
        expected_campaign,
        ErrorCode::InvalidCampaignTerms
    );

    let pending_units = ctx.accounts.position.pending_units;
    let pending_amount = campaign
        .unit_price_atomic
        .checked_mul(pending_units)
        .ok_or(ErrorCode::ArithmeticOverflow)?;

    if pending_amount > 0 {
        // Escrow holds only this supporter's refundable pending funds, so the
        // whole amount moves in one direction: to the athlete on success (spec
        // §124a/T4 -- released immediately, exempt from vesting), or back to the
        // supporter on failure (spec §147a).
        //
        // The success branch was previously missing entirely: settlement moved
        // unit counters but never transferred escrow to the athlete, so a
        // successful campaign left every supporter's USDC stranded in escrow.
        let destination = if successful {
            ctx.accounts.athlete_token_account.to_account_info()
        } else {
            ctx.accounts.supporter_token_account.to_account_info()
        };

        let signer_seeds: &[&[u8]] = &[
            CAMPAIGN_SEED,
            campaign.creator.as_ref(),
            campaign.nonce.as_ref(),
            &[campaign_bump],
        ];

        transfer_checked(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.key(),
                TransferChecked {
                    from: ctx.accounts.escrow_token_account.to_account_info(),
                    mint: ctx.accounts.usdc_mint.to_account_info(),
                    to: destination,
                    authority: campaign.to_account_info(),
                },
                &[signer_seeds],
            ),
            pending_amount,
            USDC_DECIMALS,
        )?;

        campaign.pending_units = campaign
            .pending_units
            .checked_sub(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
        if successful {
            campaign.active_units = campaign
                .active_units
                .checked_add(pending_units)
                .ok_or(ErrorCode::ArithmeticOverflow)?;
        }
    }

    if successful {
        ctx.accounts.position.active_units = ctx
            .accounts
            .position
            .active_units
            .checked_add(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
    }
    ctx.accounts.position.pending_units = 0;
    campaign.status = if successful {
        STATUS_SUCCESSFUL
    } else {
        STATUS_UNSUCCESSFUL
    };
    emit!(CampaignSettled {
        campaign: campaign.key(),
        supporter: ctx.accounts.position.supporter,
        successful,
        pending_units,
    });
    Ok(())
}

#[event]
pub struct CampaignInitialized {
    pub campaign: Pubkey,
    pub creator: Pubkey,
    pub usdc_mint: Pubkey,
    pub snapshot_hash: [u8; 32],
}

#[event]
pub struct SubscriptionPurchased {
    pub campaign: Pubkey,
    pub supporter: Pubkey,
    pub amount_atomic: u64,
    pub purchased_units: u64,
    pub immediate_units: u64,
    pub pending_units: u64,
}

#[event]
pub struct CampaignSettled {
    pub campaign: Pubkey,
    pub supporter: Pubkey,
    pub successful: bool,
    pub pending_units: u64,
}

// The hand-rolled spl_token_program_id() helper is gone: `Program<'info, Token>`
// enforces the canonical program id at deserialization, so the manual check and
// its hardcoded byte array were redundant.

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_args() -> InitializeCampaignArgs {
        InitializeCampaignArgs {
            nonce: *b"0123456789abcdef",
            unit_price_atomic: 25_000_000,
            minimum_success_threshold_atomic: 800_000_000,
            main_goal_atomic: 1_000_000_000,
            stretch_goals_atomic: vec![1_250_000_000, 1_500_000_000],
            start_at: 1_790_000_000,
            end_at: 1_800_000_000,
            metadata_uri: "https://example.invalid/campaign.json".to_owned(),
            metadata_hash: [7; 32],
        }
    }

    #[test]
    fn initialize_validation_accepts_a_valid_campaign() {
        assert!(validate_initialize_args(&valid_args(), Pubkey::new_unique()).is_ok());
    }

    // --- Immediate/pending allocation (spec §73/§80/§81) -------------------

    #[test]
    fn three_units_allocate_one_immediate_and_two_pending() {
        // The Part 2 acceptance criterion: "one purchase with three units
        // records one immediate and two pending".
        assert_eq!(allocate_units(3, 0).unwrap(), (1, 2));
    }

    #[test]
    fn a_single_unit_activates_immediately() {
        assert_eq!(allocate_units(1, 0).unwrap(), (1, 0));
    }

    #[test]
    fn a_large_purchase_still_activates_exactly_one_unit() {
        // Regression guard: the previous rule activated min(purchased, 12 -
        // active), so this returned (10, 0) and handed out ten active months.
        assert_eq!(allocate_units(10, 0).unwrap(), (1, 9));
        assert_eq!(allocate_units(100, 0).unwrap(), (1, 99));
    }

    #[test]
    fn a_supporter_with_an_active_unit_gets_no_second_immediate_unit() {
        assert_eq!(allocate_units(5, 1).unwrap(), (0, 5));
    }

    #[test]
    fn a_supporter_at_the_forward_limit_gets_nothing_immediately() {
        assert_eq!(allocate_units(5, MAX_ACTIVE_UNITS).unwrap(), (0, 5));
    }

    #[test]
    fn initialize_validation_rejects_default_mint() {
        assert!(validate_initialize_args(&valid_args(), Pubkey::default()).is_err());
    }

    #[test]
    fn initialize_validation_rejects_non_increasing_stretch_goals() {
        let mut args = valid_args();
        args.stretch_goals_atomic = vec![1_100_000_000, 1_100_000_000];
        assert!(validate_initialize_args(&args, Pubkey::new_unique()).is_err());
    }

    #[test]
    fn initialize_validation_rejects_more_than_eight_stretch_goals() {
        let mut args = valid_args();
        args.stretch_goals_atomic = (0..=MAX_STRETCH_GOALS)
            .map(|index| 1_100_000_000 + (index as u64 * 1_000_000))
            .collect();
        assert!(validate_initialize_args(&args, Pubkey::new_unique()).is_err());
    }

    #[test]
    fn initialize_validation_rejects_metadata_overflow() {
        let mut args = valid_args();
        args.metadata_uri = "x".repeat(MAX_METADATA_URI + 1);
        assert!(validate_initialize_args(&args, Pubkey::new_unique()).is_err());
    }
}
