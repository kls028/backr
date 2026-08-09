use anchor_lang::prelude::*;
use anchor_lang::solana_program::{
    instruction::{AccountMeta, Instruction},
    program::{invoke, invoke_signed},
};

use crate::{
    constants::*,
    error::ErrorCode,
    state::{Campaign, SubscriptionPosition},
};

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
    require!(args.unit_price_atomic > 0, ErrorCode::InvalidCampaignTerms);
    require!(
        args.minimum_success_threshold_atomic > 0
            && args.main_goal_atomic >= args.minimum_success_threshold_atomic
            && args.end_at > args.start_at
            && args.stretch_goals_atomic.len() <= MAX_STRETCH_GOALS
            && args.metadata_uri.len() <= MAX_METADATA_URI,
        ErrorCode::InvalidCampaignTerms
    );

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
    campaign.status = STATUS_SCHEDULED;
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
    /// CHECK: Validated by the SPL Token CPI and owned by the token program.
    #[account(mut)]
    pub source_token_account: UncheckedAccount<'info>,
    /// CHECK: Campaign escrow token account; its authority is the campaign PDA.
    #[account(mut, address = campaign.escrow_token_account)]
    pub escrow_token_account: UncheckedAccount<'info>,
    /// CHECK: Must equal campaign.usdc_mint.
    pub usdc_mint: UncheckedAccount<'info>,
    /// CHECK: Must be the canonical SPL Token program.
    pub token_program: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
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
    require_keys_eq!(
        campaign.usdc_mint,
        ctx.accounts.usdc_mint.key(),
        ErrorCode::InvalidCampaignTerms
    );
    require!(
        ctx.accounts.token_program.key() == spl_token_program_id(),
        ErrorCode::InvalidTokenProgram
    );

    let amount = campaign
        .unit_price_atomic
        .checked_mul(purchased_units)
        .ok_or(ErrorCode::ArithmeticOverflow)?;
    let capacity = MAX_ACTIVE_UNITS.saturating_sub(ctx.accounts.position.active_units);
    let immediate = purchased_units.min(capacity);
    let pending = purchased_units - immediate;

    let transfer_data = {
        let mut data = vec![12u8]; // SPL Token TransferChecked
        data.extend_from_slice(&amount.to_le_bytes());
        data.push(6u8);
        data
    };
    let transfer = Instruction {
        program_id: ctx.accounts.token_program.key(),
        accounts: vec![
            AccountMeta::new(ctx.accounts.source_token_account.key(), false),
            AccountMeta::new_readonly(ctx.accounts.usdc_mint.key(), false),
            AccountMeta::new(ctx.accounts.escrow_token_account.key(), false),
            AccountMeta::new_readonly(ctx.accounts.supporter.key(), true),
        ],
        data: transfer_data,
    };
    invoke(
        &transfer,
        &[
            ctx.accounts.source_token_account.to_account_info(),
            ctx.accounts.usdc_mint.to_account_info(),
            ctx.accounts.escrow_token_account.to_account_info(),
            ctx.accounts.supporter.to_account_info(),
            ctx.accounts.token_program.to_account_info(),
        ],
    )?;

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
    #[account(address = campaign.creator @ ErrorCode::UnauthorizedSettlement)]
    pub creator: Signer<'info>,
    /// CHECK: The supporter token account is checked by the SPL Token CPI.
    #[account(mut)]
    pub supporter_token_account: UncheckedAccount<'info>,
    /// CHECK: Campaign escrow token account; the campaign PDA signs refunds.
    #[account(mut, address = campaign.escrow_token_account)]
    pub escrow_token_account: UncheckedAccount<'info>,
    /// CHECK: Must equal campaign.usdc_mint.
    pub usdc_mint: UncheckedAccount<'info>,
    /// CHECK: Must be the canonical SPL Token program.
    pub token_program: UncheckedAccount<'info>,
}

pub fn handle_settle_position(
    ctx: Context<SettlePosition>,
    successful: bool,
) -> Result<()> {
    let now = Clock::get()?.unix_timestamp;
    let campaign = &mut ctx.accounts.campaign;
    require!(now >= campaign.end_at, ErrorCode::SettlementNotReady);
    require_keys_eq!(
        campaign.usdc_mint,
        ctx.accounts.usdc_mint.key(),
        ErrorCode::InvalidCampaignTerms
    );
    require!(
        ctx.accounts.token_program.key() == spl_token_program_id(),
        ErrorCode::InvalidTokenProgram
    );
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

    let pending_units = ctx.accounts.position.pending_units;
    if !successful && pending_units > 0 {
        let amount = campaign
            .unit_price_atomic
            .checked_mul(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
        let transfer = Instruction {
            program_id: ctx.accounts.token_program.key(),
            accounts: vec![
                AccountMeta::new(ctx.accounts.escrow_token_account.key(), false),
                AccountMeta::new_readonly(ctx.accounts.usdc_mint.key(), false),
                AccountMeta::new(ctx.accounts.supporter_token_account.key(), false),
                AccountMeta::new_readonly(campaign.key(), true),
            ],
            data: {
                let mut data = vec![12u8];
                data.extend_from_slice(&amount.to_le_bytes());
                data.push(6u8);
                data
            },
        };
        let signer_seeds: &[&[u8]] = &[
            CAMPAIGN_SEED,
            campaign.creator.as_ref(),
            campaign.nonce.as_ref(),
            &[ctx.bumps.campaign],
        ];
        invoke_signed(
            &transfer,
            &[
                ctx.accounts.escrow_token_account.to_account_info(),
                ctx.accounts.usdc_mint.to_account_info(),
                ctx.accounts.supporter_token_account.to_account_info(),
                campaign.to_account_info(),
                ctx.accounts.token_program.to_account_info(),
            ],
            &[signer_seeds],
        )?;
        campaign.pending_units = campaign
            .pending_units
            .checked_sub(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
    } else if successful {
        campaign.active_units = campaign
            .active_units
            .checked_add(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
        campaign.pending_units = campaign
            .pending_units
            .checked_sub(pending_units)
            .ok_or(ErrorCode::ArithmeticOverflow)?;
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

fn spl_token_program_id() -> Pubkey {
    Pubkey::new_from_array([
        6, 221, 246, 225, 215, 101, 161, 147, 217, 203, 225, 70, 206, 235, 121, 172,
        28, 180, 133, 237, 95, 91, 55, 145, 58, 140, 245, 133, 126, 255, 0, 169,
    ])
}
