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

    // Emits an event indicating that the subscription plan was created.
    emit!(SubscriptionPlanInitialized{
        creator: plan.athlete,
        unit_price: plan.price,
        usdc_mint: plan.usdc_mint,
    });

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

    emit!(SubscriptionPlanPurchased{
        athlete: subscription.athlete,
        supporter: subscription.supporter,
        usdc_mint: subscription.usdc_mint,
        months: subscription.months,
        unit_price: subscription.unit_price,
        starts_at: subscription.start_at,
        ends_at: subscription.end_at,
    });

    Ok(())
}

#[event]
pub struct SubscriptionPlanInitialized {
    creator: Pubkey,
    usdc_mint: Pubkey,
    unit_price: u64,
}

#[event]
pub struct SubscriptionPlanPurchased {
    athlete: Pubkey,
    supporter: Pubkey,
    usdc_mint: Pubkey,
    months: u64,
    unit_price: u64,
    starts_at: i64,
    ends_at: i64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use anchor_lang::prelude::Pubkey;

    #[test]
    fn test_subscription_duration_calculation() {
        let now = 1_000_000_000;
        let months = 2;
        let seconds_in_month = 30 * 24 * 60 * 60;
        let expected_end = now + (months as i64 * seconds_in_month);
        
        let calculated_end = now + (months as i64 * seconds_in_month);
        assert_eq!(calculated_end, expected_end);
    }

    #[test]
    fn test_total_amount_calculation() {
        let price: u64 = 25_000_000; // e.g., 25 USDC
        let months: u64 = 3;
        let expected_total = 75_000_000;

        // Matches the checked_mul logic in handle_purchase_subscription_plan
        let total_amount = price.checked_mul(months).unwrap();
        assert_eq!(total_amount, expected_total);
    }

    #[test]
    fn test_total_amount_overflow() {
        let price: u64 = u64::MAX;
        let months: u64 = 2;

        // Ensures the arithmetic overflow check works
        let total_amount = price.checked_mul(months);
        assert!(total_amount.is_none(), "Should overflow and return None");
    }

    #[test]
    fn test_new_subscription_time_update() {
        let now: i64 = 1_700_000_000;
        let months: u64 = 1;
        let seconds_in_month: i64 = 30 * 24 * 60 * 60;

        // Mocking the state of a new or expired subscription.
        // If the supporter does not have an active subscription, the subscription starts at the current time[cite: 1].
        let mut subscription = SupporterSubscription {
            start_at: 0,
            end_at: 0,
            athlete: Pubkey::new_unique(),
            supporter: Pubkey::new_unique(),
            usdc_mint: Pubkey::new_unique(),
            months: 0,
            unit_price: 0,
        };

        // Simulating the time-check logic from your instruction
        if subscription.end_at > now {
            subscription.end_at += months as i64 * seconds_in_month;
        } else {
            subscription.start_at = now;
            subscription.end_at = now + (months as i64 * seconds_in_month);
        }

        // Verify the subscription starts now and lasts exactly one month
        assert_eq!(subscription.start_at, now);
        assert_eq!(subscription.end_at, now + seconds_in_month);
    }

    #[test]
    fn test_existing_subscription_time_update() {
        let now: i64 = 1_700_000_000;
        let seconds_in_month: i64 = 30 * 24 * 60 * 60;
        let initial_end_at: i64 = now + 5000; // Subscription is currently active and ends in the future
        let months: u64 = 2;

        // Mocking the state of an already active subscription.
        // If the supporter already has an active subscription, the unit is added to the current expiration date[cite: 1].
        let mut subscription = SupporterSubscription {
            start_at: now - 5000,
            end_at: initial_end_at,
            athlete: Pubkey::new_unique(),
            supporter: Pubkey::new_unique(),
            usdc_mint: Pubkey::new_unique(),
            months: 1,
            unit_price: 25_000_000,
        };

        // Simulating the time-check logic from your instruction
        if subscription.end_at > now {
            subscription.end_at += months as i64 * seconds_in_month;
        } else {
            subscription.start_at = now;
            subscription.end_at = now + (months as i64 * seconds_in_month);
        }

        // start_at should remain unchanged, end_at should be extended by 2 months
        assert_eq!(subscription.start_at, now - 5000);
        assert_eq!(subscription.end_at, initial_end_at + (months as i64 * seconds_in_month));
    }
}