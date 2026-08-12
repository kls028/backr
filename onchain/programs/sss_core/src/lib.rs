pub mod constants;
pub mod error;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use constants::*;
pub use instructions::*;
pub use state::*;

declare_id!("3Qathj3eVMhLmupJPdMKWxhcemuhhyzYJH47pHT1FY7f");

#[program]
pub mod sss_core {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        crate::instructions::initialize::handle_initialize(ctx)
    }

    pub fn increment(ctx: Context<Increment>) -> Result<()> {
        crate::instructions::increment::handle_increment(ctx)
    }

    pub fn initialize_campaign(
        ctx: Context<InitializeCampaign>,
        args: InitializeCampaignArgs,
    ) -> Result<()> {
        crate::instructions::campaign::handle_initialize_campaign(ctx, args)
    }

    pub fn purchase_subscription(
        ctx: Context<PurchaseSubscription>,
        purchased_units: u64,
    ) -> Result<()> {
        crate::instructions::campaign::handle_purchase_subscription(ctx, purchased_units)
    }

    pub fn settle_position(ctx: Context<SettlePosition>, successful: bool) -> Result<()> {
        crate::instructions::campaign::handle_settle_position(ctx, successful)
    }

    pub fn create_subscription_plan(ctx: Context<CreateSubscriptionPlan>, price: u64, usdc_mint: Pubkey) -> Result<()> {
        crate::instructions::subscription::handle_create_subscription_plan(ctx, price, usdc_mint)
    }

    pub fn purchase_subscription_plan(ctx: Context<PurchaseSubscriptionPlan>, months: u64) -> Result<()> {
        crate::instructions::subscription::handle_purchase_subscription_plan(ctx, months)
    }
}
