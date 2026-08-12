use anchor_lang::prelude::*;
use anchor_spl::token::{transfer, Token, TokenAccount, Transfer};

use crate::{
    constants::*,
    state::{SubscriptionPlan, SupporterSubscription},
    error::ErrorCode,
};

#[derive(Accounts)]
pub struct CreateSubscriptionPlan<'info> {
    #[account(mut)]
    pub creator: Signer<'info>,
    #[account(
        init,
        payer = creator,
        space = 8 + SubscriptionPlan::INIT_SPACE,
        seeds = [MONTHLY_SUB_SEED, creator.key().as_ref()],
        bump
    )]
    pub plan: Account<'info, SubscriptionPlan>,
    pub system_program: Program<'info, System>,
}

// Allows the creation of a subscription plan.
pub fn handle_create_subscription_plan(
    ctx: Context<CreateSubscriptionPlan>,
    price: u64,
    usdc_mint: Pubkey,
) -> Result<()> {
    require!(price > 0, ErrorCode::InvalidSubscriptionPlanPrice);
    let plan = &mut ctx.accounts.plan;
    plan.athlete = ctx.accounts.creator.key();
    plan.usdc_mint = usdc_mint;
    plan.price = price;
    plan.active = true;
    Ok(())
}

// The accounts needed to buy the subscription plan monthly
#[derive(Accounts)]
#[instruction(months: u64)]
pub struct PurchaseSubscriptionPlan<'info> {
    #[account(mut)]
    pub supporter: Signer<'info>,
    #[account(
        init_if_needed,
        payer = supporter,
        space = 8 + SupporterSubscription::INIT_SPACE,
        seeds = [b"supporter_sub", plan.key().as_ref(), supporter.key().as_ref()],
        bump
    )]
    pub subscription: Account<'info, SupporterSubscription>,
    #[account(mut)]
    pub plan: Account<'info, SubscriptionPlan>,
    #[account(mut)]
    pub supporter_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub athlete_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

// Allows the supporter to purchase the monthly subscription plan.
pub fn handle_purchase_subscription_plan(
    ctx: Context<PurchaseSubscriptionPlan>,
    months: u64,
) -> Result<()> {
    require!(months > 0, ErrorCode::InvalidPurchaseUnits);
    require!(ctx.accounts.plan.active, ErrorCode::InactiveSubscriptionPlan);

    let total_amount = ctx.accounts.plan.price
        .checked_mul(months)
        .ok_or(ErrorCode::ArithmeticOverflow)?;

    // Transferring the tokens from the supporter 
    // token_account to the athlete token_account.
    let cpi_accounts = Transfer {
        from: ctx.accounts.supporter_token_account.to_account_info(),
        to: ctx.accounts.athlete_token_account.to_account_info(),
        authority: ctx.accounts.supporter.to_account_info(),
    };
    let cpi_ctx = CpiContext::new(
        ctx.accounts.token_program.to_account_info().key(),
        cpi_accounts,
    );
    transfer(cpi_ctx, total_amount)?;

    let now = Clock::get()?.unix_timestamp;
    let subscription = &mut ctx.accounts.subscription;
    
    if subscription.end_at > now {
        subscription.end_at += months as i64 * 30 * 24 * 60 * 60;
    } else {
        subscription.start_at = now;
        subscription.end_at = now + (months as i64 * 30 * 24 * 60 * 60);
    }
    
    subscription.athlete = ctx.accounts.plan.athlete;
    subscription.supporter = ctx.accounts.supporter.key();
    subscription.usdc_mint = ctx.accounts.plan.usdc_mint;
    subscription.months = subscription.months.checked_add(months).unwrap();
    subscription.unit_price = ctx.accounts.plan.price;

    Ok(())
}
